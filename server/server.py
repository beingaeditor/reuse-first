"""MCP server: find existing GitHub codebases, extract their architecture, and
scaffold a new project shaped like the best one.

    python server.py            # stdio (Claude Code / Claude Desktop)
    python server.py --http     # streamable HTTP at 127.0.0.1:8000/mcp (ChatGPT connectors)
    HOST=0.0.0.0 PORT=8000 python server.py --http   # on a hosting service
"""
import asyncio
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent))
import core  # noqa: E402

mcp = FastMCP("reuse-first")
REMOTE = False  # set by --http: callers are on another machine


# GitHub calls block, so they run in a worker thread to keep the server responsive.
async def find(query: str, limit: int = 10, allow_copyleft: bool = False) -> list[dict]:
    return await asyncio.to_thread(core.find, query, limit, allow_copyleft)


async def get_blueprint(full_name: str) -> dict:
    return await asyncio.to_thread(core.blueprint, full_name)


@mcp.tool()
async def find_repos(query: str, limit: int = 10, allow_copyleft: bool = False) -> list[dict]:
    """Search GitHub for existing projects matching a description and rank them by
    health, adoption and fit. Repos with no/unsuitable license or archived are marked
    in `excluded` and listed last. `score` is 0..1; `confidence` is how much data backed it."""
    return await find(query, limit, allow_copyleft)


@mcp.tool()
async def blueprint(full_name: str) -> dict:
    """Extract a reusable architecture blueprint from a repo ('owner/repo'): stack,
    layers (api/domain/services/data/ui/cli/tests/infra), entrypoints, key dependencies,
    a build plan, and a README excerpt. Use it to design the user's project."""
    return await get_blueprint(full_name)


@mcp.tool()
async def scaffold_project(full_name: str, project_name: str, idea: str,
                           output_dir: str = ".") -> dict:
    """Create a starter project in `output_dir` shaped like `full_name`'s architecture:
    layer folders, a dependency manifest, ARCHITECTURE.md with the build plan, and
    ATTRIBUTIONS.md. Copies no source code. Then implement features layer by layer.
    Not available over HTTP: use `blueprint` and create the files on the user's side."""
    if REMOTE:  # it would write files on this server, not on the caller's computer
        raise ValueError("scaffold_project is disabled in HTTP mode: it would write files on the "
                         "server. Use blueprint and create the files on your side.")
    return await asyncio.to_thread(core.scaffold_project, full_name, project_name, idea, output_dir)


if __name__ == "__main__":
    if "--http" in sys.argv:
        REMOTE = True
        # private to this machine unless HOST=0.0.0.0 (hosting); ngrok works with 127.0.0.1
        mcp.settings.host = os.getenv("HOST", "127.0.0.1")
        mcp.settings.port = int(os.getenv("PORT", "8000"))
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
