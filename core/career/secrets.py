"""Find secrets committed to a project before an interviewer does. Values are masked and never stored."""
import re

RULES = (
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}"), "high"),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "high"),
    ("Groq API key", re.compile(r"gsk_[A-Za-z0-9]{20,}"), "high"),
    ("OpenAI-style API key", re.compile(r"sk-[A-Za-z0-9]{20,}"), "high"),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "high"),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "high"),
    ("Private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "high"),
    ("Hard-coded credential", re.compile(r"""(?i)\b(?:api[_-]?key|secret|token|passwd|password)\b\s*[:=]\s*['"]([^'"\s]{12,})['"]"""), "medium"),
)
PLACEHOLDER = re.compile(r"(?i)your|example|changeme|xxx|<|\$\{|process\.env|os\.environ|placeholder|dummy|sample|test")
SKIP_FILES = (".env.example", ".env.sample", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock")


def mask(value):
    return value[:4] + "…" + f"({len(value)} chars)"


def scan(files):
    findings = []
    for path, text in files.items():
        name = path.rsplit("/", 1)[-1]
        if name in SKIP_FILES:
            continue
        if name == ".env" or (name.startswith(".env.") and name not in SKIP_FILES):
            findings.append({"file": path, "line": 1, "kind": "A .env file is committed", "severity": "high", "preview": ""})
        for number, line in enumerate(text.splitlines(), 1):
            if len(line) > 600:
                continue
            for kind, pattern, severity in RULES:
                match = pattern.search(line)
                value = match.group(match.lastindex or 0) if match else ""
                if match and not PLACEHOLDER.search(line if severity == "medium" else value):
                    findings.append({"file": path, "line": number, "kind": kind, "severity": severity, "preview": mask(value)})
                    break
    return findings[:50]
