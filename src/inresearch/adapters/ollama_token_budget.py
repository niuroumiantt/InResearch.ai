"""Exact local Ollama token budget for whole-campus adjudication only.

The ordinary model adapter keeps its conservative byte guard. This narrow path
uses Ollama 0.33.3's real renderer and the already loaded, bound GGUF tokenizer;
it never truncates evidence, changes context, or starts a tokenizer process.
"""
import hashlib
import json
from pathlib import Path
import pwd
import re
import stat
import urllib.error
import urllib.request

from inresearch.adapters.models import InferenceError, MAX_RESPONSE, json_object

VERSION = "0.33.3"
MODEL = "qwen3.8:27b"
CONTEXT = 32768
OUTPUT = 4096
RESERVE = 1024
MODEL_ROOT = Path("/usr/share/ollama/.ollama/models")
MANIFEST_SHA = "22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643"
MODEL_SHA = "f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d"
RUNNER = "/usr/local/lib/ollama/llama-server"
PROC = Path("/proc")


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


class CompletionUnverified(InferenceError):
    """Retain a returned completion that failed its post-generation checks."""
    def __init__(self, error, body, proof, response):
        code = error.code if isinstance(error, InferenceError) else "campus_token_runtime_unverified"
        super().__init__(code)
        self.completion_evidence = {"phase": "completion_returned_unverified", "reason": code,
            "request": body, "request_sha256": digest(body), "token_budget": proof,
            "response": response, "response_sha256": digest(response)}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _call(url, payload=None, timeout=20):
    # No proxy or redirects: source material cannot select a remote destination.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    request = urllib.request.Request(url, data=None if payload is None else encoded(payload),
                                     headers={"Content-Type": "application/json"})
    with opener.open(request, timeout=timeout) as response:
        if response.geturl() != url or response.status != 200:
            raise InferenceError("campus_token_transport_unverified")
        raw = response.read(MAX_RESPONSE+1)
    if len(raw) > MAX_RESPONSE:
        raise InferenceError("campus_token_response_too_large")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("error"):
        raise InferenceError("campus_token_response_invalid")
    return value


def _file_identity(path, size=None):
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or size is not None and info.st_size != size:
        raise InferenceError("campus_token_blob_unverified")
    return {"path": str(path.resolve()), "device": info.st_dev, "inode": info.st_ino,
            "size": info.st_size, "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns}


def _small_blob(descriptor):
    sha = descriptor.get("digest", "")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", sha):
        raise InferenceError("campus_token_manifest_unverified")
    path = MODEL_ROOT/"blobs"/sha.replace(":", "-")
    identity = _file_identity(path, descriptor.get("size"))
    if not 0 < identity["size"] <= MAX_RESPONSE:
        raise InferenceError("campus_token_manifest_unverified")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha[7:]:
        raise InferenceError("campus_token_manifest_unverified")
    return raw, identity


def _model_identity(base):
    if _call(base+"/api/version").get("version") != VERSION:
        raise InferenceError("campus_token_ollama_version_unverified")
    manifest_path = MODEL_ROOT/"manifests/registry.ollama.ai/library/qwen3.8/27b"
    manifest_stat = _file_identity(manifest_path)
    if manifest_stat["size"] > MAX_RESPONSE:
        raise InferenceError("campus_token_manifest_unverified")
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
        raise InferenceError("campus_token_manifest_unverified")
    manifest = json.loads(raw)
    config_raw, config_stat = _small_blob(manifest["config"])
    config = json.loads(config_raw)
    if (config.get("renderer") != "qwen3.8" or config.get("parser") != "qwen3.5"
            or config.get("remote_host") or config.get("remote_model")):
        raise InferenceError("campus_token_renderer_unverified")
    layers = [row for row in manifest["layers"]
              if row.get("mediaType") == "application/vnd.ollama.image.model"]
    if len(layers) != 1 or layers[0].get("digest") != "sha256:"+MODEL_SHA:
        raise InferenceError("campus_token_blob_unverified")
    model_path = MODEL_ROOT/"blobs"/("sha256-"+MODEL_SHA)
    model_stat = _file_identity(model_path, layers[0]["size"])
    # Bind the content-addressed layer and unchanged file identity, without
    # claiming to hash sixteen gigabytes anew for each campus.
    with model_path.open("rb") as handle:
        if handle.read(4) != b"GGUF":
            raise InferenceError("campus_token_blob_unverified")
    tags = [row for row in _call(base+"/api/tags").get("models", [])
            if row.get("name") == MODEL]
    if len(tags) != 1 or tags[0].get("digest") != MANIFEST_SHA:
        raise InferenceError("campus_token_tag_unverified")
    show = _call(base+"/api/show", {"model": MODEL})
    info = show.get("model_info", {})
    if (show.get("remote_host") or show.get("remote_model") or show.get("messages")
            or show.get("system") or info.get("tokenizer.ggml.add_bos_token") is not False
            or info.get("tokenizer.ggml.pre") != "qwen35"):
        raise InferenceError("campus_token_template_unverified")
    return {"ollama_version": VERSION, "manifest_sha256": MANIFEST_SHA,
            "manifest_file": manifest_stat, "config_sha256": hashlib.sha256(config_raw).hexdigest(),
            "config_file": config_stat, "model_layer_sha256": MODEL_SHA,
            "model_file": model_stat, "renderer": config["renderer"], "parser": config["parser"],
            "show_sha256": digest(show)}


def _runner_identity(model):
    # The intake user cannot read another account's /proc/<pid>/exe. Bind the
    # fixed command path and all Linux credentials to the local ollama account;
    # no sudo, permission changes, or permissive fallback.
    expected_uid = pwd.getpwnam("ollama").pw_uid
    if type(expected_uid) is not int or expected_uid <= 0:
        raise InferenceError("campus_token_runner_unverified")
    matching = []
    for process in PROC.iterdir():
        if not process.name.isdigit():
            continue
        try:
            raw = (process/"cmdline").read_bytes()
            args = [part.decode() for part in raw.split(b"\0") if part]
            if not args or args[0] != RUNNER or "--model" not in args:
                continue
            if args[args.index("--model")+1] != model["model_file"]["path"]:
                continue
            def option(key):
                if args.count(key) != 1:
                    raise InferenceError("campus_token_runner_unverified")
                return args[args.index(key)+1]
            uid_rows = re.findall(r"^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$",
                                  (process/"status").read_text(), re.MULTILINE)
            if len(uid_rows) != 1 or any(int(value) != expected_uid for value in uid_rows[0]):
                raise InferenceError("campus_token_runner_unverified")
            port = int(option("--port"))
            context = int(option("-c"))
            if (option("--host") != "127.0.0.1" or not 1 <= port <= 65535
                    or context <= 0 or int(option("-np")) != 1):
                raise InferenceError("campus_token_runner_unverified")
            start = (process/"stat").read_text().rsplit(")", 1)[1].split()[19]
            matching.append({"pid": int(process.name), "starttime": start, "port": port,
                             "uid": expected_uid, "account": "ollama", "context": context,
                             "cmdline_sha256": hashlib.sha256(raw).hexdigest()})
        except (OSError, UnicodeDecodeError):
            continue
    if not matching:
        raise InferenceError("campus_token_runner_unavailable")
    if len(matching) != 1:
        raise InferenceError("campus_token_runner_unverified")
    identity = matching[0]
    props = _call("http://127.0.0.1:"+str(identity["port"])+"/props")
    if (props.get("model_path") != model["model_file"]["path"]
            or props.get("default_generation_settings", {}).get("n_ctx") != identity["context"]
            or props.get("total_slots") != 1 or props.get("is_sleeping")):
        raise InferenceError("campus_token_runner_unverified")
    # This is a vocabulary/tokenizer binding, not a generation KV context.
    # A legitimate 16K instance of the same GGUF tokenizes the same full text.
    return {**identity, "props_sha256": digest(props),
            "model_path": props["model_path"]}


def _bound_runner(base, model):
    try:
        return _runner_identity(model)
    except InferenceError as error:
        if error.code == "campus_token_runner_unavailable":
            # A competing runner is retryable only while model identity still
            # matches the original binding, including file metadata.
            if _model_identity(base) != model:
                raise InferenceError("campus_token_model_binding_changed") from None
        raise


def _unchanged(base, model, runner):
    if _model_identity(base) != model:
        raise InferenceError("campus_token_model_binding_changed")
    if _bound_runner(base, model) != runner:
        if _model_identity(base) != model:
            raise InferenceError("campus_token_model_binding_changed")
        raise InferenceError("campus_token_runtime_changed")


def _body(profile, system, user, schema):
    if (profile.backend != "ollama" or profile.model != MODEL
            or profile.request_model not in ("", MODEL)
            or profile.url not in ("http://127.0.0.1:11434", "http://localhost:11434")
            or profile.context != CONTEXT or profile.max_output_tokens != OUTPUT
            or profile.max_parallel != 1 or profile.api_key_env
            or "text_json" not in profile.capabilities):
        raise InferenceError("campus_token_profile_unverified")
    if (not isinstance(system, str) or not system or not isinstance(user, str)
            or not user or json_object(user).get("stage") != "whole_campus_adjudication"
            or not isinstance(schema, dict) or schema.get("type") != "object"):
        raise InferenceError("campus_token_scope_required")
    options = {"num_ctx": CONTEXT, "num_predict": OUTPUT, "temperature": 0}
    if profile.repeat_penalty is not None:
        options["repeat_penalty"] = profile.repeat_penalty
    if profile.repeat_last_n is not None:
        options["repeat_last_n"] = profile.repeat_last_n
    return {"model": MODEL, "messages": [{"role": "system", "content": system},
            {"role": "user", "content": user}], "stream": False, "think": False,
            "format": json.loads(encoded(schema)), "options": options,
            "truncate": False, "shift": False}


def _render(base, body, timeout):
    response = _call(base+"/api/chat", {**body, "_debug_render_only": True}, timeout)
    debug = response.get("_debug_info", {})
    message = response.get("message", {})
    rendered = debug.get("rendered_template")
    if (response.get("model") != MODEL or response.get("remote_host") or response.get("remote_model")
            or not isinstance(rendered, str) or not rendered or debug.get("image_count", 0) != 0
            or response.get("done") not in (None, False) or response.get("done_reason")
            or message.get("content") or message.get("thinking") or message.get("tool_calls")
            or any(response.get(key) for key in ("eval_count", "prompt_eval_count", "eval_duration"))):
        raise InferenceError("campus_token_render_unverified")
    if any(message["content"] not in rendered for message in body["messages"]):
        raise InferenceError("campus_token_render_incomplete")
    return rendered


def _prepare(client, system, user, json_schema):
    body = _body(client.profile, system, user, json_schema)
    base = client.profile.url
    model = _model_identity(base)
    rendered = _render(base, body, client.profile.timeout)
    if _model_identity(base) != model:
        raise InferenceError("campus_token_model_binding_changed")
    runner = _bound_runner(base, model)
    try:
        tokens = _call("http://127.0.0.1:"+str(runner["port"])+"/tokenize",
            {"content": rendered, "add_special": False, "parse_special": True,
             "with_pieces": False}).get("tokens")
    except OSError:
        # Direct /tokenize has no scheduler lease. Retry only if a fresh
        # binding check proves this instance disappeared/changed; an ordinary
        # transport failure against the same instance remains permanent.
        _unchanged(base, model, runner)
        raise
    if (not isinstance(tokens, list) or not tokens
            or any(type(token) is not int or token < 0 for token in tokens)):
        raise InferenceError("campus_token_count_unverified")
    _unchanged(base, model, runner)
    if len(tokens)+OUTPUT+RESERVE > CONTEXT:
        raise InferenceError("campus_adjudication_token_budget_exceeded")
    proof = {"version": "ollama-campus-token-v2", "request_sha256": digest(body),
             "schema_sha256": digest(body["format"]),
             "system_sha256": hashlib.sha256(system.encode()).hexdigest(),
             "input_sha256": hashlib.sha256(user.encode()).hexdigest(),
             "rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
             "rendered_utf8_bytes": len(rendered.encode()), "input_tokens": len(tokens),
             "token_ids_sha256": digest(tokens), "context": CONTEXT,
             "max_output_tokens": OUTPUT, "reserve_tokens": RESERVE,
             "truncate": False, "shift": False, "think": False,
             "model_binding": model, "tokenizer_binding": runner}
    return body, proof


def revalidate(client, proof):
    """Recheck the generation model, without claiming a cross-request PID lease."""
    if _model_identity(client.profile.url) != proof["model_binding"]:
        raise InferenceError("campus_token_model_binding_changed")


def measure(client, system, user, *, json_schema):
    """Render/tokenize only, for gated private preflight; never a completion."""
    try:
        with client._slots:
            _, proof = _prepare(client, system, user, json_schema)
            return proof
    except InferenceError:
        raise
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise InferenceError("campus_token_runtime_unverified") from None


def generate(client, system, user, *, json_schema, before_completion=None):
    """Produce its own request-bound proof; callers cannot supply token counts."""
    try:
        with client._slots:
            # The tokenizer instance must be stable only during /tokenize.
            # Ollama may legitimately replace it before/after /api/chat, whose
            # fixed request schedules its own 32K runner for the same model.
            try:
                body, proof = _prepare(client, system, user, json_schema)
                if before_completion:
                    before_completion()
                revalidate(client, proof)
                if digest(body) != proof["request_sha256"]:
                    raise InferenceError("campus_token_request_changed")
            except InferenceError as error:
                if error.code in ("campus_token_runner_unavailable", "campus_token_runtime_changed"):
                    raise InferenceError("campus_token_runner_contention") from None
                raise
            response = _call(client.profile.url+"/api/chat", body, client.profile.timeout)
            try:
                revalidate(client, proof)
                client._verify_model(response.get("model"))
                if response.get("done_reason") == "length":
                    raise InferenceError("model_output_truncated")
                if (response.get("model") != MODEL or response.get("remote_host")
                        or response.get("remote_model") or response.get("done") is not True
                        or response.get("done_reason") != "stop" or response.get("_debug_info")):
                    raise InferenceError("model_output_incomplete")
                message = response["message"]
                if message.get("thinking") or message.get("tool_calls") or message.get("images"):
                    raise InferenceError("model_output_incomplete")
                result = client._provenance(json_object(message.get("content")),
                                            response["model"], system, user)
                result["_model"]["token_budget"] = {**proof, "generation_binding": {
                    "model_binding_sha256": digest(proof["model_binding"]),
                    "request_sha256": proof["request_sha256"], "actual_model": response["model"],
                    "model_verified_before_and_after": True, "response_sha256": digest(response)}}
                return result
            except (InferenceError, OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
                # This evidence is audit-only, never an accepted adjudication.
                raise CompletionUnverified(error, body, proof, response) from None
    except InferenceError:
        raise
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise InferenceError("campus_token_runtime_unverified") from None
