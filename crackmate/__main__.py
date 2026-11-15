"""The CrackMate command line:  python -m crackmate <command>   (or ./crackmate_cli <command>)"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from api.deps import build_core
from api.services import career
from api.services.profiles import create_from_resume
from core.career import repo as repo_mod
from core.resume import ResumeError, read_upload, reviewed_text
from crackmate import tools
from crackmate.tools import CrackError

GRADES = {"1": "Again", "2": "Hard", "3": "Good", "4": "Easy"}
URL_BASE = "http://127.0.0.1:8000"


def table(rows, headers):
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]
    line = lambda r: "  ".join(str(c).ljust(w) for c, w in zip(r, widths)).rstrip()
    return "\n".join([line(headers), line(["-" * w for w in widths]), *map(line, rows)])


def attach(core, record, url, hint, progress):
    """Attach a repo to a project: by name (URL=Project), by repo name, or the only project."""
    projects = record.profile.projects
    if not projects:
        raise CrackError("Add a project to the profile first.")
    repo_name = url.rstrip("/").split("/")[-1].removesuffix(".git").casefold()
    pick = [p for p in projects if hint and hint.casefold() in p.title.casefold()] or [p for p in projects if repo_name in p.title.casefold().replace(" ", "-")] or (projects if len(projects) == 1 else [])
    if len(pick) != 1:
        raise CrackError(f"Which project is {url} for? Use --repo {url}=<project name>. Projects: {', '.join(p.title for p in projects)}.")
    return career.attach(core, record, pick[0].id, url, None, False, progress)["repo"]


def run(args, core, out, read):
    cmd = args.command
    if cmd == "profiles":
        rows = tools.profiles(core)
        out(table([[p["id"], p["name"], p["role"], p["projects"]] for p in rows], ["ID", "NAME", "ROLE", "PROJECTS"]) if rows else "No profiles yet.")
        return 0
    if cmd == "init":
        path = Path(args.resume)
        data = path.read_bytes() if path.is_file() else None
        if data is None:
            raise CrackError(f"Cannot find {args.resume}.")
        limits = core.settings.limits
        text = reviewed_text(data.decode("utf-8", "ignore"), limits) if path.suffix.lower() in (".txt", ".md") else read_upload(path.name, data, limits)
        if not core.settings.api_key:
            raise CrackError("Set GROQ_API_KEY (environment or .streamlit/secrets.toml) to extract a profile.")
        if not args.yes and read("This sends the resume text to Groq to extract your profile. Continue? [y/N] ").strip().lower() not in ("y", "yes"):
            raise CrackError("Cancelled. Nothing was sent.")
        made = create_from_resume(core, text, {"role": args.role, "company": args.company}, True, lambda m: out(f"  {m}"))
        record = core.store.get(made["id"])
        out(f"Created profile {record.id[:8]} with {len(record.profile.projects)} project(s): {', '.join(p.title for p in record.profile.projects) or 'none found'}.")
        for spec in args.repo or []:
            url, _, hint = spec.partition("=")
            out(f"Reading {url} …")
            repo = attach(core, record, url, hint, lambda m: out(f"  {m}"))
            out(f"  {repo['facts']['loc']:,} lines; stack: {', '.join(t['name'] for t in repo['facts']['technologies'][:8]) or 'none detected'}.")
        _show_next(core, record, out)
        return 0
    record = tools.resolve_profile(core, getattr(args, "profile", None))
    if cmd == "update":
        rows = tools.update_repos(core, record, lambda m: out(f"  {m}"))
        out("\n".join(f"{'Updated ' if r['changed'] else 'Up to date'}  {r['url']}" for r in rows) or "No repositories attached. Add one in the web app (Learn → Projects) or with `init --repo`.")
    elif cmd == "next":
        _show_next(core, record, out)
    elif cmd == "risk":
        rows = tools.weak_spots(core, record, args.n)
        out(table([[r["topic"], f"{r['risk']:.1f}", f"{r['readiness']}/10" if r["assessed"] else "not assessed"] for r in rows], ["TOPIC", "RISK /10", "READINESS"]) if rows else "No risk yet. Add a project with technologies first.")
        out("\nRisk = how likely a topic is to come up x how weak you are on it. Run `crackmate next` for the one to do first.")
    elif cmd == "brief":
        text = tools.interview_brief(core, record)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            out(f"Wrote {args.output} ({len(text):,} characters).")
        else:
            out(text)
    elif cmd == "quiz":
        return _quiz(core, record, args, out, read)
    elif cmd == "serve":
        if not Path("web/out").is_dir():
            out("The web app is not built yet; run ./run.sh once. Starting the API only.")
        out(f"Open {URL_BASE}  (Ctrl+C to stop)")
        os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(args.port)])
    elif cmd == "mcp":
        from crackmate.mcp_server import serve
        serve()
    return 0


def _show_next(core, record, out):
    nxt = tools.study_next(core, record)
    if nxt is None:
        out("Nothing to study yet. Add a project with its technologies.")
        return
    out(f"Study first: {nxt['topic']}\n  {nxt['reason']}\n  {nxt['do']}")


def _quiz(core, record, args, out, read):
    deck = tools.cards(core, record, args.topic, args.level)[:args.n]
    if not deck:
        out("No questions available yet. Generate a lesson in the web app (Learn → Skills), or run `crackmate quiz` after you have due reviews.")
        return 0
    out(f"{len(deck)} card(s). Answer out loud first, then press Enter to reveal.  Rate: 1 Again  2 Hard  3 Good  4 Easy  (q to quit)\n")
    for i, card in enumerate(deck, 1):
        out(f"[{i}/{len(deck)}]{' (due)' if card['due'] else ''}  {card['question']}")
        if read("  Enter to reveal… ").strip().lower() == "q":
            break
        out(f"\n  {card['answer']}\n")
        choice = read("  How well did you recall it? [1-4] ").strip().lower()
        if choice == "q":
            break
        if choice in GRADES:
            days = tools.rate(core, record, card, GRADES[choice])
            out("  " + ("Due again today.\n" if days == 0 else f"Next review in {days} day(s).\n"))
    return 0


def parser():
    p = argparse.ArgumentParser(prog="crackmate", description="Free, open-source interview preparation. For practice only, never during a real interview.")
    sub = p.add_subparsers(dest="command", required=True)
    def add(name, help_, profile=True):
        s = sub.add_parser(name, help=help_)
        if profile:
            s.add_argument("--profile", help="profile id (default: the newest, or $CRACKMATE_PROFILE)")
        return s
    add("profiles", "list your profiles", profile=False)
    s = add("init", "create a profile from a resume and optional GitHub repos", profile=False)
    s.add_argument("--resume", required=True, help="a .pdf, .tex, .txt or .md file")
    s.add_argument("--repo", action="append", metavar="URL[=PROJECT]", help="a public GitHub repo; repeat for more")
    s.add_argument("--role"); s.add_argument("--company")
    s.add_argument("--yes", action="store_true", help="agree to send the resume text to Groq without asking")
    add("update", "re-read attached repositories (only if their commit changed)")
    add("next", "the single best thing to study right now")
    s = add("risk", "your top interview-risk topics"); s.add_argument("-n", type=int, default=10)
    s = add("brief", "write your Interview Brief as Markdown"); s.add_argument("-o", "--output")
    s = add("quiz", "terminal flashcards with spaced repetition")
    s.add_argument("--topic"); s.add_argument("--level", default="Basics", choices=tools.LEVELS); s.add_argument("-n", type=int, default=5)
    s = add("serve", "start the web app and API", profile=False); s.add_argument("--port", type=int, default=8000)
    add("mcp", "start the MCP server (stdio) for Claude and other MCP hosts", profile=False)
    return p


def main(argv=None, core_factory=build_core, out=print, read=input):
    args = parser().parse_args(argv)
    try:
        return run(args, core_factory(), out, read)
    except (CrackError, ResumeError, repo_mod.RepoError, ValueError) as exc:
        out(f"crackmate: {exc}")
        return 1
    except KeyboardInterrupt:
        out("\nStopped.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
