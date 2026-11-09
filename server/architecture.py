"""Turn a GitHub repo into a reusable architecture blueprint, and a blueprint into a
starter project. Only structure, stack and dependency *names* are reused, never code."""
import base64
import json
import re
from collections import Counter
from pathlib import Path

from cache import Cache
from github import GitHubError, get

MANIFESTS = ("package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml",
             "pom.xml", "build.gradle", "Gemfile", "composer.json")
INFRA_FILES = ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", "Makefile")

EXT_LANG = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript",
            ".jsx": "JavaScript", ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
            ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".cpp": "C++", ".c": "C", ".swift": "Swift",
            ".vue": "Vue", ".svelte": "Svelte", ".dart": "Dart"}

FRAMEWORKS = {"react": "React", "next": "Next.js", "vue": "Vue", "svelte": "Svelte",
              "astro": "Astro", "@sveltejs/kit": "SvelteKit", "nuxt": "Nuxt",
              "@remix-run/react": "Remix",
              "@angular/core": "Angular", "express": "Express", "fastify": "Fastify",
              "@nestjs/core": "NestJS", "electron": "Electron", "vite": "Vite",
              "tailwindcss": "Tailwind", "prisma": "Prisma", "fastapi": "FastAPI",
              "django": "Django", "flask": "Flask", "sqlalchemy": "SQLAlchemy",
              "pydantic": "Pydantic", "celery": "Celery", "torch": "PyTorch",
              "transformers": "HF Transformers", "langchain": "LangChain", "streamlit": "Streamlit",
              "pytest": "pytest", "jest": "Jest", "vitest": "Vitest",
              "github.com/gin-gonic/gin": "Gin", "actix-web": "Actix", "tokio": "Tokio",
              "axum": "Axum", "spring-boot": "Spring Boot", "spring-boot-starter-web": "Spring Boot",
              "rails": "Rails", "laravel/framework": "Laravel", "symfony/framework-bundle": "Symfony",
              "slim/slim": "Slim", "mezzio/mezzio": "Mezzio", "doctrine/orm": "Doctrine ORM",
              "drizzle-orm": "Drizzle", "next-auth": "NextAuth", "@supabase/supabase-js": "Supabase",
              "mongoose": "Mongoose", "redis": "Redis", "ioredis": "Redis",
              "github.com/labstack/echo/v4": "Echo", "github.com/gofiber/fiber/v2": "Fiber"}

LAYERS = {
    "api": {"api", "apis", "routes", "routers", "router", "controllers", "handlers", "endpoints", "graphql"},
    "domain": {"models", "model", "schemas", "schema", "entities", "domain", "types"},
    "services": {"services", "service", "core", "usecases", "lib", "pkg", "internal"},
    "data": {"db", "database", "migrations", "repositories", "repository", "store", "stores", "prisma"},
    "ui": {"components", "pages", "views", "screens", "frontend", "web", "client", "ui", "public", "static", "templates"},
    "cli": {"cli", "cmd", "bin", "commands"},
    "tests": {"tests", "test", "__tests__", "spec", "specs", "e2e"},
    "infra": {".github", "docker", "deploy", "deployment", "k8s", "helm", "infra", "terraform", "scripts"},
    "docs": {"docs", "doc", "examples", "example"},
}
ENTRY_NAMES = {"main.py", "app.py", "server.py", "manage.py", "__main__.py", "main.go", "main.rs",
               "index.ts", "index.js", "server.ts", "server.js", "main.ts", "App.tsx", "App.jsx",
               "cli.py", "wsgi.py", "asgi.py", "index.php", "artisan", "Program.cs",
               "main.dart", "Main.java", "Application.java", "page.tsx", "layout.tsx"}
SKIP = {"node_modules", "vendor", "dist", "build", ".git", "venv", ".venv", "__pycache__", "target"}


def _b64(data: dict, limit: int) -> str:
    return base64.b64decode(data["content"]).decode("utf-8", "replace")[:limit]


def snapshot(full_name: str, cache: Cache) -> dict:
    """Repo metadata, file paths, README and manifests (cached, ~4-8 API calls when cold)."""
    key = f"snap:{full_name}"
    cached, _ = cache.get(key)
    if cached is not None:
        return cached
    status, repo, _ = get(f"/repos/{full_name}", timeout=25)
    if status != 200:
        raise GitHubError(status, f"/repos/{full_name}")
    branch = repo.get("default_branch", "main")
    ts, tree_body, _ = get(f"/repos/{full_name}/git/trees/{branch}", {"recursive": 1}, timeout=25)
    tree = tree_body.get("tree", []) if ts == 200 else []
    paths = [x["path"] for x in tree if x.get("type") == "blob"
             and not SKIP.intersection(x["path"].split("/"))]
    rs, rd, _ = get(f"/repos/{full_name}/readme", timeout=25)
    readme = _b64(rd, 6000) if rs == 200 else ""
    manifests: dict[str, str] = {}
    wanted = [p for p in paths if p.split("/")[-1] in MANIFESTS and p.count("/") <= 2]
    wanted.sort(key=lambda p: p.count("/"))
    for p in wanted[:5]:
        ms, m, _ = get(f"/repos/{full_name}/contents/{p}", timeout=25)
        if ms == 200 and m.get("encoding") == "base64":
            manifests[p] = _b64(m, 8000)
    snap = {
        "full_name": full_name, "url": repo.get("html_url"),
        "description": repo.get("description"), "stars": repo.get("stargazers_count"),
        "license": (repo.get("license") or {}).get("spdx_id"),
        "pushed_at": repo.get("pushed_at"), "default_branch": branch,
        "paths": paths[:5000], "truncated": bool(ts == 200 and tree_body.get("truncated")),
        "readme": readme, "manifests": manifests,
    }
    cache.put(key, snap)
    return snap


def _section(toml: str, name: str) -> str:
    """Body of a TOML [name] table up to the next table header."""
    m = re.search(rf"^\[{re.escape(name)}\]\s*$(.*?)(?=^\[|\Z)", toml, re.M | re.S)
    return m.group(1) if m else ""


def parse_deps(manifests: dict[str, str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path, text in manifests.items():
        name = path.split("/")[-1]
        deps: list[str] = []
        try:
            if name in ("package.json", "composer.json"):
                d = json.loads(text)
                for k in ("dependencies", "devDependencies", "require", "require-dev"):
                    deps += list((d.get(k) or {}).keys())
            elif name == "requirements.txt":
                deps = [re.split(r"[<>=!~\[; ]", ln.strip())[0] for ln in text.splitlines()
                        if ln.strip() and not ln.startswith(("#", "-"))]
            elif name == "pyproject.toml":
                # PEP 621 arrays: dependencies = [...] and optional-dependencies groups
                for arr in re.findall(r"^\s*[\w\-]*\s*=\s*\[(.*?)\]", _section(text, "project"), re.M | re.S):
                    deps += re.findall(r'"\s*([A-Za-z0-9_.\-]+)', arr)
                for arr in re.findall(r"^\s*[\w\-]+\s*=\s*\[(.*?)\]",
                                      _section(text, "project.optional-dependencies"), re.M | re.S):
                    deps += re.findall(r'"\s*([A-Za-z0-9_.\-]+)', arr)
                # Poetry tables
                for sec in ("tool.poetry.dependencies", "tool.poetry.dev-dependencies",
                            "tool.poetry.group.dev.dependencies"):
                    deps += re.findall(r"^([A-Za-z0-9_.\-]+)\s*=", _section(text, sec), re.M)
                own = re.search(r'^name\s*=\s*"([^"]+)"', text, re.M)
                deps = [d for d in deps if d.lower() != "python" and (not own or d != own.group(1))]
            elif name == "go.mod":
                deps = re.findall(r"^\s*([\w.\-]+/[\w.\-/]+)\s+v", text, re.M)
            elif name == "Cargo.toml":
                sec = re.search(r"\[dependencies\](.*?)(\n\[|\Z)", text, re.S)
                deps = re.findall(r"^([\w\-]+)\s*=", sec.group(1), re.M) if sec else []
            elif name == "pom.xml":
                deps = re.findall(r"<artifactId>([^<]+)</artifactId>", text)[1:]
            elif name == "Gemfile":
                deps = re.findall(r"^\s*gem\s+['\"]([^'\"]+)", text, re.M)
        except (json.JSONDecodeError, AttributeError):
            pass
        out[path] = sorted({d.lower() for d in deps if d})
    return out


def detect_stack(paths: list[str], deps: dict[str, list[str]]) -> dict:
    langs = Counter(EXT_LANG[Path(p).suffix] for p in paths if Path(p).suffix in EXT_LANG)
    total = sum(langs.values()) or 1
    all_deps = {d for ds in deps.values() for d in ds}
    frameworks = sorted({v for k, v in FRAMEWORKS.items() if k in all_deps})
    infra = sorted({Path(p).name for p in paths if Path(p).name in INFRA_FILES})
    if any(p.startswith(".github/workflows/") for p in paths):
        infra.append("GitHub Actions")
    return {"languages": {k: round(v / total, 2) for k, v in langs.most_common(5)},
            "frameworks": frameworks, "infra": infra}


def classify_layers(paths: list[str]) -> dict[str, list[str]]:
    layers: dict[str, Counter] = {k: Counter() for k in LAYERS}
    for p in paths:
        parts = p.split("/")[:-1]
        for depth, seg in enumerate(parts[:4]):
            for layer, names in LAYERS.items():
                if seg.lower() in names:
                    layers[layer]["/".join(parts[: depth + 1])] += 1
                    break
            else:
                continue
            break
    return {k: [d for d, _ in c.most_common(4)] for k, c in layers.items() if c}


def make_blueprint(snap: dict) -> dict:
    paths = snap["paths"]
    deps = parse_deps(snap["manifests"])
    stack = detect_stack(paths, deps)
    layers = classify_layers(paths)
    entry = sorted({p for p in paths if Path(p).name in ENTRY_NAMES and p.count("/") <= 3},
                   key=lambda p: (p.count("/"), p))[:8]
    top_dirs = Counter(p.split("/")[0] for p in paths if "/" in p)
    key_deps = sorted({d for ds in deps.values() for d in ds},
                      key=lambda d: (d not in FRAMEWORKS, d))[:40]

    plan = ["Create the project skeleton mirroring the layers below."]
    if "domain" in layers:
        plan.append(f"Define data models first (reference: {layers['domain'][0]}/).")
    if "data" in layers:
        plan.append(f"Add persistence/migrations (reference: {layers['data'][0]}/).")
    if "services" in layers:
        plan.append(f"Implement core logic as services (reference: {layers['services'][0]}/).")
    if "api" in layers:
        plan.append(f"Expose it through the API layer (reference: {layers['api'][0]}/).")
    if "cli" in layers:
        plan.append(f"Add the CLI entrypoint (reference: {layers['cli'][0]}/).")
    if "ui" in layers:
        plan.append(f"Build the UI (reference: {layers['ui'][0]}/).")
    plan.append("Write tests alongside each layer" + (f" (reference: {layers['tests'][0]}/)." if "tests" in layers else "."))
    if stack["infra"]:
        plan.append("Add " + ", ".join(stack["infra"]) + " for build and deploy.")

    return {
        "source": snap["full_name"], "url": snap["url"], "license": snap["license"],
        "description": snap["description"], "total_files": len(paths),
        "tree_truncated": snap["truncated"], "stack": stack, "layers": layers,
        "entrypoints": entry, "top_level": [d for d, _ in top_dirs.most_common(12)],
        "key_dependencies": key_deps, "manifests": list(snap["manifests"]),
        "deps_by_manifest": deps,
        "build_plan": plan, "readme_excerpt": snap["readme"][:2500],
    }


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "my-project"


def scaffold(bp: dict, project_name: str, idea: str, out_dir: Path) -> list[str]:
    """Write a starter project shaped like the blueprint. Returns created relative paths."""
    root = out_dir / _slug(project_name)
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    def write(rel: str, text: str):
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        created.append(rel)

    seen = set()
    for layer, dirs in bp["layers"].items():
        for d in dirs[:2]:
            if d.startswith(".github") or d in seen:
                continue
            seen.add(d)
            write(f"{d}/README.md", f"# {d}\n\nLayer: **{layer}**. Mirrors `{d}/` in "
                  f"[{bp['source']}]({bp['url']}/tree/HEAD/{d}).\n")

    # One manifest per ecosystem the source uses, at the same relative path
    # (e.g. go.mod at the root and web/package.json for the frontend).
    slug = _slug(project_name)
    by_manifest = bp.get("deps_by_manifest") or {}
    if not by_manifest and bp["key_dependencies"]:
        by_manifest = {"DEPENDENCIES": bp["key_dependencies"]}
    done_kinds: set[tuple[str, str]] = set()
    for path, all_deps in by_manifest.items():
        name, folder = path.split("/")[-1], "/".join(path.split("/")[:-1])
        if (folder, name) in done_kinds:
            continue
        done_kinds.add((folder, name))
        deps = sorted([d for d in all_deps if not d.startswith("@types/")],
                      key=lambda d: (d not in FRAMEWORKS, d))[:20]
        if name == "package.json":
            write(path, json.dumps({"name": slug if not folder else f"{slug}-{folder.replace('/', '-')}",
                  "version": "0.1.0", "private": True,
                  "dependencies": {d: "*" for d in deps}}, indent=2) + "\n")
        elif name == "pyproject.toml":
            lines = ",\n".join(f'  "{d}"' for d in deps)
            write(path, f'[project]\nname = "{slug}"\nversion = "0.1.0"\n'
                  f'requires-python = ">=3.10"\ndependencies = [\n{lines}\n]\n')
        elif name == "requirements.txt":
            write(path, "".join(f"{d}\n" for d in deps))
        elif name == "go.mod":
            write(path, f"module {slug}\n\ngo 1.22\n\n// Add with `go get`:\n"
                  + "".join(f"// {d}\n" for d in deps))
        elif name == "Cargo.toml":
            write(path, f'[package]\nname = "{slug}"\nversion = "0.1.0"\nedition = "2021"\n\n'
                  "[dependencies]\n" + "".join(f'{d} = "*"\n' for d in deps))
        elif name == "composer.json":
            write(path, json.dumps({"name": f"app/{slug}",
                  "require": {d: "*" for d in deps if "/" in d}}, indent=2) + "\n")
        else:
            write(f"{folder + '/' if folder else ''}DEPENDENCIES.md",
                  f"# Dependencies used by the reference ({name})\n\n" + "".join(f"- {d}\n" for d in deps))

    layer_md = "\n".join(f"- **{k}**: " + ", ".join(f"`{d}/`" for d in v) for k, v in bp["layers"].items())
    plan_md = "\n".join(f"{i}. {s}" for i, s in enumerate(bp["build_plan"], 1))
    stack = bp["stack"]
    write("ARCHITECTURE.md", f"# Architecture\n\nBased on the structure of [{bp['source']}]({bp['url']}).\n\n"
          f"## Stack\n- Languages: {', '.join(stack['languages']) or 'unknown'}\n"
          f"- Frameworks: {', '.join(stack['frameworks']) or 'none detected'}\n"
          f"- Infra: {', '.join(stack['infra']) or 'none detected'}\n\n"
          f"## Layers\n{layer_md or '- (flat layout)'}\n\n"
          f"## Reference entrypoints\n" + "\n".join(f"- `{e}`" for e in bp["entrypoints"]) +
          f"\n\n## Build plan\n{plan_md}\n")
    write("README.md", f"# {project_name}\n\n{idea}\n\nStarter generated by reuse-first. "
          "See ARCHITECTURE.md for the design and build plan.\n")
    write("ATTRIBUTIONS.md", f"# Attributions\n\nProject structure inspired by "
          f"[{bp['source']}]({bp['url']}) (license: {bp['license'] or 'not detected'}).\n"
          "No source code was copied. If you copy code from it later, keep its license and "
          "copyright notice and list the files here.\n")
    return created
