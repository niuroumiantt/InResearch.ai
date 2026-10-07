import base64
import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from inresearch.adapters import gap_ocr, models
from inresearch.materials.artifacts import atomic_json, digest_file, read_json

ROOT = Path(__file__).resolve().parents[2]


class CliImageTests(unittest.TestCase):
    """The Claude CLI sees the page as an image block on stdin; tools stay off."""

    def test_image_goes_in_as_one_stream_json_message(self):
        profile = models.ModelProfile(backend="claude_cli", url="", model="claude-test", capabilities=("vision_json",))
        seen = {}

        def fake(command, **kwargs):
            seen["command"], seen["input"] = command, kwargs["input"]
            events = [{"type": "assistant", "message": {"model": "claude-test"}},
                      {"type": "result", "is_error": False, "structured_output": {"text": "300 W", "blank": False, "unreadable": False}}]
            kwargs["stdout"].write("\n".join(json.dumps(e) for e in events).encode())
            return SimpleNamespace(returncode=0)
        with tempfile.TemporaryDirectory() as d:
            image = Path(d) / "page.png"
            image.write_bytes(b"\x89PNG fake")
            with mock.patch.object(models.subprocess, "run", side_effect=fake):
                value = models.JsonModelClient(profile).generate("sys", "read it", image_path=image, json_schema=gap_ocr.SCHEMA)
        command = seen["command"]
        self.assertEqual(command[command.index("--input-format") + 1], "stream-json")
        self.assertEqual(command[command.index("--tools") + 1], "")
        message = json.loads(seen["input"])
        self.assertEqual(message["type"], "user")
        image_block, text_block = message["message"]["content"]
        self.assertEqual(base64.b64decode(image_block["source"]["data"]), b"\x89PNG fake")
        self.assertEqual(text_block, {"type": "text", "text": "read it"})
        self.assertEqual(value["text"], "300 W")
        self.assertEqual(len(value["_model"]["image_sha256"]), 64)

    def test_text_calls_are_unchanged(self):
        profile = models.ModelProfile(backend="claude_cli", url="", model="claude-test")
        seen = {}

        def fake(command, **kwargs):
            seen["command"], seen["input"] = command, kwargs["input"]
            events = [{"type": "assistant", "message": {"model": "claude-test"}}, {"type": "result", "result": '{"a":1}'}]
            kwargs["stdout"].write("\n".join(json.dumps(e) for e in events).encode())
            return SimpleNamespace(returncode=0)
        with mock.patch.object(models.subprocess, "run", side_effect=fake):
            value = models.JsonModelClient(profile).generate("sys", "plain text")
        self.assertNotIn("--input-format", seen["command"])
        self.assertEqual(seen["input"], "plain text")
        self.assertNotIn("image_sha256", value["_model"])

    def test_the_shipped_gap_role_is_a_claude_vision_profile(self):
        profile = models.load_profile("gap_ocr", ROOT / "deploy/models.json")
        self.assertEqual((profile.backend, profile.capabilities), ("claude_cli", ("vision_json",)))
        with self.assertRaises(ValueError):
            models.ModelProfile(backend="gateway", url="http://x", model="m", capabilities=("vision_json",))


class Reads:
    """A stand-in vision client: pages listed in ``fail`` disagree between reads."""

    def __init__(self, fail=()):
        self.fail, self.calls = set(fail), []

    def generate(self, system, user, image_path=None, json_schema=None):
        page = int(Path(image_path).stem.split("-")[1])
        self.calls.append(page)
        number = page * 100 + (len(self.calls) if page in self.fail else 0)
        return {"text": "第%d页 %d W" % (page, number), "blank": False, "unreadable": False, "_model": {"actual": "claude-test"}}


class FillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)
        original = self.data / "originals/a.pdf"
        original.parent.mkdir(parents=True)
        original.write_bytes(b"%PDF fake")
        self.sha = digest_file(original)
        (self.data / "catalog").mkdir()
        conn = sqlite3.connect(self.data / "catalog/catalog.sqlite")
        conn.execute("CREATE TABLE current_readings (doc_id,sha256,original_rel,extracted_rel)")
        conn.execute("INSERT INTO current_readings VALUES ('doc-a',?,'originals/a.pdf','extracted/doc-a')", (self.sha,))
        conn.commit(); conn.close()
        self.pages = self.data / "offload/m4/results/doc-a/pages"
        for i in (1, 2, 3):
            gap = i != 1
            atomic_json(self.pages / ("%06d.json" % i), {
                "doc_id": "doc-a", "content_sha256": self.sha, "page_index": i,
                "method": "m4_vision_ocr_gap" if gap else "m4_vision_ocr_double_pass",
                "gap": gap, "gap_reason": "model_output_truncated", "text": "" if gap else "p1", "text_second_pass": ""})
            atomic_json(self.data / ("extracted/doc-a/pages/%06d.json" % i), {"page_index": i, "gap": gap, "source_sha256": self.sha})

    def tearDown(self):
        self.temp.cleanup()

    def render(self, source, index, directory):
        image = Path(directory) / ("page-%06d.png" % index)
        image.write_bytes(b"png")
        return image

    def test_agreeing_reads_fill_the_gap_and_drop_only_its_cached_page(self):
        client = Reads(fail={3})
        with mock.patch.object(gap_ocr, "render", side_effect=self.render):
            result = gap_ocr.fill(self.data, "doc-a", client)
        self.assertEqual(result["filled_pages"], [2])
        self.assertEqual(result["still_gaps"], [{"page": 3, "reason": "ocr_numbers_disagree", "reads": 3}])
        attempts = read_json(self.data / "offload/m4/gap-history/doc-a/000003.attempts.json")
        self.assertEqual([r["numbers_not_in_every_read"] for r in attempts["reads"]],
                         [["303"], ["304"], ["305"]])
        self.assertEqual(sorted(set(client.calls)), [2, 3])            # page 1 was never a gap
        page = read_json(self.pages / "000002.json")
        self.assertEqual((page["method"], page["text"], page["replaces_gap_reason"]),
                         (gap_ocr.METHOD, "第2页 200 W", "model_output_truncated"))
        self.assertEqual(read_json(self.data / "offload/m4/gap-history/doc-a/000002.json")["method"], "m4_vision_ocr_gap")
        self.assertFalse((self.data / "extracted/doc-a/pages/000002.json").exists())
        self.assertTrue((self.data / "extracted/doc-a/pages/000001.json").exists())
        self.assertTrue((self.data / "extracted/doc-a/pages/000003.json").exists())
        self.assertEqual(read_json(self.pages / "000003.json")["method"], "m4_vision_ocr_gap")

    def test_a_third_read_that_agrees_with_one_of_the_first_two_fills_the_page(self):
        answers = iter(["第2页 200 W", "第2页 290 W", "第2页 200 W", "第3页 300 W", "第3页 300 W"])

        def generate(system, user, image_path=None, json_schema=None):
            return {"text": next(answers), "blank": False, "unreadable": False, "_model": {"actual": "claude-test"}}
        with mock.patch.object(gap_ocr, "render", side_effect=self.render):
            result = gap_ocr.fill(self.data, "doc-a", SimpleNamespace(generate=generate))
        self.assertEqual(result["filled_pages"], [2, 3])
        page2, page3 = read_json(self.pages / "000002.json"), read_json(self.pages / "000003.json")
        self.assertEqual((page2["text"], page2["text_second_pass"], page2["reads"]), ("第2页 200 W", "第2页 200 W", 3))
        self.assertEqual(page3["reads"], 2)
        self.assertFalse((self.data / "offload/m4/gap-history/doc-a/000002.attempts.json").exists())

    def test_a_rerun_after_an_interrupted_fill_drops_the_stale_cache(self):
        with mock.patch.object(gap_ocr, "render", side_effect=self.render), \
             mock.patch.object(gap_ocr, "drop_cached_gap"):            # crash before the cache went
            gap_ocr.fill(self.data, "doc-a", Reads(fail={3}))
        self.assertTrue((self.data / "extracted/doc-a/pages/000002.json").exists())
        client = Reads(fail={3})
        with mock.patch.object(gap_ocr, "render", side_effect=self.render):
            result = gap_ocr.fill(self.data, "doc-a", client)
        self.assertEqual((result["filled_pages"], sorted(set(client.calls))), ([], [3]))
        self.assertFalse((self.data / "extracted/doc-a/pages/000002.json").exists())

    def test_changed_original_is_refused_before_any_model_call(self):
        (self.data / "originals/a.pdf").write_bytes(b"%PDF other")
        client = Reads()
        with self.assertRaisesRegex(RuntimeError, "source_hash_mismatch"):
            gap_ocr.fill(self.data, "doc-a", client)
        self.assertEqual(client.calls, [])

    def test_dry_run_lists_gaps_without_reading(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(gap_ocr.main(["--data-root", str(self.data), "--doc-id", "doc-a", "--dry-run"]), 0)
        self.assertEqual(json.loads(out.getvalue()), {"doc_id": "doc-a", "gap_pages": [2, 3]})
        self.assertTrue((self.data / "extracted/doc-a/pages/000002.json").exists())

    def test_the_reader_accepts_the_filled_page(self):
        from inresearch.workflow.reading_stages import ReadingStages
        with mock.patch.object(gap_ocr, "render", side_effect=self.render):
            gap_ocr.fill(self.data, "doc-a", Reads())
        stages = ReadingStages(self.data, SimpleNamespace(ocr_model=""), 10, 10_000)
        doc = {"doc_id": "doc-a", "sha256": self.sha}
        page = stages._ocr_page(doc, None, 2)
        self.assertEqual((page["method"], page["text"]), (gap_ocr.METHOD, "第2页 200 W"))

class ReceiveTests(FillTests):
    def rescue(self, index=2):
        return {'doc_id':'doc-a', 'content_sha256':self.sha, 'page_index':index,
                'method':gap_ocr.RESCUE_METHOD, 'text':'300 W', 'text_second_pass':'300 W',
                'blank':False, 'unreadable':False, 'ocr_model':{'backend':'codex_cli','actual':None},
                'ocr_models':[{'image_sha256':'a'*64},{'image_sha256':'a'*64}],
                'verification':'candidate_ocr_agreement_not_accuracy_certification'}

    def native_gap(self):
        self.pages.joinpath('000002.json').unlink()
        atomic_json(self.data / 'extracted/doc-a/pages/000002.json', {
            'page_index':2, 'source_sha256':self.sha, 'gap':True,
            'method':'vision_ocr_gap','gap_reason':'ocr_page_unreadable','text':''})

    def test_codex_cache_gap_discovered_without_m4_inbox(self):
        self.native_gap()
        self.assertEqual([p for p,_,_ in gap_ocr.gap_pages(self.data,gap_ocr.document(self.data,'doc-a'),False)], [2,3])

    def test_receive_archives_gap_keeps_other_pages_and_does_not_write_catalog(self):
        self.native_gap();catalog=digest_file(self.data/'catalog/catalog.sqlite')
        good=digest_file(self.data/'extracted/doc-a/pages/000001.json')
        receipt=gap_ocr.receive(self.data,'doc-a',self.rescue())
        cached=read_json(self.data/'extracted/doc-a/pages/000002.json')
        self.assertEqual(cached['method'],gap_ocr.RESCUE_METHOD)
        self.assertNotIn('gap',cached)
        self.assertEqual(digest_file(self.data/'catalog/catalog.sqlite'),catalog)
        self.assertEqual(digest_file(self.data/'extracted/doc-a/pages/000001.json'),good)
        history=self.data/receipt['history_rel']
        self.assertEqual(read_json(history/'cached-gap.json')['method'],'vision_ocr_gap')
        self.assertEqual(read_json(history/'rescue-result.json'),self.rescue())

    def test_receive_rejects_disagreement_identity_and_successful_page(self):
        self.native_gap();p=self.data/'extracted/doc-a/pages/000002.json';before=digest_file(p)
        for key,value,code in [('text_second_pass','310 W','ocr_numbers_disagree'),
                               ('content_sha256','a'*64,'rescue_page_identity_mismatch'),
                               ('unreadable',True,'ocr_page_unreadable')]:
            result=self.rescue();result[key]=value
            with self.assertRaisesRegex(RuntimeError,code):gap_ocr.receive(self.data,'doc-a',result)
            self.assertEqual(digest_file(p),before)
        with self.assertRaisesRegex(RuntimeError,'rescue_target_is_not_gap'):
            gap_ocr.receive(self.data,'doc-a',self.rescue(1))

    def test_interrupted_receive_can_notify_without_overwriting_success(self):
        self.native_gap();result=self.rescue()
        gap_ocr.receive(self.data,'doc-a',result,notify=False)
        self.assertFalse((self.pages/'000002.json').exists())
        receipt=gap_ocr.receive(self.data,'doc-a',result)
        self.assertEqual(receipt['outcome'],'already_received')
        self.assertEqual(read_json(self.pages/'000002.json'),result)

    def test_empty_second_nonblank_read_rejected_even_without_numbers(self):
        self.assertEqual(gap_ocr.pair_problem({'text':'hello','blank':False,'unreadable':False},
                                            {'text':'','blank':False,'unreadable':False}), 'ocr_empty_nonblank_page')

    def test_sealed_extraction_refused(self):
        self.native_gap();atomic_json(self.data/'extracted/doc-a/extraction.json',{})
        with self.assertRaisesRegex(RuntimeError,'rescue_extraction_already_sealed'):
            gap_ocr.receive(self.data,'doc-a',self.rescue())

class RegionVerificationTests(unittest.TestCase):
    def result(self):
        meta={'image_sha256':gap_ocr.digest_file(self.image)}
        reads=[{'text':'300 W','blank':False,'unreadable':False,'_model':meta} for _ in range(2)]
        text='Native paragraph\n\n[Original embedded image 0; full source image, page viewport may clip it]\n300 W'
        return {'text':text,'text_second_pass':text,'recovery_evidence':[
            {'image_number':0,'image_sha256':meta['image_sha256'],'reads':reads,'agreed_pair':[0,1]}]}

    def test_regions_require_all_source_images_two_distinct_reads_and_exact_assembly(self):
        with tempfile.TemporaryDirectory() as td:
            self.image=Path(td)/'image.png';self.image.write_bytes(b'original image bytes')
            def output(args,**kwargs):
                if args[0]=='pdfimages':return b'header\nheader\n7 0 image 768 400 rgb 3 8 image no 90 0 100 100 1K 1%\n'
                return b'Native paragraph\f'
            def extract(args,**kwargs):
                Path(args[-1]+'-000.png').write_bytes(self.image.read_bytes())
                return SimpleNamespace(returncode=0)
            with mock.patch.object(gap_ocr.subprocess,'check_output',side_effect=output), \
                 mock.patch.object(gap_ocr.subprocess,'run',side_effect=extract):
                gap_ocr.verify_regions(Path(td)/'source.pdf',7,self.result())
                for mutation,code in [
                    (lambda r:r.update(text='summary instead'),'rescue_region_text_mismatch'),
                    (lambda r:r['recovery_evidence'][0].update(image_number=1),'rescue_region_coverage_mismatch'),
                    (lambda r:r['recovery_evidence'][0].update(image_sha256='0'*64),'rescue_region_image_mismatch'),
                    (lambda r:r['recovery_evidence'][0].update(agreed_pair=[0,0]),'rescue_region_pair_invalid'),
                    (lambda r:r['recovery_evidence'][0]['reads'][1].update(unreadable=True),'ocr_page_unreadable'),
                    (lambda r:r['recovery_evidence'][0]['reads'][1].update(text='310 W'),'ocr_numbers_disagree')]:
                    r=self.result();mutation(r)
                    with self.assertRaisesRegex(RuntimeError,code):gap_ocr.verify_regions(Path(td)/'source.pdf',7,r)


class EmbeddedImageRenderTests(unittest.TestCase):
    def test_wrapper_preserves_original_pixels_and_handles_rgb_and_gray(self):
        import struct
        for color, space, colors in [(2, 'DeviceRGB', 3), (0, 'DeviceGray', 1)]:
            with tempfile.TemporaryDirectory() as td:
                source=Path(td)/'source.png'
                def chunk(kind, value):return struct.pack('>I',len(value))+kind+value+b'crc!'
                payload=b'original compressed pixels'
                source.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',10,20,8,color,0,0,0))+chunk(b'IDAT',payload))
                original=digest_file(source)
                def render(args,**kw):
                    pdf=Path(args[-2]).read_bytes()
                    self.assertIn(payload,pdf)
                    self.assertIn(('/ColorSpace /'+space).encode(),pdf)
                    self.assertIn(('/Colors %d'%colors).encode(),pdf)
                    Path(args[-1]+'.png').write_bytes(b'rendered pixels')
                    return SimpleNamespace(returncode=0)
                with mock.patch.object(gap_ocr.subprocess,'run',side_effect=render):
                    enlarged=gap_ocr.enlarge_embedded_png(source,td,2400)
                self.assertEqual(enlarged.read_bytes(),b'rendered pixels')
                self.assertEqual(digest_file(source),original)

    def test_unsupported_png_does_not_silently_drop_pixels(self):
        import struct
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'source.png'
            data=struct.pack('>IIBBBBB',10,20,8,6,0,0,0)
            source.write_bytes(b'\x89PNG\r\n\x1a\n'+struct.pack('>I',len(data))+b'IHDR'+data+b'crc!')
            with self.assertRaisesRegex(RuntimeError,'rescue_source_png_unsupported'):
                gap_ocr.enlarge_embedded_png(source,td)


if __name__ == "__main__":
    unittest.main()
