"""Same operations as the MCP tools, from the command line. Prints JSON. Standard library only.

    python cli.py find "<project idea>" [--limit N] [--allow-copyleft]
    python cli.py blueprint <owner/repo>
    python cli.py scaffold <owner/repo> "<project name>" "<idea>" [dir]
"""
import argparse
import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import core  # noqa: E402
from github import GitHubError  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="reuse-first")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find", help="search and rank GitHub repos for an idea")
    f.add_argument("query")
    f.add_argument("--limit", type=int, default=10)
    f.add_argument("--allow-copyleft", action="store_true")
    sub.add_parser("blueprint", help="extract a repo's architecture").add_argument("repo")
    s = sub.add_parser("scaffold", help="create a starter project shaped like a repo")
    s.add_argument("repo")
    s.add_argument("name")
    s.add_argument("idea")
    s.add_argument("dir", nargs="?", default=".")
    a = p.parse_args(argv)

    try:
        if a.cmd == "find":
            result = core.find(a.query, a.limit, a.allow_copyleft)
        elif a.cmd == "blueprint":
            result = core.blueprint(a.repo)
        else:
            result = core.scaffold_project(a.repo, a.name, a.idea, a.dir)
    except GitHubError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    except (urllib.error.URLError, TimeoutError):
        print(
            "error: could not reach GitHub (check your internet connection)",
            file=sys.stderr,
        )
        sys.exit(2)
    # ASCII-escaped JSON: a Windows console can't encode every character repos use
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
