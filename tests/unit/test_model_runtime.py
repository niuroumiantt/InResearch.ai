"""Model switches, capability boundaries and provenance without real inference."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import subprocess
import unittest
from unittest import mock
from concurrent.futures import ThreadPoolExecutor

from inresearch.adapters import models as models
from inresearch.workflow import reader as reader
import inresearch.adapters.reader_model as reader_model
from inresearch.materials import triage as triage
from inresearch.workflow import attribution as extraction
from inresearch.workflow import terminal_batch as pack
from types import SimpleNamespace


class Response:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.body[:size]


class ModelRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.profile = models.ModelProfile(**json.loads(models.DEFAULT_CONFIG.read_text())["profiles"]["spark"])

    def response(self, model=None, content='{"answer":42}'):
        return Response({"model": model or self.profile.model, "done_reason": "stop",
                         "message": {"content": content}})

    def test_model_switch_changes_transport_without_changing_task(self):
        profile = replace(self.profile, model="larger-research-model", context=65536,
                          max_output_tokens=8192)
        client = models.JsonModelClient(profile)
        with mock.patch.object(models.urllib.request, "urlopen",
                               return_value=self.response(profile.model)) as request:
            value = client.generate("read", "the same source")
        body = json.loads(request.call_args.args[0].data)
        self.assertEqual(body["model"], profile.model)
        self.assertEqual(body["options"]["num_ctx"], 65536)
        self.assertEqual(body["options"]["num_predict"], 8192)
        self.assertEqual(value["_model"]["actual"], profile.model)

    def test_reader_prompt_requires_verbatim_source_quotes(self):
        client = reader_model.ModelClient()
        payload = {"doc_id": "doc-test", "page_index": 1, "chunk_index": 0,
                   "chunk_sha256": "a" * 64, "text": "source", "allowed_ids": {"objects": [], "questions": []}}
        with mock.patch.object(client.client, "generate", return_value={"chunk_sha256": "a" * 64,
                "summary": "summary", "claims": [], "object_ids": [], "question_ids": []}) as generate:
            client.generate("read", payload)
        prompt = generate.call_args.args[0]
        self.assertIn("short, contiguous, verbatim excerpt", prompt)
        self.assertIn("exact substring", prompt)
        self.assertIn("whitespace-only normalization", prompt)
        self.assertIn("omit that claim", prompt)
        schema = generate.call_args.kwargs["json_schema"]
        self.assertEqual(schema["type"], "object")
        self.assertIn("claims", schema["required"])
        self.assertEqual(schema["properties"]["claims"]["items"]["properties"]["evidence"]["items"]
                         ["properties"]["quote"]["maxLength"], 500)

    def test_gateway_route_and_actual_model_are_separate(self):
        profile = replace(self.profile, backend="gateway", model="larger-model",
                          request_model="research-route", api_key_env="TEST_MODEL_KEY")
        response = Response({"model": "larger-model", "choices": [
            {"finish_reason": "stop", "message": {"content": '{"answer":1}'}}]})
        with mock.patch.dict(os.environ, {"TEST_MODEL_KEY": "secret"}), mock.patch.object(
                models.urllib.request, "urlopen", return_value=response) as request:
            value = models.JsonModelClient(profile).generate("read", "source")
        req = request.call_args.args[0]
        self.assertTrue(req.full_url.endswith("/v1/chat/completions"))
        self.assertEqual(json.loads(req.data)["model"], "research-route")
        self.assertEqual(value["_model"]["actual"], "larger-model")
        self.assertNotIn("secret", json.dumps(value))

    def test_wrong_model_is_rejected_and_model_cannot_forge_provenance(self):
        client = models.JsonModelClient(self.profile)
        with mock.patch.object(models.urllib.request, "urlopen", return_value=self.response("wrong")):
            with self.assertRaisesRegex(models.InferenceError, "model_identity_unverified"):
                client.generate("read", "source")
        with mock.patch.object(models.urllib.request, "urlopen", return_value=self.response(
                content='{"_model":{"actual":"forged"}}')):
            value = client.generate("read", "source")
        self.assertEqual(value["_model"]["actual"], self.profile.model)

    def test_invalid_or_truncated_output_is_not_accepted(self):
        client = models.JsonModelClient(self.profile)
        for content in ('[]', 'not json', '{"n":NaN}', '{"n":Infinity}'):
            with self.subTest(content=content), mock.patch.object(models.urllib.request, "urlopen",
                    return_value=self.response(content=content)):
                with self.assertRaisesRegex(models.InferenceError, "model_output_invalid"):
                    client.generate("read", "source")
        with mock.patch.object(models.urllib.request, "urlopen", return_value=Response({
                "model": self.profile.model, "done_reason": "length", "message": {"content": '{}'}})):
            with self.assertRaisesRegex(models.InferenceError, "model_output_truncated"):
                client.generate("read", "source")

    def test_missing_vision_and_oversized_input_do_not_call_provider(self):
        client = models.JsonModelClient(self.profile)
        with mock.patch.object(models.urllib.request, "urlopen") as request:
            with self.assertRaisesRegex(models.InferenceError, "model_capability_missing"):
                client.generate("OCR", "source", image_path="does-not-exist.png")
            with self.assertRaisesRegex(models.InferenceError, "input_exceeds_context_budget"):
                client.generate("read", "中" * self.profile.context)
            request.assert_not_called()

    def test_transport_failures_do_not_expose_private_response(self):
        with mock.patch.object(models.urllib.request, "urlopen", side_effect=OSError("private-key-and-source")):
            with self.assertRaises(models.InferenceError) as raised:
                models.JsonModelClient(self.profile).generate("read", "source")
        self.assertEqual(str(raised.exception), "model_failure")

    def test_config_is_validated_and_client_is_frozen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.json"
            config = json.loads(models.DEFAULT_CONFIG.read_text())
            path.write_text(json.dumps(config))
            with mock.patch.dict(os.environ, {"INRESEARCH_MODEL_CONFIG": str(path)}):
                client = models.configured_client()
                selected = config["roles"]["research_default"]
                initial_model = client.profile.model
                config["profiles"][selected]["model"] = "next-model"
                path.write_text(json.dumps(config))
                self.assertIs(models.configured_client(), client)
                self.assertEqual(client.profile.model, initial_model)
                self.assertEqual(models.load_profile().model, "next-model")
                with self.assertRaisesRegex(models.InferenceError, "model_role_not_configured:ocr"):
                    models.configured_client("ocr")
                config["profiles"][selected]["context"] = 4096
                path.write_text(json.dumps(config))
                with self.assertRaises(ValueError):
                    models.load_profile()

    def test_legacy_reader_environment_and_recipe_remain_compatible(self):
        old = {"backend": "ollama", "model": self.profile.model,
               "context": self.profile.context, "ocr_model": ""}
        self.assertEqual(models.reading_identity(reader_model.ModelClient(backend="ollama", url=self.profile.url, model=self.profile.model).identity), models.reading_identity(old))
        with mock.patch.dict(os.environ, {"READER_BACKEND": "gateway", "READER_URL": "http://localhost:8080", "READER_MODEL": "new-model"}):
            profile = models.reader_profile()
            self.assertEqual((profile.model, profile.request_model), ("new-model", "brain"))
            self.assertEqual(models.reader_profile(model="explicit").model, "explicit")

    def test_changed_inference_parameters_change_recipe_identity(self):
        old = self.profile.identity
        for field, value in (("model", "larger"), ("context", 65536),
                             ("max_output_tokens", 2048), ("revision", "weights-v2")):
            newer = replace(self.profile, **{field: value})
            self.assertNotEqual(models.reading_identity(old), models.reading_identity(newer.identity))
        self.assertEqual(models.reading_identity(old), models.reading_identity(
            replace(self.profile, timeout=1200, url="http://localhost:11434").identity))

    def test_configured_concurrency_budget_is_observed(self):
        client = models.JsonModelClient(replace(self.profile, max_parallel=2))
        active = peak = 0
        lock = threading.Lock()

        def provider(*args, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.01)
            with lock:
                active -= 1
            return self.response()

        with mock.patch.object(models.urllib.request, "urlopen", side_effect=provider):
            with ThreadPoolExecutor(6) as pool:
                list(pool.map(lambda _: client.generate("read", "source"), range(12)))
        self.assertEqual(peak, 2)


class ClaudeCliTests(unittest.TestCase):
    def setUp(self):
        self.profile = models.ModelProfile(backend="claude_cli", url="", model="claude-test-model")
        self.client = models.JsonModelClient(self.profile)

    def fake_process(self, command, **kwargs):
        self.command, self.options = command, kwargs
        events = [{"type": "assistant", "message": {"model": model}} for model in self.actual_models]
        events.append({"type": "result", **self.envelope})
        kwargs["stdout"].write("\n".join(json.dumps(event) for event in events).encode())
        return SimpleNamespace(returncode=self.exit_code)

    def invoke(self, envelope, exit_code=0, actual_models=None, json_schema=None):
        self.envelope, self.exit_code = envelope, exit_code
        self.actual_models = [self.profile.model] if actual_models is None else actual_models
        with mock.patch.object(models.subprocess, "run", side_effect=self.fake_process):
            return self.client.generate("task contract", "private document text", json_schema=json_schema)

    def test_cli_uses_stdin_and_returns_verified_model_metadata(self):
        value = self.invoke({"result": '{"answer":42}', "is_error": False,
                             "modelUsage": {self.profile.model: {"outputTokens": 7}}})
        self.assertEqual(value["answer"], 42)
        self.assertEqual(value["_model"]["executor"], "claude-code")
        self.assertEqual(value["_model"]["actual"], self.profile.model)
        self.assertNotIn("private document text", self.command)
        self.assertEqual(self.options["input"], "private document text")
        self.assertEqual(self.command[self.command.index("--tools") + 1], "")
        self.assertIn("--safe-mode", self.command)
        self.assertIn("--no-session-persistence", self.command)
        self.assertIn("--strict-mcp-config", self.command)
        self.assertEqual(self.options["env"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"], "4096")
        self.assertFalse(Path(self.options["cwd"]).exists())

    def test_cli_auth_failure_is_explicit_without_leaking_response(self):
        with self.assertRaisesRegex(models.InferenceError, "^model_cli_authentication_failed$"):
            self.invoke({"is_error": True, "result": "Failed to authenticate: 403 private-token"}, 1)

    def test_cli_cannot_claim_success_without_a_matching_model(self):
        for actual in ([], ["wrong-model"], [self.profile.model, "other-model"]):
            with self.subTest(actual=actual), self.assertRaisesRegex(models.InferenceError, "model_identity_unverified"):
                self.invoke({"result": '{}', "is_error": False,
                             "modelUsage": {self.profile.model: {}}}, actual_models=actual)

    def test_auxiliary_usage_does_not_impersonate_the_answering_model(self):
        value = self.invoke({"result": '{"answer":42}', "is_error": False,
                             "modelUsage": {"auxiliary-model": {}, self.profile.model: {}}})
        self.assertEqual(value["_model"]["actual"], self.profile.model)
        with self.assertRaisesRegex(models.InferenceError, "model_output_incomplete"):
            self.invoke({"result": '{}', "stop_reason": "max_tokens"})

    def test_cli_failure_timeout_and_missing_executable_are_distinct(self):
        for error, code in ((FileNotFoundError(), "model_cli_not_installed"),
                            (subprocess.TimeoutExpired("claude", 1), "model_cli_timeout")):
            with mock.patch.object(models.subprocess, "run", side_effect=error):
                with self.assertRaisesRegex(models.InferenceError, code):
                    self.client.generate("contract", "source")
        with self.assertRaisesRegex(models.InferenceError, "model_cli_failed"):
            self.invoke({"is_error": True, "result": "unavailable"}, 1)

    def test_cli_structured_result_still_requires_object_and_provenance(self):
        value = self.invoke({"structured_output": {"answer": 42, "_model": {"actual": "forged"}},
                             "is_error": False, "modelUsage": {self.profile.model: {}}})
        self.assertEqual(value["_model"]["actual"], self.profile.model)
        with self.assertRaisesRegex(models.InferenceError, "model_output_invalid"):
            self.invoke({"result": '[]', "is_error": False, "modelUsage": {self.profile.model: {}}})

    def test_cli_schema_requests_structured_output_and_accepts_its_tool_use_stop(self):
        schema = {"type": "object", "properties": {"answer": {"type": "integer"}}, "required": ["answer"]}
        value = self.invoke({"structured_output": {"answer": 42}, "is_error": False,
                             "stop_reason": "tool_use", "modelUsage": {self.profile.model: {}}},
                            json_schema=schema)
        self.assertEqual(value["answer"], 42)
        self.assertEqual(json.loads(self.command[self.command.index("--json-schema") + 1]), schema)


class CliOutputLimitTests(unittest.TestCase):
    """Thinking that fills the output budget gets one low-effort retry, recorded."""
    LIMIT = {"is_error": True, "result": "API Error: Claude's response exceeded the 4096 output token maximum. "
             "To configure this behavior, set the CLAUDE_CODE_MAX_OUTPUT_TOKENS environment variable."}
    OK = {"result": '{"answer":42}', "is_error": False}

    def setUp(self):
        self.profile = models.ModelProfile(backend="claude_cli", url="", model="claude-test-model")
        self.client = models.JsonModelClient(self.profile)
        self.commands = []

    def run_with(self, *envelopes):
        queue = list(envelopes)

        def fake(command, **kwargs):
            self.commands.append(command)
            envelope = queue.pop(0)
            events = [{"type": "assistant", "message": {"model": self.profile.model}}, {"type": "result", **envelope}]
            kwargs["stdout"].write("\n".join(json.dumps(e) for e in events).encode())
            return SimpleNamespace(returncode=1 if envelope.get("is_error") else 0)
        with mock.patch.object(models.subprocess, "run", side_effect=fake):
            return self.client.generate("contract", "source")

    def test_output_limit_is_retried_once_at_low_effort_and_recorded(self):
        value = self.run_with(self.LIMIT, self.OK)
        self.assertEqual(value["answer"], 42)
        self.assertEqual(value["_model"]["effort"], "low")
        self.assertNotIn("--effort", self.commands[0])
        self.assertEqual(self.commands[1][self.commands[1].index("--effort") + 1], "low")

    def test_a_second_output_limit_is_reported_and_other_errors_are_not_retried(self):
        with self.assertRaisesRegex(models.InferenceError, "^model_cli_output_limit$"):
            self.run_with(self.LIMIT, self.LIMIT)
        self.commands.clear()
        with self.assertRaisesRegex(models.InferenceError, "^model_cli_failed$"):
            self.run_with({"is_error": True, "result": "overloaded"})
        self.assertEqual(len(self.commands), 1)

    def test_normal_calls_carry_no_effort_flag(self):
        value = self.run_with(self.OK)
        self.assertNotIn("--effort", self.commands[0])
        self.assertNotIn("effort", value["_model"])


class TriageRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_formal_and_legacy_inventory_share_one_content_identity(self):
        path = self.root / "inventory.jsonl"
        rows = [{"sha256": "a" * 64, "original_rel": "a.pdf", "size_bytes": 42, "suffix": ".pdf"},
                {"sha256": "a" * 64, "rel": "copy.pdf", "size": 42, "suffix": ".pdf"}]
        path.write_text("\n".join(json.dumps(row) for row in rows))
        with mock.patch.object(triage, "INVENTORY", path):
            records = triage.load_inventory()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["paths"], ["a.pdf", "copy.pdf"])
        self.assertEqual(records[0]["size"], 42)

    def test_model_failure_stays_retryable_in_both_pending_sets(self):
        path = self.root / "results.jsonl"
        path.write_text('\n'.join(json.dumps(row) for row in [
            {"sha256": "failed", "status": "error", "error": "model_failure"},
            {"sha256": "complete", "status": "ok"}]))
        with mock.patch.object(triage, "RESULTS", path):
            self.assertEqual(triage.done_keys(), {"complete"})
        with mock.patch.object(extraction, "digest_files", return_value=[path]):
            self.assertEqual(extraction.done_digests(), {"complete"})

    def test_single_zero_judgement_needs_review(self):
        rec = {"sha256": "abc", "rel": "a.pdf", "suffix": ".pdf", "size": 42,
               "level": "p", "task_version": triage.TASK_VERSION, "preview": "text",
               "meta": {}, "category": None}
        value = triage.finalize(rec, {"score": 0, "module": "unrelated"}, None, None)
        self.assertEqual(value["category"], "_review")
        self.assertEqual(value["score_status"], "provisional_zero_needs_review")
        self.assertIsNone(value["model"])

    def test_terminal_record_separates_client_from_unknown_model(self):
        batch = self.root / "batch.json"
        result = self.root / "results.jsonl"
        sha = "a" * 64
        batch.write_text(json.dumps([{"id": sha[:12], "path": "a.pdf", "level": "p",
                                      "preview": "source", "meta": {}}]))
        item = {"sha256": sha, "rel": "a.pdf", "suffix": ".pdf", "size": 42,
                "paths": ["a.pdf"], "copies": 1}
        verdict = {"id": sha[:12], "score": 5, "module": "M09", "title": "source"}
        args = SimpleNamespace(verdicts="unused", batch=str(batch), digests=False,
                               executor="codex", model=None)
        with mock.patch.object(pack, "parse_verdicts", return_value=[verdict]), mock.patch.object(
                triage, "load_inventory", return_value=[item]), mock.patch.object(triage, "RESULTS", result):
            pack.cmd_record(args)
        row = json.loads(result.read_text())
        self.assertEqual(row["executor"], "codex")
        self.assertIsNone(row["model"])
        self.assertEqual(row["model_identity"], "unknown")


if __name__ == "__main__":
    unittest.main()
