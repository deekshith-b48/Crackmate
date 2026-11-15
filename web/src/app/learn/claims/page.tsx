"use client";
import { ShieldCheck } from "lucide-react";
import { useMemo } from "react";
import { NoProfile } from "@/components/learn/NoProfile";
import { RunBar } from "@/components/learn/RunBar";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Markdown } from "@/components/ui/Markdown";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useProfiles } from "@/lib/profile";
import type { ClaimReport } from "@/lib/types";
import { useArtifact } from "@/lib/useArtifact";

const RISK = { high: ["bad", "High risk"], medium: ["warn", "Medium risk"], low: ["good", "Low risk"] } as const;

export default function Claims() {
  const { active } = useProfiles();
  const pid = active?.id;
  const toast = useToast();
  const { state, job, run, setData, exportHref } = useArtifact<ClaimReport>(pid, "claims");
  const claims = state?.data?.claims ?? [];
  const ticked = useMemo(() => new Set(state?.ticked ?? []), [state?.ticked]);
  const order = useMemo(() => claims.map((_, i) => i).sort((a, b) => ["high", "medium", "low"].indexOf(claims[a].risk) - ["high", "medium", "low"].indexOf(claims[b].risk)), [claims]);
  const openHigh = order.filter((i) => claims[i].risk === "high" && !ticked.has(i)).length;

  async function tick(index: number, on: boolean) {
    setData((old) => ({ ...old, ticked: on ? [...(old.ticked ?? []), index] : (old.ticked ?? []).filter((i) => i !== index) }));
    try {
      await api.put(`/api/profiles/${pid}/claims/tick`, { digest: state!.digest, index, on });
    } catch (error) {
      toast("bad", error instanceof Error ? error.message : "Could not save.");
      setData((old) => ({ ...old, ticked: on ? (old.ticked ?? []).filter((i) => i !== index) : [...(old.ticked ?? []), index] }));
    }
  }

  return (
    <>
      <PageHeader title="Claim Checker" description="Every resume line is a claim an interviewer may probe. Find the ones you cannot defend yet. Questions are most likely, never guaranteed." />
      {!pid ? <NoProfile /> : (
        <div className="space-y-6">
          <RunBar state={state} job={job as never} onRun={run} runLabel="Check my claims" redoLabel="Re-check" runningTitle="Finding claims to defend" exportHref={exportHref} />
          {!state?.data && job.status !== "running" && <EmptyState icon={ShieldCheck} title="Find out what you can defend" text="CrackMate reads your projects and experience, then lists the claims an interviewer is most likely to question." />}
          {claims.length > 0 && (
            <>
              <Card className="flex items-center justify-between">
                <div><p className="text-sm text-muted">Claims you can defend</p><p className="text-3xl font-semibold text-ink">{ticked.size} <span className="text-lg font-normal text-muted">/ {claims.length}</span></p></div>
                <p className={cn("text-sm font-medium", openHigh ? "text-bad" : "text-good")}>{openHigh ? `${openHigh} high-risk still open` : "No high-risk claims open"}</p>
              </Card>
              <div className="space-y-3">
                {order.map((i) => {
                  const c = claims[i];
                  const [tone, label] = RISK[c.risk];
                  return (
                    <details key={i} className="group rounded-[var(--radius-card)] border border-line bg-surface">
                      <summary className="flex cursor-pointer list-none items-start gap-3 p-4">
                        <input type="checkbox" checked={ticked.has(i)} onClick={(e) => e.stopPropagation()} onChange={(e) => tick(i, e.target.checked)} aria-label={`I can defend: ${c.claim}`} className="mt-1 size-4 accent-[var(--color-brand-600)]" />
                        <div className="min-w-0 flex-1"><p className={cn("font-medium", ticked.has(i) ? "text-muted line-through" : "text-ink")}>{c.claim}</p><p className="mt-0.5 text-xs text-muted">{c.source} · {c.kind}</p></div>
                        <Badge tone={ticked.has(i) ? "good" : tone}>{ticked.has(i) ? "Defended" : label}</Badge>
                      </summary>
                      <div className="space-y-3 border-t border-line px-4 py-4 text-sm">
                        <div><p className="font-medium text-ink">Why it is risky</p><Markdown>{c.why}</Markdown></div>
                        <div><p className="font-medium text-ink">Most likely question</p><Markdown>{c.probe}</Markdown></div>
                        <div><p className="font-medium text-ink">Be ready to explain</p><Markdown>{c.defend}</Markdown></div>
                        <div><p className="font-medium text-ink">How to prepare</p><Markdown>{c.prepare}</Markdown></div>
                      </div>
                    </details>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
