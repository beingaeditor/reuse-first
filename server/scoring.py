"""Confidence-aware scoring. Missing data is *unknown*, never zero.

score      = weighted mean over signals that are known (0..1)
confidence = share of total weight that was actually observed (0..1)
Hard gates (license, archived) exclude a repo regardless of score.
"""
from datetime import datetime, timezone
from math import log10

PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense", "0BSD"}
WEAK_COPYLEFT = {"MPL-2.0", "LGPL-3.0", "LGPL-2.1", "EPL-2.0"}
STRONG_COPYLEFT = {"GPL-2.0", "GPL-3.0", "AGPL-3.0"}
WEIGHTS = {"recency": 0.35, "adoption": 0.25, "issue_load": 0.15, "fit": 0.25}


def _days_since(iso: str | None, now: datetime) -> float | None:
    if not iso:
        return None
    return (now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days


def license_gate(spdx: str | None, allow_copyleft: bool = False) -> tuple[bool, str]:
    if spdx in PERMISSIVE:
        return True, "permissive"
    if spdx in WEAK_COPYLEFT:
        return allow_copyleft, "weak copyleft"
    if spdx in (None, "NOASSERTION"):
        return False, "no detectable license (all rights reserved by default)"
    if spdx in STRONG_COPYLEFT:
        return allow_copyleft, f"strong copyleft ({spdx}): derived work must use the same license"
    return allow_copyleft, f"unreviewed license {spdx}: check its terms"


def keyword_fit(repo: dict, query: str) -> float | None:
    words = {w.lower() for w in query.split() if len(w) > 2}
    if not words:
        return None
    text = " ".join(
        [repo.get("description") or "", " ".join(repo.get("topics") or []), repo["full_name"]]
    ).lower()
    return sum(w in text for w in words) / len(words)


def score_repo(repo: dict, query: str, now: datetime | None = None,
               allow_copyleft: bool = False) -> dict:
    now = now or datetime.now(timezone.utc)
    signals: dict[str, float | None] = {}

    age = _days_since(repo.get("pushed_at"), now)
    signals["recency"] = None if age is None else max(0.0, 1 - age / 730)  # 0 at 2 years idle

    stars = repo.get("stars")
    signals["adoption"] = None if stars is None else min(1.0, log10(stars + 1) / 4)  # 10k stars = 1

    issues, stars_ = repo.get("open_issues"), repo.get("stars")
    signals["issue_load"] = (
        None if issues is None or stars_ is None else 1 - min(1.0, issues / (stars_ + 50))
    )
    signals["fit"] = keyword_fit(repo, query)

    known = {k: v for k, v in signals.items() if v is not None}
    known_w = sum(WEIGHTS[k] for k in known)
    score = sum(WEIGHTS[k] * v for k, v in known.items()) / known_w if known_w else None
    confidence = known_w / sum(WEIGHTS.values())

    ok, lic_note = license_gate(repo.get("license"), allow_copyleft)
    excluded = []
    if not ok:
        excluded.append(f"license: {lic_note}")
    if repo.get("archived"):
        excluded.append("archived")

    return {
        **repo,
        "score": None if score is None else round(score, 3),
        "confidence": round(confidence, 2),
        "signals": signals,
        "license_note": lic_note,
        "excluded": excluded,
    }


def rank(repos: list[dict], query: str, **kw) -> list[dict]:
    scored = [score_repo(r, query, **kw) for r in repos]
    # eligible first, then by score; unknown-score sinks but is not treated as 0 elsewhere
    return sorted(
        scored, key=lambda r: (bool(r["excluded"]), -(r["score"] if r["score"] is not None else -1))
    )
