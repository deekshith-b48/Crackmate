"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Clock, Download, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Markdown } from "@/components/ui/Markdown";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { useToast } from "@/components/ui/Toast";
import { api, API_BASE } from "@/lib/api";
import { useProfiles, type Status } from "@/lib/profile";
import { useJob } from "@/lib/stream";
import type { PlanState } from "@/lib/types";

const fmt = (iso: string) => new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const hm = (m: number) => `${Math.floor(m / 60)}h ${m % 60}m`;

export default function Plan() {
  const { active } = useProfiles();
  const pid = active?.id;
  const client = useQueryClient();
  const toast = useToast();
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: () => api.get<Status>("/api/status") });
  const { data: state } = useQuery({ queryKey: ["plan", pid], queryFn: () => api.get<PlanState>(`/api/profiles/${pid}/plan`), enabled: !!pid });
  const job = useJob<PlanState>();
  const [form, setForm] = useState({ interview: "", hours: 2, weak_areas: "", role_context: "" });
  useEffect(() => { if (state) setForm({ interview: state.defaults.interview, hours: state.defaults.hours, weak_areas: state.defaults.weak_areas, role_context: state.defaults.role_context }); }, [state]);

  async function build(regenerate: boolean) {
    const next = await job.run(`/api/profiles/${pid}/plan`, { ...form, regenerate });
    if (next) { client.setQueryData(["plan", pid], next); toast("good", regenerate ? "Plan regenerated." : "Plan ready."); }
  }

  const plan = state?.plan;
  return (
    <>
      <PageHeader title="Preparation plan" description="Fit the highest-priority material into the hours you actually have before the interview." />
      {!pid ? <NoProfile /> : (
        <div className="space-y-6">
          <Card className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Interview date and time (your local time)" htmlFor="when"><Input id="when" type="datetime-local" value={form.interview} onChange={(e) => setForm({ ...form, interview: e.target.value })} /></Field>
              <Field label="Available study hours" htmlFor="hours" hint="Up to 24. Sleep (23:00–07:00) and a 15-minute buffer are reserved."><Input id="hours" type="number" min={0.25} max={24} step={0.25} value={form.hours} onChange={(e) => setForm({ ...form, hours: Number(e.target.value) })} /></Field>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Weak areas (optional)" htmlFor="weak"><Textarea id="weak" maxLength={1500} value={form.weak_areas} onChange={(e) => setForm({ ...form, weak_areas: e.target.value })} className="min-h-20" /></Field>
              <Field label="Additional role context (optional)" htmlFor="role"><Textarea id="role" maxLength={1500} value={form.role_context} onChange={(e) => setForm({ ...form, role_context: e.target.value })} className="min-h-20" /></Field>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" onClick={() => build(false)} loading={job.status === "running"} disabled={!status?.has_key || !form.interview}><CalendarClock className="size-4" /> Build plan</Button>
              {plan && <Button onClick={() => build(true)} disabled={!status?.has_key || job.status === "running"}><RefreshCw className="size-4" /> Regenerate plan</Button>}
            </div>
            {job.status === "error" && <p role="alert" className="text-sm text-bad">{job.error}</p>}
          </Card>

          {job.status === "running" && <StepGenerating title="Checking your time and building the plan" steps={job.steps} running startedAt={job.startedAt} />}
          {!plan && job.status !== "running" && <EmptyState icon={CalendarClock} title="See exactly what to study, and when" text="Build a plan to get study blocks with the reason for each and a measurable outcome you can check." />}
          {plan && (
            <>
              {state.status === "outdated" && <p className="rounded-[var(--radius-control)] bg-warn-tint p-3 text-sm text-warn">Outdated: your profile, resources, practice results, model settings or interview timing changed. Regenerate to refresh.</p>}
              <div className="grid gap-4 sm:grid-cols-3">
                <Card className="py-4"><p className="text-sm text-muted">Time until interview</p><p className="text-2xl font-semibold text-ink">{hm(plan.minutes_until)}</p></Card>
                <Card className="py-4"><p className="text-sm text-muted">Planned study time</p><p className="text-2xl font-semibold text-ink">{hm(plan.total_minutes)}</p></Card>
                <Card className="flex items-center justify-between py-4"><div><p className="text-sm text-muted">Status</p><Badge tone={state.status === "current" ? "good" : "warn"}>{state.status === "current" ? "Saved plan" : "Outdated"}</Badge></div><a href={`${API_BASE}/api/profiles/${pid}/plan/export`} download><Button size="sm"><Download className="size-4" /> Download</Button></a></Card>
              </div>
              <p className="text-xs text-muted">Ten-minute breaks between nearby blocks. Times are in your computer’s local time.</p>
              <ol className="relative space-y-4 border-l-2 border-brand-100 pl-6">
                {plan.blocks.map((b, i) => (
                  <li key={b.start} className="relative">
                    <span className="absolute -left-[33px] top-5 flex size-4 items-center justify-center rounded-full border-2 border-brand-600 bg-surface" />
                    <Card className="space-y-3">
                      <div className="flex flex-wrap items-center gap-2"><span className="flex items-center gap-1.5 text-sm font-medium text-brand-700"><Clock className="size-4" />{fmt(b.start)} – {new Date(b.end).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</span><Badge>{b.minutes} min</Badge></div>
                      <h3 className="text-lg font-semibold text-ink">{i + 1}. {b.topic}</h3>
                      <div><p className="text-xs font-medium uppercase tracking-wide text-muted">Reason</p><Markdown>{b.reason}</Markdown></div>
                      <div><p className="text-xs font-medium uppercase tracking-wide text-muted">Measurable outcome</p><Markdown>{b.outcome}</Markdown></div>
                      {b.href && <Link href={b.href}><Button size="sm">Open relevant lesson</Button></Link>}
                    </Card>
                  </li>
                ))}
              </ol>
            </>
          )}
        </div>
      )}
    </>
  );
}
