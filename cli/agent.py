#!/usr/bin/env python3
"""
workflow CLI — entry point for qa-payment (qa-payment-agent + /qa-payment skill).
Handles Jira, GitLab and pay-hook commands.

Usage:
    workflow <command> [args]
    workflow help
"""

import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

_WORKFLOW_ROOT = Path(__file__).resolve().parent.parent
if str(_WORKFLOW_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKFLOW_ROOT))

from modules.gitlab.cli import run_command as gitlab_run, _get_client as get_gitlab_client  # noqa: E402
from modules.jira.cli import run_command as jira_run  # noqa: E402
from modules.payhook.cli import run_command as payhook_run  # noqa: E402

HELP = """
  Jira:
    jira-task <KEY>                       — task details
    jira-comments <KEY>                   — ALL comments, full text
    jira-attachments <KEY>                — list attachments
    jira-download <KEY> [--name=<file>|--id=<id>|--all]  — download attachment(s)
    jira-dev-status <KEY>                 — MRs linked to the task (Development panel)
    jira-search "<jql>"                   — search issues
    jira-comment <KEY> "<text>" [--from-file=<path>] [--dry-run]   — post comment (JIRA_WRITE_ENABLED)
    jira-attach <KEY> <file> [--dry-run]  — attach a file (JIRA_WRITE_ENABLED)

  GitLab:
    mrs <project> [--state=all|opened|merged]  — list MRs
    mr <project> <id>                        — MR details
    mr-changes <project> <id>               — changed files
    mr-diff <project> <id> [--file=<path>]  — diff
    mr-notes <project> <id>                 — MR comments
    file <project> <path> [--ref=<branch|sha>] [--list]  — file (or dir listing) at a ref
    find <project> <KEY>                    — MRs + branches by task key (empty Development panel)
    code-search <project> <term> [--ref=] [--limit=N]  — code search in a repo

  Pay-hook (prints a signed synthetic webhook curl, never sends; non-prod hosts only):
    pay-hook <provider> deposit|withdrawal --status=<s> --request-id=<id> --payment-id=<id> --amount=<minor>
             [--initial=<minor>] [--currency=UZS] [--ref=<branch|sha>] [--host=<url>] [--bad-sig]
    pay-hook-providers                    — list adapters

  help                                    — this message
"""


def run_command(parts: list):
    cmd = parts[0].lower() if parts else ""

    if gitlab_run(cmd, parts, jira_client=None):
        return
    if jira_run(cmd, parts):
        return
    if payhook_run(cmd, parts):
        return

    if cmd == "task-branch":
        if len(parts) < 2:
            print("  Usage: task-branch <KEY>")
        else:
            key = parts[1].upper()
            print(f"feature/{key.lower()}-description")
    elif cmd in ("help", "?", "h"):
        print(HELP)
    elif cmd in ("exit", "quit", "q"):
        sys.exit(0)
    else:
        print(f"  Unknown command: '{cmd}'. Type 'help'.")


def interactive():
    print("\n  workflow CLI (qa-payment)")
    print("  Type 'help' for commands.\n")
    while True:
        try:
            line = input("workflow> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        run_command(line.split())


def main(argv: list = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if not args:
        interactive()
        return 0
    try:
        run_command(args)
        return 0
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
