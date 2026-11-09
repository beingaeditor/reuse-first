# reuse-first
Tell Claude what you want to build, and reuse-first finds open-source GitHub projects that already do it, ranks them by activity, popularity and license, and sets up your project in the best one's structure. For developers using Claude Code.
```bash
git clone https://github.com/beingaeditor/reuse-first && pip install -r reuse-first/server/requirements.txt && claude --plugin-dir reuse-first
```
![Demo: reuse-first finding URL shorteners and scaffolding a project](assets/demo.gif)

| Part | What it is |
| --- | --- |
| `server/` | MCP server with 3 tools: `find_repos`, `blueprint`, `scaffold_project` |
| `skills/reuse-first/` | The workflow Claude follows (search → compare → scaffold → build) |
| `demo/` | Web demo of the same flow, no AI needed |
| `tests/` | Unit tests and a live end-to-end test that drives the MCP server like Claude does |

## Setup

```bash
pip install -r server/requirements.txt
```

Optional: set `GITHUB_TOKEN` to a [GitHub personal access token](https://github.com/settings/personal-access-tokens/new). No scopes are needed. Without a token GitHub allows about 60 requests an hour and 10 searches a minute. One search plus one blueprint uses about 7.

Set it in your shell before running reuse-first:

| Shell | Command |
| --- | --- |
| bash / zsh (macOS, Linux) | `export GITHUB_TOKEN="YOUR_TOKEN"` |
| PowerShell (Windows) | `$env:GITHUB_TOKEN = "YOUR_TOKEN"` |
| Command Prompt (Windows) | `set GITHUB_TOKEN=YOUR_TOKEN` |

## Try the web demo

```bash
pip install fastapi uvicorn
python demo/app.py
```

Open http://localhost:8765. Describe a project, pick a repo, see its blueprint, and download a starter .zip.

## Command line (no install)

`server/cli.py` runs the same three steps with only Python 3.10+, and prints JSON:

```bash
python server/cli.py find "self-hosted url shortener"
python server/cli.py blueprint shlinkio/shlink
python server/cli.py scaffold shlinkio/shlink "My Shortener" "Short links for my team" ./projects
```

## Add to Claude Code (full plugin: tools + skill)

```bash
claude --plugin-dir ./reuse-first-plugin
```

Then say: "I want to build a self-hosted URL shortener." The skill triggers on new-project requests.

## Add to Claude Desktop (tools only)

In Settings, Developer, Edit Config, add:

```json
{"mcpServers": {"reuse-first": {"command": "python", "args": ["C:/full/path/reuse-first-plugin/server/server.py"]}}}
```

Restart Claude Desktop. For the workflow, paste the body of `skills/reuse-first/SKILL.md` into a Project's instructions.

## Add to ChatGPT

ChatGPT only accepts remote MCP servers (Settings, Apps & Connectors, Developer mode).

```bash
python server/server.py --http
```

Expose it at a public HTTPS URL (Render, Fly.io, or `ngrok http 8000` for testing), add `https://your-host/mcp` as a connector, and paste SKILL.md into custom instructions. Add authentication before leaving it public. Note that on a remote server, `scaffold_project` writes files on that server, not on your PC.

## Verify

```bash
python -m pytest tests -q
python tests/e2e_live.py "self-hosted url shortener"
```

## Limits

- Ranking is a heuristic (recency, stars, issue load, keyword fit), not a quality guarantee.
- License notes are informational, not legal advice. Unlicensed and copyleft repos are excluded unless you allow copyleft.
- The scaffold reuses structure and dependency names only, never source code.

## Contributing

Issues and pull requests are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). Questions and ideas go in [Discussions](https://github.com/beingaeditor/reuse-first/discussions).

## License

[MIT](LICENSE)
