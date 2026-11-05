from __future__ import annotations

import json
import re
from typing import Any

KNOWN_PACKAGES = {
    "fastapi": "Python web API framework",
    "flask": "Python web framework",
    "django": "Python web framework",
    "uvicorn": "ASGI server",
    "sqlalchemy": "Python SQL toolkit",
    "httpx": "HTTP client",
    "requests": "HTTP client",
    "pydantic": "Data validation",
    "pytest": "Python testing",
    "react": "UI library",
    "react-dom": "React DOM renderer",
    "vite": "Frontend build tool",
    "next": "React meta-framework",
    "express": "Node.js web framework",
    "axios": "HTTP client",
    "prisma": "ORM",
    "mongoose": "MongoDB ODM",
    "typescript": "Typed JavaScript",
    "lucide-react": "Icon library",
    "chromadb": "Vector store",
    "openai": "OpenAI API client",
    "groq": "Groq API client",
}

ROUTE_PATTERNS = [
    (re.compile(r"@(?:app|router|api_router)\.(get|post|put|patch|delete|options|head)\(\s*['\"]([^'\"]+)['\"]", re.I), "python"),
    (re.compile(r"@(?:app|bp|blueprint)\.route\(\s*['\"]([^'\"]+)['\"]", re.I), "flask"),
    (re.compile(r"""(?:app|router|r)\.(get|post|put|patch|delete)\(\s*['"]([^'"]+)['"]""", re.I), "express"),
    (re.compile(r"@(Get|Post|Put|Patch|Delete)\(\s*['\"]([^'\"]+)['\"]", re.I), "nestjs"),
]

IMPORT_HINTS = [
    ("fastapi", "FastAPI"),
    ("flask", "Flask"),
    ("django", "Django"),
    ("express", "Express"),
    ("react", "React"),
    ("next", "Next.js"),
    ("vite", "Vite"),
    ("sqlalchemy", "SQLAlchemy"),
    ("prisma", "Prisma"),
    ("mongoose", "MongoDB/Mongoose"),
    ("celery", "Celery"),
    ("openai", "OpenAI"),
    ("langchain", "LangChain"),
    ("chromadb", "ChromaDB"),
    ("jwt", "JWT"),
    ("passport", "Passport"),
    ("oauth", "OAuth"),
]

ENTRY_FILES = {
    "main.py", "app.py", "manage.py", "wsgi.py", "asgi.py", "server.py",
    "index.js", "index.ts", "main.js", "main.ts", "server.js", "app.js",
    "main.go", "main.rs", "Program.cs", "index.html",
}


def analyze_repository_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    files = payload.get("files") or []
    facts = payload.get("facts") or {}
    tree = payload.get("tree") or []
    readme = payload.get("readme")
    by_name = {f["path"].split("/")[-1].lower(): f for f in files}
    technologies = _detect_technologies(files, facts)
    entry_points = _detect_entry_points(files)
    endpoints = _detect_endpoints(files)
    dependencies = _parse_dependencies(files)
    env_vars = _detect_env_vars(files)
    testing = _detect_testing(files, tree)
    deployment = _detect_deployment(files, tree)
    auth = _detect_auth(files)
    ai_integrations = _detect_ai(files)
    databases = _detect_databases(files)
    quality = _detect_quality(files, tree, testing)
    modules = _top_modules(files, tree)
    features = _detect_features(files, readme)
    mermaid = _architecture_diagram(technologies, entry_points, endpoints, databases)
    setup = _setup_guide(dependencies, env_vars, files, facts)
    summary = _heuristic_summary(facts, files, tree, readme, technologies, entry_points)
    purpose = facts.get("description") or _purpose_from_readme(readme) or (
        "Purpose could not be confidently inferred from repository metadata or README."
    )
    important = _important_files(files)
    limitations = [
        "Analysis is static inspection of a bounded file sample. Repository code was not executed.",
        "Inferred technologies are labeled as inferred and may be incomplete.",
        "Secret-looking files are excluded; detected credential-like strings are redacted.",
    ]
    if payload.get("stats", {}).get("tree_truncated"):
        limitations.append("GitHub reported a truncated tree; some files may be missing from the index.")
    if payload.get("stats", {}).get("skipped_due_to_file_cap"):
        limitations.append("File count or size limits prevented indexing the entire repository.")
    if not readme:
        limitations.append("No README was found.")
    return {
        "summary": summary,
        "purpose": purpose,
        "github_facts": facts,
        "technologies": technologies,
        "entry_points": entry_points,
        "modules": modules,
        "api_endpoints": endpoints,
        "features": features,
        "auth": auth,
        "databases": databases,
        "ai_integrations": ai_integrations,
        "testing": testing,
        "deployment": deployment,
        "dependencies": dependencies,
        "setup": setup,
        "quality": quality,
        "important_files": important,
        "architecture_diagram": mermaid,
        "env_vars": env_vars,
        "ai_enabled": False,
        "mode": "heuristic",
        "limitations": limitations,
        "by_name_present": sorted(by_name.keys())[:40],
    }


def _file_text(files: list[dict[str, Any]]) -> str:
    return "\n".join(f.get("content") or "" for f in files)


def _detect_technologies(files: list[dict[str, Any]], facts: dict[str, Any]) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    if facts.get("language"):
        found[facts["language"]] = {
            "name": facts["language"],
            "kind": "language",
            "confidence": "observed",
            "evidence": "GitHub primary language field",
        }
    for lang in (facts.get("languages") or {}):
        found.setdefault(lang, {
            "name": lang,
            "kind": "language",
            "confidence": "observed",
            "evidence": "GitHub languages API",
        })
    blob = _file_text(files).lower()
    paths = [f["path"].lower() for f in files]
    for token, label in IMPORT_HINTS:
        evidence_path = next((p for p in paths if token in p), None)
        if token in blob or evidence_path:
            found[label] = {
                "name": label,
                "kind": "framework",
                "confidence": "inferred",
                "evidence": evidence_path or f"source mention of '{token}'",
            }
    for path in paths:
        if path.endswith("package.json"):
            found["Node.js"] = {"name": "Node.js", "kind": "runtime", "confidence": "inferred", "evidence": path}
        if path.endswith("requirements.txt") or path.endswith("pyproject.toml"):
            found["Python"] = {"name": "Python", "kind": "language", "confidence": "inferred", "evidence": path}
        if path.endswith("go.mod"):
            found["Go"] = {"name": "Go", "kind": "language", "confidence": "inferred", "evidence": path}
        if path.endswith("cargo.toml"):
            found["Rust"] = {"name": "Rust", "kind": "language", "confidence": "inferred", "evidence": path}
        if "dockerfile" in path.split("/")[-1]:
            found["Docker"] = {"name": "Docker", "kind": "tooling", "confidence": "inferred", "evidence": path}
    return list(found.values())[:40]


def _detect_entry_points(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = []
    for file in files:
        name = file["path"].split("/")[-1]
        content = file.get("content") or ""
        reasons = []
        if name in ENTRY_FILES or name.lower() in {n.lower() for n in ENTRY_FILES}:
            reasons.append("common entry-point filename")
        if re.search(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]', content):
            reasons.append("Python __main__ guard")
        if re.search(r"createRoot\(|ReactDOM\.render\(", content):
            reasons.append("React bootstrap")
        if re.search(r"FastAPI\(|Flask\(|express\(", content):
            reasons.append("web application constructor")
        if reasons:
            entries.append({"path": file["path"], "reason": "; ".join(reasons), "confidence": "inferred"})
    return entries[:20]


def _detect_endpoints(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    endpoints = []
    for file in files:
        content = file.get("content") or ""
        for pattern, kind in ROUTE_PATTERNS:
            for match in pattern.finditer(content):
                groups = match.groups()
                if kind == "flask":
                    method, route = "ANY", groups[0]
                else:
                    method, route = groups[0].upper(), groups[1] if len(groups) > 1 else groups[0]
                line = content[: match.start()].count("\n") + 1
                endpoints.append({
                    "method": method,
                    "path": route,
                    "evidence_file": file["path"],
                    "line": line,
                    "confidence": "inferred",
                    "kind": kind,
                })
    # de-dupe
    seen = set()
    unique = []
    for item in endpoints:
        key = (item["method"], item["path"], item["evidence_file"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:80]


def _parse_dependencies(files: list[dict[str, Any]]) -> dict[str, Any]:
    ecosystems = []
    for file in files:
        name = file["path"].split("/")[-1].lower()
        content = file.get("content") or ""
        declared = []
        ecosystem = None
        if name == "requirements.txt":
            ecosystem = "python"
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                pkg = re.split(r"[=<>!~\[]", line, maxsplit=1)[0].strip()
                if pkg:
                    declared.append(_dep(pkg, line, file["path"]))
        elif name == "pyproject.toml":
            ecosystem = "python"
            for match in re.finditer(r'^\s*"?([A-Za-z0-9_.\-]+)"?\s*[=,]', content, re.M):
                pkg = match.group(1)
                if pkg.lower() in {"name", "version", "description", "requires-python", "license", "authors"}:
                    continue
                declared.append(_dep(pkg, match.group(0).strip(), file["path"]))
        elif name == "package.json":
            ecosystem = "node"
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                data = {}
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                section_data = data.get(section) or {}
                if isinstance(section_data, dict):
                    for pkg, spec in section_data.items():
                        item = _dep(pkg, f"{pkg}@{spec}", file["path"])
                        item["scope"] = section
                        declared.append(item)
        elif name == "go.mod":
            ecosystem = "go"
            for match in re.finditer(r"^\s*([A-Za-z0-9./\-_]+)\s+v[0-9][^\s]*", content, re.M):
                declared.append(_dep(match.group(1), match.group(0).strip(), file["path"]))
        elif name == "cargo.toml":
            ecosystem = "rust"
            block = re.search(r"\[dependencies\](.*?)(\n\[|\Z)", content, re.S | re.I)
            if block:
                for match in re.finditer(r"^([A-Za-z0-9_\-]+)\s*=", block.group(1), re.M):
                    declared.append(_dep(match.group(1), match.group(0).strip(), file["path"]))
        elif name in {"gemfile"}:
            ecosystem = "ruby"
            for match in re.finditer(r"""gem\s+['"]([^'"]+)['"]""", content):
                declared.append(_dep(match.group(1), match.group(0), file["path"]))
        if ecosystem:
            ecosystems.append({
                "name": ecosystem,
                "file": file["path"],
                "declared": declared[:120],
                "note": "These packages are declared in the manifest. Installed versions were not verified.",
            })
    return {"ecosystems": ecosystems}


def _dep(name: str, spec: str, source: str) -> dict[str, Any]:
    purpose = KNOWN_PACKAGES.get(name.lower())
    item = {
        "name": name,
        "spec": spec,
        "source_file": source,
        "confidence": "observed" if spec else "inferred",
    }
    if purpose:
        item["purpose"] = purpose
        item["purpose_confidence"] = "inferred"
        item["purpose_note"] = "Common purpose for this package name; usage in this repository was not fully verified."
    return item


def _detect_env_vars(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = []
    pattern = re.compile(r"""(?:os\.getenv|os\.environ(?:\.get)?|process\.env|ENV)\(?['"]([A-Z0-9_]{2,})['"]""")
    example_pattern = re.compile(r"^([A-Z][A-Z0-9_]+)=", re.M)
    seen = set()
    for file in files:
        name = file["path"].split("/")[-1].lower()
        content = file.get("content") or ""
        if name.endswith(".env.example") or name == ".env.example":
            for match in example_pattern.finditer(content):
                key = match.group(1)
                if key in seen:
                    continue
                seen.add(key)
                found.append({"name": key, "source_file": file["path"], "has_example": True, "value": None})
        for match in pattern.finditer(content):
            key = match.group(1)
            if key in seen:
                continue
            seen.add(key)
            found.append({"name": key, "source_file": file["path"], "has_example": False, "value": None})
    return found[:80]


def _detect_testing(files: list[dict[str, Any]], tree: list[str]) -> dict[str, Any]:
    test_files = [p for p in tree if re.search(r"(^|/)(tests?|spec)/", p.lower()) or re.search(r"(test_|_test\.|\.test\.|\.spec\.)", p.lower())]
    frameworks = []
    blob = _file_text(files).lower()
    for token, label in [("pytest", "pytest"), ("unittest", "unittest"), ("vitest", "vitest"), ("jest", "jest"), ("mocha", "mocha")]:
        if token in blob:
            frameworks.append(label)
    return {
        "test_file_count_in_tree": len(test_files),
        "sample_test_paths": test_files[:20],
        "frameworks": frameworks,
        "confidence": "inferred" if test_files or frameworks else "unknown",
        "note": "Tests were not executed.",
    }


def _detect_deployment(files: list[dict[str, Any]], tree: list[str]) -> dict[str, Any]:
    paths = [p.lower() for p in tree]
    files_found = [p for p in paths if any(token in p for token in (
        "dockerfile", "docker-compose", "render.yaml", "vercel.json", "netlify.toml",
        ".github/workflows", "procfile", "fly.toml", "kubernetes", "helm",
    ))]
    return {
        "config_files": files_found[:30],
        "confidence": "inferred" if files_found else "unknown",
    }


def _detect_auth(files: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = []
    blob_files = []
    for file in files:
        content = (file.get("content") or "").lower()
        hits = []
        for token in ("oauth", "jwt", "authorization", "authenticate", "passport", "session", "csrf"):
            if token in content:
                hits.append(token)
        if hits:
            evidence.append({"path": file["path"], "tokens": hits[:8]})
            blob_files.append(file["path"])
    return {
        "detected": bool(evidence),
        "evidence": evidence[:15],
        "confidence": "inferred" if evidence else "unknown",
        "summary": "Authentication-related tokens were found in source files." if evidence else "No authentication implementation was confidently identified.",
    }


def _detect_ai(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = []
    for file in files:
        content = (file.get("content") or "").lower()
        for token, label in [("openai", "OpenAI"), ("groq", "Groq"), ("langchain", "LangChain"), ("chromadb", "ChromaDB"), ("anthropic", "Anthropic"), ("embedding", "Embeddings")]:
            if token in content:
                found.append({"name": label, "evidence_file": file["path"], "confidence": "inferred"})
    unique = []
    seen = set()
    for item in found:
        if item["name"] in seen:
            continue
        seen.add(item["name"])
        unique.append(item)
    return unique


def _detect_databases(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = []
    for file in files:
        content = (file.get("content") or "").lower()
        path = file["path"]
        for token, label in [
            ("sqlalchemy", "SQLAlchemy"),
            ("sqlite", "SQLite"),
            ("postgres", "PostgreSQL"),
            ("mysql", "MySQL"),
            ("mongodb", "MongoDB"),
            ("prisma", "Prisma"),
            ("redis", "Redis"),
            ("django.db", "Django ORM"),
        ]:
            if token in content or token in path.lower():
                found.append({"name": label, "evidence_file": path, "confidence": "inferred"})
    unique = []
    seen = set()
    for item in found:
        if item["name"] in seen:
            continue
        seen.add(item["name"])
        unique.append(item)
    return unique


def _detect_quality(files: list[dict[str, Any]], tree: list[str], testing: dict[str, Any]) -> dict[str, Any]:
    findings = []
    if testing.get("test_file_count_in_tree", 0) == 0:
        findings.append({
            "title": "No test files detected in the repository tree sample",
            "severity": "info",
            "confidence": "inferred",
            "kind": "testing",
            "evidence_path": None,
            "evidence": "No paths matching common test naming patterns were found in the indexed tree.",
        })
    ci = any(".github/workflows" in p.lower() for p in tree)
    if not ci:
        findings.append({
            "title": "No GitHub Actions workflow detected",
            "severity": "info",
            "confidence": "inferred",
            "kind": "deployment",
            "evidence_path": None,
            "evidence": "No .github/workflows files were present in the tree sample.",
        })
    for file in files:
        content = file.get("content") or ""
        path = file["path"]
        if re.search(r"except\s*:", content) and path.endswith(".py"):
            line = next((i + 1 for i, line in enumerate(content.splitlines()) if re.search(r"except\s*:", line)), 1)
            findings.append({
                "title": "Bare except clause",
                "severity": "low",
                "confidence": "inferred",
                "kind": "error-handling",
                "evidence_path": path,
                "line": line,
                "evidence": "A bare except: was found. This can hide unexpected errors.",
            })
        if re.search(r"\beval\s*\(", content):
            findings.append({
                "title": "Use of eval()",
                "severity": "medium",
                "confidence": "inferred",
                "kind": "unsafe-pattern",
                "evidence_path": path,
                "evidence": "eval() can execute untrusted input if reached at runtime. This is a static finding, not a confirmed exploit.",
            })
        if "TODO" in content or "FIXME" in content:
            findings.append({
                "title": "TODO/FIXME comments present",
                "severity": "info",
                "confidence": "observed",
                "kind": "completeness",
                "evidence_path": path,
                "evidence": "The file contains TODO or FIXME comments.",
            })
    return {
        "findings": findings[:40],
        "disclaimer": "These are potential findings from static inspection, not a security audit. Code was not executed.",
    }


def _top_modules(files: list[dict[str, Any]], tree: list[str]) -> list[dict[str, Any]]:
    dirs: dict[str, int] = {}
    for path in tree:
        if "/" in path:
            top = path.split("/")[0]
            dirs[top] = dirs.get(top, 0) + 1
    modules = [{"name": name, "file_count_in_tree": count, "confidence": "observed"} for name, count in sorted(dirs.items(), key=lambda x: -x[1])[:20]]
    return modules


def _detect_features(files: list[dict[str, Any]], readme: dict[str, Any] | None) -> list[str]:
    features = []
    text = (readme or {}).get("content") or ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")) and 12 < len(stripped) < 140:
            features.append(stripped[2:].strip())
        if len(features) >= 8:
            break
    return features


def _important_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    important = []
    for file in files[:25]:
        important.append({
            "path": file["path"],
            "lines": file.get("line_count"),
            "url": file.get("html_url"),
            "reason": "Included in the bounded analysis sample.",
        })
    return important


def _architecture_diagram(technologies, entry_points, endpoints, databases) -> dict[str, Any]:
    nodes = []
    edges = []
    names = {t["name"] for t in technologies}
    frontend = next((n for n in names if n in {"React", "Next.js", "Vite", "Vue"}), None)
    backend = next((n for n in names if n in {"FastAPI", "Flask", "Django", "Express"}), None)
    if frontend:
        nodes.append(frontend)
    if backend:
        nodes.append(backend)
    if frontend and backend:
        edges.append((frontend, backend))
    db = databases[0]["name"] if databases else None
    if db and backend:
        nodes.append(db)
        edges.append((backend, db))
    if not nodes:
        return {
            "mermaid": None,
            "note": "Not enough evidence to draw component relationships without inventing connections.",
        }
    lines = ["flowchart LR"]
    ident = {name: re.sub(r"[^A-Za-z0-9]", "", name) or f"N{i}" for i, name in enumerate(nodes)}
    for name in nodes:
        lines.append(f'    {ident[name]}["{name}"]')
    for src, dst in edges:
        lines.append(f"    {ident[src]} --> {ident[dst]}")
    if entry_points:
        lines.append(f'    Entry["Entry: {entry_points[0]["path"]}"]')
        target = ident.get(backend) or ident.get(frontend) or ident[nodes[0]]
        lines.append(f"    Entry --> {target}")
    if endpoints:
        lines.append(f'    API["{len(endpoints)} detected routes"]')
        if backend:
            lines.append(f"    {ident[backend]} --> API")
    return {"mermaid": "\n".join(lines), "note": "Diagram includes only detected components and simple inferred relationships."}


def _setup_guide(dependencies, env_vars, files, facts) -> dict[str, Any]:
    frontend_steps = []
    backend_steps = []
    notes = ["Review the repository README before running any commands.", "RepoMind does not install dependencies or execute project code."]
    paths = {f["path"].split("/")[-1].lower(): f for f in files}
    if "package.json" in paths:
        pkg = paths["package.json"]
        frontend_steps.append("cd into the directory that contains package.json")
        frontend_steps.append("npm install")
        try:
            data = json.loads(pkg.get("content") or "{}")
            scripts = data.get("scripts") or {}
            if "dev" in scripts:
                frontend_steps.append("npm run dev")
            elif "start" in scripts:
                frontend_steps.append("npm start")
            else:
                frontend_steps.append("Inspect package.json scripts before running a start command.")
        except json.JSONDecodeError:
            frontend_steps.append("Inspect package.json scripts before running a start command.")
    if "requirements.txt" in paths:
        backend_steps.extend([
            "Create and activate a virtual environment",
            "pip install -r requirements.txt",
        ])
    if "pyproject.toml" in paths and "requirements.txt" not in paths:
        backend_steps.extend(["Create and activate a virtual environment", "pip install ."])
    if "manage.py" in paths:
        backend_steps.append("python manage.py migrate && python manage.py runserver  (only after reviewing Django settings)")
    if "docker-compose.yml" in paths or "docker-compose.yaml" in paths:
        notes.append("A Docker Compose file is present. Review services and ports in that file before using docker compose up.")
    if "dockerfile" in paths:
        notes.append("A Dockerfile is present. Review it before building an image.")
    troubleshooting = [
        "If GitHub analysis fails with 403, configure GITHUB_TOKEN to raise API rate limits.",
        "If the project requires environment variables, copy the example file if one exists and fill in local values. Do not commit secrets.",
    ]
    if not frontend_steps and not backend_steps:
        notes.append("No standard package manifest was found in the analyzed files, so install commands were not generated.")
    return {
        "frontend_steps": frontend_steps,
        "backend_steps": backend_steps,
        "env_vars": env_vars,
        "troubleshooting": troubleshooting,
        "notes": notes,
    }


def _heuristic_summary(facts, files, tree, readme, technologies, entry_points) -> str:
    name = facts.get("full_name") or "This repository"
    language = facts.get("language") or "an unspecified primary language"
    tech_names = ", ".join(t["name"] for t in technologies[:6]) or "no additional detected stack"
    entry = entry_points[0]["path"] if entry_points else "not confidently identified"
    readme_note = "A README was retrieved." if readme else "No README was retrieved."
    return (
        f"{name} is a public GitHub repository whose GitHub-reported primary language is {language}. "
        f"The analyzer indexed {len(files)} text files from a tree of {len(tree)} paths. "
        f"Detected stack signals: {tech_names}. Likely entry point: {entry}. {readme_note} "
        "This overview is heuristic unless an LLM is configured."
    )


def _purpose_from_readme(readme: dict[str, Any] | None) -> str | None:
    if not readme:
        return None
    text = readme.get("content") or ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and len(stripped) > 40:
            return stripped[:400]
    return None
