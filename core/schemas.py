"""Validated data at the provider and storage boundaries."""
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Tags = Annotated[list[Short], Field(max_length=40)]


class Data(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Skills(Data):
    language: Tags = Field(default_factory=list)
    frontend: Tags = Field(default_factory=list)
    backend: Tags = Field(default_factory=list)
    database: Tags = Field(default_factory=list)
    cloud_devops: Tags = Field(default_factory=list)
    tools: Tags = Field(default_factory=list)
    other: Tags = Field(default_factory=list)


class ProjectDraft(Data):
    title: Short
    summary: str = Field(default="", max_length=2400)
    technologies: Tags = Field(default_factory=list)
    contribution: str = Field(default="", max_length=2400)
    implementation: str = Field(default="", max_length=3500)

    @field_validator("summary", "contribution", "implementation", mode="before")
    @classmethod
    def unknown_as_empty(cls, value):
        return "" if value is None else value


class Project(ProjectDraft):
    id: str = Field(default_factory=lambda: uuid4().hex)
    clarification: dict[str, str] = Field(default_factory=dict)
    reference: str = Field(default="", max_length=3500)


class Background(Data):
    name: Short | None = None
    summary: Text | None = None
    experience_level: Short | None = None
    skills: Skills = Field(default_factory=Skills)
    work_experience: list[Text] = Field(default_factory=list, max_length=25)
    education: list[Text] = Field(default_factory=list, max_length=15)


class ProfileDraft(Background):
    projects: list[ProjectDraft] = Field(default_factory=list, max_length=20)


class Profile(Background):
    projects: list[Project] = Field(default_factory=list, max_length=20)
    role: Short | None = None
    company: Short | None = None
    job_description: Text | None = None

    @classmethod
    def from_draft(cls, draft: ProfileDraft, **target):
        return cls(**draft.model_dump(), **target)


class Question(Data):
    question: Short
    answer: Text
    hint: Short


class Citation(Data):
    passage_id: Short
    claim: Text
    quote: str = Field(default="", max_length=250)


class Grounded(Data):
    citations: list[Citation] = Field(default_factory=list, max_length=20)
    evidence: list[dict] = Field(default_factory=list, max_length=4)


class ProjectLesson(Grounded):
    prerequisites: list[Short] = Field(min_length=1, max_length=8)
    terms: list[Short] = Field(min_length=1, max_length=12)
    explanation: Text
    example: Text
    project_application: Text
    questions: list[Question] = Field(min_length=6, max_length=6)
    follow_ups: list[Question] = Field(min_length=2, max_length=2)
    exercise: Text
    assumptions: Text


class CodingExample(Data):
    problem: Text
    approach: Text
    solution: Text
    walkthrough: Text
    edge_cases: Text
    complexity: Text


class SkillLesson(Grounded):
    prerequisites: list[Short] = Field(min_length=1, max_length=8)
    explanation: Text
    example: Text
    mistakes: list[Short] = Field(min_length=1, max_length=10)
    questions: list[Question] = Field(min_length=5, max_length=5)
    exercise: Text
    coding: CodingExample | None = None


class Score(Data):
    score: int = Field(ge=0, le=4, strict=True)
    reason: Text


class Feedback(Grounded):
    learning_metadata: dict = Field(default_factory=dict)
    accuracy: Score
    coverage: Score
    reasoning: Score
    clarity: Score
    correct: Text
    missing: Text
    corrected: Text
    follow_up: Short


class StudyBlock(Data):
    duration_minutes: int = Field(ge=1, le=50, strict=True)
    topic: Short
    reason: Text
    outcome: Text
    reference: Short | None = None


class PlanDraft(Data):
    blocks: list[StudyBlock] = Field(max_length=48)


class Claim(Data):
    claim: Short
    source: Short
    kind: Literal["metric", "technology", "ownership", "scale", "other"]
    risk: Literal["low", "medium", "high"]
    why: Short
    probe: Short
    defend: Text
    prepare: Text


class ClaimReport(Data):
    claims: list[Claim] = Field(min_length=1, max_length=30)


class Pitch(Data):
    opening: Short
    pitch: Text
    key_points: list[Short] = Field(min_length=3, max_length=6)
    assumptions: Text


LADDER = ("why", "how", "what_if_it_fails", "how_does_it_scale")


class LadderStep(Data):
    level: Literal["why", "how", "what_if_it_fails", "how_does_it_scale"]
    question: Short
    answer: Text


class Ladder(Data):
    steps: list[LadderStep] = Field(min_length=4, max_length=4)

    @field_validator("steps")
    @classmethod
    def in_order(cls, steps):
        if tuple(step.level for step in steps) != LADDER:
            raise ValueError("Steps must follow why, how, what_if_it_fails, how_does_it_scale.")
        return steps


class Diagram(Data):
    diagram: Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=4000)]
    assumptions: Text

    @field_validator("diagram")
    @classmethod
    def flowchart_only(cls, value):
        if not value.startswith(("flowchart ", "graph ")) or "%%{" in value or "```" in value:
            raise ValueError("Use a plain Mermaid flowchart without directives or code fences.")
        return value


class DecisionEvidence(Data):
    kind: Literal["commit", "readme", "dependency"]
    ref: Short
    quote: str = Field(default="", max_length=200)


class Decision(Data):
    title: Short
    decision: Text
    alternatives: list[Short] = Field(default_factory=list, max_length=4)
    evidence: list[DecisionEvidence] = Field(min_length=1, max_length=4)
    tradeoff_question: Short
    answer: Text
    confidence: Literal["high", "medium", "low"]
    assumption: str = Field(default="", max_length=500)


class DecisionSet(Data):
    decisions: list[Decision] = Field(min_length=1, max_length=6)
