"""Exact local Ollama token budget for explicit native-campus stages.

The ordinary model adapter keeps its conservative byte guard. This narrow path
uses Ollama 0.33.3's real renderer and the already loaded, bound GGUF tokenizer;
it never truncates evidence, changes context, or starts a tokenizer process.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request

from inresearch.adapters.models import InferenceError, MAX_RESPONSE, json_object
from inresearch.adapters import ollama_macos

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


class ReadingBudgetExceeded(InferenceError):
    """A fully bound, measured reading input overflow before any completion."""
    def __init__(self, body, proof):
        super().__init__("campus_reading_token_budget_exceeded")
        self.budget_evidence = json.loads(encoded({"request": body,
            "request_sha256": digest(body), "token_budget": proof}))


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
    if ollama_macos.enabled():
        return ollama_macos.model_identity(base)
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


def _system_ollama_service():
    """Read only the host system manager, with no caller-selected bus or host."""
    keys = ("Id", "LoadState", "ActiveState", "SubState", "User", "Group", "MainPID",
            "ControlGroup", "Delegate", "DynamicUser", "PrivateUsers")
    try:
        # A file bounds memory even if the local manager returns malformed output.
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(["/usr/bin/systemctl", "--system", "--no-pager",
                "--no-ask-password", "show", "ollama.service", "--property="+",".join(keys)],
                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.DEVNULL,
                timeout=3, check=False, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C",
                                            "SYSTEMD_PAGER": "cat", "SYSTEMD_COLORS": "0"})
            if result.returncode != 0 or output.tell() > 8192:
                raise ValueError("system manager output")
            output.seek(0)
            lines = output.read(8193).decode().splitlines()
        fields = {}
        for line in lines:
            key, value = line.split("=", 1)
            if key not in keys or key in fields:
                raise ValueError("system manager property")
            fields[key] = value
        if set(fields) != set(keys):
            raise ValueError("system manager properties missing")
        expected = {"Id": "ollama.service", "LoadState": "loaded", "ActiveState": "active",
            "SubState": "running", "User": "ollama", "Group": "ollama",
            "ControlGroup": "/system.slice/ollama.service", "Delegate": "no",
            "DynamicUser": "no", "PrivateUsers": "no"}
        if any(fields[key] != value for key, value in expected.items()):
            raise ValueError("system service identity")
        if not fields["MainPID"].isascii() or not fields["MainPID"].isdigit() or int(fields["MainPID"]) <= 1:
            raise ValueError("system service PID")
        return fields
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        raise InferenceError("campus_token_runner_unverified") from None


def _uid_map(path):
    rows = [tuple(int(part) for part in line.split()) for line in path.read_text().splitlines()]
    if not rows or any(len(row) != 3 or min(row) < 0 or row[2] == 0 for row in rows):
        raise ValueError("invalid UID map")
    return rows


def _namespace_runner_binding(process, expected_uid, uid_rows):
    """Prove service parentage when PrivateTmp's user namespace masks host UIDs.

    An overflow UID alone never establishes account identity. This deliberately
    supports only the observed single-user namespace and non-delegated host
    ollama service, not arbitrary user namespaces or service descendants.
    """
    try:
        caller = os.getuid()
        mapping = _uid_map(PROC/"self/uid_map")
        overflow = int((PROC/"sys/kernel/overflowuid").read_text().strip())
        if (caller <= 0 or caller == expected_uid or mapping != [(caller, caller, 1)]
                or overflow <= 0 or overflow in (caller, expected_uid)
                or len(uid_rows) != 1 or any(int(value) != overflow for value in uid_rows[0])):
            raise ValueError("namespace does not mask the host account")
        service = _system_ollama_service()
        parent = PROC/service["MainPID"]
        def snapshot(item):
            status = item.joinpath("status").read_text()
            credentials = re.findall(r"^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$",
                                     status, re.MULTILINE)
            ppid = re.findall(r"^PPid:\s+(\d+)\s*$", status, re.MULTILINE)
            fields = item.joinpath("stat").read_text().rsplit(")", 1)[1].split()
            cgroup = item.joinpath("cgroup").read_text().splitlines()
            target_map = _uid_map(item/"uid_map")
            if (len(credentials) != 1 or any(int(value) != overflow for value in credentials[0])
                    or len(ppid) != 1 or fields[1] != ppid[0]
                    or cgroup != ["0::"+service["ControlGroup"]]
                    or target_map != [(0, 4294967295, 4294967295)]
                    or not fields[19].isdigit()):
                raise ValueError("unbound service process")
            command = item.joinpath("cmdline").read_bytes()
            if (not command or (item == parent and
                    [part for part in command.split(b"\0") if part] != [b"/usr/local/bin/ollama", b"serve"])):
                raise ValueError("unverified service command")
            return {"pid": int(item.name), "ppid": int(ppid[0]),
                "starttime": fields[19], "cmdline_sha256": hashlib.sha256(command).hexdigest(),
                "uid_map": target_map, "cgroup": cgroup[0], "observed_uids": [overflow]*4}
        snapshots = [snapshot(process), snapshot(parent)]
        repeated = [snapshot(process), snapshot(parent)]
        if service != _system_ollama_service() or snapshots != repeated:
            raise ValueError("service or process identity changed during observation")
        if snapshots[0]["ppid"] != int(service["MainPID"]) or snapshots[1]["ppid"] != 1:
            raise ValueError("runner is not the direct system service child")
        return {"method": "system_service_parent_in_user_namespace", "caller_uid": caller,
            "self_uid_map": mapping, "overflow_uid": overflow, "observed_uids": [overflow]*4,
            "service": service, "runner_process": snapshots[0], "service_process": snapshots[1]}
    except (OSError, ValueError, IndexError, UnicodeError):
        raise InferenceError("campus_token_runner_unverified") from None


def _runner_identity(model):
    # The intake user cannot read another account's /proc/<pid>/exe. Bind the
    # fixed command path and credentials, or strict host service parentage when
    # the existing service user namespace masks host UIDs. No privilege changes.
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
            if len(uid_rows) == 1 and all(int(value) == expected_uid for value in uid_rows[0]):
                uid_binding = {"method": "direct_process_uid", "observed_uids": [expected_uid]*4}
            else:
                uid_binding = _namespace_runner_binding(process, expected_uid, uid_rows)
            port = int(option("--port"))
            context = int(option("-c"))
            if (option("--host") != "127.0.0.1" or not 1 <= port <= 65535
                    or context <= 0 or int(option("-np")) != 1):
                raise InferenceError("campus_token_runner_unverified")
            start = (process/"stat").read_text().rsplit(")", 1)[1].split()[19]
            command_sha = hashlib.sha256(raw).hexdigest()
            if uid_binding["method"] == "system_service_parent_in_user_namespace":
                bound = uid_binding["runner_process"]
                if (bound["pid"] != int(process.name) or bound["starttime"] != start
                        or bound["cmdline_sha256"] != command_sha):
                    raise InferenceError("campus_token_runner_unverified")
            matching.append({"pid": int(process.name), "starttime": start, "port": port,
                             "uid": expected_uid, "account": "ollama", "context": context,
                             "uid_binding": uid_binding, "cmdline_sha256": command_sha})
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
    if model.get("runtime") == ollama_macos.RUNTIME:
        return ollama_macos.runner_identity(model)
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


def _body(profile, system, user, schema, *, reading=False):
    if (profile.backend != "ollama" or profile.model != MODEL
            or profile.request_model not in ("", MODEL)
            or profile.url not in ("http://127.0.0.1:11434", "http://localhost:11434")
            or profile.context != CONTEXT or profile.max_output_tokens != OUTPUT
            or profile.max_parallel != 1 or profile.api_key_env
            or "text_json" not in profile.capabilities):
        raise InferenceError("campus_token_profile_unverified")
    if (not isinstance(system, str) or not system or not isinstance(user, str)
            or not user or not isinstance(schema, dict) or schema.get("type") != "object"):
        raise InferenceError("campus_token_scope_required")
    scope = json_object(user)
    stage = "native_campus_reading" if reading else "whole_campus_adjudication"
    if (scope.get("stage") != stage or reading
            and scope.get("reading_recipe") != "campus-packed-reading-v1"):
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


def _prepare(client, system, user, json_schema, *, reading=False):
    body = _body(client.profile, system, user, json_schema, reading=reading)
    base = client.profile.url
    model = _model_identity(base)
    rendered = _render(base, body, client.profile.timeout)
    if _model_identity(base) != model:
        raise InferenceError("campus_token_model_binding_changed")
    runner = _bound_runner(base, model)
    try:
        tokens = ollama_macos.tokenize(runner, rendered) if ollama_macos.enabled() else _call("http://127.0.0.1:"+str(runner["port"])+"/tokenize",
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
    if reading:
        proof.update(stage="native_campus_reading", reading_recipe="campus-packed-reading-v1")
    if len(tokens)+OUTPUT+RESERVE > CONTEXT:
        if reading:
            # Only this measured, fully bound pre-generation condition may
            # authorize a lossless split. Other errors carry no budget proof.
            raise ReadingBudgetExceeded(body, proof)
        raise InferenceError("campus_adjudication_token_budget_exceeded")
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
                if proof["model_binding"].get("runtime") == ollama_macos.RUNTIME:
                    if response.get("prompt_eval_count") != proof["input_tokens"]:
                        raise InferenceError("campus_token_render_incomplete")
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


def generate_reading(client, system, user, *, json_schema,
                     before_completion=None, before_dispatch=None):
    """Measure then durably dispatch one frozen native window, never truncate.

    Resource checks run before renderer scheduling and again before completion.
    The caller journals the bound request in before_dispatch; an uncertain HTTP
    outcome therefore cannot be silently regenerated by a later receive cycle.
    """
    try:
        with client._slots:
            try:
                if before_completion:
                    before_completion()
                body, proof = _prepare(client, system, user, json_schema, reading=True)
                if before_completion:
                    before_completion()
                revalidate(client, proof)
                if digest(body) != proof["request_sha256"]:
                    raise InferenceError("campus_token_request_changed")
            except InferenceError as error:
                if error.code in ("campus_token_runner_unavailable", "campus_token_runtime_changed"):
                    raise InferenceError("campus_token_runner_contention") from None
                raise
            if before_dispatch:
                # Copies keep the journal callback from changing measured input
                # or making a caller-supplied proof authoritative.
                before_dispatch(json.loads(encoded(body)), json.loads(encoded(proof)))
            if digest(body) != proof["request_sha256"]:
                raise InferenceError("campus_token_request_changed")
            response = _call(client.profile.url+"/api/chat", body, client.profile.timeout)
            try:
                revalidate(client, proof)
                client._verify_model(response.get("model"))
                if proof["model_binding"].get("runtime") == ollama_macos.RUNTIME:
                    if response.get("prompt_eval_count") != proof["input_tokens"]:
                        raise InferenceError("campus_token_render_incomplete")
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
                # Process identity includes tuples (UIDs/maps/stat fields). Return
                # the same JSON representation as the durable completion receipt.
                result["_model"]["token_budget"] = json.loads(encoded({**proof, "generation_binding": {
                    "model_binding_sha256": digest(proof["model_binding"]),
                    "request_sha256": proof["request_sha256"], "actual_model": response["model"],
                    "model_verified_before_and_after": True, "response_sha256": digest(response)}}))
                evidence = json.loads(encoded({"request": body,
                    "request_sha256": digest(body), "token_budget": proof,
                    "response": response, "response_sha256": digest(response)}))
                return result, evidence
            except (InferenceError, OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
                raise CompletionUnverified(error, body, proof, response) from None
    except InferenceError:
        raise
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise InferenceError("campus_token_runtime_unverified") from None
