import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import cli  # noqa: E402
import core  # noqa: E402
from github import GitHubError  # noqa: E402


@pytest.mark.parametrize("argv, fn, expected", [
    (["find", "url shortener"], "find", ("url shortener", 10, False)),
    (["find", "x y", "--limit", "3", "--allow-copyleft"], "find", ("x y", 3, True)),
    (["blueprint", "o/r"], "blueprint", ("o/r",)),
    (["scaffold", "o/r", "My App", "an idea"], "scaffold_project", ("o/r", "My App", "an idea", ".")),
    (["scaffold", "o/r", "My App", "an idea", "out"], "scaffold_project", ("o/r", "My App", "an idea", "out")),
])
def test_commands_call_core_and_print_json(argv, fn, expected, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(core, fn, lambda *a: calls.append(a) or {"ok": "café"})
    cli.main(argv)
    assert calls == [expected]
    out = capsys.readouterr().out
    assert json.loads(out) == {"ok": "café"} and out.isascii()


def test_github_error_prints_one_line_and_exits_2(monkeypatch, capsys):
    def limited(*a):
        raise GitHubError(403, "/search/repositories")
    monkeypatch.setattr(core, "find", limited)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(SystemExit) as e:
        cli.main(["find", "x"])
    out, err = capsys.readouterr()
    assert e.value.code == 2 and out == ""
    assert err.count("\n") == 1 and "GITHUB_TOKEN" in err


def test_missing_command_exits_with_usage():
    with pytest.raises(SystemExit) as e:
        cli.main([])
    assert e.value.code == 2


def test_existing_folder_prints_one_line_and_exits_2(monkeypatch, capsys):
    def exists(*a):
        raise FileExistsError("out/my-app already exists and is not empty")
    monkeypatch.setattr(core, "scaffold_project", exists)
    with pytest.raises(SystemExit) as e:
        cli.main(["scaffold", "o/r", "My App", "idea"])
    assert e.value.code == 2 and capsys.readouterr().err.startswith("error: out/my-app")
