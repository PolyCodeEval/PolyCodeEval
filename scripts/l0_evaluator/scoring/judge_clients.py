"""Judge client helpers for L0 scoring."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


class JudgeError(RuntimeError):
    """Base error for judge failures."""


class WebSearchUnavailable(JudgeError):
    """Raised when provider web search is unavailable."""


MAX_JUDGE_RETRIES = 3


def _load_env() -> None:
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key and key not in os.environ:
            os.environ[key.strip()] = value.strip()


_load_env()


def resolve_judge_provider_model(provider: str | None, model: str | None) -> tuple[str, str]:
    provider = provider or os.environ.get("JUDGE_PROVIDER") or os.environ.get("LLM_PROVIDER") or "openai"
    if model:
        return provider, model
    if provider == "openai":
        model = os.environ.get("JUDGE_OPENAI_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    else:
        model = os.environ.get("JUDGE_ANTHROPIC_MODEL") or os.environ.get("ANTHROPIC_MODEL") or "claude-3-5-sonnet-latest"
    return provider, model


def _is_yunwu_openai_compatible() -> bool:
    base_url = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
    return "yunwu.ai" in base_url


def _yunwu_google_search_model() -> str:
    return os.environ.get("YUNWU_GOOGLE_SEARCH_MODEL", "gemini-2.5-flash")


def _extract_text(response) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text.strip()
    if hasattr(response, "choices"):
        return (response.choices[0].message.content or "").strip()
    if hasattr(response, "content"):
        chunks = []
        for item in response.content:
            maybe_text = getattr(item, "text", None)
            if maybe_text:
                chunks.append(maybe_text)
        return "\n".join(chunks).strip()
    return str(response).strip()


def _retry_call(fn, *args, **kwargs):
    last_exc = None
    for attempt in range(MAX_JUDGE_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt + 1 < MAX_JUDGE_RETRIES:
                time.sleep(1.0 * (attempt + 1))
    if isinstance(last_exc, Exception):
        raise last_exc
    raise JudgeError("Judge call failed without an exception.")


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = next((part for part in parts if "{" in part and "}" in part), text)
        text = text.replace("json", "", 1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_escape_control_chars_in_json(text))


def _escape_control_chars_in_json(text: str) -> str:
    """Escape raw control chars inside JSON strings for tolerant parsing."""
    out: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == "\\":
                out.append(ch)
                escaped = True
                continue
            if ch == '"':
                out.append(ch)
                in_string = False
                continue
            code = ord(ch)
            if code < 0x20:
                mapping = {
                    "\b": "\\b",
                    "\f": "\\f",
                    "\n": "\\n",
                    "\r": "\\r",
                    "\t": "\\t",
                }
                out.append(mapping.get(ch, f"\\u{code:04x}"))
                continue
            out.append(ch)
            continue

        out.append(ch)
        if ch == '"':
            in_string = True
            escaped = False
    return "".join(out)


def _extract_gemini_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        texts = [part.get("text", "") for part in parts if part.get("text")]
        if texts:
            return "\n".join(texts).strip()
    return ""


def _run_yunwu_google_search(system_prompt: str, user_prompt: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise WebSearchUnavailable("OPENAI_API_KEY is not set for Yunwu Gemini web search.")
    model = _yunwu_google_search_model()
    url = f"https://yunwu.ai/v1beta/models/{model}:generateContent"
    body = {
        "system_instruction": {
            "parts": [{"text": system_prompt}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "tools": [{"googleSearch": {}}],
        "generationConfig": {"temperature": 0},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        raise WebSearchUnavailable(str(exc)) from exc

    text = _extract_gemini_text(payload)
    if not text:
        raise WebSearchUnavailable("Yunwu Gemini search returned no text content.")
    return extract_json(text)


def run_judge(provider: str, model: str, system_prompt: str, user_prompt: str) -> dict:
    def _call() -> dict:
        if provider == "openai":
            from openai import OpenAI

            client = OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url=os.environ.get("OPENAI_BASE_URL") or None,
            )
            resp = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return extract_json(_extract_text(resp))

        if provider == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY") or None)
            msg = client.messages.create(
                model=model,
                max_tokens=4000,
                temperature=0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return extract_json(_extract_text(msg))

        raise JudgeError(f"Unsupported judge provider: {provider}")

    try:
        return _retry_call(_call)
    except Exception as exc:  # noqa: BLE001
        raise JudgeError(str(exc)) from exc


def run_web_search_judge(provider: str, model: str, system_prompt: str, user_prompt: str) -> dict:
    if provider == "openai":
        if _is_yunwu_openai_compatible():
            try:
                return _retry_call(_run_yunwu_google_search, system_prompt, user_prompt)
            except Exception as exc:  # noqa: BLE001
                raise WebSearchUnavailable(str(exc)) from exc
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url=os.environ.get("OPENAI_BASE_URL") or None,
            )
            def _call_tool(tool_type: str) -> dict:
                resp = client.responses.create(
                    model=model,
                    temperature=0,
                    tools=[{"type": tool_type}],
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return extract_json(_extract_text(resp))

            last_exc = None
            for tool_type in ("web_search_preview", "web_search"):
                try:
                    return _retry_call(_call_tool, tool_type)
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
            raise last_exc if last_exc is not None else RuntimeError("OpenAI web search unavailable")
        except Exception as exc:  # noqa: BLE001
            raise WebSearchUnavailable(str(exc)) from exc

    if provider == "anthropic":
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY") or None)
            def _call() -> dict:
                msg = client.messages.create(
                    model=model,
                    max_tokens=4000,
                    temperature=0,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
                )
                return extract_json(_extract_text(msg))
            return _retry_call(_call)
        except Exception as exc:  # noqa: BLE001
            raise WebSearchUnavailable(str(exc)) from exc

    raise WebSearchUnavailable(f"Unsupported judge provider: {provider}")
