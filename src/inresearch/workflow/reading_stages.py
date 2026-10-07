"""Read/validate candidate artifacts; no queue or catalog writes."""
from __future__ import annotations
import re, shutil, subprocess, tempfile, time
from pathlib import Path
from inresearch.materials.reader_contracts import Blocked, Deferred, UnsafePath, IntegrityError, ModelOutputError, TransientModelError, ReaderError, RECIPE_VERSION, OCR_DEFERRED_PRIORITY, MODULES, OCR_GAP_REASONS, max_gap_pages
from inresearch.materials.artifacts import numeric_tokens, now_iso, encoded, digest_bytes, digest_file, safe_path, atomic_bytes, atomic_json, read_json, signature, split_text, require_text, require_content

from inresearch.materials.reading_artifacts import ReadingArtifacts

class ReadingStages(ReadingArtifacts):
    def __init__(self, data, model, ocr_max_pages, large_format_points, pdf_mode='full_visual',
                 read_batch_chunks=1, read_batch_chars=6000):
        super().__init__(data)
        if pdf_mode not in ('full_visual', 'native_text_only'):
            raise ValueError('invalid PDF reading mode')
        self.pdf_mode = pdf_mode
        if type(read_batch_chunks) is not int or not 1 <= read_batch_chunks <= 4:
            raise ValueError('read_batch_chunks must be an integer 1..4')
        if type(read_batch_chars) is not int or not 1 <= read_batch_chars <= 6000:
            raise ValueError('read_batch_chars must be an integer 1..6000')
        self.read_batch_chunks, self.read_batch_chars = read_batch_chunks, read_batch_chars
        self.model = model
        self.ocr_max_pages, self.large_format_points = ocr_max_pages, large_format_points

    def batch_policy(self, doc):
        if doc['suffix'] != '.pdf' or self.pdf_mode != 'native_text_only' or self.read_batch_chunks == 1:
            return {}
        return {'read_batch': {'version': 'read-batch-v1', 'max_chunks': self.read_batch_chunks,
                               'max_characters': self.read_batch_chars}}




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
        texts, page_meta, scope_meta = [], [], {}
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
        elif suffix == '.pdf' and self.artifact_path(doc, 'recipe.json').exists() and read_json(self.artifact_path(doc, 'recipe.json')).get('pdf_mode') == 'native_text_only':
            if not all(shutil.which(name) for name in ('pdftotext', 'pdfinfo', 'pdfimages')):
                raise Blocked('pdf_tools_missing')
            from inresearch.adapters.pdf_text import extract_pdf
            try:
                texts, meta = extract_pdf(source, run=self._command)
            except (ValueError, UnicodeError) as exc:
                raise Blocked('pdf_native_text_extraction_invalid') from exc
            scope_meta = {'scope': meta['scope'], 'visual_review_performed': False,
                          'skipped_image_pages': meta['image_pages'],
                          'text_layer_empty_pages': meta['text_layer_empty_pages'],
                          'replacement_character_pages': meta['replacement_character_pages'],
                          'nul_character_pages': meta['nul_character_pages'], 'ocr_calls': 0}
            for i, text in enumerate(texts, 1):
                page = {'page_index': i, 'text': text, 'method': 'pdftotext_native_only',
                        'source_sha256': doc['sha256'], 'visual_skipped': True,
                        'has_raster_image': i in meta['image_pages'],
                        'text_layer_empty': not text.strip()}
                atomic_json(safe_path(self.data, '%s/pages/%06d.json' % (doc['extracted_rel'], i)), page)
                page_meta.append({k: v for k, v in page.items() if k != 'text'})
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
            new_ocr_pages = 0
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
                        if new_ocr_pages and getattr(self.model,'backend','') == 'codex_cli':
                            # Release a bounded inference slot after one new
                            # vision page. Persisted pages resume unchanged;
                            # eligible text and finishing jobs can now run.
                            raise Deferred('ocr_checkpoint_yield')
                        if getattr(self.model, "ocr_model", "") and doc["priority"] != OCR_DEFERRED_PRIORITY:
                            # First OCR need of this document: step aside so text-layer
                            # documents are read first. Text pages extracted so far stay cached.
                            raise Deferred("ocr_deferred_behind_text_documents")
                        ocr_pages += 1
                        if ocr_pages > self.ocr_max_pages:
                            raise Blocked("ocr_page_budget_exceeded")
                        page.update(self._ocr_page(doc, source, i))
                        new_ocr_pages += 1
                    atomic_json(page_file, page)
                texts.append(page["text"])
                page_meta.append({k: v for k, v in page.items() if k not in {"text", "text_second_pass"}})
        else:
            raise Blocked("unsupported_format_" + (suffix.lstrip(".") or "unknown"))
        if signature(source) != before:
            raise IntegrityError()
        gaps = [p["page_index"] for p in page_meta if p.get("gap")]
        if len(gaps) > max_gap_pages(len(texts)):
            raise Blocked("ocr_gap_pages_exceed_limit")
        if not any(t.strip() for t in texts):
            raise Blocked('image_only_requires_user_text' if scope_meta else 'no_substantive_text')
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
                  "extraction_version": RECIPE_VERSION, **scope_meta}
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
            required = {"doc_id": doc["doc_id"], "content_sha256": doc["sha256"], "page_index": i}
            if any(result.get(key) != value for key, value in required.items()):
                raise IntegrityError()
            if result.get("method") == "m4_vision_ocr_gap":
                # M4 could not read this page even with the rescue pass. It stays an
                # explicit gap: no text, listed in the report, capped per document.
                if result.get("gap") is not True or result.get("gap_reason") not in OCR_GAP_REASONS:
                    raise IntegrityError()
                return {"text": "", "text_second_pass": "", "method": "m4_vision_ocr_gap", "gap": True,
                        "gap_reason": result["gap_reason"], "ocr_model": result.get("ocr_model"), "blank": False,
                        "verification": "page_not_read_after_rescue"}
            # A gap page re-read by the stronger gap_ocr model (adapters.gap_ocr) is held
            # to the same double-read rules as the Ollama pages.
            if result.get("method") not in {"m4_vision_ocr_double_pass", "m4_claude_vision_ocr_double_pass", "offload_vision_ocr_double_pass"}:
                raise IntegrityError()
            if not isinstance(result.get("text"), str) or not isinstance(result.get("text_second_pass"), str):
                raise IntegrityError()
            # Same page rules as local OCR: a blank page is allowed, but both passes
            # must be empty; a non-blank page must carry text.
            if result.get("unreadable") is not False or not isinstance(result.get("blank"), bool):
                raise Blocked("m4_offload_page_unreadable")
            if result["blank"] and (result["text"].strip() or result["text_second_pass"].strip()):
                raise Blocked("ocr_blank_has_text")
            if not result["blank"] and (not result["text"].strip() or not result["text_second_pass"].strip()):
                raise Blocked("ocr_empty_nonblank_page")
            if numeric_tokens(result["text"]) != numeric_tokens(result["text_second_pass"]):
                raise Blocked("m4_offload_numbers_disagree")
            page = {key: result[key] for key in ("text", "text_second_pass", "method", "ocr_model", "blank", "verification")}
            for key in ("ocr_models", "attempts_rel", "recovery_evidence", "source_image_scope"):
                if key in result:
                    page[key] = result[key]
            return page
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
            from inresearch.adapters.gap_ocr import pair_problem
            def problem(a, b):
                if any(not isinstance(x.get('text'),str) or type(x.get('blank')) is not bool or type(x.get('unreadable')) is not bool for x in (a,b)):
                    return 'ocr_page_unreadable'
                return pair_problem(a,b)
            issue = problem(first,second)
            reads, scale = [first,second], 1800
            if issue and getattr(self.model,'vision_rescue',None):
                # Preserve the failed evidence before doing bounded, higher-
                # resolution reads. Never turn disagreement into accepted text.
                history = self.artifact_path(doc,'ocr-attempts/%06d-%d.json' % (i,time.time_ns()))
                record = {'doc_id':doc['doc_id'],'content_sha256':doc['sha256'],
                          'reading_revision_id':doc['revision_id'],'page_index':i,
                          'initial_reason':issue,'normal_reads':reads,'rescue_reads':[]}
                atomic_json(history,record)
                self._command(['pdftoppm','-f',str(i),'-l',str(i),'-singlefile','-scale-to','3200','-png',str(source),str(base)],90)
                rescue_reads, pair = [], None
                for _ in range(3):
                    try:
                        rescue_reads.append(self.model.ocr(image,rescue=True))
                    finally:
                        record['rescue_reads']=rescue_reads
                        atomic_json(history,record)
                    for prior in rescue_reads[:-1]:
                        if problem(prior,rescue_reads[-1]) is None:
                            pair = (prior,rescue_reads[-1]);break
                    if pair:break
                if pair:
                    first,second=pair;issue=None;scale=3200
                    record['outcome']='agreed';atomic_json(history,record)
                else:
                    record['outcome']='blocked';atomic_json(history,record)
                    if getattr(self.model,'allow_ocr_gaps',False) and issue in OCR_GAP_REASONS:
                        record['outcome']='explicit_gap';atomic_json(history,record)
                        return {'text':'','text_second_pass':'','method':'vision_ocr_gap','gap':True,
                                'gap_reason':issue,'ocr_model':rescue_reads[-1].get('_model'),
                                'blank':False,'verification':'page_not_read_after_rescue',
                                'attempts_rel':history.relative_to(self.data.resolve()).as_posix()}
            if issue:raise Blocked(issue)
        return {"text": first["text"], "text_second_pass": second["text"], "method": "vision_ocr_double_pass",
                "ocr_model": first.get("_model"), "blank": first["blank"],
                "render_scale":scale,
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
        demands = snapshot.get('research_demands', [])
        focus_nodes = {r['node'] for r in demands}
        if focus_nodes:
            ranked_objects = [(score+30 if row['id'] in focus_nodes else score,row) for score,row in ranked_objects]
            ranked_questions = [(score+30 if any(q.get('node') in focus_nodes and q['id']==row['id'] for q in snapshot['questions']) else score,row) for score,row in ranked_questions]
        result = {"objects": [], "questions": []}
        current = snapshot.get('reading_contract')=='skeleton-demand-v1'
        budgets = (1400, 1500) if current else (2200, 2500)
        for key, rows, budget in (("objects", ranked_objects, budgets[0]), ("questions", ranked_questions, budgets[1])):
            for _, row in sorted(rows, key=lambda pair: (-pair[0], pair[1]["id"])):
                if len(encoded(result[key] + [row]).encode()) <= budget:
                    result[key].append(row)
        if current:
            result['reading_contract'] = snapshot['reading_contract']
            result['research_demands'] = []
            for row in demands:
                if len(encoded(result['research_demands']+[row]).encode())<=1500:
                    result['research_demands'].append(row)
            by_id = {q['id']:q for q in snapshot['questions']}
            for row in result['questions']:
                for key in ('node','variable_class'):
                    if key in by_id[row['id']]: row[key] = by_id[row['id']][key]
            while len(encoded(result).encode())>4800 and result['questions']:
                result['questions'].pop()
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
        for field in ("title", "org", "year"):
            require_text(cls.get(field), 300, empty=field in {"org", "year"})
        cls.setdefault('module_id','unknown')
        if cls["module_id"] not in MODULES | {"unknown"}:
            raise ModelOutputError()
        if cls["year"] and not re.fullmatch(r"\d{4}|unknown|未知", cls["year"]):
            raise ModelOutputError()
        importance = result.get("importance")
        if type(importance) is not int or not 1 <= importance <= 9:
            raise ModelOutputError()
        require_text(result.get("rationale"), 2000)
        result.update(self._ids(result, context))
        if context.get('reading_contract'):
            node = cls.get('node')
            if node is not None and node not in {r['id'] for r in context['objects']}:
                raise ModelOutputError()
            cls['node'] = node or (result['object_ids'][0] if result['object_ids'] else None)
            result['research_demands'] = context['research_demands']
        result["sampling_pages"] = [p["page_index"] for p in preview]
        return self._persist(doc, "triage.json", "triage", result)

    def _read_chunk(self, doc, index):
        relative, marker = "chunks/%06d.json" % index, "read:%d" % index
        cached = self._cached(doc, relative, marker)
        if cached:
            return cached
        payload = self._read_payload(doc, index)
        result = self.model.generate("read", payload)
        return self._save_read_result(doc, index, payload, result)

    def _read_payload(self, doc, index):
        extraction = read_json(self.artifact_path(doc, "extraction.json"))
        chunk = extraction["chunks"][index]
        text = self._chunk_text(chunk)
        context = self._context(doc, text)
        payload = {"doc_id": doc["doc_id"], "page_index": chunk["page_index"], "chunk_index": index,
                   "chunk_sha256": chunk["sha256"], "text": text, "allowed_ids": context}
        if extraction.get('scope') == 'pdf_native_text_only':
            payload['reading_scope'] = 'Native PDF text only. Image and vector contents are excluded; use only supplied text as evidence.'
        return payload

    def _read_batch(self, doc, indices):
        """One inference, independent source-bound artifacts and per-member failures."""
        policy = read_json(self.artifact_path(doc, 'recipe.json')).get('read_batch', {})
        if policy.get('version') != 'read-batch-v1' or not 2 <= len(indices) <= policy.get('max_chunks', 0):
            raise IntegrityError()
        if indices != list(range(indices[0], indices[0] + len(indices))):
            raise IntegrityError()
        payloads = [self._read_payload(doc, index) for index in indices]
        if sum(len(p['text']) for p in payloads) > policy['max_characters']:
            raise IntegrityError()
        results, fresh = {}, []
        for index, payload in zip(indices, payloads):
            cached = self._cached(doc, 'chunks/%06d.json' % index, 'read:%d' % index)
            if cached is not None:
                results[index] = cached
            else:
                fresh.append(payload)
        # A recovered attempt may already have persisted all but one member.
        if len(fresh) < 2:
            return self._read_members(doc, fresh, results)
        started = time.monotonic()
        try:
            response = self.model.generate('read_batch', {'doc_id': doc['doc_id'], 'chunks': fresh})
            members = response.get('chunks')
            if (not isinstance(members, list) or len(members) != len(fresh)
                    or any(not isinstance(m, dict) or type(m.get('chunk_index')) is not int for m in members)
                    or sorted(m['chunk_index'] for m in members) != sorted(p['chunk_index'] for p in fresh)):
                raise ModelOutputError()
            by_index = {m['chunk_index']: m for m in members}
            # Wrong hashes cannot be assigned to another chunk, even with equal text.
            if any(by_index[p['chunk_index']].get('chunk_sha256') != p['chunk_sha256'] for p in fresh):
                raise ModelOutputError()
        except (ModelOutputError, TransientModelError) as exc:
            # Failed envelopes fall back to the unchanged single-chunk contract.
            print(encoded({'at': now_iso(), 'stage': 'read_batch', 'doc_id': doc['doc_id'],
                           'chunks': indices, 'outcome': 'fallback_single', 'error_code': exc.code,
                           'seconds': round(time.monotonic() - started, 3)}), flush=True)
            return self._read_members(doc, fresh, results)
        for payload in fresh:
            index = payload['chunk_index']
            value = {**by_index[index], '_model': response.get('_model', {}),
                     'batch_execution': {'version': 'read-batch-v1', 'chunks': [p['chunk_index'] for p in fresh]}}
            try:
                results[index] = self._save_read_result(doc, index, payload, value)
            except ModelOutputError:
                # A malformed member cannot erase other checked pages.
                results.update(self._read_members(doc, [payload], {}))
            except ReaderError as exc:
                results[index] = exc
        print(encoded({'at': now_iso(), 'stage': 'read_batch', 'doc_id': doc['doc_id'], 'chunks': indices,
                       'outcome': 'checked', 'seconds': round(time.monotonic() - started, 3)}), flush=True)
        return results

    def _read_members(self, doc, payloads, results):
        for n, payload in enumerate(payloads):
            index = payload['chunk_index']
            try:
                results[index] = self._read_chunk(doc, index)
            except Deferred as exc:
                # A global provider wait must not issue more calls for this batch.
                for pending in payloads[n:]:
                    results[pending['chunk_index']] = exc
                break
            except ReaderError as exc:
                results[index] = exc
        return results

    def _save_read_result(self, doc, index, payload, result):
        relative, marker = 'chunks/%06d.json' % index, 'read:%d' % index
        text, context = payload['text'], payload['allowed_ids']
        extraction = read_json(self.artifact_path(doc, 'extraction.json'))
        chunk = extraction['chunks'][index]
        normalized = re.sub(r"\s+", "", text)
        claims = result.get("claims")
        has_unverifiable_quote = (isinstance(claims, list) and any(
            isinstance(e, dict) and isinstance(e.get("quote"), str)
            and re.sub(r"\s+", "", e["quote"]) not in normalized
            for claim in claims if isinstance(claim, dict)
            for e in claim.get("evidence", []) if isinstance(claim.get("evidence"), list)))
        if has_unverifiable_quote:
            result = self.model.generate("read", payload, retry_instruction=(
                "The previous response was rejected because one or more evidence quotes did not exactly occur in the source chunk. "
                "Correct this once: retain only claims supported by a short, contiguous, verbatim source excerpt; preserve every source character except whitespace may differ. "
                "Do not translate, paraphrase, join passages, or exceed the quote length limit. If an exact excerpt cannot be copied, omit that claim; an empty claims list is valid. Recheck every quote before returning."
            ))
        if result.get("chunk_sha256") != chunk["sha256"]:
            raise ModelOutputError()
        require_content(result.get("summary"), 1200)
        claims = result.get("claims")
        if not isinstance(claims, list) or len(claims) > 30:
            raise ModelOutputError()
        evs, clean_claims, dropped = [], [], []
        for claim in claims:
            if not isinstance(claim, dict):
                raise ModelOutputError()
            require_text(claim.get("text"), 1500)
            if claim.get("kind") not in {"observation", "author_claim", "author_forecast", "calculation", "unverified"}:
                raise ModelOutputError()
            evidence = claim.get("evidence")
            claim_ids = self._ids(claim, context)
            if not isinstance(evidence, list) or not 1 <= len(evidence) <= 8:
                raise ModelOutputError()
            quotes = [require_text(ev.get("quote") if isinstance(ev, dict) else None, 500) for ev in evidence]
            missing = [q for q in quotes if re.sub(r"\s+", "", q) not in normalized]
            if missing:
                # Still unverifiable after the one correction: drop this claim, keep the verified ones, and record it.
                dropped.append({"text": claim["text"], "kind": claim["kind"], "unverified_quotes": missing})
                continue
            c_index, refs = len(clean_claims), []
            for e_index, quote in enumerate(quotes):
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
        result.pop("dropped_claims", None)
        if dropped:
            result["dropped_claims"] = dropped
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
                    payload = {"doc_id": doc["doc_id"], "sections": members,
                               "level": level, "scope": "all supplied sections, candidate synthesis"}
                    if read_json(self.artifact_path(doc,'context.json')).get('reading_contract'):
                        payload['allowed_ids'] = self._context(doc,doc['original_name'])
                    result = self.model.generate("synthesize", payload)
                    require_content(result.get("summary"), 1500)
                    points = result.get("key_points")
                    if not isinstance(points, list) or len(points) > 20:
                        raise ModelOutputError()
                    for point in points:
                        require_content(point, 300)
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
        # Blank and gap pages are processed without text; gaps are named in the report.
        pages_read = len({c["page_index"] for c in chunks} | {p["page_index"] for p in extraction["pages"] if p.get("blank") or p.get("gap") or p.get('text_layer_empty')})
        coverage = {"pages_total": extraction["pages_total"], "pages_read": pages_read,
                    "chunks_total": len(extraction["chunks"]), "chunks_read": len(chunks),
                    "characters_total": extraction["characters_total"], "characters_read": sum(c["characters"] for c in chunks)}
        gap_pages = sorted(p["page_index"] for p in extraction["pages"] if p.get("gap"))
        if gap_pages:
            coverage["gap_pages"] = gap_pages
        from inresearch.materials.reading_artifacts import native_coverage
        coverage.update(native_coverage(extraction))
        dropped = sum(len(c.get("dropped_claims", [])) for c in chunks)
        if dropped:
            coverage["dropped_claims"] = dropped
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
        if context.get('reading_contract'):
            report.update(reading_contract=context['reading_contract'], research_demands=context['research_demands'],
                          targets_sha256=context['targets_sha256'])
        if gap_pages:
            report["warning"] += " Pages %s could not be read by OCR and are not covered by this report." % ", ".join(map(str, gap_pages))
        if coverage.get('scope') == 'pdf_native_text_only':
            report['warning'] += ' Native PDF text only; all image and vector content was skipped. No-text pages are not certified blank. This is not a full visual reading.'
        if dropped:
            report["warning"] += (" %d claims were dropped because their quotes still did not match the source after one correction;"
                                  " they are listed per chunk as dropped_claims and are not evidence." % dropped)
        return self._persist(doc, "report.json", "report", report)
