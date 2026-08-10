"""Structured LLM access selected with MEDICAL_NEWS_LLM_PROVIDER.

Providers: claude-cli (legacy), openai, anthropic, gemini. API keys are read
only from environment variables and are never persisted by this module.
"""
import json
import os
import re
import time
from typing import Optional

import requests

from generator.config import LLM_PROVIDER


class LlmError(RuntimeError):
    pass


def _post(url, headers, payload, timeout):
    last = None
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last = exc
            if attempt < 2:
                time.sleep(2 ** attempt * 5)
    raise LlmError(f"LLM API request failed after 3 attempts: {last}")


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise LlmError("model response did not contain a JSON object")
        return json.loads(match.group(0))


def _openai(prompt, schema, model, timeout):
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise LlmError("OPENAI_API_KEY is not set")
    payload = {
        "model": model or os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        "input": prompt,
        "text": {"format": {"type": "json_schema", "name": "result", "strict": False, "schema": schema}},
    }
    data = _post("https://api.openai.com/v1/responses", {"Authorization": f"Bearer {key}"}, payload, timeout)
    if "output_text" in data:
        return _extract_json(data["output_text"])
    texts = [c.get("text", "") for o in data.get("output", []) for c in o.get("content", []) if c.get("type") == "output_text"]
    return _extract_json("".join(texts))


def _anthropic(prompt, schema, model, timeout):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise LlmError("ANTHROPIC_API_KEY is not set")
    tool = {"name": "submit_result", "description": "Return the requested structured result", "input_schema": schema}
    payload = {
        "model": model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        "max_tokens": int(os.getenv("ANTHROPIC_MAX_TOKENS", "16000")),
        "messages": [{"role": "user", "content": prompt}],
        "tools": [tool], "tool_choice": {"type": "tool", "name": "submit_result"},
    }
    data = _post(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        payload, timeout,
    )
    block = next((x for x in data.get("content", []) if x.get("type") == "tool_use"), None)
    if not block:
        raise LlmError("Anthropic response did not call submit_result")
    return block["input"]


def _gemini(prompt, schema, model, timeout):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise LlmError("GEMINI_API_KEY is not set")
    selected = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    payload = {
        "systemInstruction": {"parts": [{"text": (
            "Return only JSON matching the response schema. Use only facts "
            "present in the supplied sources; never invent figures or quotes."
        )}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
        },
    }
    data = _post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{selected}:generateContent?key={key}",
        {"content-type": "application/json"}, payload, timeout,
    )
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError("Gemini response did not contain structured text") from exc
    return _extract_json(text)


def run(prompt: str, json_schema: dict, allowed_tools: Optional[list] = None,
        model: Optional[str] = None, timeout: int = 1500, attempts: int = 2) -> dict:
    if LLM_PROVIDER == "claude-cli":
        from generator.claude_cli import run as cli_run
        return cli_run(prompt, json_schema, allowed_tools=allowed_tools, model=model, timeout=timeout, attempts=attempts)
    if LLM_PROVIDER == "openai":
        return _openai(prompt, json_schema, model, timeout)
    if LLM_PROVIDER == "anthropic":
        return _anthropic(prompt, json_schema, model, timeout)
    if LLM_PROVIDER == "gemini":
        return _gemini(prompt, json_schema, model, timeout)
    raise LlmError(f"unknown MEDICAL_NEWS_LLM_PROVIDER: {LLM_PROVIDER}")
