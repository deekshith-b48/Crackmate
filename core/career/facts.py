"""Read a cloned repository as data and extract facts. Nothing here calls a model or runs repo code."""
import json
import os
import re
import tomllib
from collections import Counter
from pathlib import Path

from core.career.ontology import TECH_CONCEPTS, canon

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".next", "venv", ".venv", "__pycache__", "target", ".gradle", "Pods"}
LANGUAGES = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java",
             ".kt": "Kotlin", ".go": "Go", ".cpp": "C++", ".c": "C", ".cs": "C#", ".rb": "Ruby", ".php": "PHP", ".rs": "Rust", ".swift": "Swift"}
TEXT_EXT = set(LANGUAGES) | {".json", ".yml", ".yaml", ".toml", ".xml", ".cfg", ".ini", ".properties", ".env", ".txt", ".md", ".gradle", ".sh"}
DEP_FILES = {"package.json", "requirements.txt", "pyproject.toml", "go.mod", "pom.xml", "Dockerfile", "docker-compose.yml", "docker-compose.yaml"}
LANGUAGE_TECH = {"JavaScript": "javascript", "TypeScript": "typescript", "Python": "python", "Java": "java", "Kotlin": "kotlin"}
MAX_FILE, MAX_FILES = 300_000, 4000


def read_repo(root):
    """{relative path: text} for text files. Skips symlinks (untrusted), big files and vendored folders."""
    root, files = Path(root), {}
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            path = Path(folder) / name
            if path.is_symlink() or not path.is_file() or len(files) >= MAX_FILES:
                continue
            if name not in DEP_FILES and not name.startswith(".env") and path.suffix.lower() not in TEXT_EXT:
                continue
            try:
                if path.stat().st_size > MAX_FILE:
                    continue
                files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
    return files


def parse_dependencies(name, text):
    """Dependency names from one manifest. Malformed files yield nothing instead of raising."""
    found = []
    try:
        if name == "package.json":
            data = json.loads(text)
            found = [*data.get("dependencies", {}), *data.get("devDependencies", {})]
        elif name == "requirements.txt":
            found = [m.group(1) for line in text.splitlines() if (m := re.match(r"\s*([A-Za-z0-9_.\-]+)", line)) and not line.strip().startswith(("#", "-"))]
        elif name == "pyproject.toml":
            data = tomllib.loads(text)
            found = [re.match(r"[A-Za-z0-9_.\-]+", d).group(0) for d in data.get("project", {}).get("dependencies", []) if re.match(r"[A-Za-z0-9_.\-]+", d)]
            found += list(data.get("tool", {}).get("poetry", {}).get("dependencies", {}))
        elif name == "go.mod":
            found = re.findall(r"^\s*(?:require\s+)?([\w.\-]+\.[\w.\-]+/[\w./\-]+)\s+v", text, re.M)
        elif name == "pom.xml":
            found = re.findall(r"<artifactId>([^<]+)</artifactId>", text)
        elif name == "Dockerfile":
            found = ["docker"]
        elif name.startswith("docker-compose"):
            found = ["docker", *[re.split(r"[:@]", m)[0].split("/")[-1] for m in re.findall(r"^\s*image:\s*(\S+)", text, re.M)]]
    except (ValueError, TypeError, AttributeError, tomllib.TOMLDecodeError):
        return []
    return found


def imports_in(path, text):
    """Top-level package names imported by one source file."""
    ext = Path(path).suffix.lower()
    if ext in (".js", ".jsx", ".ts", ".tsx"):
        names = re.findall(r"""(?:from\s+|require\(\s*|import\s+)['"]([^'"./][^'"]*)['"]""", text)
        return [("/".join(n.split("/")[:2]) if n.startswith("@") else n.split("/")[0]) for n in names]
    if ext == ".py":
        return re.findall(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", text, re.M)
    if ext in (".java", ".kt"):
        return [m for m in re.findall(r"^\s*import\s+([\w.]+)", text, re.M) if m.startswith(("org.springframework",))] and ["org.springframework"]
    return []


def detect(files):
    """Technologies (with confidence and evidence), languages, size and layout. Pure: files in, facts out."""
    tech = {}

    def add(name, confidence, kind, path):
        key = canon(name)
        if key not in TECH_CONCEPTS:
            return
        entry = tech.setdefault(key, {"name": key, "confidence": 0.0, "evidence": []})
        entry["confidence"] = max(entry["confidence"], confidence)
        if len(entry["evidence"]) < 5 and not any(e["file"] == path and e["kind"] == kind for e in entry["evidence"]):
            entry["evidence"].append({"kind": kind, "file": path})

    loc, langs = 0, Counter()
    for path, text in files.items():
        base = Path(path).name
        if base in DEP_FILES:
            for dep in parse_dependencies(base, text):
                add(dep, 0.8, "dependency file", path)
        if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml")):
            add("github actions", 0.8, "workflow file", path)
        if re.search(r"(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.|(^|/)test_[^/]*\.py$", path):
            add("testing", 0.8, "test files", path)
        lang = LANGUAGES.get(Path(path).suffix.lower())
        if lang:
            lines = text.count("\n") + 1
            loc += lines
            langs[lang] += lines
            for imported in imports_in(path, text):
                add(imported, 0.9, "import in code", path)
    for lang, name in LANGUAGE_TECH.items():  # a language is evidence too: Python files back a "Python" claim
        if langs[lang]:
            add(name, 0.9, "source files", f"{langs[lang]} lines of {lang}")
    if any(Path(p).name == "package.json" for p in files):
        add("node.js", 0.8, "dependency file", "package.json")
    top = Counter(p.split("/")[0] for p in files if "/" in p)
    return {"technologies": sorted(tech.values(), key=lambda t: -t["confidence"]), "languages": dict(langs.most_common()),
            "loc": loc, "files": len(files), "top_dirs": [d for d, _ in top.most_common(8)]}
