import io
import json
import sys
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import github  # noqa: E402
from cache import Cache  # noqa: E402
from github import GitHubError, search_repos  # noqa: E402
from scoring import rank, score_repo  # noqa: E402

NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


def repo(**kw):
    base = dict(full_name="a/b", url="u", description="pdf table extraction", stars=1000,
                forks=1, open_issues=10, pushed_at="2026-10-01T00:00:00Z", archived=False,
                license="MIT", topics=["pdf"], language="Python")
    return {**base, **kw}


def test_missing_data_is_unknown_not_zero():
    r = score_repo(repo(stars=None, pushed_at=None, open_issues=None), "pdf table", NOW)
    assert r["signals"]["recency"] is None and r["signals"]["adoption"] is None
    assert r["confidence"] < 0.5          # low confidence...
    assert r["score"] == 1.0              # ...but not punished with zeros


def test_license_gate_excludes_unlicensed_and_archived():
    assert score_repo(repo(license=None), "pdf", NOW)["excluded"]
    assert score_repo(repo(license="GPL-3.0"), "pdf", NOW)["excluded"]
    assert not score_repo(repo(license="GPL-3.0"), "pdf", NOW, allow_copyleft=True)["excluded"]
    assert "archived" in score_repo(repo(archived=True), "pdf", NOW)["excluded"]


def test_excluded_repos_rank_last():
    good = repo(full_name="good/x", stars=50)
    bad = repo(full_name="bad/x", stars=100000, license=None)
    assert [r["full_name"] for r in rank([bad, good], "pdf table")] == ["good/x", "bad/x"]


BODY = {"items": [{"full_name": "a/b", "html_url": "u", "stargazers_count": 5}]}


class FakeResp(io.BytesIO):
    status = 200
    headers = {"ETag": "abc"}


def fake_open(responses, seen):
    """Stands in for urllib's urlopen: replays `responses`, records request headers."""
    def _open(req, timeout):
        seen.append(dict(req.header_items()))
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    return _open


def test_search_is_cached(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(github, "_open", fake_open([FakeResp(json.dumps(BODY).encode())], seen))
    cache = Cache(str(tmp_path / "c.db"))
    first, second = search_repos("pdf", cache), search_repos("pdf", cache)
    assert first == second and len(seen) == 1
    assert first[0]["license"] is None  # unknown stays None


def test_stale_cache_revalidates_with_etag(tmp_path, monkeypatch):
    seen = []
    not_modified = urllib.error.HTTPError("u", 304, "Not Modified", {"ETag": "abc"}, None)
    monkeypatch.setattr(github, "_open", fake_open(
        [FakeResp(json.dumps(BODY).encode()), not_modified], seen))
    cache = Cache(str(tmp_path / "c.db"), ttl=0)  # every entry is stale at once
    first, second = search_repos("pdf", cache), search_repos("pdf", cache)
    assert second == first and len(seen) == 2
    assert seen[1].get("If-none-match") == "abc"  # urllib capitalizes header names


def test_search_error_raises(tmp_path, monkeypatch):
    limited = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
    monkeypatch.setattr(github, "_open", fake_open([limited], []))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(GitHubError) as e:
        search_repos("pdf", Cache(str(tmp_path / "c.db")))
    assert e.value.status == 403 and "set GITHUB_TOKEN" in str(e.value)


def test_rate_limit_message_with_token_says_wait(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    assert "wait a minute" in str(GitHubError(429, "/search/repositories"))


def test_rate_limited_snapshot_raises_and_is_not_cached(tmp_path, monkeypatch):
    from architecture import snapshot
    limited = lambda: urllib.error.HTTPError("u", 403, "Forbidden", {}, None)  # noqa: E731
    repo_body = json.dumps({"default_branch": "main", "html_url": "h"}).encode()
    monkeypatch.setattr(github, "_open", fake_open([FakeResp(repo_body), limited(), limited()], []))
    cache = Cache(str(tmp_path / "c.db"))
    with pytest.raises(GitHubError) as e:
        snapshot("o/r", cache)  # repo details load, then the file list hits the limit
    assert e.value.status == 403
    assert cache.get("snap:o/r", allow_stale=True) == (None, None)
