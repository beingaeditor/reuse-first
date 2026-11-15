import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from architecture import classify_layers, detect_stack, make_blueprint, parse_deps, scaffold  # noqa: E402

PYPROJECT = '''
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "dedoc"
dependencies = [
  "fastapi>=0.100",
  "pydantic[email]>=2",
]
[project.optional-dependencies]
dev = ["pytest"]

[project.urls]
documentation = "https://x"
changelog = "https://y"
'''

SNAP = {
    "full_name": "o/r", "url": "https://github.com/o/r", "license": "MIT", "description": "d",
    "truncated": False, "readme": "# r",
    "paths": ["app/api/routes.py", "app/models/user.py", "app/services/pay.py",
              "app/main.py", "tests/test_api.py", "Dockerfile", ".github/workflows/ci.yml",
              "web/components/Button.tsx", "node_modules/x/index.js"],
    "manifests": {"pyproject.toml": PYPROJECT,
                  "web/package.json": json.dumps({"dependencies": {"react": "18"},
                                                   "devDependencies": {"vite": "5"}})},
}


def test_pyproject_parses_only_real_dependencies():
    deps = parse_deps({"pyproject.toml": PYPROJECT})["pyproject.toml"]
    assert deps == ["fastapi", "pydantic", "pytest"]


def test_poetry_and_requirements():
    poetry = '[tool.poetry.dependencies]\npython = "^3.10"\nflask = "^3"\n[tool.other]\nx = 1\n'
    assert parse_deps({"pyproject.toml": poetry})["pyproject.toml"] == ["flask"]
    req = "django>=4\n# c\n-e .\ncelery[redis]==5\n"
    assert parse_deps({"requirements.txt": req})["requirements.txt"] == ["celery", "django"]


def test_stack_and_layers():
    deps = parse_deps(SNAP["manifests"])
    stack = detect_stack(SNAP["paths"], deps)
    assert {"FastAPI", "React", "Vite"} <= set(stack["frameworks"])
    assert "GitHub Actions" in stack["infra"] and "Dockerfile" in stack["infra"]
    layers = classify_layers(SNAP["paths"])
    assert layers["api"] == ["app/api"] and layers["domain"] == ["app/models"]
    assert layers["ui"] == ["web"] and layers["tests"] == ["tests"]


def test_blueprint_and_scaffold(tmp_path):
    bp = make_blueprint(SNAP)
    assert "app/main.py" in bp["entrypoints"]
    assert any("data models" in s for s in bp["build_plan"])
    files = scaffold(bp, "Pay Hub", "Payments dashboard", tmp_path)
    root = tmp_path / "pay-hub"
    assert {"ARCHITECTURE.md", "ATTRIBUTIONS.md", "README.md", "pyproject.toml"} <= set(files)
    assert (root / "app/api/README.md").exists()
    assert "o/r" in (root / "ATTRIBUTIONS.md").read_text()
    assert '"fastapi"' in (root / "pyproject.toml").read_text()
    # the frontend manifest is mirrored at its own path, not merged into Python deps
    assert "web/package.json" in files
    assert '"react"' in (root / "web/package.json").read_text()
    assert "react" not in (root / "pyproject.toml").read_text()


def test_scaffold_refuses_non_empty_folder(tmp_path):
    import pytest
    bp = make_blueprint(SNAP)
    (tmp_path / "pay-hub").mkdir()
    scaffold(bp, "Pay Hub", "x", tmp_path)  # an empty existing folder is fine
    (tmp_path / "pay-hub" / "README.md").write_text("MY OWN NOTES")
    with pytest.raises(FileExistsError):
        scaffold(bp, "Pay Hub", "x", tmp_path)
    assert (tmp_path / "pay-hub" / "README.md").read_text() == "MY OWN NOTES"
