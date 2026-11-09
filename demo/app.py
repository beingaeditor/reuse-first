"""Web demo of the reuse-first flow, using the same code as the MCP tools.

    pip install -r server/requirements.txt fastapi uvicorn
    python demo/app.py      # http://localhost:8765
    HOST=0.0.0.0 PORT=10000 python demo/app.py   # on a hosting service
"""
import io
import os
import secrets
import sys
import tempfile
import zipfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from architecture import _slug, scaffold  # noqa: E402
from github import GitHubError  # noqa: E402
from server import find, get_blueprint  # noqa: E402

app = FastAPI(title="reuse-first demo")
_zips: dict[str, tuple[str, bytes]] = {}


def _gh_error(e: GitHubError):
    raise HTTPException(502, str(e))  # a new GITHUB_TOKEN needs a demo restart to take effect


@app.get("/")
def index():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/api/find")
async def api_find(q: str, copyleft: bool = False):
    if len(q.strip()) < 3:
        raise HTTPException(400, "Describe the project in a few words.")
    try:
        return await find(q, 10, copyleft)
    except GitHubError as e:
        _gh_error(e)


@app.get("/api/blueprint")
async def api_blueprint(repo: str):
    try:
        return await get_blueprint(repo)
    except GitHubError as e:
        _gh_error(e)


class ScaffoldReq(BaseModel):
    repo: str
    name: str
    idea: str


@app.post("/api/scaffold")
async def api_scaffold(req: ScaffoldReq):
    try:
        bp = await get_blueprint(req.repo)
    except GitHubError as e:
        _gh_error(e)
    with tempfile.TemporaryDirectory() as tmp:
        name = req.name or "my-project"
        files = scaffold(bp, name, req.idea, Path(tmp))
        root = Path(tmp) / _slug(name)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.write(root / f, f"{root.name}/{f}")
        arch = (root / "ARCHITECTURE.md").read_text(encoding="utf-8")
    token = secrets.token_urlsafe(8)
    _zips[token] = (root.name, buf.getvalue())
    return {"files": files, "architecture_md": arch, "download": f"/api/download/{token}"}


@app.get("/api/download/{token}")
def api_download(token: str):
    if token not in _zips:
        raise HTTPException(404, "Expired. Generate again.")
    name, data = _zips[token]
    return StreamingResponse(io.BytesIO(data), media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})


if __name__ == "__main__":
    # hosting services set HOST=0.0.0.0 and PORT; locally it stays private on 127.0.0.1:8765
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8765")))
