"use client";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useMemo } from "react";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { useSignals } from "@/lib/career";
import type { CareerGraph } from "@/lib/types";

const Graph = dynamic(() => import("./KnowledgeGraph").then((m) => m.KnowledgeGraph), { ssr: false, loading: () => <div className="h-64 shimmer rounded-[var(--radius-card)]" /> });

/** A glance at your graph: you, your projects and technologies, and the ten riskiest concepts. Click through for the full thing. */
export function MiniGraph({ pid }: { pid: string }) {
  const { data: graph } = useQuery({ queryKey: ["career-graph", pid], queryFn: () => api.get<CareerGraph>(`/api/profiles/${pid}/career/graph`) });
  const { data: signals } = useSignals(pid);
  const risk = useMemo(() => new Map((signals?.topics ?? []).map((t) => [t.topic, t])), [signals]);
  // Compact version: you, your projects and the ten riskiest concepts, with each project linked straight to the concepts it depends on.
  const mini = useMemo<CareerGraph | null>(() => {
    if (!graph) return null;
    const out = (kind: string) => graph.edges.filter((e) => e.kind === kind);
    const next = (kinds: string[]) => { const m = new Map<string, string[]>(); for (const e of graph.edges) if (kinds.includes(e.kind)) m.set(e.source, [...(m.get(e.source) ?? []), e.target]); return m; };
    const forward = next(["uses", "requires", "prerequisite"]);
    const top = new Set(graph.nodes.filter((n) => n.type === "concept").sort((a, b) => (risk.get(b.label)?.risk ?? 0) - (risk.get(a.label)?.risk ?? 0)).slice(0, 10).map((n) => n.id));
    const projects = graph.nodes.filter((n) => n.type === "project");
    const edges: CareerGraph["edges"] = out("built").filter((e) => e.source === "you");
    for (const p of projects) {
      const seen = new Set<string>(); const stack = [p.id];
      while (stack.length) for (const t of forward.get(stack.pop()!) ?? []) if (!seen.has(t)) { seen.add(t); stack.push(t); }
      for (const c of seen) if (top.has(c)) edges.push({ source: p.id, target: c, kind: "depends", confidence: 0.8, evidence: [] });
    }
    const keep = new Set(["you", ...projects.map((p) => p.id), ...edges.map((e) => e.target)]);
    return { ...graph, nodes: graph.nodes.filter((n) => keep.has(n.id)), edges };
  }, [graph, risk]);
  const visible = useMemo(() => new Set(mini?.nodes.map((n) => n.id)), [mini]);
  if (!graph || !mini || !graph.nodes.some((n) => n.type === "project")) return null;
  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between"><h2 className="font-semibold text-ink">Your skill graph</h2><Link href="/analyse/graph/" className="text-sm text-brand-700 hover:underline">Open the full graph</Link></div>
      <Link href="/analyse/graph/" aria-label="Open the full knowledge graph" className="block">
        <Graph graph={mini} risk={risk} visible={visible} compact scale={1.1} className="h-64 pointer-events-none" />
      </Link>
      <p className="text-xs text-muted">Your projects linked to the ten riskiest concepts they depend on. Red and amber concepts are where an interviewer is most likely to find a gap.</p>
    </Card>
  );
}
