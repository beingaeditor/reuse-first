# Changelog

## Unreleased

Fixes:

- A blueprint fetched while GitHub's rate limit ran out is no longer cached for 6 hours with no files; you get the rate-limit message instead.
- Scaffolding refuses a project folder that already exists and is not empty, instead of overwriting your files.
- `server.py --http` listens on 127.0.0.1 unless `HOST` is set, and turns off `scaffold_project`, so other machines can't write files on yours.
- Excluded repos (no or copyleft license, archived) are no longer cut off by the result limit: the best 3 follow the eligible ones with their reason, so the skill can say when a better fit was left out.
- GPL and AGPL are labelled "strong copyleft" instead of "restrictive or unreviewed license".
- The skill and tool description say to search with 2-4 words, and no longer ask Claude to weigh `confidence`, which is almost always 1.0.

## v0.1.0 (2026-11-10)

First release.

- Claude Code plugin: MCP server with `find_repos`, `blueprint` and `scaffold_project`, plus a skill that runs search, compare, scaffold and build.
- Ranking by recency, stars, open-issue load and keyword fit. Missing data counts as unknown, not zero. Unlicensed and archived repos are excluded; copyleft only when allowed.
- Blueprints: languages, frameworks, layers, entrypoints, dependencies and a build plan. Scaffolds mirror the layout and write `ARCHITECTURE.md` and `ATTRIBUTIONS.md`. No code is copied.
- Command line with no install: `python server/cli.py find | blueprint | scaffold`, standard library only.
- GitHub errors are one readable line (rate limit, bad token, not found); the CLI exits with code 2.
- Web demo (`demo/app.py`).
