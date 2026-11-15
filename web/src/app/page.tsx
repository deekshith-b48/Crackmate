"use client";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, CalendarClock, Check, FileUp, GraduationCap, RefreshCw, Repeat, Target } from "lucide-react";
import Link from "next/link";
import { MiniGraph } from "@/components/analyse/MiniGraph";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ReadinessRing } from "@/components/ui/ReadinessRing";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { lessonHref, riskTone, useSummary } from "@/lib/career";
import { useProfiles } from "@/lib/profile";
import type { Dashboard } from "@/lib/types";

const band = (v: number | null) => (v === null ? "Answer a few questions to get your first score." : v >= 7.5 ? "Strong. Keep your reviews up." : v >= 5 ? "Building nicely. Target the weak spots." : "Getting started. Every answer counts.");

export default function Home() {
  const { active, loading } = useProfiles();
  const pid = active?.id;
  const { data: career } = useSummary(pid);
  const { data } = useQuery({ queryKey: ["dashboard", pid], queryFn: () => api.get<Dashboard>(`/api/profiles/${pid}/dashboard`), enabled: !!pid });

  if (!loading && !active) {
    return (
      <>
        <PageHeader title="Welcome to CrackMate" description="Upload your resume and get lessons, practice and a plan that fit your projects." />
        <EmptyState icon={FileUp} title="Upload your resume to start" text="CrackMate reads your projects and skills, teaches the concepts from basics to advanced, then lets you practise out loud."
          action={<Link href="/setup/"><Button variant="primary">Get started</Button></Link>} />
      </>
    );
  }

  const name = active?.name?.split(" ")[0];
  const steps = [
    { label: "Set up your profile", href: "/setup/", done: !!active },
    { label: "Learn a project or skill", href: "/learn/projects/", done: (data?.lessons.saved ?? 0) > 0 },
    { label: "Practise out loud", href: "/practice/interview/", done: (data?.attempts ?? 0) > 0 || (data?.readiness.assessed ?? 0) > 0 },
    { label: "Plan your last hours", href: "/plan/", done: false },
  ];
  const next = steps.find((s) => !s.done);

  return (
    <>
      <PageHeader title={name ? `Hello, ${name}` : "Your dashboard"} description="Here is where you stand and what to do next." />
      <div className="space-y-6">
        {(career?.stale_pages ?? 0) > 0 && (
          <Link href="/learn/wiki/" className="flex items-center gap-3 rounded-[var(--radius-card)] border border-amber-200 bg-warn-tint px-4 py-3 text-sm text-ink hover:border-amber-300">
            <RefreshCw className="size-4 text-warn" aria-hidden /><span><strong>{career!.stale_pages} page{career!.stale_pages === 1 ? " is" : "s are"} out of date.</strong> Your profile or repository changed since they were written.</span><ArrowRight className="ml-auto size-4" />
          </Link>
        )}
        <div className="grid gap-6 md:grid-cols-[auto_1fr]">
          <Card className="flex flex-col items-center gap-3 md:px-10">
            <p className="text-sm font-medium text-muted">Overall readiness</p>
            <ReadinessRing value={career?.readiness.overall ?? null} max={10} />
            <p className="max-w-52 text-center text-sm text-muted">{band(career?.readiness.overall ?? null)}</p>
            {career && <p className="text-xs text-muted">{career.readiness.assessed} of {career.readiness.total} topics assessed · scored 1 to 10</p>}
          </Card>
          <div className="grid content-start gap-4 sm:grid-cols-3">
            <Link href="/analyse/risk/"><Card className="h-full transition-colors hover:border-brand-200"><Activity className="mb-3 size-5 text-brand-600" /><p className={cn("text-3xl font-semibold", (career?.high_risk ?? 0) > 0 ? "text-bad" : "text-ink")}>{career?.high_risk ?? 0}</p><p className="text-sm text-muted">high-risk topics</p></Card></Link>
            <Card><GraduationCap className="mb-3 size-5 text-brand-600" /><p className="text-3xl font-semibold text-ink">{career?.mastered ?? 0}<span className="text-lg font-normal text-muted"> / {career?.readiness.total ?? 0}</span></p><p className="text-sm text-muted">topics mastered</p></Card>
            <Link href="/plan/"><Card className="h-full transition-colors hover:border-brand-200"><CalendarClock className="mb-3 size-5 text-brand-600" /><p className="text-3xl font-semibold text-ink">{career?.days_to_interview ?? "—"}</p><p className="text-sm text-muted">{career?.days_to_interview === null || career?.days_to_interview === undefined ? "set your interview date" : "days to interview"}</p></Card></Link>
            <Link href="/practice/review/"><Card className="h-full transition-colors hover:border-brand-200"><Repeat className="mb-3 size-5 text-brand-600" /><p className="text-3xl font-semibold text-ink">{data?.due_reviews ?? 0}</p><p className="text-sm text-muted">questions due today</p></Card></Link>
            <Card><Check className="mb-3 size-5 text-brand-600" /><p className="text-3xl font-semibold text-ink">{data?.lessons.completed ?? 0}<span className="text-lg font-normal text-muted"> / {data?.lessons.saved ?? 0}</span></p><p className="text-sm text-muted">lessons completed</p></Card>
            <Card><Target className="mb-3 size-5 text-brand-600" /><p className="text-3xl font-semibold text-ink">{career?.projects ?? 0}</p><p className="text-sm text-muted">projects to defend{career ? ` · ${career.repos} with code` : ""}</p></Card>
            <Card className="sm:col-span-3">
              <p className="mb-3 text-sm font-semibold text-ink">Your workflow</p>
              <ol className="grid gap-2 sm:grid-cols-2">
                {steps.map((s, i) => (
                  <li key={s.label}><Link href={s.href} className={cn("flex items-center gap-3 rounded-[var(--radius-control)] border px-3 py-2 text-sm transition-colors", s.done ? "border-green-200 bg-good-tint text-good" : s === next ? "border-brand-200 bg-brand-50 font-medium text-brand-700" : "border-line text-body hover:bg-slate-50")}>
                    <span className={cn("flex size-5 items-center justify-center rounded-full text-[11px] font-semibold", s.done ? "bg-good text-white" : "bg-slate-200 text-slate-600")}>{s.done ? <Check className="size-3" /> : i + 1}</span>{s.label}{s === next && <ArrowRight className="ml-auto size-4" />}
                  </Link></li>
                ))}
              </ol>
            </Card>
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold text-ink">Study first</h2><Link href="/practice/study-first/" className="text-sm text-brand-700 hover:underline">See all</Link></div>
            {career?.study_first.length ? (
              <ul className="divide-y divide-line">
                {career.study_first.map((q) => (
                  <li key={q.topic} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                    <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold", riskTone(q.risk) === "bad" ? "bg-bad-tint text-bad" : riskTone(q.risk) === "warn" ? "bg-warn-tint text-warn" : "bg-good-tint text-good")} title={q.reason}>{q.risk.toFixed(1)}</span>
                    <div className="min-w-0 flex-1"><p className="truncate font-medium text-ink">{q.topic}</p><p className="truncate text-xs text-muted">{q.assessed ? `Readiness ${q.readiness}/10` : "Not assessed yet"}</p></div>
                    <Link href={lessonHref(q.topic)}><Button size="sm">Start</Button></Link>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted">Add a project and its technologies to see what to study first.</p>}
          </Card>
          <Card>
            <h2 className="mb-3 font-semibold text-ink">Today&apos;s study queue</h2>
            {data?.queue.length ? (
              <ul className="divide-y divide-line">
                {data.queue.map((q) => (
                  <li key={q.topic} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0 flex-1"><p className="truncate font-medium text-ink">{q.name}</p><p className="text-xs text-muted">{q.activity} · {q.duration} min · {q.reason}</p></div>
                    <Link href={`/learn/skills/?topic=${encodeURIComponent(q.name)}`}><Button size="sm">Open</Button></Link>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted">Your study queue will appear here once you have a profile.</p>}
          </Card>
          <Card>
            <h2 className="mb-3 font-semibold text-ink">Weakest topics</h2>
            {data?.weakest.length ? (
              <ul className="space-y-3">
                {data.weakest.map((w) => (
                  <li key={w.name}><div className="mb-1 flex justify-between text-sm"><span className="text-ink">{w.name}</span><span className="text-muted">{w.score}</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-600" style={{ width: `${w.score}%` }} /></div></li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted">Nothing assessed yet. Practise a few questions and your weak spots will show up here.</p>}
          </Card>
        </div>
        {pid && <MiniGraph pid={pid} />}
      </div>
    </>
  );
}
