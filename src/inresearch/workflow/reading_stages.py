"""Read/validate candidate artifacts; no queue or catalog writes."""
from __future__ import annotations
import re, shutil, subprocess, tempfile
from pathlib import Path
from inresearch.materials.reader_contracts import Blocked, Deferred, UnsafePath, IntegrityError, ModelOutputError, RECIPE_VERSION, OCR_DEFERRED_PRIORITY, MODULES
from inresearch.materials.artifacts import numeric_tokens, now_iso, encoded, digest_bytes, digest_file, safe_path, atomic_bytes, atomic_json, read_json, signature, split_text, require_text

from inresearch.materials.reading_artifacts import ReadingArtifacts

class ReadingStages(ReadingArtifacts):
    def __init__(self, data, model, ocr_max_pages, large_format_points):
        super().__init__(data)
        self.model = model
        self.ocr_max_pages, self.large_format_points = ocr_max_pages, large_format_points




    def _persist(self, doc, relative, marker, value):
        prior = self._cached(doc, relative, marker)
        if prior is not None:
            return prior
        out = {**value, "doc_id": doc["doc_id"], "content_sha256": doc["sha256"],
               "reading_revision_id": doc["revision_id"], "_recipe": doc["recipe"], "_marker": marker, "created_at": now_iso(), "acceptance": "candidate"}
        atomic_json(self.artifact_path(doc, relative), out)
        return out

    def _extract(self, doc):
        cached = self._cached(doc, "extraction.json", "extract")
        if cached:
            return cached
        source = safe_path(self.data, doc["original_rel"])
        before = signature(source)
        if digest_file(source) != doc["sha256"]:
            raise IntegrityError()
        suffix = doc["suffix"]
        texts, page_meta = [], []
        if suffix in {".txt", ".md", ".csv", ".tsv"}:
            try:
                text = source.read_text(encoding="utf-8-sig")
            except UnicodeError:
                raise Blocked("text_encoding_requires_conversion")
            if "\0" in text:
                raise Blocked("binary_text_input")
            texts = [text]
            page_meta = [{"page_index": 1, "method": "utf8_text"}]
        elif suffix in {".html", ".htm"}:
            from inresearch.adapters.html_document import extract
            text, meta = extract(source)
            if meta["truncated"]:
                raise Blocked("html_extraction_truncated")
            if not text.strip():
                raise Blocked("html_no_substantive_text")
            texts = [text]
            page_meta = [{"page_index": 1, **meta}]
        elif suffix in {".docx", ".pptx", ".xlsx", ".xls", ".ppt", ".et", ".wps", ".dps"}:
            from inresearch.adapters.office import extract
            text, meta = extract(source, limit=10_000_000)
            if meta.get("truncated"):
                raise Blocked("office_extraction_truncated")
            if meta.get("extract_error") or not text.strip():
                raise Blocked("office_extraction_failed")
            texts = [text]
            page_meta = [{"page_index": 1, "method": "office_structural_text_v1", **meta}]
        elif suffix == ".pdf":
            if not all(shutil.which(name) for name in ("pdftotext", "pdfinfo", "pdfimages")):
                raise Blocked("pdf_tools_missing")
            info = self._command(["pdfinfo", str(source)], timeout=60)
            m = re.search(r"^Pages:\s*(\d+)", info, re.M)
            if not m or not 0 < int(m.group(1)) <= 10000:
                raise Blocked("pdf_page_count_unavailable_or_excessive")
            image_pages = set()
            image_info = self._command(["pdfimages", "-list", str(source)], timeout=60)
            for line in image_info.splitlines():
                cols = line.split()
                if len(cols) >= 5 and cols[0].isdigit() and cols[3].isdigit() and cols[4].isdigit():
                    if int(cols[3]) >= 400 and int(cols[4]) >= 400:
                        image_pages.add(int(cols[0]))
            ocr_pages = 0
            for i in range(1, int(m.group(1)) + 1):
                page_file = safe_path(self.data, "%s/pages/%06d.json" % (doc["extracted_rel"], i))
                if page_file.exists():
                    page = read_json(page_file)
                    if page.get("source_sha256") != doc["sha256"]:
                        raise IntegrityError()
                    if page.get("method") == "vision_ocr_double_pass":
                        ocr_pages += 1
                else:
                    text = self._command(["pdftotext", "-f", str(i), "-l", str(i), "-layout", "-enc", "UTF-8", str(source), "-"], timeout=90).replace("\f", "")
                    page = {"page_index": i, "text": text, "method": "pdftotext", "source_sha256": doc["sha256"]}
                    # Pages without text must take the pixel route or remain blocked.
                    if not text.strip() or "\ufffd" in text or i in image_pages:
                        if self._offload_path(doc, i).exists():
                            # M4 already did the vision work: no deferral, no local OCR budget.
                            page.update(self._ocr_page(doc, source, i))
                            atomic_json(page_file, page)
                            texts.append(page["text"])
                            page_meta.append({k: v for k, v in page.items() if k not in {"text", "text_second_pass"}})
                            continue
                        if getattr(self.model, "ocr_model", "") and doc["priority"] != OCR_DEFERRED_PRIORITY:
                            # First OCR need of this document: step aside so text-layer
                            # documents are read first. Text pages extracted so far stay cached.
                            raise Deferred("ocr_deferred_behind_text_documents")
                        ocr_pages += 1
                        if ocr_pages > self.ocr_max_pages:
                            raise Blocked("ocr_page_budget_exceeded")
                        page.update(self._ocr_page(doc, source, i))
                    atomic_json(page_file, page)
                texts.append(page["text"])
                page_meta.append({k: v for k, v in page.items() if k not in {"text", "text_second_pass"}})
        else:
            raise Blocked("unsupported_format_" + (suffix.lstrip(".") or "unknown"))
        if signature(source) != before:
            raise IntegrityError()
        if not any(t.strip() for t in texts):
            raise Blocked("no_substantive_text")
        chunks = []
        for i, text in enumerate(texts, 1):
            recipe = read_json(self.artifact_path(doc, "recipe.json"))
            for part in split_text(text, recipe["chunk_chars"]):
                index = len(chunks)
                rel = "%s/chunks/%06d.txt" % (doc["extracted_rel"], index)
                atomic_bytes(safe_path(self.data, rel), part.encode("utf-8"))
                chunks.append({"index": index, "page_index": i, "text_rel": rel, "sha256": digest_bytes(part.encode()), "characters": len(part)})
        result = {"pages": page_meta, "pages_total": len(texts), "chunks": chunks,
                  "characters_total": sum(map(len, texts)), "chunks_total": len(chunks),
                  "extraction_version": RECIPE_VERSION}
        return self._persist(doc, "extraction.json", "extract", result)

    @staticmethod
    def _command(args, timeout):
        try:
            r = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise Blocked("extractor_unavailable_or_timeout")
        if r.returncode != 0:
            raise Blocked("document_extraction_failed")
        if len(r.stdout) > 16 * 1024 * 1024:
            raise Blocked("extracted_page_too_large")
        return r.stdout.decode("utf-8", errors="strict")

    def _offload_path(self, doc, i):
        return safe_path(self.data, "offload/m4/results/%s/pages/%06d.json" % (doc["doc_id"], i))

    def _ocr_page(self, doc, source, i):
        # M4 may offload a *blocked* OCR task, but it never writes this catalog.
        # A result is accepted only when it is tied to the immutable source hash;
        # otherwise the normal local OCR path remains authoritative.
        offload = self._offload_path(doc, i)
        if offload.exists():
            result = read_json(offload)
            required = {"doc_id": doc["doc_id"], "content_sha256": doc["sha256"], "page_index": i,
                        "method": "m4_vision_ocr_double_pass"}
            if any(result.get(key) != value for key, value in required.items()):
                raise IntegrityError()
            if not isinstance(result.get("text"), str) or not isinstance(result.get("text_second_pass"), str):
                raise IntegrityError()
            # Same page rules as local OCR: a blank page is allowed, but both passes
            # must be empty; a non-blank page must carry text.
            if result.get("unreadable") is not False or not isinstance(result.get("blank"), bool):
                raise Blocked("m4_offload_page_unreadable")
            if result["blank"] and (result["text"].strip() or result["text_second_pass"].strip()):
                raise Blocked("ocr_blank_has_text")
            if not result["blank"] and not result["text"].strip():
                raise Blocked("ocr_empty_nonblank_page")
            if numeric_tokens(result["text"]) != numeric_tokens(result["text_second_pass"]):
                raise Blocked("m4_offload_numbers_disagree")
            return {key: result[key] for key in ("text", "text_second_pass", "method", "ocr_model", "blank", "verification")}
        if not getattr(self.model, "ocr_model", ""):
            raise Blocked("scanned_page_requires_ocr")
        if not shutil.which("pdftoppm"):
            raise Blocked("pdf_render_tool_missing")
        size = re.search(r"^Page\s+%d\s+size:\s*([\d.]+) x ([\d.]+) pts" % i, self._command(["pdfinfo", "-f", str(i), "-l", str(i), str(source)], timeout=60), re.M)
        if size and min(float(size.group(1)), float(size.group(2))) >= self.large_format_points:
            # A2 and larger raster pages are drawings, not prose: a vision OCR pass returns
            # noise or invalid JSON and burned days of worker time. Keep the bytes, block.
            raise Blocked("large_format_page_requires_drawing_workflow")
        with tempfile.TemporaryDirectory(prefix="reader-ocr-") as td:
            base = Path(td) / "page"
            self._command(["pdftoppm", "-f", str(i), "-l", str(i), "-singlefile", "-scale-to", "1800", "-png", str(source), str(base)], 90)
            image = base.with_suffix(".png")
            try:
                first, second = self.model.ocr(image), self.model.ocr(image)
            except ModelOutputError:
                # Unparseable vision output is a property of the page, not a transient
                # failure: block once instead of re-rendering and re-reading three times.
                raise Blocked("ocr_output_invalid")
        for out in (first, second):
            if not isinstance(out.get("text"), str) or not isinstance(out.get("blank"), bool) or out.get("unreadable") is not False:
                raise Blocked("ocr_page_unreadable")
        if first["blank"] != second["blank"]:
            raise Blocked("ocr_blank_disagreement")
        if numeric_tokens(first["text"]) != numeric_tokens(second["text"]):
            raise Blocked("ocr_numbers_disagree")
        if not first["text"].strip() and not first["blank"]:
            raise Blocked("ocr_empty_nonblank_page")
        if first["blank"] and (first["text"].strip() or second["text"].strip()):
            raise Blocked("ocr_blank_has_text")
        return {"text": first["text"], "text_second_pass": second["text"], "method": "vision_ocr_double_pass",
                "ocr_model": first.get("_model"), "blank": first["blank"],
                "verification": "candidate_ocr_agreement_not_accuracy_certification"}

    def _context(self, doc, text):
        snapshot = read_json(self.artifact_path(doc, "context.json"))
        # Separate budgets prevent hundreds of questions from displacing all objects.
        # Retrieval hints propose candidates, never establish a document/claim mapping.
        lower = text.lower()
        compact = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", lower)

        def lexical(row):
            name = str(row.get("name") or row.get("text") or "")[:100]
            aliases = row.get("aliases", [])
            if not isinstance(aliases, list):
                aliases = [aliases] if isinstance(aliases, str) else []
            aliases = [a[:100] for a in aliases if isinstance(a, str)][:12]
            score = 0
            for phrase in set([name] + aliases):
                normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", phrase.lower())
                if len(normalized) >= 2 and normalized in compact:
                    score += 8
            # IDs bridge e.g. part:coldplate to 'cold plate' without a synonym API.
            identifier = row["id"].split(":", 1)[-1].lower()
            for word in set(re.findall(r"[a-z]{3,}", identifier)) - {"obj", "part", "object", "question"}:
                if word in compact:
                    score += 4
            for word in set(re.findall(r"[a-z]{3,}|[\u4e00-\u9fff]{2,4}", " ".join([name] + aliases).lower())):
                if word in lower:
                    score += 1
            return score, name, aliases

        object_scores, ranked_objects = {}, []
        for row in snapshot["objects"]:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                continue
            score, name, aliases = lexical(row)
            object_scores[row["id"]] = score
            candidate = {"id": row["id"], "name": name, "match": "lexical" if score else "needs_review"}
            if aliases:
                candidate["aliases"] = aliases[:4]
            ranked_objects.append((score, candidate))
        ranked_questions = []
        for row in snapshot["questions"]:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                continue
            score, name, _ = lexical(row)
            related = max([object_scores.get(oid, 0) for oid in row.get("object_ids", [])] or [0])
            boost = 12 + min(related, 20) if related >= 4 else 0
            ranked_questions.append((score + boost, {"id": row["id"], "name": name,
                                      "match": "related_object" if boost else ("lexical" if score else "needs_review")}))
        result = {"objects": [], "questions": []}
        for key, rows, budget in (("objects", ranked_objects, 2200), ("questions", ranked_questions, 2500)):
            for _, row in sorted(rows, key=lambda pair: (-pair[0], pair[1]["id"])):
                if len(encoded(result[key] + [row]).encode()) <= budget:
                    result[key].append(row)
        if len(encoded(result).encode()) > 4800:
            raise IntegrityError()
        return result

    def _ids(self, result, context):
        out = {}
        for field, key in (("object_ids", "objects"), ("question_ids", "questions")):
            values = result.get(field, [])
            if not isinstance(values, list) or len(values) > 100 or any(not isinstance(v, str) for v in values):
                raise ModelOutputError()
            allowed = {x["id"] for x in context[key]}
            if any(v not in allowed for v in values):
                raise ModelOutputError()
            out[field] = sorted(set(values))
        return out


    def _triage(self, doc):
        cached = self._cached(doc, "triage.json", "triage")
        if cached:
            return cached
        extraction = read_json(self.artifact_path(doc, "extraction.json"))
        # Explicit bounded preview across the beginning, middle and end, never claimed as full coverage.
        chunks = extraction["chunks"]
        picks = sorted({0, len(chunks) // 2, len(chunks) - 1})
        preview = [{"page_index": chunks[n]["page_index"], "text": self._chunk_text(chunks[n])[:1000]} for n in picks]
        context = self._context(doc, doc["original_name"] + " " + encoded(preview))
        result = self.model.generate("triage", {"doc_id": doc["doc_id"], "original_name": doc["original_name"],
                    "sampling": "bounded preview; not full reading", "preview": preview, "allowed_ids": context})
        cls = result.get("classification")
        if not isinstance(cls, dict):
            raise ModelOutputError()
        for field in ("title", "org", "year", "module_id"):
            require_text(cls.get(field), 300, empty=field in {"org", "year"})
        if cls["module_id"] not in MODULES | {"unknown"}:
            raise ModelOutputError()
        if cls["year"] and not re.fullmatch(r"\d{4}|unknown|未知", cls["year"]):
            raise ModelOutputError()
        importance = result.get("importance")
        if type(importance) is not int or not 1 <= importance <= 9:
            raise ModelOutputError()
        require_text(result.get("rationale"), 2000)
        result.update(self._ids(result, context))
        result["sampling_pages"] = [p["page_index"] for p in preview]
        return self._persist(doc, "triage.json", "triage", result)

    def _read_chunk(self, doc, index):
        relative, marker = "chunks/%06d.json" % index, "read:%d" % index
        cached = self._cached(doc, relative, marker)
        if cached:
            return cached
        extraction = read_json(self.artifact_path(doc, "extraction.json"))
        chunk = extraction["chunks"][index]
        text = self._chunk_text(chunk)
        context = self._context(doc, text)
        result = self.model.generate("read", {"doc_id": doc["doc_id"], "page_index": chunk["page_index"],
                    "chunk_index": index, "chunk_sha256": chunk["sha256"], "text": text, "allowed_ids": context})
        if result.get("chunk_sha256") != chunk["sha256"]:
            raise ModelOutputError()
        require_text(result.get("summary"), 1200)
        claims = result.get("claims")
        if not isinstance(claims, list) or len(claims) > 30:
            raise ModelOutputError()
        evs, clean_claims = [], []
        normalized = re.sub(r"\s+", "", text)
        for c_index, claim in enumerate(claims):
            if not isinstance(claim, dict):
                raise ModelOutputError()
            require_text(claim.get("text"), 1500)
            if claim.get("kind") not in {"observation", "author_claim", "author_forecast", "calculation", "unverified"}:
                raise ModelOutputError()
            evidence = claim.get("evidence")
            claim_ids = self._ids(claim, context)
            if not isinstance(evidence, list) or not 1 <= len(evidence) <= 8:
                raise ModelOutputError()
            refs = []
            for e_index, ev in enumerate(evidence):
                quote = require_text(ev.get("quote") if isinstance(ev, dict) else None, 500)
                if re.sub(r"\s+", "", quote) not in normalized:
                    raise ModelOutputError()
                eid = "%s:chunk:%d:claim:%d:ev:%d" % (doc["revision_id"], index, c_index, e_index)
                evs.append({"id": eid, "page_index": chunk["page_index"],
                            "locator": "page:%d/chunk:%d" % (chunk["page_index"], index),
                            "quote": quote, "source_sha256": doc["sha256"], "reading_revision_id": doc["revision_id"], "chunk_sha256": chunk["sha256"], **claim_ids})
                refs.append(eid)
            clean_claims.append({"id": "%s:chunk:%d:claim:%d" % (doc["revision_id"], index, c_index),
                                 "text": claim["text"], "kind": claim["kind"], "evidence_ids": refs, "reading_revision_id": doc["revision_id"], "acceptance": "candidate", **claim_ids})
        result.update(self._ids(result, context))
        for field in ("object_ids", "question_ids"):
            result[field] = sorted(set(result[field]) | {v for claim in clean_claims for v in claim[field]})
        result.update({"claims": clean_claims, "evidence": evs, "chunk_index": index, "page_index": chunk["page_index"], "characters": len(text)})
        return self._persist(doc, relative, marker, result)

    def _synthesize(self, doc):
        cached = self._cached(doc, "report.json", "report")
        if cached:
            return cached
        extraction = read_json(self.artifact_path(doc, "extraction.json"))
        triage = read_json(self.artifact_path(doc, "triage.json"))
        chunks = []
        for chunk in extraction["chunks"]:
            result = self._cached(doc, "chunks/%06d.json" % chunk["index"], "read:%d" % chunk["index"])
            if not result or result["chunk_sha256"] != chunk["sha256"]:
                raise IntegrityError()
            chunks.append(result)
        items = [{"section": "chunk:%d" % c["chunk_index"], "summary": c["summary"]} for c in chunks]
        level = 0
        while True:
            groups, group = [], []
            for item in items:
                if group and len(encoded(group + [item]).encode()) > 15000:
                    groups.append(group)
                    group = []
                group.append(item)
            if group:
                groups.append(group)
            next_items = []
            for n, members in enumerate(groups):
                marker = "synth:" + digest_bytes(encoded(members).encode())
                name = "synthesis/l%03d-g%06d.json" % (level, n)
                result = self._cached(doc, name, marker)
                if result is None:
                    result = self.model.generate("synthesize", {"doc_id": doc["doc_id"], "sections": members,
                                                               "level": level, "scope": "all supplied sections, candidate synthesis"})
                    require_text(result.get("summary"), 1500)
                    points = result.get("key_points")
                    if not isinstance(points, list) or len(points) > 20:
                        raise ModelOutputError()
                    for point in points:
                        require_text(point, 300)
                    result = self._persist(doc, name, marker, {**result, "member_hash": marker, "section_count": len(members)})
                next_items.append({"section": "level:%d/group:%d" % (level, n), "summary": result["summary"]})
            if len(groups) == 1:
                final = result
                break
            if len(next_items) >= len(items):
                raise Blocked("synthesis_budget_cannot_reduce")
            items, level = next_items, level + 1
        context = read_json(self.artifact_path(doc, "context.json"))
        object_ids = sorted(set(v for c in chunks + [triage] for v in c["object_ids"]))
        question_ids = sorted(set(v for c in chunks + [triage] for v in c["question_ids"]))
        pages_read = len({c["page_index"] for c in chunks} | {p["page_index"] for p in extraction["pages"] if p.get("blank")})
        coverage = {"pages_total": extraction["pages_total"], "pages_read": pages_read,
                    "chunks_total": len(extraction["chunks"]), "chunks_read": len(chunks),
                    "characters_total": extraction["characters_total"], "characters_read": sum(c["characters"] for c in chunks)}
        coverage["complete"] = (coverage["pages_total"] == coverage["pages_read"] and coverage["chunks_total"] == coverage["chunks_read"]
                                and coverage["characters_total"] == coverage["characters_read"])
        if not coverage["complete"]:
            raise IntegrityError()
        report = {"schema_version": 1, "summary": final["summary"], "key_points": final["key_points"],
                  "model": self.model.identity, "actual_models": [c.get("_model") for c in chunks],
                  "graph_version": context["graph_version"], "questions_version": context["questions_version"],
                  "research_snapshot_hash": context["snapshot_hash"], "coverage": coverage,
                  "classification": triage["classification"], "importance": triage["importance"],
                  "object_ids": object_ids, "question_ids": question_ids,
                  "mapping_status": "candidate_mapped" if object_ids or question_ids else "pending_mapping",
                  "evidence": [e for c in chunks for e in c["evidence"]], "claims": [c for x in chunks for c in x["claims"]],
                  "quality": "model_read_candidate_requires_adoption_review",
                  "warning": "Coverage is processing coverage, not proof that every interpretation or number is correct."}
        return self._persist(doc, "report.json", "report", report)
