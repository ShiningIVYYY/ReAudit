"""OpenAI-compatible HTTP adapter with exact per-call usage and no retries."""
import os
import uuid
import httpx
from .logging import canonical, digest, monotonic


class ExecutionFailure(Exception):
    def __init__(self, failure_type, detail):
        super().__init__(detail)
        self.failure_type = failure_type


class OpenAIAdapter:
    def __init__(self, config, journal, seed, transport=None):
        self.config, self.journal, self.seed = config, journal, seed
        endpoint = config["endpoint"]
        headers = {}
        key = os.environ.get(endpoint["api_key_env"])
        if key:
            headers["Authorization"] = f"Bearer {key}"
        self.client = httpx.Client(
            base_url=endpoint["base_url"].rstrip("/") + "/",
            headers=headers, timeout=config["agent"]["request_timeout_seconds"],
            transport=transport, trust_env=False)

    def close(self):
        self.client.close()

    def complete(self, messages):
        call_id = uuid.uuid4().hex
        body = {"model": self.config["model"]["model_id"], "messages": messages,
                "seed": self.seed, **self.config["decoding"],
                **self.config["endpoint"]["request_extras"]}
        self.journal.append("call_start", call_id=call_id, request=body,
                            request_hash=digest(canonical(body)))
        started = monotonic()
        usage = None
        try:
            response = self.client.post("chat/completions", json=body)
            self.journal.append("http_response", call_id=call_id,
                                http_status=response.status_code, body=response.text)
            try:
                data = response.json()
            except ValueError as error:
                kind = "service_error" if response.status_code >= 400 else "parse_error"
                raise ExecutionFailure(kind, "Service returned non-JSON content.") from error
            if response.status_code >= 400:
                detail = canonical(data)
                lower = detail.lower()
                overflow = any(s in lower for s in (
                    "maximum context length", "context length", "context_length_exceeded",
                    "max_model_len", "too many tokens", "context window"))
                self.journal.append("service_response", call_id=call_id,
                                    http_status=response.status_code, body=data)
                raise ExecutionFailure("context_overflow" if overflow else "service_error",
                                       f"HTTP {response.status_code}: {detail}")
            try:
                usage = data.get("usage")
                choice = data["choices"][0]
                content = choice["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Missing text completion")
                if (not usage or not isinstance(usage.get("prompt_tokens"), int)
                        or not isinstance(usage.get("completion_tokens"), int)):
                    raise ValueError("Response missing exact token usage")
            except (KeyError, IndexError, TypeError, ValueError) as error:
                raise ExecutionFailure("parse_error", str(error)) from error
            self.journal.append(
                "call_end", call_id=call_id, status="ok", response=data,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                latency_seconds=monotonic() - started)
            return content
        except (httpx.TimeoutException, httpx.TransportError, ExecutionFailure) as error:
            kind = (error.failure_type if isinstance(error, ExecutionFailure)
                    else "timeout" if isinstance(error, httpx.TimeoutException)
                    else "service_error")
            detail = str(error)
            key = os.environ.get(self.config["endpoint"]["api_key_env"], "")
            if key:
                detail = detail.replace(key, "[REDACTED]")
            self.journal.append(
                "call_end", call_id=call_id, status="error", failure_type=kind,
                detail=detail, latency_seconds=monotonic() - started,
                prompt_tokens=usage.get("prompt_tokens") if isinstance(usage, dict) else None,
                completion_tokens=usage.get("completion_tokens") if isinstance(usage, dict) else None)
            raise ExecutionFailure(kind, detail) from error
