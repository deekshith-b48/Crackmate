"""CrackMate as an MCP server, so you can study inside Claude or any MCP host.

Run:  ./crackmate_cli mcp   (stdio). Add it to a host with the command  <project folder>/crackmate_cli mcp
Nothing here helps during a real interview: it is for preparation and mock practice only.
Tools read your local data. No model key is needed: prepare_* tools hand the writing and scoring to your assistant and save_* tools store the result.
grade_answer is an optional shortcut that uses a Groq key instead.
"""
import functools
import sys

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from api.deps import build_core
from api.errors import describe
from crackmate import tools

INSTRUCTIONS = ("CrackMate helps a candidate prepare for interviews from their resume and project code. Use get_study_next to pick what to study, "
                "quiz_me to practise, and search_knowledge for cited sources. You (the assistant) are the model, so no API key is needed: "
                "to create a lesson call prepare_lesson, write the JSON it asks for (follow `instructions` and `schema` exactly, return only JSON), then call save_lesson. "
                "To score an answer call prepare_grading, score it honestly against the rubric, then call save_grading. Never invent sources or claims about the candidate's code. "
                "For preparation and mock practice only: never use it to help someone during a live interview.")


def build_server(core_factory=build_core):
    server = MCPServer("crackmate", instructions=INSTRUCTIONS)
    cache = {}

    def tool(fn):
        """Register fn, turning any failure into a readable tool error (a host needs the message to recover, for example 'Did you mean…')."""
        @functools.wraps(fn)
        def safe(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except ToolError:
                raise
            except Exception as exc:  # noqa: BLE001 - describe() maps known errors to friendly text and hides internals of unknown ones
                raise ToolError(describe(exc)[1]) from None
        return server.tool()(safe)

    def core_only():
        if "core" not in cache:
            cache["core"] = core_factory()
        return cache["core"]

    def ctx():
        core = core_only()
        return core, tools.resolve_profile(core)

    @tool
    def create_profile(resume_text: str) -> dict:
        """Start a profile from resume text (no API key needed). Returns instructions and a schema: extract the profile yourself, then call save_profile."""
        return tools.prepare_profile(core_only(), resume_text)

    @tool
    def save_profile(task_id: str, profile: dict, role: str = "", company: str = "") -> dict:
        """Save the profile you extracted for a create_profile task. Optionally set the target role and company."""
        return tools.save_profile(core_only(), task_id, profile, role, company)

    @tool
    def attach_repo(url: str, project: str = "") -> dict:
        """Read a public GitHub repository for a project (stack, ownership, hotspots; no model used). project is optional when the repo name matches or there is one project."""
        c, r = ctx(); repo = tools.attach(c, r, url, project, lambda _: None)
        return {"url": url, "lines": repo["facts"]["loc"], "stack": [t["name"] for t in repo["facts"]["technologies"][:8]]}

    @tool
    def get_profile() -> dict:
        """The candidate's profile (skills, projects, experience). Contact details are removed."""
        c, r = ctx(); return tools.profile(c, r)

    @tool
    def get_overview() -> dict:
        """Readiness out of 10, topics mastered, high-risk topic count, days to interview and the study-first list."""
        c, r = ctx(); return tools.overview(c, r)

    @tool
    def get_lesson(topic: str, level: str = "Basics") -> dict:
        """A saved or shared lesson for a topic (Basics, Intermediate or Advanced) with its questions and answers. Does not call a model."""
        c, r = ctx(); return tools.lesson(c, r, topic, level)

    @tool
    def quiz_me(topic: str = "", n: int = 3) -> list[dict]:
        """Up to n practice questions without answers. Leave topic empty to quiz your riskiest topics. Pass an id to grade_answer."""
        c, r = ctx(); return tools.quiz_me(c, r, topic or None, n)

    @tool
    def grade_answer(question_id: str, answer: str) -> dict:
        """Score a spoken-style answer to a question from quiz_me. Uses the model, and saves the attempt toward readiness."""
        c, r = ctx(); return tools.grade_answer(c, r, question_id, answer)

    @tool
    def prepare_lesson(kind: str = "skill", topic: str = "", level: str = "Basics", project: str = "", section: str = "") -> dict:
        """Start a lesson for YOU to write (no API key needed). kind: skill (give topic, level), project (project, section), claims, pitch or diagram (project). Returns the lesson if it already exists, else instructions, a JSON schema and context. Write the JSON, then call save_lesson."""
        c, r = ctx(); return tools.prepare_lesson(c, r, kind, topic, level, project, section)

    @tool
    def save_lesson(task_id: str, lesson: dict) -> dict:
        """Save the lesson you wrote for a prepare_lesson task. It is checked against the schema and labelled as written by your assistant."""
        c, r = ctx(); return tools.save_lesson(c, r, task_id, lesson)

    @tool
    def prepare_grading(question_id: str, answer: str) -> dict:
        """Start scoring a candidate's answer to a quiz_me question yourself (no API key needed). Returns the rubric, schema and context. Score honestly, then call save_grading."""
        c, r = ctx(); return tools.prepare_grading(c, r, question_id, answer)

    @tool
    def save_grading(task_id: str, feedback: dict) -> dict:
        """Save your scoring for a prepare_grading task. It counts toward readiness like any practice attempt."""
        c, r = ctx(); return tools.save_grading(c, r, task_id, feedback)

    @tool
    def get_weak_spots(n: int = 8) -> list[dict]:
        """The topics with the highest interview risk (likelihood times weakness), with why."""
        c, r = ctx(); return tools.weak_spots(c, r, max(1, min(n, 20)))

    @tool
    def get_study_next() -> dict:
        """The single best thing to study right now, with the reason."""
        c, r = ctx(); return tools.study_next(c, r) or {"message": "Nothing to study yet. Add a project first."}

    @tool
    def get_project_architecture(project: str) -> dict:
        """The saved architecture diagram (Mermaid) for a project, with its labelled assumptions."""
        c, r = ctx(); return tools.architecture(c, r, project)

    @tool
    def search_knowledge(query: str) -> list[dict]:
        """Search your resume, attached repositories, saved lessons and the knowledge base. Every result has a source and location to cite."""
        c, r = ctx(); return tools.search_knowledge(c, r, query)

    @tool
    def get_interview_brief() -> str:
        """The Interview Brief as Markdown: pitches, risks, claims to defend, decisions and key answers."""
        c, r = ctx(); return tools.interview_brief(c, r)

    return server


def serve():
    print("CrackMate MCP server (stdio). Preparation use only.", file=sys.stderr)
    build_server().run()
