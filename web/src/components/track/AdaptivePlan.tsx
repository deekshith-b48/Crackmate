"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox, Field, Input, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { LearningSettings, PlanActivity, Proposal } from "@/lib/types";

export function AdaptivePlan({ pid }: { pid: string }) {
  const client = useQueryClient();
  const toast = useToast();
  const { data: cfg } = useQuery({ queryKey: ["learning-settings", pid], queryFn: () => api.get<{ settings: LearningSettings; topics: { id: string; name: string }[] }>(`/api/profiles/${pid}/learning/settings`) });
  const { data: blocks = [] } = useQuery({ queryKey: ["active-plan", pid], queryFn: () => api.get<PlanActivity[]>(`/api/profiles/${pid}/learning/plan`) });
  const [s, setS] = useState<LearningSettings | null>(null);
  const [unavailable, setUnavailable] = useState("");
  const [intervals, setIntervals] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (cfg) { setS(cfg.settings); setUnavailable(cfg.settings.unavailable.join("\n")); setIntervals(cfg.settings.intervals.join(", ")); } }, [cfg]);

  const fail = (e: unknown) => toast("bad", e instanceof Error ? e.message : "That did not work.");
  async function save() {
    if (!s) return;
    setBusy(true);
    try {
      const next = await api.put<{ settings: LearningSettings; topics: { id: string; name: string }[] }>(`/api/profiles/${pid}/learning/settings`, { ...s, unavailable: unavailable.split("\n").map((l) => l.trim()).filter(Boolean), intervals: intervals.split(",").map((n) => Number(n.trim())).filter((n) => !Number.isNaN(n)) });
      client.setQueryData(["learning-settings", pid], next);
      toast("good", "Learning settings saved.");
    } catch (e) { fail(e); } finally { setBusy(false); }
  }
  async function propose() { try { setProposal(await api.post<Proposal>(`/api/profiles/${pid}/learning/propose`)); } catch (e) { fail(e); } }
  async function apply() {
    try {
      client.setQueryData(["active-plan", pid], await api.post<PlanActivity[]>(`/api/profiles/${pid}/learning/apply`, { id: proposal!.id }));
      setProposal(null);
      toast("good", "Plan applied.");
    } catch (e) { fail(e); }
  }
  async function update(b: PlanActivity, patch: Partial<Pick<PlanActivity, "completed" | "pinned">>) {
    try { client.setQueryData(["active-plan", pid], await api.put<PlanActivity[]>(`/api/profiles/${pid}/learning/plan/${b.id}`, { completed: b.completed, pinned: b.pinned, ...patch })); } catch (e) { fail(e); }
  }
  const byDate = blocks.reduce<Record<string, PlanActivity[]>>((acc, b) => ({ ...acc, [b.date]: [...(acc[b.date] ?? []), b] }), {});

  return (
    <div className="space-y-6">
      <Card className="space-y-4">
        <h2 className="font-semibold text-ink">Learning settings</h2>
        {s && (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Timezone" htmlFor="tz" hint="For example Asia/Kolkata"><Input id="tz" value={s.timezone} onChange={(e) => setS({ ...s, timezone: e.target.value })} /></Field>
              <Field label="Interview date (optional)" htmlFor="idate"><Input id="idate" type="date" value={s.interview} onChange={(e) => setS({ ...s, interview: e.target.value })} /></Field>
              <Field label="Study minutes per day" htmlFor="daily"><Input id="daily" type="number" min={5} max={240} value={s.daily_minutes} onChange={(e) => setS({ ...s, daily_minutes: Number(e.target.value) })} /></Field>
              <Field label="Preferred block minutes" htmlFor="block"><Input id="block" type="number" min={5} max={50} value={s.session_minutes} onChange={(e) => setS({ ...s, session_minutes: Number(e.target.value) })} /></Field>
              <Field label="Strong-answer threshold (1–4)" htmlFor="thr"><Input id="thr" type="number" min={1} max={4} value={s.threshold} onChange={(e) => setS({ ...s, threshold: Number(e.target.value) })} /></Field>
              <Field label="Independent successes needed" htmlFor="succ"><Input id="succ" type="number" min={2} max={5} value={s.successes} onChange={(e) => setS({ ...s, successes: Number(e.target.value) })} /></Field>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Unavailable dates" htmlFor="unav" hint="One YYYY-MM-DD per line."><Textarea id="unav" value={unavailable} onChange={(e) => setUnavailable(e.target.value)} className="min-h-20" /></Field>
              <Field label="Review intervals in days" htmlFor="int" hint="Increasing, from 1 to 365."><Input id="int" value={intervals} onChange={(e) => setIntervals(e.target.value)} /></Field>
            </div>
            <div><p className="mb-2 text-sm font-medium text-ink">Priority topics</p><div className="flex flex-wrap gap-x-5 gap-y-2">{cfg?.topics.map((t) => <Checkbox key={t.id} label={t.name} checked={s.priorities.includes(t.id)} onChange={(e) => setS({ ...s, priorities: e.target.checked ? [...s.priorities, t.id] : s.priorities.filter((p) => p !== t.id) })} />)}</div></div>
            <Button variant="primary" onClick={save} loading={busy}>Save learning settings</Button>
          </>
        )}
      </Card>

      <Card className="space-y-4">
        <div className="flex items-center justify-between"><h2 className="font-semibold text-ink">Seven-day plan</h2><Button onClick={propose}>Propose revised seven-day plan</Button></div>
        {proposal && (
          <div className="space-y-3 rounded-[var(--radius-control)] border border-brand-100 bg-brand-50/40 p-4">
            <p className="text-sm text-body">{proposal.reason}</p>
            <p className="text-xs text-muted">Active activities: {proposal.active_count}. Proposed: {proposal.blocks.length}. Completed and pinned activities are preserved. Blocks are flexible daytime tasks; reserve five-minute breaks between blocks.</p>
            <ul className="space-y-1 text-sm">{proposal.blocks.map((b) => <li key={b.id}><span className="font-mono text-xs text-muted">{b.date}</span> · {b.name} · {b.duration} min</li>)}</ul>
            <div className="flex gap-2"><Button variant="primary" onClick={apply}>Apply proposed plan</Button><Button variant="ghost" onClick={() => setProposal(null)}>Discard</Button></div>
          </div>
        )}
        {Object.keys(byDate).length === 0 && !proposal && <p className="text-sm text-muted">No active plan yet. Propose one and it will use your readiness, due reviews and available minutes.</p>}
        {Object.entries(byDate).map(([date, items]) => (
          <div key={date}>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">{date}</p>
            <div className="space-y-2">
              {items.map((b) => (
                <div key={b.id} className="flex flex-wrap items-center gap-3 rounded-[var(--radius-control)] border border-line px-3 py-2">
                  <div className="min-w-0 flex-1"><p className={`font-medium ${b.completed ? "text-muted line-through" : "text-ink"}`}>{b.name} <span className="font-normal text-muted">· {b.duration} min</span></p><p className="text-xs text-muted">{b.activity}</p></div>
                  {b.pinned && <Badge tone="brand">Pinned</Badge>}
                  <Checkbox label="Done" checked={b.completed} onChange={(e) => update(b, { completed: e.target.checked })} />
                  <Checkbox label="Pin" checked={b.pinned} onChange={(e) => update(b, { pinned: e.target.checked })} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}
