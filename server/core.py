"""The three operations behind the MCP tools, the CLI and the demo. Standard library only."""
import os
from pathlib import Path

from architecture import _slug, make_blueprint, scaffold, snapshot
from cache import Cache
from github import search_repos
from scoring import rank

cache = Cache(os.getenv("REUSE_FIRST_CACHE", str(Path.home() / ".reuse-first-cache.db")))

FIELDS = ("full_name", "url", "description", "stars", "pushed_at", "license",
          "license_note", "score", "confidence", "excluded", "language")
EXCLUDED_SHOWN = 3  # excluded repos listed after the eligible ones, best score first


def find(query: str, limit: int = 10, allow_copyleft: bool = False) -> list[dict]:
    repos = search_repos(query, cache, max(limit * 2, 10))
    ranked = rank(repos, query, allow_copyleft=allow_copyleft)
    # Excluded repos sort last; cutting them at `limit` would hide them, so the best few
    # always follow the eligible ones and the user can be told what was left out and why.
    shown = [r for r in ranked if not r["excluded"]][:limit] + \
            [r for r in ranked if r["excluded"]][:EXCLUDED_SHOWN]
    return [{k: r[k] for k in FIELDS} for r in shown]


def blueprint(full_name: str) -> dict:
    return make_blueprint(snapshot(full_name, cache))


def scaffold_project(full_name: str, project_name: str, idea: str, output_dir: str = ".") -> dict:
    bp = blueprint(full_name)
    out = Path(output_dir).expanduser().resolve()
    files = scaffold(bp, project_name, idea, out)
    return {"root": str(out / _slug(project_name)), "files": files, "build_plan": bp["build_plan"]}
