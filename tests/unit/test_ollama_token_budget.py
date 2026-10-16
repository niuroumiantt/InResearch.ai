"""No-inference tests for the final-only, bound local tokenizer guard."""
import copy
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from inresearch.adapters import models, ollama_token_budget as budget


class TokenBudgetTests(unittest.TestCase):
    def setUp(self):
        self.profile = models.ModelProfile(backend="ollama", url="http://127.0.0.1:11434",
            model="qwen3.8:27b", context=32768, max_output_tokens=4096, max_parallel=1)
        self.client = models.JsonModelClient(self.profile)
        self.system = "完整系统规则"
        self.user = budget.encoded({"stage": "whole_campus_adjudication",
                                    "evidence": "原文不可截断"*2500}).decode()
        self.schema = {"type": "object", "properties": {"answer": {"type": "integer"}}}
        self.model = {"manifest_sha256": "m", "model_file": {"path": "/bound.gguf"}}
        self.runner = {"pid": 123, "starttime": "456", "port": 12345,
                       "props_sha256": "p"}
        self.calls = []
        self.tokens = [1]*1000
        self.reply = {"model": budget.MODEL, "done": True, "done_reason": "stop",
                      "message": {"content": '{"answer":42,"_model":{"forged":true}}'}}
        for name, value in (("_model_identity", self.model), ("_runner_identity", self.runner)):
            item = patch.object(budget, name, return_value=value)
            item.start(); self.addCleanup(item.stop)
        transport = patch.object(budget, "_call", side_effect=self.call)
        transport.start(); self.addCleanup(transport.stop)

    def call(self, url, body=None, timeout=20):
        self.assertEqual(self.client._slots._value, 0)
        self.calls.append((url, copy.deepcopy(body)))
        if url.endswith("/tokenize"):
            self.assertEqual(body["content"], "<system>"+self.system+"</system>"+self.user+"<assistant>")
            self.assertEqual({k:v for k,v in body.items() if k != "content"},
                {"add_special": False, "parse_special": True, "with_pieces": False})
            return {"tokens": self.tokens}
        if body.get("_debug_render_only"):
            return {"model": budget.MODEL, "done": False, "message": {"content": ""},
                    "_debug_info": {"rendered_template":
                        "<system>"+self.system+"</system>"+self.user+"<assistant>"}}
        return copy.deepcopy(self.reply)

    def generate(self, **kwargs):
        return self.client.generate_campus_adjudication(self.system, self.user,
                                                        json_schema=self.schema, **kwargs)

    def actual_calls(self):
        return [body for url,body in self.calls
                if url.endswith("/api/chat") and not body.get("_debug_render_only")]

    def test_long_full_input_uses_exact_tokens_and_same_nontruncating_request(self):
        with self.assertRaisesRegex(models.InferenceError, "input_exceeds_context_budget"):
            self.client.generate(self.system, self.user, json_schema=self.schema)
        self.assertEqual(self.calls, [])
        result = self.generate()
        self.assertEqual(result["answer"], 42)
        proof = result["_model"]["token_budget"]
        self.assertNotIn("forged", result["_model"])
        self.assertEqual(proof["input_tokens"], 1000)
        self.assertEqual(proof["input_sha256"], hashlib.sha256(self.user.encode()).hexdigest())
        debug = self.calls[0][1]; actual = self.actual_calls()[0]
        self.assertEqual({k:v for k,v in debug.items() if k != "_debug_render_only"}, actual)
        self.assertEqual(actual["messages"][1]["content"], self.user)
        self.assertEqual(actual["format"], self.schema)
        self.assertEqual(actual["options"]["num_ctx"], 32768)
        self.assertFalse(actual["truncate"]); self.assertFalse(actual["shift"])
        self.assertFalse(actual["think"])
        self.assertEqual(len(self.actual_calls()), 1)
        self.assertEqual(self.client._slots._value, 1)

    def test_caller_schema_mutation_cannot_change_the_bound_completion_body(self):
        original=copy.deepcopy(self.schema)
        def mutate_caller_schema():
            self.schema['properties']['answer']['type']='string'
        result=self.generate(before_completion=mutate_caller_schema)
        self.assertNotEqual(self.schema,original)
        self.assertEqual(self.actual_calls()[0]['format'],original)
        self.assertEqual(self.calls[0][1]['format'],original)
        self.assertEqual(result['_model']['token_budget']['schema_sha256'],budget.digest(original))

    def test_measure_has_no_completion_and_proof_cannot_bypass_generate(self):
        proof = budget.measure(self.client, self.system, self.user, json_schema=self.schema)
        self.assertEqual(proof["input_tokens"], 1000)
        self.assertEqual(self.actual_calls(), [])
        with self.assertRaises(TypeError):
            self.client.generate_campus_adjudication(self.system, self.user,
                json_schema=self.schema, token_count=1)
        self.calls.clear()
        self.tokens = [1]*27649
        with self.assertRaisesRegex(models.InferenceError, "token_budget_exceeded"):
            self.generate()
        self.assertEqual(self.actual_calls(), [])

    def test_boundary_includes_output_and_reserve(self):
        self.tokens = [1]*27648
        self.assertEqual(self.generate()["_model"]["token_budget"]["input_tokens"], 27648)
        self.calls.clear(); self.tokens.append(1)
        with self.assertRaisesRegex(models.InferenceError, "token_budget_exceeded"):
            self.generate()
        self.assertEqual(self.actual_calls(), [])

    def test_wrong_scope_or_profile_never_renders(self):
        with self.assertRaisesRegex(models.InferenceError, "scope_required"):
            self.client.generate_campus_adjudication(self.system, '{"stage":"reading"}',
                                                     json_schema=self.schema)
        for changes in ({"url":"http://example.org"}, {"context":65536}, {"max_parallel":2},
                        {"request_model":"other"}, {"model":"other"}):
            with self.subTest(changes=changes):
                client = models.JsonModelClient(replace(self.profile, **changes))
                with self.assertRaisesRegex(models.InferenceError, "profile_unverified"):
                    client.generate_campus_adjudication(self.system, self.user,
                                                        json_schema=self.schema)
        self.assertEqual(self.calls, [])

    def test_missing_or_generating_debug_response_cannot_pass(self):
        variants = [
            {"model":budget.MODEL,"_debug_info":{"rendered_template":self.user}},
            {"model":budget.MODEL,"_debug_info":{"rendered_template":self.system+self.user},
             "eval_count":1},
            {"model":budget.MODEL,"_debug_info":{"rendered_template":self.system+self.user},
             "remote_host":"https://other"},
            {"model":budget.MODEL,"_debug_info":{"rendered_template":self.system+self.user},
             "done":True}]
        for response in variants:
            with self.subTest(response=response), patch.object(budget,"_call",return_value=response) as call:
                with self.assertRaises(models.InferenceError):
                    self.generate()
                self.assertEqual(call.call_count,1)

    def test_token_array_must_be_actual_integer_ids(self):
        for value in ([], [True], [-1], ["2"], None, {"count":1}):
            with self.subTest(tokens=value):
                self.tokens=value
                with self.assertRaisesRegex(models.InferenceError,"count_unverified"):
                    self.generate()
                self.assertEqual(self.actual_calls(),[])

    def test_model_change_before_completion_stops_generation(self):
        def changed_after_gate():
            replacement = patch.object(budget, "_model_identity", return_value={"manifest_sha256": "changed"})
            replacement.start(); self.addCleanup(replacement.stop)
        with self.assertRaisesRegex(models.InferenceError, "model_binding_changed"):
            self.generate(before_completion=changed_after_gate)
        self.assertEqual(self.actual_calls(), [])

    def test_same_model_pid_or_context_rotation_outside_tokenize_allows_fixed_32k_generation(self):
        tokenizer = {**self.runner, "context": 16384}
        events = []
        def rotated_before_completion():
            events.append("another valid same-GGUF runner is now loaded")
        call = self.call
        def completed_after_another_rotation(url, body=None, timeout=20):
            response = call(url, body, timeout)
            if url.endswith("/api/chat") and not body.get("_debug_render_only"):
                events.append("the queued caller replaces the runner after completion")
            return response
        with patch.object(budget, "_runner_identity", side_effect=[tokenizer, tokenizer,
                AssertionError("generation must not claim a cross-request PID lease")]) as identity, \
                patch.object(budget, "_call", side_effect=completed_after_another_rotation):
            result = self.generate(before_completion=rotated_before_completion)
        self.assertEqual(identity.call_count, 2)
        self.assertEqual(len(events), 2)
        proof = result["_model"]["token_budget"]
        self.assertEqual(proof["version"], "ollama-campus-token-v2")
        self.assertEqual(proof["tokenizer_binding"]["context"], 16384)
        self.assertNotIn("runner_binding", proof)
        generation = proof["generation_binding"]
        self.assertNotIn("pid", generation)
        self.assertEqual(generation["model_binding_sha256"], budget.digest(proof["model_binding"]))
        self.assertTrue(generation["model_verified_before_and_after"])
        actual = self.actual_calls()[0]
        self.assertEqual(actual["options"]["num_ctx"], 32768)
        self.assertEqual(actual["options"]["num_predict"], 4096)
        self.assertFalse(actual["truncate"]); self.assertFalse(actual["shift"])
        self.assertEqual({key:value for key,value in self.calls[0][1].items()
                          if key != "_debug_render_only"}, actual)

    def test_precompletion_runner_contention_remeasures_before_retry(self):
        for observed in ([models.InferenceError("campus_token_runner_unavailable")],
                         [self.runner, models.InferenceError("campus_token_runner_unavailable")],
                         [self.runner, {**self.runner, "pid": 999}],
                         [self.runner, {**self.runner, "props_sha256": "other", "context": 16384}]):
            with self.subTest(observed=observed):
                self.calls.clear()
                with patch.object(budget, "_runner_identity", side_effect=observed):
                    with self.assertRaisesRegex(models.InferenceError, "campus_token_runner_contention"):
                        self.generate()
                self.assertEqual(self.actual_calls(), [])
                self.assertEqual(self.client._slots._value, 1)
                self.tokens = [2]*1100
                result = self.generate()
                self.assertEqual(result["_model"]["token_budget"]["input_tokens"], 1100)
                self.assertEqual(len(self.actual_calls()), 1)
                self.assertEqual(sum(bool(body.get("_debug_render_only"))
                                     for _, body in self.calls), 2)
                self.assertEqual(self.calls[-2][0].rsplit("/", 1)[-1], "tokenize")

    def test_tokenize_transport_error_is_retryable_only_with_confirmed_runner_change(self):
        call = self.call
        def interrupted(url, body=None, timeout=20):
            response = call(url, body, timeout)
            if url.endswith("/tokenize"):
                raise ConnectionResetError("runner closed during tokenization")
            return response
        for after, reason in ((self.runner, "campus_token_runtime_unverified"),
                ({**self.runner, "pid": 999}, "campus_token_runner_contention"),
                (models.InferenceError("campus_token_runner_unavailable"), "campus_token_runner_contention")):
            with self.subTest(reason=reason, after=after):
                self.calls.clear()
                with patch.object(budget, "_call", side_effect=interrupted), \
                        patch.object(budget, "_runner_identity", side_effect=[self.runner, after]):
                    with self.assertRaisesRegex(models.InferenceError, reason):
                        self.generate()
                self.assertEqual(self.actual_calls(), [])
                self.assertEqual(sum(url.endswith("/tokenize") for url, _ in self.calls), 1)

    def test_model_binding_and_other_precompletion_failures_are_not_contention(self):
        with patch.object(budget, "_model_identity", side_effect=[self.model, {"changed": True}]):
            with self.assertRaisesRegex(models.InferenceError, "campus_token_model_binding_changed"):
                self.generate()
        for code in ("campus_token_ollama_version_unverified", "campus_token_blob_unverified",
                     "campus_token_runner_unverified", "campus_adjudication_token_budget_exceeded"):
            with self.subTest(code=code), patch.object(budget, "_prepare", side_effect=models.InferenceError(code)):
                with self.assertRaises(models.InferenceError) as error:
                    self.generate()
                self.assertEqual(error.exception.code, code)
        self.assertEqual(self.actual_calls(), [])

    def test_model_change_after_completion_retains_unaccepted_response(self):
        for observed, reason in (({**self.model, "manifest_sha256": "other"}, "campus_token_model_binding_changed"),
                ({**self.model, "renderer": "other"}, "campus_token_model_binding_changed"),
                ({**self.model, "model_file": {"path": "/changed.gguf"}}, "campus_token_model_binding_changed"),
                (models.InferenceError("campus_token_ollama_version_unverified"), "campus_token_ollama_version_unverified"),
                (OSError("metadata unavailable"), "campus_token_runtime_unverified")):
            with self.subTest(reason=reason, observed=observed):
                self.calls.clear()
                with patch.object(budget, "_model_identity", side_effect=[self.model]*4+[observed]):
                    with self.assertRaises(budget.CompletionUnverified) as error:
                        self.generate()
                self.assertEqual(error.exception.code, reason)
                evidence = error.exception.completion_evidence
                self.assertEqual(evidence["phase"], "completion_returned_unverified")
                self.assertEqual(evidence["response"], self.reply)
                self.assertEqual(evidence["response_sha256"], budget.digest(self.reply))
                self.assertEqual(evidence["request"], self.actual_calls()[0])
                self.assertEqual(evidence["request_sha256"], evidence["token_budget"]["request_sha256"])
                self.assertNotIn("generation_binding", evidence["token_budget"])
                self.assertEqual(len(self.actual_calls()), 1)

    def test_model_change_during_runner_failure_is_permanent(self):
        with patch.object(budget, "_model_identity", side_effect=[self.model, self.model, {"changed": True}]), \
                patch.object(budget, "_runner_identity", side_effect=models.InferenceError("campus_token_runner_unavailable")):
            with self.assertRaisesRegex(models.InferenceError, "campus_token_model_binding_changed"):
                self.generate()
        self.assertEqual(self.actual_calls(), [])

    def test_completion_transport_outcome_unknown_is_not_runner_contention(self):
        call = self.call
        def uncertain(url, body=None, timeout=20):
            response = call(url, body, timeout)
            if url.endswith("/api/chat") and not body.get("_debug_render_only"):
                raise TimeoutError("completion response not received")
            return response
        with patch.object(budget, "_call", side_effect=uncertain):
            with self.assertRaisesRegex(models.InferenceError, "campus_token_runtime_unverified"):
                self.generate()
        self.assertEqual(len(self.actual_calls()), 1)

    def test_truncated_incomplete_remote_or_wrong_model_output_is_rejected(self):
        for change, reason in [({"done_reason":"length"},"model_output_truncated"),
                ({"done":False},"model_output_incomplete"),
                ({"model":"other"},"model_identity_unverified"),
                ({"remote_host":"remote"},"model_output_incomplete"),
                ({"message":{"content":'{"answer":42}',"tool_calls":[{}]}},"model_output_incomplete")]:
            with self.subTest(change=change):
                original=self.reply; self.reply={**original,**change}
                with self.assertRaisesRegex(models.InferenceError,reason):
                    self.generate()
                self.reply=original


class TokenRuntimeBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.model_root=self.root/"models"
        (self.model_root/"blobs").mkdir(parents=True)
        model=b"GGUFfixture"; self.model_sha=hashlib.sha256(model).hexdigest()
        self.model_path=self.model_root/"blobs"/("sha256-"+self.model_sha)
        self.model_path.write_bytes(model)
        config=budget.encoded({"renderer":"qwen3.8","parser":"qwen3.5"})
        sha=hashlib.sha256(config).hexdigest()
        (self.model_root/"blobs"/("sha256-"+sha)).write_bytes(config)
        manifest=budget.encoded({"config":{"digest":"sha256:"+sha,"size":len(config)},
          "layers":[{"mediaType":"application/vnd.ollama.image.model",
                     "digest":"sha256:"+self.model_sha,"size":len(model)}]})
        self.manifest_path=self.model_root/"manifests/registry.ollama.ai/library/qwen3.8/27b"
        self.manifest_path.parent.mkdir(parents=True);self.manifest_path.write_bytes(manifest)
        self.manifest_sha=hashlib.sha256(manifest).hexdigest()
        for name,value in (("MODEL_ROOT",self.model_root),("MODEL_SHA",self.model_sha),
                           ("MANIFEST_SHA",self.manifest_sha)):
            p=patch.object(budget,name,value);p.start();self.addCleanup(p.stop)

    def metadata(self,url,body=None,timeout=20):
        if url.endswith("/api/version"): return {"version":"0.33.3"}
        if url.endswith("/api/tags"):
            return {"models":[{"name":budget.MODEL,"digest":self.manifest_sha}]}
        if url.endswith("/api/show"):
            return {"model_info":{"tokenizer.ggml.add_bos_token":False,
                                  "tokenizer.ggml.pre":"qwen35"}}
        raise AssertionError(url)

    def test_manifest_config_blob_and_api_tag_are_bound_without_large_blob_hash_claim(self):
        with patch.object(budget,"_call",side_effect=self.metadata):
            first=budget._model_identity("http://127.0.0.1:11434")
            self.assertEqual(first["model_layer_sha256"],self.model_sha)
            self.assertEqual(first["model_file"]["size"],len(b"GGUFfixture"))
            self.assertNotIn("verified_blob_sha256",first)
            self.model_path.write_bytes(b"GGUFchanged")
            second=budget._model_identity("http://127.0.0.1:11434")
            self.assertNotEqual(first,second)
            with patch.object(budget,"_runner_identity",return_value={}):
                with self.assertRaisesRegex(models.InferenceError,"model_binding_changed"):
                    budget._unchanged("http://127.0.0.1:11434",first,{})

    def test_wrong_version_tag_config_or_manifest_fails_closed(self):
        for url_suffix,response in [("/api/version",{"version":"0.32.0"}),
                ("/api/tags",{"models":[{"name":budget.MODEL,"digest":"wrong"}]}),
                ("/api/show",{"model_info":{"tokenizer.ggml.add_bos_token":True,
                                           "tokenizer.ggml.pre":"qwen35"}})]:
            with self.subTest(endpoint=url_suffix):
                def call(url,body=None,timeout=20):
                    return response if url.endswith(url_suffix) else self.metadata(url,body,timeout)
                with patch.object(budget,"_call",side_effect=call):
                    with self.assertRaises(models.InferenceError):
                        budget._model_identity("http://127.0.0.1:11434")
        self.manifest_path.write_bytes(self.manifest_path.read_bytes()+b" ")
        with patch.object(budget,"_call",side_effect=self.metadata):
            with self.assertRaisesRegex(models.InferenceError,"manifest_unverified"):
                budget._model_identity("http://127.0.0.1:11434")

    def test_runner_pid_starttime_model_path_context_and_props_are_bound(self):
        proc=self.root/"proc";process=proc/"321";process.mkdir(parents=True)
        executable=self.root/"llama-server";executable.write_text("fixture")
        (process/"exe").symlink_to(executable)
        (process/"status").write_text("Name:\tllama-server\nUid:\t996\t996\t996\t996\n")
        args=[str(executable),"--model",str(self.model_path),"--port","12345",
              "--host","127.0.0.1","-c","32768","-np","1"]
        (process/"cmdline").write_bytes(b"\0".join(x.encode() for x in args)+b"\0")
        def set_start(value):
            (process/"stat").write_text("321 (llama server) "+" ".join(["S"]+["0"]*18+[value]))
        set_start("900")
        props={"model_path":str(self.model_path),"total_slots":1,
               "default_generation_settings":{"n_ctx":32768}}
        model={"model_file":{"path":str(self.model_path)}}
        with patch.object(budget,"PROC",proc),patch.object(budget,"RUNNER",str(executable)), \
                patch.object(budget.pwd,"getpwnam",return_value=SimpleNamespace(pw_uid=996)), \
                patch.object(budget,"_call",return_value=props):
            first=budget._runner_identity(model);self.assertEqual(first["starttime"],"900")
            set_start("901");self.assertNotEqual(first,budget._runner_identity(model))
            props["default_generation_settings"]["n_ctx"]=16384
            with self.assertRaisesRegex(models.InferenceError,"runner_unverified"):
                budget._runner_identity(model)

    def runner_fixture(self):
        proc=self.root/"runner-proc";process=proc/"654";process.mkdir(parents=True)
        args=[budget.RUNNER,"--model",str(self.model_path),"--port","12345",
              "--host","127.0.0.1","-c","32768","-np","1"]
        (process/"cmdline").write_bytes(b"\0".join(x.encode() for x in args)+b"\0")
        (process/"status").write_text("Name:\tllama-server\nUid:\t996\t996\t996\t996\n")
        (process/"stat").write_text("654 (llama-server) "+" ".join(["S"]+["0"]*18+["900"]))
        return proc,process,{"model_file":{"path":str(self.model_path)}}, {
            "model_path":str(self.model_path),"total_slots":1,
            "default_generation_settings":{"n_ctx":32768}}

    def test_cross_uid_runner_uses_controlled_metadata_without_exe_permission(self):
        proc,process,model,props=self.runner_fixture()
        with patch.object(budget,"PROC",proc), \
                patch.object(budget.pwd,"getpwnam",return_value=SimpleNamespace(pw_uid=996)) as account, \
                patch.object(budget,"_call",return_value=props), \
                patch("os.readlink",side_effect=PermissionError(13,"cross-UID")) as readlink:
            result=budget._runner_identity(model)
        account.assert_called_once_with("ollama")
        readlink.assert_not_called()
        self.assertEqual((result["uid"],result["account"],result["pid"]),(996,"ollama",654))
        self.assertEqual(result["starttime"],"900")

    def test_runner_wrong_real_or_effective_uid_is_rejected(self):
        proc,process,model,props=self.runner_fixture()
        for uids in ("1001\t1001\t1001\t1001","996\t1001\t996\t996"):
            with self.subTest(uids=uids):
                (process/"status").write_text("Uid:\t"+uids+"\n")
                with patch.object(budget,"PROC",proc), \
                        patch.object(budget.pwd,"getpwnam",return_value=SimpleNamespace(pw_uid=996)), \
                        patch.object(budget,"_call",return_value=props) as call:
                    with self.assertRaisesRegex(models.InferenceError,"runner_unverified"):
                        budget._runner_identity(model)
                    call.assert_not_called()

    def test_16k_tokenizer_still_requires_exact_uid_host_model_and_props(self):
        proc, process, model, props = self.runner_fixture()
        raw = (process/"cmdline").read_bytes().replace(b"32768", b"16384")
        (process/"cmdline").write_bytes(raw)
        props["default_generation_settings"]["n_ctx"] = 16384
        with patch.object(budget, "PROC", proc), \
                patch.object(budget.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=996)), \
                patch.object(budget, "_call", return_value=props):
            self.assertEqual(budget._runner_identity(model)["context"], 16384)
            (process/"status").write_text("Uid:\t1001\t1001\t1001\t1001\n")
            with self.assertRaisesRegex(models.InferenceError, "campus_token_runner_unverified"):
                budget._runner_identity(model)
            (process/"status").write_text("Uid:\t996\t996\t996\t996\n")
            (process/"cmdline").write_bytes(raw.replace(b"127.0.0.1", b"0.0.0.0"))
            with self.assertRaisesRegex(models.InferenceError, "campus_token_runner_unverified"):
                budget._runner_identity(model)
            (process/"cmdline").write_bytes(raw)
            props["model_path"] = "/different.gguf"
            with self.assertRaisesRegex(models.InferenceError, "campus_token_runner_unverified"):
                budget._runner_identity(model)
            props["model_path"] = model["model_file"]["path"]
            props["default_generation_settings"]["n_ctx"] = 32768
            with self.assertRaisesRegex(models.InferenceError, "campus_token_runner_unverified"):
                budget._runner_identity(model)

    def test_same_basename_at_another_path_is_not_the_ollama_runner(self):
        proc,process,model,props=self.runner_fixture()
        raw=(process/"cmdline").read_bytes()
        (process/"cmdline").write_bytes(raw.replace(budget.RUNNER.encode(),b"/tmp/llama-server",1))
        with patch.object(budget,"PROC",proc), \
                patch.object(budget.pwd,"getpwnam",return_value=SimpleNamespace(pw_uid=996)), \
                patch.object(budget,"_call",return_value=props) as call:
            with self.assertRaisesRegex(models.InferenceError,"runner_unavailable"):
                budget._runner_identity(model)
            call.assert_not_called()

    def test_transport_disables_proxies_redirects_and_caps_responses(self):
        class Response(io.BytesIO):
            status=200
            def geturl(self):return "http://127.0.0.1:11434/api/version"
        with patch.object(budget.urllib.request,"build_opener") as build:
            build.return_value.open.return_value=Response(b"x"*(models.MAX_RESPONSE+1))
            with self.assertRaisesRegex(models.InferenceError,"response_too_large"):
                budget._call("http://127.0.0.1:11434/api/version")
            handlers=build.call_args.args
            self.assertEqual(handlers[0].proxies,{})
            self.assertIsInstance(handlers[1],budget._NoRedirect)
            self.assertIsNone(handlers[1].redirect_request(None,None,302,"",{},"https://other"))


if __name__ == "__main__":
    unittest.main()
