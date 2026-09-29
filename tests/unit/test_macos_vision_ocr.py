import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from inresearch.adapters import macos_vision_ocr
from inresearch.adapters import reader_model


class MacOSVisionOCRTests(unittest.TestCase):
    def test_binary_is_compiled_once_then_two_distinct_passes_are_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "page.png"
            image.write_bytes(b"fixture")
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                if command[0] == "swiftc":
                    Path(command[-1]).write_bytes(b"test executable")
                    return subprocess.CompletedProcess(command, 0, "", "")
                pass_index = int(command[-1])
                return subprocess.CompletedProcess(command, 0, json.dumps({
                    "text": "GPU 300 W" if pass_index == 0 else "GPU 300 W",
                    "blank": False, "unreadable": False,
                    "model": "Apple Vision fixture"
                }), "")

            with mock.patch.object(macos_vision_ocr, "available", return_value=True), \
                 mock.patch.object(macos_vision_ocr.subprocess, "run", side_effect=run):
                first = macos_vision_ocr.recognize(image, root / "state", 0)
                second = macos_vision_ocr.recognize(image, root / "state", 1)

            self.assertEqual([call[-1] for call in calls if call[0] != "swiftc"], ["0", "1"])
            self.assertEqual(sum(call[0] == "swiftc" for call in calls), 1)
            self.assertEqual(first["text"], "GPU 300 W")
            self.assertEqual(second["_model"]["provider"], "macOS Vision")

    def test_unreadable_page_is_not_silently_called_blank(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "page.png"
            image.write_bytes(b"fixture")

            def run(command, **kwargs):
                if command[0] == "swiftc":
                    Path(command[-1]).write_bytes(b"test executable")
                    return subprocess.CompletedProcess(command, 0, "", "")
                return subprocess.CompletedProcess(command, 0, json.dumps({
                    "text": "", "blank": False, "unreadable": True,
                    "model": "Apple Vision fixture"
                }), "")

            with mock.patch.object(macos_vision_ocr, "available", return_value=True), \
                 mock.patch.object(macos_vision_ocr.subprocess, "run", side_effect=run):
                result = macos_vision_ocr.recognize(image, root / "state", 0)
            self.assertTrue(result["unreadable"])
            self.assertFalse(result["blank"])

    def test_claude_reader_uses_local_vision_only_when_no_ocr_role_is_configured(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "page.png"
            image.write_bytes(b"fixture")
            expected = {"text": "GPU 300 W", "blank": False, "unreadable": False,
                        "_model": {"actual": "Apple Vision fixture", "provider": "macOS Vision"}}
            with mock.patch.object(macos_vision_ocr, "available", return_value=True), \
                 mock.patch.object(macos_vision_ocr, "recognize", return_value=expected) as recognize:
                client = reader_model.ModelClient()
                result = client.ocr_pass(image, 1)
            recognize.assert_called_once_with(image, Path.home() / ".local/state/inresearch.ai", 1)
            self.assertEqual(client.backend, "claude_cli")
            self.assertEqual(client.ocr_model, "Apple Vision VNRecognizeTextRequest")
            self.assertEqual(result["text"], "GPU 300 W")
