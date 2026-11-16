#!/usr/bin/env python3
"""Blocks the evaluator from reading the implementation. app/contracts.py stays readable: it is the public interface.
Exit code 2 denies the tool call and shows stderr to the agent."""
import json
import re
import sys

BLOCKED = re.compile(r"(^|[\s\"'/=])app(/|$|\s|[\"'])(?!contracts\.py)|\bapp/\*")
ALLOWED_RUN = re.compile(r"^\s*\S*(python3?\s+-m\s+)?pytest(\s+-q)?(\s+tests/\S+)?\s*$")


def main() -> int:
    tool_input = json.load(sys.stdin).get("tool_input", {})
    command = tool_input.get("command", "")
    if command and ALLOWED_RUN.match(command) and not re.search(r"[;&|]", command):
        return 0
    targets = [command, *(tool_input.get(k, "") for k in ("file_path", "path", "pattern", "glob"))]
    if any(BLOCKED.search(t) for t in targets if t):
        print("Blocked: the evaluator tests from the outside and may not read app/ (app/contracts.py is allowed).",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
