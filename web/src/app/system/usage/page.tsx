"use client";
import { useQuery } from "@tanstack/react-query";
import { Gauge } from "lucide-react";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { api } from "@/lib/api";
import type { UsageSummary } from "@/lib/types";

const k = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n));

export default function Usage() {
  const { data } = useQuery({ queryKey: ["usage"], queryFn: () => api.get<UsageSummary>("/api/usage"), refetchInterval: 15000 });
  const max = Math.max(1, ...(data?.days ?? []).map((d) => d.tokens));
  return (
    <>
      <PageHeader title="Usage" description="Every model call CrackMate made in the last 24 hours, the calls its caches saved, and how much of the free tier is left." />
      {!data ? null : data.calls + data.cached === 0 ? (
        <EmptyState icon={Gauge} title="No model calls yet" text="Generate a lesson or run the Claim Checker and this page will show what it cost, and what the caches saved you." />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="py-4"><p className="text-sm text-muted">Model calls</p><p className="text-3xl font-semibold text-ink">{data.calls}</p></Card>
            <Card className="py-4"><p className="text-sm text-muted">Calls saved by cache</p><p className="text-3xl font-semibold text-good">{data.cached}</p></Card>
            <Card className="py-4"><p className="text-sm text-muted">Tokens used</p><p className="text-3xl font-semibold text-ink">{k(data.tokens_in + data.tokens_out)}</p><p className="text-xs text-muted">{k(data.tokens_in)} in · {k(data.tokens_out)} out</p></Card>
            <Card className="py-4"><p className="text-sm text-muted">Tokens saved (estimate)</p><p className="text-3xl font-semibold text-good">~{k(data.saved_tokens)}</p></Card>
          </div>

          <Card className="space-y-4">
            <div className="flex items-center justify-between"><h2 className="font-semibold text-ink">Free-tier headroom, per model</h2><Badge>last {data.window_hours} hours</Badge></div>
            {data.by_model.length === 0 ? <p className="text-sm text-muted">No live model calls in this window.</p> : data.by_model.map((m) => {
              const used = Math.min(1, m.tokens / m.limit);
              return (
                <div key={m.model}>
                  <div className="mb-1 flex justify-between text-sm"><span className="font-mono text-xs text-ink">{m.model}</span><span className="text-muted">{k(m.tokens)} of {k(m.limit)} used · {k(m.remaining)} left</span></div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={Math.round(used * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={`${m.model} daily tokens used`}><div className={`h-full rounded-full transition-[width] duration-500 ${used > 0.85 ? "bg-bad" : used > 0.6 ? "bg-warn" : "bg-good"}`} style={{ width: `${used * 100}%` }} /></div>
                </div>
              );
            })}
            <p className="text-xs text-muted">{data.note}</p>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <h2 className="mb-3 font-semibold text-ink">Tokens by feature</h2>
              <table className="w-full text-left text-sm"><thead className="text-xs uppercase tracking-wide text-muted"><tr><th className="pb-2">Feature</th><th className="pb-2">Calls</th><th className="pb-2">Cached</th><th className="pb-2 text-right">Tokens</th></tr></thead>
                <tbody className="divide-y divide-line">{data.by_feature.map((f) => <tr key={f.feature}><td className="py-2 font-medium text-ink">{f.feature}</td><td className="py-2">{f.calls}</td><td className="py-2 text-good">{f.cached}</td><td className="py-2 text-right font-mono text-xs">{k(f.tokens)}</td></tr>)}</tbody></table>
            </Card>
            <Card>
              <h2 className="mb-3 font-semibold text-ink">Last 7 days</h2>
              <div className="flex h-36 items-end gap-2" role="img" aria-label="Tokens used per day">
                {data.days.map((d) => <div key={d.date} className="flex flex-1 flex-col items-center gap-1" title={`${d.date}: ${d.calls} calls, ${d.cached} cached, ${k(d.tokens)} tokens`}><div className="w-full rounded-t bg-brand-600" style={{ height: `${Math.max(4, (d.tokens / max) * 100)}%` }} /><span className="text-[10px] text-muted">{d.date.slice(5)}</span></div>)}
              </div>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
