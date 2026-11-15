import {
  Activity, BookOpenCheck, Building2, ClipboardList, MessageSquare, ClipboardCheck, Compass, FileCheck2, FileText, Flame, GitCommitHorizontal, GraduationCap, Home, Library, LineChart,
  ListOrdered, Lock, Mic, Network, Radar, Scale, Repeat, ShieldCheck, Sparkles, Gauge, UploadCloud, Workflow, type LucideIcon,
} from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon; hint: string };
export type NavGroup = { title: string; items: NavItem[] };

// The workflow: set up once, learn, practise out loud, plan the last hours, then track.
export const NAV: NavGroup[] = [
  { title: "Overview", items: [{ href: "/", label: "Home", icon: Home, hint: "Your readiness and what to do next" }] },
  {
    title: "Setup",
    items: [
      { href: "/setup/", label: "Resume and profile", icon: UploadCloud, hint: "Upload your resume and review your profile" },
    ],
  },
  {
    title: "Learn",
    items: [
      { href: "/learn/projects/", label: "Projects", icon: Workflow, hint: "Learn the concepts behind each project" },
      { href: "/learn/skills/", label: "Skills", icon: GraduationCap, hint: "Topics from basics to advanced" },
      { href: "/learn/wiki/", label: "Study wiki", icon: BookOpenCheck, hint: "Every page with a freshness badge" },
      { href: "/learn/claims/", label: "Claim Checker", icon: ShieldCheck, hint: "Find resume lines you must defend" },
      { href: "/learn/pitch/", label: "Project Pitch", icon: Sparkles, hint: "A 2-minute pitch to rehearse" },
      { href: "/learn/architecture/", label: "Architecture", icon: Compass, hint: "Likely architecture diagrams" },
      { href: "/learn/library/", label: "Knowledge Library", icon: Library, hint: "Trusted sources behind your lessons" },
      { href: "/learn/company/", label: "Company DSA", icon: Building2, hint: "Problems a company asks most" },
    ],
  },
  {
    title: "Practice",
    items: [
      { href: "/practice/study-first/", label: "Study first", icon: ListOrdered, hint: "The topics most likely to hurt you, in order" },
      { href: "/practice/brief/", label: "Interview brief", icon: ClipboardList, hint: "Everything you prepared, in one document" },
      { href: "/practice/review/", label: "Review today", icon: Repeat, hint: "Spaced-repetition questions due" },
      { href: "/practice/session/", label: "Practice", icon: ClipboardCheck, hint: "Answer questions and get feedback" },
      { href: "/practice/interview/", label: "Interview Room", icon: Mic, hint: "Mock interview with your voice" },
    ],
  },
  {
    title: "Analyse",
    items: [
      { href: "/analyse/graph/", label: "Knowledge graph", icon: Network, hint: "You, projects, technologies and concepts" },
      { href: "/analyse/risk/", label: "Interview risk", icon: Activity, hint: "Likelihood times weakness, per topic" },
      { href: "/analyse/blast/", label: "Concept blast radius", icon: Radar, hint: "Everything that depends on one concept" },
      { href: "/analyse/decisions/", label: "Decisions", icon: Scale, hint: "Why you chose X, mined from your code" },
      { href: "/analyse/claims/", label: "Resume claims", icon: FileCheck2, hint: "Which technologies the code backs up" },
      { href: "/analyse/built/", label: "What you built", icon: GitCommitHorizontal, hint: "Your share of each project's code" },
      { href: "/analyse/talking-points/", label: "Talking points", icon: Flame, hint: "The files where the hard problems were" },
      { href: "/analyse/security/", label: "Security check", icon: Lock, hint: "Committed secrets and likely security questions" },
    ],
  },
  {
    title: "Plan",
    items: [{ href: "/plan/", label: "Preparation plan", icon: FileText, hint: "Fit study into the hours you have" }],
  },
  {
    title: "Track",
    items: [{ href: "/track/", label: "Progress", icon: LineChart, hint: "Readiness, weak spots and study queue" }],
  },
  {
    title: "System",
    items: [{ href: "/system/ask/", label: "Ask CrackMate", icon: MessageSquare, hint: "A chat that cites its sources" }, { href: "/system/usage/", label: "Usage", icon: Gauge, hint: "Model calls, cache savings and free-tier headroom" }],
  },
];

