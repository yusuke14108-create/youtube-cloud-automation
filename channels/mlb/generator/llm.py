"""Structured text generation usable on macOS or a headless Linux VM."""
import json
import os
import re

import requests

from generator.claude_cli import run as run_claude_cli


def _extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    return json.loads(text)


def _run_anthropic(prompt, schema, model=None):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model or os.environ["ANTHROPIC_MODEL"],
            "max_tokens": 12000,
            "temperature": 0.2,
            "system": "Return only valid JSON matching the supplied schema. Never add facts not present in the input.",
            "messages": [{"role": "user", "content": f"JSON schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n{prompt}"}],
        },
        timeout=900,
    )
    response.raise_for_status()
    blocks = response.json().get("content", [])
    return _extract_json("".join(b.get("text", "") for b in blocks if b.get("type") == "text"))


def _run_gemini(prompt, schema, model=None):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
    selected = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": "Return only valid JSON. Never add facts, figures, or quotes absent from the input."}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "responseJsonSchema": schema},
    }
    response = requests.post(
        url,
        headers={"content-type": "application/json"},
        json=payload,
        timeout=900,
    )
    if response.status_code == 400:
        # Some Gemini model revisions reject otherwise-valid JSON Schema
        # keywords. Preserve JSON mode and put the schema in the prompt rather
        # than dropping the generation altogether.
        fallback = dict(payload)
        fallback["contents"] = [{"role": "user", "parts": [{"text": f"JSON schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n{prompt}"}]}]
        fallback["generationConfig"] = {"temperature": 0.2, "responseMimeType": "application/json"}
        response = requests.post(url, headers={"content-type": "application/json"}, json=fallback, timeout=900)
    response.raise_for_status()
    parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return _extract_json("".join(part.get("text", "") for part in parts))


def run(prompt, schema):
    provider = os.getenv("LLM_PROVIDER", "claude_cli")
    if provider == "anthropic":
        return _run_anthropic(prompt, schema)
    if provider == "gemini":
        return _run_gemini(prompt, schema)
    if provider == "claude_cli":
        return run_claude_cli(prompt, schema, allowed_tools=[])
    raise ValueError(f"unsupported LLM_PROVIDER: {provider}")
