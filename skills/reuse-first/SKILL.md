---
name: reuse-first
description: Use before building any new project or major feature. Finds existing, well-maintained, properly licensed GitHub codebases that solve the same problem, studies their architecture, and builds the user's project on that proven structure instead of from scratch.
---

# Reuse first

Before writing code for a new project, look for prior art.

## Workflow

1. **Pin down the need.** From the user's description, write a one-line problem statement and 3–5 must-have capabilities. Ask at most one question if the goal is unclear.
2. **Discover.** Call `find_repos` 2–3 times with different wordings of 2–4 words each, the way a repo would describe itself: "bookmark manager", "read later app". GitHub requires every word to match, so long phrases return tiny repos or nothing. Merge results.
3. **Shortlist 3–5.** Prefer high `score` and empty `excluded`. (`confidence` is almost always 1.0 here; below 1 means GitHub lacked some data.) Never recommend an excluded repo as a base to copy (no license = all rights reserved). The excluded repos at the end of `find_repos`'s list are there so you can mention when one fits better than your shortlist, and why. A copyleft license may still suit a team that only runs the software internally; it can be included with `allow_copyleft` (not legal advice).
4. **Study architecture.** Call `blueprint` on the top 2–3. Summarise for each: stack, layers, entrypoints, what is reusable, what is missing versus the must-haves.
5. **Present a short comparison and a recommendation** (table: repo, license, last push, fit, gaps). State that star counts and scores are heuristics, and license notes are not legal advice. Let the user choose before building.
6. **Scaffold.** Call `scaffold_project` with the chosen repo, a project name, the idea, and `output_dir` set to where the user wants the project (default: current folder). It creates layer folders, dependency manifests, `ARCHITECTURE.md` with a build plan, and `ATTRIBUTIONS.md`.
7. **Build on the chosen architecture.** Follow the build plan layer by layer, reproducing the *structure and design ideas* (module boundaries, data model, patterns), adapted to the must-haves. If copying code verbatim, only from permissive licenses, keep the copyright notice, and list the files in `ATTRIBUTIONS.md`. Otherwise write it fresh.
8. **Close the gaps** the study found, and say clearly which parts are inspired by which repo.

## Rules
- If tools are unavailable or GitHub is rate-limited, say so; don't invent repositories or stats.
- Every claim about a repo (stars, license, structure) must come from tool output.
- Don't clone and run unreviewed code without telling the user.
