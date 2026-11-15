"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, LineChart } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { AdaptivePlan } from "@/components/track/AdaptivePlan";
import { TopicDialog } from "@/components/track/TopicDialog";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Field";
import { ReadinessRing } from "@/components/ui/ReadinessRing";
import { Tabs } from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";
import { api, API_BASE } from "@/lib/api";
import { useSignals } from "@/lib/career";
import { useProfiles } from "@/lib/profile";
import type { Progress, QueueItem } from "@/lib/types";

type Tab = "overview" | "next" | "plan";
const TONE = { "Demonstrated recently": "good", "Needs revision": "bad", "Due for review": "warn", Learning: "brand", "Not assessed": "neutral" } as const;

export default function Track() {
  const { active } = useProfiles();
  const pid = active?.id;
  const client = useQueryClient();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("overview");
  const [topic, setTopic] = useState<string | null>(null);
  const [minutes, setMinutes] = useState(30);
  const { data: career } = useSignals(pid);
  const byTopic = new Map((career?.topics ?? []).map((t) => [t.topic, t]));
  const { data } = useQuery({ queryKey: ["progress", pid], queryFn: () => api.get<Progress>(`/api/profiles/${pid}/learning/progress`), enabled: !!pid });
  const { data: queue = [] } = useQuery({ queryKey: ["queue", pid, minutes], queryFn: () => api.get<QueueItem[]>(`/api/profiles/${pid}/learning/queue?minutes=${minutes}`), enabled: !!pid && tab === "next" });

  async function act(tid: string, action: string) {
    try { await api.post(`/api/profiles/${pid}/learning/queue/${tid}`, { action }); client.invalidateQueries({ queryKey: ["queue", pid] }); }
    catch (e) { toast("bad", e instanceof Error ? e.message : "That did not work."); }
  }
  async function restore() { await api.post(`/api/profiles/${pid}/learning/queue/restore`); client.invalidateQueries({ queryKey: ["queue", pid] }); toast("good", "Recommendations restored."); }

  const assessed = data?.topics.filter((t) => t.count > 0).length ?? 0;
  return (
    <>
      <PageHeader title="Progress" description="Readiness, weak spots and what to study next. Progress uses local evidence, and lesson completion alone does not establish understanding."
        actions={pid ? <a href={`${API_BASE}/api/profiles/${pid}/export/learning`} download><Button size="sm"><Download className="size-4" /> Learning report</Button></a> : undefined} />
      {!pid ? <NoProfile /> : (
        <>
          <Tabs<Tab> tabs={[{ id: "overview", label: "Overview" }, { id: "next", label: "Study next" }, { id: "plan", label: "Adaptive plan" }]} value={tab} onChange={setTab} />
          {tab === "overview" && data && (
            <div className="space-y-6">
              <Card className="flex flex-wrap items-center gap-8">
                <ReadinessRing value={career?.overall ?? null} max={10} />
                <div className="max-w-md"><p className="text-lg font-semibold text-ink">{career?.overall == null ? "No readiness score yet" : `${career.assessed} of ${career.total} topics assessed · ${career.overall}/10`}</p>
                  <p className="mt-1 text-sm text-muted">A coaching estimate (1 to 10) from your latest scored answers and review retention, weighted by how likely each topic is to come up. Hints, reveals and retries cap a topic at 70, and topics you have not practised are not counted. {assessed === 0 && "Answer practice questions or run a mock interview to get one."}</p></div>
              </Card>
              <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-line bg-slate-50 text-xs uppercase tracking-wide text-muted"><tr><th className="px-4 py-3">Topic</th><th className="px-4 py-3">State</th><th className="px-4 py-3">Readiness</th><th className="hidden px-4 py-3 md:table-cell">Next review</th></tr></thead>
                  <tbody className="divide-y divide-line">
                    {data.topics.map((t) => (
                      <tr key={t.id} onClick={() => setTopic(t.id)} className="cursor-pointer hover:bg-slate-50">
                        <td className="px-4 py-3 font-medium text-ink">{t.name}</td>
                        <td className="px-4 py-3"><Badge tone={TONE[t.state as keyof typeof TONE] ?? "neutral"}>{t.state}</Badge></td>
                        <td className="px-4 py-3">{(() => { const r = byTopic.get(t.name)?.readiness; return r == null ? <span className="text-muted">—</span> : <div className="flex items-center gap-2"><div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-600" style={{ width: `${r * 10}%` }} /></div><span className="font-mono text-xs">{r}/10</span></div>; })()}</td>
                        <td className="hidden px-4 py-3 text-muted md:table-cell">{t.due ?? "Not scheduled"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {tab === "next" && (
            <div className="space-y-4">
              <div className="flex items-end gap-4"><div className="w-48"><label htmlFor="mins" className="mb-1.5 block text-sm font-medium text-ink">Study minutes available now</label><Input id="mins" type="number" min={5} max={240} step={5} value={minutes} onChange={(e) => setMinutes(Math.max(5, Math.min(240, Number(e.target.value) || 5)))} /></div><Button variant="ghost" onClick={restore}>Restore dismissed and postponed</Button></div>
              {queue.length === 0 ? <EmptyState icon={LineChart} title="Nothing fits right now" text="No activities fit your current choices. Restore postponed or dismissed recommendations, or add more minutes." /> : queue.map((q) => (
                <Card key={q.topic} className="flex flex-wrap items-center gap-4">
                  <div className="min-w-0 flex-1"><h3 className="font-semibold text-ink">{q.name}</h3><p className="text-sm text-body">{q.activity} · {q.duration} min</p><p className="text-xs text-muted">{q.reason}</p></div>
                  <div className="flex flex-wrap gap-2">
                    <Link href={`/learn/skills/?topic=${encodeURIComponent(q.name)}&level=Basics`}><Button variant="primary" size="sm">Open lesson</Button></Link>
                    <Button size="sm" onClick={() => act(q.topic, "pin")}>Pin</Button><Button size="sm" onClick={() => act(q.topic, "tomorrow")}>Tomorrow</Button><Button size="sm" variant="ghost" onClick={() => act(q.topic, "dismiss")}>Dismiss</Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
          {tab === "plan" && <AdaptivePlan pid={pid} />}
          <TopicDialog pid={pid} tid={topic} onClose={() => setTopic(null)} />
        </>
      )}
    </>
  );
}
