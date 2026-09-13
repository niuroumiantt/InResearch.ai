"""Configured JSON inference, shared by research workers. Python standard library.

Task prompts and semantic validation belong to callers. This module owns only
configuration, transport, capability checks, bounded output and model provenance.
Configuration is frozen for each client; changing a file requires a new process.
"""

from inresearch.paths import project_root
from dataclasses import dataclass, replace
from functools import lru_cache
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess as subprocess
import sys
import tempfile
import threading
import urllib.parse
import urllib.request

DEFAULT_CONFIG = project_root() / "deploy/models.json"
MAX_RESPONSE = 4 * 1024 * 1024


class InferenceError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ModelProfile:
    backend: str
    url: str
    model: str
    context: int = 32768
    max_output_tokens: int = 4096
    timeout: int = 900
    max_parallel: int = 2
    capabilities: tuple = ("text_json",)
    request_model: str = ""
    api_key_env: str = ""
    revision: str = ""
    command: str = "claude"

    def __post_init__(self):
        if self.backend not in {"ollama", "gateway", "claude_cli"}:
            raise ValueError("unknown model backend")
        url = urllib.parse.urlsplit(self.url)
        if self.backend == "claude_cli":
            if self.url or self.request_model or self.api_key_env:
                raise ValueError("Claude CLI uses its own login, without HTTP route settings")
        elif (url.scheme not in {"http", "https"} or not url.hostname or url.username
                or url.password or url.query or url.fragment):
            raise ValueError("model URL must be an HTTP base URL without credentials or query")
        for value in (self.model, self.request_model, self.revision, self.api_key_env, self.command):
            if not isinstance(value, str) or any(ord(c) < 32 for c in value):
                raise ValueError("invalid model configuration string")
        if not self.model.strip():
            raise ValueError("model identity is required")
        if not self.command.strip():
            raise ValueError("CLI executable is required")
        for name in ("context", "max_output_tokens", "timeout", "max_parallel"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(name + " must be a positive integer")
        if self.max_output_tokens + 1024 >= self.context or self.max_parallel > 16:
            raise ValueError("invalid model context or concurrency budget")
        if (not isinstance(self.capabilities, (tuple, list))
                or not set(self.capabilities) <= {"text_json", "vision_json"}
                or not self.capabilities):
            raise ValueError("invalid model capabilities")
        if "vision_json" in self.capabilities and self.backend != "ollama":
            raise ValueError("vision_json currently requires the Ollama adapter")
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "url", self.url.rstrip("/"))

    @property
    def identity(self):
        # Endpoint, credentials, timeouts and concurrency are operational settings.
        # They may change without changing the identity of the reading recipe.
        return {"backend": self.backend, "model": self.model, "context": self.context,
                "max_output_tokens": self.max_output_tokens,
                "request_model": self.request_model or self.model, "revision": self.revision}


def load_profile(role="research_default", path=None):
    path = Path(path or os.environ.get("INRESEARCH_MODEL_CONFIG") or DEFAULT_CONFIG).expanduser()
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("unsupported model configuration schema")
    roles, profiles = value.get("roles"), value.get("profiles")
    if not isinstance(roles, dict) or not isinstance(profiles, dict):
        raise ValueError("model roles and profiles must be objects")
    name = roles.get(role)
    if name is None:
        raise InferenceError("model_role_not_configured:" + role)
    if not isinstance(name, str) or name not in profiles or not isinstance(profiles[name], dict):
        raise ValueError("model role references an unknown profile")
    return ModelProfile(**profiles[name])


@lru_cache(maxsize=32)
def _configured_client(path, role):
    return JsonModelClient(load_profile(role, path))


def configured_client(role="research_default"):
    """One frozen client per configuration path and role in this process."""
    path = str(Path(os.environ.get("INRESEARCH_MODEL_CONFIG") or DEFAULT_CONFIG).expanduser().resolve())
    return _configured_client(path, role)


def _reject_constant(value):
    raise ValueError("non-finite JSON number")


def json_object(text):
    if not isinstance(text, str):
        raise InferenceError("model_output_invalid")
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(text, parse_constant=_reject_constant)
    except (ValueError, TypeError):
        raise InferenceError("model_output_invalid") from None
    if not isinstance(value, dict):
        raise InferenceError("model_output_invalid")
    return value


class JsonModelClient:
    def __init__(self, profile):
        self.profile = profile
        self._slots = threading.BoundedSemaphore(profile.max_parallel)

    def generate(self, system, user, *, image_path=None, think=None):
        p = self.profile
        capability = "vision_json" if image_path is not None else "text_json"
        if capability not in p.capabilities:
            raise InferenceError("model_capability_missing:" + capability)
        # Conservative UTF-8 bound, shared with the reader. Never truncate input.
        if len((system + user).encode("utf-8")) > p.context - p.max_output_tokens - 1024:
            raise InferenceError("input_exceeds_context_budget")
        if p.backend == "claude_cli":
            return self._generate_cli(system, user)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        if image_path is not None:
            messages[-1]["images"] = [base64.b64encode(Path(image_path).read_bytes()).decode("ascii")]
        headers = {"Content-Type": "application/json"}
        key_env = p.api_key_env or ("DGX_API_KEY" if p.backend == "gateway" else "")
        if key_env:
            key = os.environ.get(key_env)
            if not key:
                raise InferenceError("model_key_not_configured")
            headers["Authorization"] = "Bearer " + key
        body = {"model": p.request_model or p.model, "messages": messages, "stream": False}
        if p.backend == "ollama":
            endpoint = "/api/chat"
            body.update(format="json", options={"num_ctx": p.context,
                        "num_predict": p.max_output_tokens, "temperature": 0})
            if think is not None:
                body["think"] = think
        else:
            endpoint = "/v1/chat/completions"
            body.update(temperature=0, max_tokens=p.max_output_tokens,
                        response_format={"type": "json_object"})
        req = urllib.request.Request(p.url + endpoint, data=json.dumps(body, ensure_ascii=False,
                                      allow_nan=False).encode("utf-8"), headers=headers)
        try:
            with self._slots, urllib.request.urlopen(req, timeout=p.timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise InferenceError("model_output_invalid")
            doc = json.loads(raw)
            actual = doc.get("model")
            self._verify_model(actual)
            if p.backend == "ollama":
                if doc.get("done_reason") == "length":
                    raise InferenceError("model_output_truncated")
                msg = doc["message"]
                content = msg.get("content") or msg.get("thinking")
            else:
                choice = doc["choices"][0]
                if choice.get("finish_reason") not in (None, "stop"):
                    raise InferenceError("model_output_incomplete")
                content = choice["message"]["content"]
            result = json_object(content)
            return self._provenance(result, actual, system, user)
        except InferenceError:
            raise
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
            # Neither response bodies nor credentials enter persisted error logs.
            raise InferenceError("model_failure") from None

    def _verify_model(self, actual):
        expected = self.profile.model
        if not isinstance(actual, str) or not (actual == expected or actual.endswith("/" + expected)):
            raise InferenceError("model_identity_unverified")

    def _provenance(self, result, actual, system, user):
        self._verify_model(actual)
        result["_model"] = {**self.profile.identity, "requested": self.profile.model, "actual": actual,
                            "prompt_sha256": hashlib.sha256(system.encode("utf-8")).hexdigest(),
                            "input_sha256": hashlib.sha256(user.encode("utf-8")).hexdigest()}
        if self.profile.backend == "claude_cli":
            result["_model"]["executor"] = "claude-code"
        return result

    def _generate_cli(self, system, user):
        """Treat the CLI as a bounded, tool-free inference process, not a writer."""
        p = self.profile
        command = [p.command, "-p", "--output-format", "stream-json", "--verbose", "--model", p.model,
                   "--safe-mode", "--tools", "", "--no-session-persistence",
                   "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--no-chrome",
                   "--system-prompt", system]
        env = {**os.environ, "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(p.max_output_tokens)}
        try:
            # Stdin carries document text. Spool output so a broken CLI cannot
            # allocate unbounded memory; no payload or stderr enters error logs.
            with self._slots, tempfile.TemporaryDirectory(prefix="inresearch-inference-") as directory:
                with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
                    process = subprocess.run(command, input=user, text=True, stdout=output, stderr=errors,
                                             cwd=directory, env=env, timeout=p.timeout, check=False)
                    output.seek(0)
                    raw = output.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise InferenceError("model_output_invalid")
            events = [json_object(line.decode("utf-8")) for line in raw.splitlines() if line.strip()]
            results = [event for event in events if event.get("type") == "result"]
            if len(results) != 1 or events[-1] is not results[0]:
                raise InferenceError("model_output_invalid")
            envelope = results[0]
            if process.returncode or envelope.get("is_error"):
                detail = str(envelope.get("result", "")).lower()
                code = ("model_cli_authentication_failed" if any(word in detail for word in
                        ("authenticate", "authentication", "not logged", "403", "401")) else "model_cli_failed")
                raise InferenceError(code)
            # Usage includes auxiliary CLI requests (e.g. Haiku classifiers).
            # Only actual assistant messages identify the model that read input.
            actual_models = {event.get("message", {}).get("model") for event in events
                             if event.get("type") == "assistant"}
            if len(actual_models) != 1:
                raise InferenceError("model_identity_unverified")
            actual = actual_models.pop()
            if envelope.get("stop_reason") not in (None, "end_turn", "stop_sequence"):
                raise InferenceError("model_output_incomplete")
            if envelope.get("structured_output") is not None:
                result = json_object(json.dumps(envelope["structured_output"], allow_nan=False))
            else:
                result = json_object(envelope.get("result"))
            return self._provenance(result, actual, system, user)
        except FileNotFoundError:
            raise InferenceError("model_cli_not_installed") from None
        except subprocess.TimeoutExpired:
            raise InferenceError("model_cli_timeout") from None
        except InferenceError:
            raise
        except (OSError, ValueError, TypeError, AttributeError):
            raise InferenceError("model_cli_failed") from None


def reader_profile(**overrides):
    """Compatibility boundary for deployed READER_* files and old CLI flags."""
    profile = load_profile()
    names = {"backend": str, "url": str, "model": str, "context": int,
             "max_output_tokens": int, "timeout": int, "request_model": str}
    changes = {}
    for name, convert in names.items():
        value = overrides.get(name)
        if value is None:
            value = os.environ.get("READER_" + name.upper())
        if value is not None:
            changes[name] = convert(value)
    # Older reader gateway deployments addressed the route 'brain'. New profile
    # files can select any route; compatibility applies only to the old env/CLI.
    if (changes.get("backend") == "gateway" and "request_model" not in changes
            and not os.environ.get("INRESEARCH_MODEL_CONFIG")):
        changes["request_model"] = "brain"
    return replace(profile, **changes)


def reading_identity(value):
    """Normalize v1 recipes so default-config upgrades do not invalidate work."""
    return {"backend": value["backend"], "model": value["model"], "context": value["context"],
            "max_output_tokens": value.get("max_output_tokens", 4096),
            "request_model": value.get("request_model", "brain" if value["backend"] == "gateway" else value["model"]),
            "revision": value.get("revision", "")}


def main():
    parser = argparse.ArgumentParser(description="Validate model configuration; optionally make one small real request.")
    parser.add_argument("--role", default="research_default")
    parser.add_argument("--config")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    try:
        profile = load_profile(args.role, args.config)
        result = {"role": args.role, "profile": profile.identity, "state": "configuration_valid"}
        if args.probe:
            value = JsonModelClient(profile).generate("Return one JSON object without markdown.",
                                                      'Return {"ready":true}.')
            if value.get("ready") is not True:
                raise InferenceError("model_output_invalid")
            result.update(state="probe_passed", actual=value["_model"]["actual"])
        print(json.dumps(result))
        return 0
    except InferenceError as exc:
        print(json.dumps({"error": exc.code}), file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError):
        print(json.dumps({"error": "model_configuration_invalid"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
