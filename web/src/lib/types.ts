export type Project = {
  id: string; title: string; summary: string; technologies: string[]; contribution: string;
  implementation: string; clarification: Record<string, string>; reference: string;
};
export type Profile = {
  name: string | null; summary: string | null; experience_level: string | null; skills: Record<string, string[]>;
  work_experience: string[]; education: string[]; projects: Project[];
  role: string | null; company: string | null; job_description: string | null;
};
export type ProfileRecord = { id: string; revision: number; profile: Profile };
export type FormLabels = { skill_labels: Record<string, string>; clarifications: Record<string, string> };

export type QA = { question: string; answer: string; hint: string; qid: string };
export type Passage = { id: string; title: string; location: string; text: string; license?: string };
export type LessonView = {
  slot: string; title: string; model: string; kind: "project" | "skill"; completed: boolean;
  sections: { label: string; body: string }[]; questions: QA[]; follow_ups: QA[]; exercise: string;
  assumptions: string | null; evidence_note: string; passages: Passage[];
};
export type LessonState = {
  slot: string; title: string; status: "current" | "outdated" | "shared" | "none"; shared_available: boolean;
  can_tailor: boolean; item: LessonView | null; fresh?: boolean;
};
export type LessonRef = { kind: "project" | "skill"; project_id?: string; section?: string; topic?: string; level?: string };
export type SectionRow = { section: string; scope: string; slot: string; status: "current" | "outdated" | "none"; completed: boolean };
export type TopicList = { levels: string[]; sections: Record<string, string>; groups: { title: string; topics: string[] }[]; shared_lessons: number };
export type ArtifactState<T> = { kind: string; title: string; status: "current" | "outdated" | "none"; model: string | null; digest: string | null; data: T | null; ticked?: number[] };
export type Claim = { claim: string; source: string; kind: string; risk: "low" | "medium" | "high"; why: string; probe: string; defend: string; prepare: string };
export type ClaimReport = { claims: Claim[] };
export type PitchData = { opening: string; pitch: string; key_points: string[]; assumptions: string };
export type DiagramData = { diagram: string; assumptions: string };
export type LadderStep = { level: string; question: string; answer: string };
export type DueCard = { slot: string; question: string; answer: string; hint: string };
export type Dashboard = {
  readiness: { overall: number | null; assessed: number; total: number };
  weakest: { name: string; score: number }[];
  queue: { name: string; activity: string; duration: number; reason: string; topic: string }[];
  due_reviews: number; lessons: { saved: number; completed: number }; attempts: number; interview: string | null; projects: number;
};

export type FeedbackData = {
  scores: { key: string; label: string; score: number; reason: string }[]; scale: string;
  correct: string; missing: string; corrected: string; follow_up: string; evidence_note: string;
};
export type PracticeFocus = { slot: string; title: string; questions: { question: string; hint: string }[] };
export type Attempt = { id: string; focus: string; question: string; answer: string; created_at: string; feedback: FeedbackData };
export type InterviewOptions = { modes: string[]; levels: string[]; topics: string[]; projects: { id: string; title: string }[]; open_claims: number; audio_seconds: number; audio_mb: number };
export type InterviewSummary = { id: string; mode: string; topic: string; difficulty: string; state: string; index: number; budget: number };
export type InterviewTurn = {
  id: string; question: string; kind: "technical" | "behavioural"; depth: number; hint: string | null; hint_used: boolean;
  original: string; confirmed: string; retries: number; has_feedback: boolean; feedback: FeedbackData | null; can_follow_up: boolean;
};
export type InterviewView = InterviewSummary & { coach: boolean; spoken: boolean; project_id: string; turn: InterviewTurn | null };
export type InterviewReport = { state: string; markdown: string; scores: { label: string; average: number; count: number }[]; study_next: { topic: string; href: string }[]; scored: number; skipped: number };

export type PlanBlock = { start: string; end: string; minutes: number; topic: string; reason: string; outcome: string; href: string | null };
export type PlanState = {
  status: "none" | "current" | "outdated"; now: string;
  defaults: { interview: string; hours: number; weak_areas: string; role_context: string };
  plan: { interview: string; total_minutes: number; minutes_until: number; blocks: PlanBlock[] } | null;
};
export type TopicRow = { id: string; name: string; category: string; state: string; due: string | null; count: number; readiness: number | null };
export type Progress = { readiness: { overall: number | null; assessed: number; total: number }; topics: TopicRow[] };
export type TopicDetail = { id: string; name: string; state: string; due: string | null; count: number; limitation: string; evidence: { question: string; source: string; time: string | null; scores: Record<string, number>; missing: string; independent: boolean | null }[] };
export type QueueItem = { topic: string; name: string; reason: string; duration: number; activity: string };
export type LearningSettings = { timezone: string; interview: string; daily_minutes: number; session_minutes: number; unavailable: string[]; priorities: string[]; threshold: number; successes: number; intervals: number[] };
export type PlanActivity = { id: string; date: string; name: string; duration: number; activity: string; reason: string; outcome: string; completed: boolean; pinned: boolean };
export type Proposal = { id: string; reason: string; blocks: PlanActivity[]; active_count: number };
export type Source = { id: string; title: string; location: string; kind: string; retrieved: string; license: string; status: string; error: string };
export type SearchPassage = { id: string; title: string; heading: string; text: string; location: string; license?: string };
export type CompanyProblem = { Title: string; Difficulty: string; Frequency: number; Topics: string; Link: string };

export type RepoTech = { name: string; confidence: number; evidence: { kind: string; file: string }[] };
export type RepoView = {
  project_id: string; url: string; commit: string; indexed_at: string; identities: string[];
  facts: { technologies: RepoTech[]; languages: Record<string, number>; loc: number; files: number; top_dirs: string[] };
  authors: { name: string; email: string; commits: number; added: number }[];
  ownership: { identified: boolean; commits: number; your_commits: number; share: number; files_yours: { path: string; yours: number; lines: number }[]; files_not_yours: { path: string; yours: number; lines: number }[] };
  hotspots: { path: string; commits: number; churn: number; your_commits: number; score: number }[];
  secrets: { file: string; line: number; kind: string; severity: "high" | "medium"; preview: string }[];
};
export type ProjectCard = { project_id: string; title: string; repo: RepoView | null; unsupported: string[]; undeclared: string[] };

export type RiskRow = { topic: string; assessed: boolean; readiness: number | null; likelihood: number; risk: number; trend: "up" | "down" | "flat"; projects: number; dependents: number; why: string[] };
export type Signals = { overall: number | null; assessed: number; total: number; topics: RiskRow[] };
export type StudyItem = { topic: string; risk: number; assessed: boolean; readiness: number | null; reason: string };
export type CareerSummary = { stale_pages: number; readiness: { overall: number | null; assessed: number; total: number }; mastered: number; high_risk: number; days_to_interview: number | null; study_first: StudyItem[]; repos: number; projects: number };
export type Blast = { topic: string; concepts: string[]; technologies: string[]; projects: string[]; questions: number };
export type ClaimRow = { project_id: string; project: string; technology: string; tier: "High" | "Medium" | "Low" | "Unchecked"; tier_note: string; evidence: { kind: string; file: string }[]; confidence: number | null; readiness: number | null; risk: number; weakest_concept: string | null };

export type GraphNode = { id: string; type: "you" | "project" | "technology" | "concept"; label: string; project_id?: string };
export type GraphEdge = { source: string; target: string; kind: string; confidence: number; evidence: string[] };
export type CareerGraph = { nodes: GraphNode[]; edges: GraphEdge[]; unsupported: { project: string; technology: string }[]; undeclared: { project: string; technology: string }[] };
export type SecurityProject = { project_id: string; title: string; has_repo: boolean; url: string | null; secrets: RepoView["secrets"]; questions: string[] };
export type SecurityReport = { projects: SecurityProject[]; remediation: string[] };

export type UsageSummary = {
  window_hours: number; calls: number; cached: number; saved_tokens: number; tokens_in: number; tokens_out: number; note: string;
  by_feature: { feature: string; calls: number; cached: number; tokens: number }[];
  by_model: { model: string; tokens: number; limit: number; remaining: number }[];
  days: { date: string; calls: number; cached: number; tokens: number }[];
};

export type WikiRow = { slot: string; group: string; title: string; kind: string; status: "fresh" | "stale" | "none"; why: string; model: string | null; href: string };
export type DecisionData = { decisions: { title: string; decision: string; alternatives: string[]; evidence: { kind: "commit" | "readme" | "dependency"; ref: string; quote: string }[]; tradeoff_question: string; answer: string; confidence: "high" | "medium" | "low"; assumption: string }[] };

export type Citation = { n: number; kind: "resume" | "repo" | "lesson" | "knowledge"; title: string; location: string; license: string; text: string };
export type ChatMessage = { role: "user" | "assistant"; text: string; sources?: Citation[]; pending?: boolean; error?: string };
export type AskStatus = { indexed: Record<string, number>; passages: number; knowledge_sources: number; suggestions: string[] };
export type Brief = { markdown: string; checklist: { pitches: [number, number]; decisions: [number, number]; lessons: number; claim_check: boolean; repos: number } };
