import json
import os
import requests
import subprocess
import time
from typing import Optional

CLAUDE_BIN = "/opt/homebrew/bin/claude"

# The single generate-scripts call fetches several source URLs via WebFetch and
# writes a full script in one shot, which regularly ran past the old 600s limit
# (see the medical/science channel 2026-07-22/23 timeouts). Give it real headroom
# and retry once, since the work reliably completes when re-run manually.
DEFAULT_TIMEOUT = 1500
MAX_ATTEMPTS = 2
RETRY_BACKOFF = 15


class ClaudeCliError(RuntimeError):
    pass


class ClaudeCliTimeout(ClaudeCliError):
    pass


def run(
    prompt: str,
    json_schema: dict,
    allowed_tools: Optional[list] = None,
    model: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    attempts: int = MAX_ATTEMPTS,
) -> dict:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if os.getenv("LLM_PROVIDER", "").lower() == "gemini":
        if not gemini_key:
            raise ClaudeCliError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        selected = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{selected}:generateContent?key={gemini_key}",
            headers={"content-type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": "Return only valid JSON matching the schema. Never invent facts, figures, or quotes."}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "responseJsonSchema": json_schema},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return json.loads("".join(part.get("text", "") for part in parts))

    api_url = os.getenv("AI_API_URL")
    api_key = os.getenv("AI_API_KEY")
    if api_url and api_key:
        response = requests.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or os.getenv("AI_MODEL", "gpt-5-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_schema", "json_schema": {"name": "video_package", "strict": False, "schema": json_schema}},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(json_schema)]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    if model:
        cmd += ["--model", model]

    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            last_error = ClaudeCliTimeout(f"claude CLI timed out after {timeout}s (attempt {attempt}/{attempts})")
            print(f"[warn] {last_error}")
            if attempt < attempts:
                time.sleep(RETRY_BACKOFF)
            continue

        if proc.returncode != 0:
            last_error = ClaudeCliError(
                f"claude CLI exited {proc.returncode} (attempt {attempt}/{attempts}); "
                f"stdout={proc.stdout[:2000]!r}; stderr={proc.stderr[:2000]!r}"
            )
            print(f"[warn] {last_error}")
            if attempt < attempts:
                time.sleep(RETRY_BACKOFF)
            continue

        payload = json.loads(proc.stdout)
        if payload.get("is_error"):
            last_error = ClaudeCliError(f"claude CLI error: {payload.get('result')}")
            print(f"[warn] {last_error}")
            if attempt < attempts:
                time.sleep(RETRY_BACKOFF)
            continue

        return json.loads(payload["result"])

    raise last_error
