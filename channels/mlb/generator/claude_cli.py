import json
import subprocess
import time
from typing import Optional

CLAUDE_BIN = "/opt/homebrew/bin/claude"

# The single generate-scripts call fetches several source URLs via WebFetch and
# writes a full script in one shot, which regularly ran past the old 600s limit
# A complete multi-video script can take several minutes. Give it real headroom
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
