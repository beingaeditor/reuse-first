import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import core  # noqa: E402
import server  # noqa: E402


def test_scaffold_is_disabled_over_http(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(core, "scaffold_project", lambda *a: called.append(a))
    monkeypatch.setattr(server, "REMOTE", True)
    with pytest.raises(ValueError, match="disabled in HTTP mode"):
        asyncio.run(server.scaffold_project("o/r", "App", "idea", str(tmp_path)))
    assert called == []
    monkeypatch.setattr(server, "REMOTE", False)
    asyncio.run(server.scaffold_project("o/r", "App", "idea", str(tmp_path)))
    assert len(called) == 1
