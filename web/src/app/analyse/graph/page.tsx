"use client";
import { useQuery } from "@tanstack/react-query";
import { Maximize2, Minimize2, Network } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { RiskBadge, WhyList } from "@/components/analyse/RiskCell";
import { KnowledgeGraph } from "@/components/analyse/KnowledgeGraph";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Field";
import { EmptyState } from "@/components/ui/EmptyState";
import { Tabs } from "@/components/ui/Tabs";
import { api } from "@/lib/api";
import { lessonHref, useSignals } from "@/lib/career";
import { reachableFrom } from "@/lib/graphLayout";
import { useProfiles } from "@/lib/profile";
import type { CareerGraph } from "@/lib/types";

const TYPES = [["project", "Projects"], ["technology", "Technologies"], ["concept", "Concepts"]] as const;

export default function GraphPage() {
  const { active } = useProfiles();
  const pid = active?.id;
  const { data: graph } = useQuery({ queryKey: ["career-graph", pid], queryFn: () => api.get<CareerGraph>(`/api/profiles/${pid}/career/graph`), enabled: !!pid });
  const { data: signals } = useSignals(pid);
  const [project, setProject] = useState("all");
  const [types, setTypes] = useState<string[]>(["project", "technology", "concept"]);
  const [weak, setWeak] = useState(false);
  const [skills, setSkills] = useState(false);
  const [scale, setScale] = useState(1);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => { if (!expanded) return; const esc = (e: KeyboardEvent) => e.key === "Escape" && setExpanded(false); window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc); }, [expanded]);
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<"graph" | "list">("graph");
  useEffect(() => { if (window.matchMedia("(max-width: 768px)").matches) setView("list"); }, []); // a graph is unusable on a phone: fall back to a list

  const risk = useMemo(() => new Map((signals?.topics ?? []).map((t) => [t.topic, t])), [signals]);
  const projects = graph?.nodes.filter((n) => n.type === "project") ?? [];
  const visible = useMemo(() => {
    if (!graph) return new Set<string>();
    const scope = project === "all" ? null : reachableFrom(project, graph.edges);
    const inProject = new Set(graph.edges.filter((e) => e.kind === "uses").map((e) => e.target)); // technologies a project actually uses
    return new Set(graph.nodes.filter((n) => {
      if (scope && !scope.has(n.id)) return false;
      if (n.type !== "you" && !types.includes(n.type)) return false;
      if (n.type === "technology" && !skills && !inProject.has(n.id)) return false; // skills listed without a project clutter the graph
      if (weak && n.type === "concept" && (risk.get(n.label)?.risk ?? 0) < 3) return false;
      return true;
    }).map((n) => n.id));
  }, [graph, project, types, weak, skills, risk]);

  const node = graph?.nodes.find((n) => n.id === selected);
  const incident = graph?.edges.filter((e) => e.source === selected || e.target === selected) ?? [];
  const label = (id: string) => graph?.nodes.find((n) => n.id === id)?.label ?? id;

  return (
    <>
      <PageHeader title="Knowledge graph" description="You, your projects, the technologies they use and the concepts behind them. Concept size shows interview risk; thicker edges mean more evidence; dashed edges are inferred." />
      {!pid ? <NoProfile /> : !graph ? null : projects.length === 0 ? <EmptyState icon={Network} title="Add a project to grow your graph" text="Every project you add links to its technologies and the concepts interviewers ask about." action={<Link href="/setup/"><Button variant="primary">Add a project</Button></Link>} /> : (
        <div className={expanded ? "fixed inset-0 z-40 space-y-4 overflow-auto bg-canvas p-6" : "space-y-4"}>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 [&_[role=tablist]]:mb-0">
            <Tabs tabs={[{ id: "graph" as const, label: "Graph" }, { id: "list" as const, label: "List" }]} value={view} onChange={setView} />
            <select aria-label="Project filter" value={project} onChange={(e) => { setProject(e.target.value); setSelected(null); }} className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm text-ink">
              <option value="all">All projects</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {TYPES.map(([id, name]) => <Checkbox key={id} label={name} checked={types.includes(id)} onChange={(e) => setTypes(e.target.checked ? [...types, id] : types.filter((t) => t !== id))} />)}
              <Checkbox label="Only weak topics" checked={weak} onChange={(e) => setWeak(e.target.checked)} />
              <Checkbox label="Include skills not tied to a project" checked={skills} onChange={(e) => setSkills(e.target.checked)} />
            </div>
            <div className="flex items-center gap-2 sm:ml-auto">
              <span className="text-xs text-muted" id="textsize" title="Larger text keeps a readable zoom. Drag to pan.">Text size</span>
              <div role="group" aria-labelledby="textsize" className="flex overflow-hidden rounded-[var(--radius-control)] border border-line">
                {([[1, "A", "text-xs"], [1.3, "A", "text-sm"], [1.6, "A", "text-base"]] as const).map(([v, l, size]) => <button key={v} aria-pressed={scale === v} aria-label={`Text size ${v}x`} onClick={() => setScale(v)} className={`h-8 w-9 font-semibold ${size} ${scale === v ? "bg-brand-50 text-brand-700" : "text-muted hover:bg-slate-100"}`}>{l}</button>)}
              </div>
              <Button size="sm" onClick={() => setExpanded(!expanded)} aria-pressed={expanded}>{expanded ? <><Minimize2 className="size-4" /> Exit full screen</> : <><Maximize2 className="size-4" /> Full screen</>}</Button>
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
            {view === "graph" ? <KnowledgeGraph key={`${project}|${types.join()}|${weak}|${skills}|${scale}|${expanded}`} scale={scale} className={expanded ? "h-[calc(100vh-11rem)]" : "h-[calc(100vh-17rem)] min-h-[560px]"} graph={graph} risk={risk} visible={visible} selected={selected} onSelect={setSelected} /> : (
              <div className="space-y-4">
                {(["project", "technology", "concept"] as const).map((t) => (
                  <Card key={t}><h2 className="mb-2 text-sm font-semibold capitalize text-ink">{t === "technology" ? "Technologies" : t + "s"}</h2>
                    <div className="flex flex-wrap gap-1.5">{graph.nodes.filter((n) => n.type === t && visible.has(n.id)).map((n) => { const r = risk.get(n.label); return <button key={n.id} onClick={() => setSelected(n.id)}><Badge tone={t === "concept" && r ? (r.risk >= 6 ? "bad" : r.risk >= 3 ? "warn" : "good") : "neutral"}>{n.label}{t === "concept" && r ? ` · ${r.risk.toFixed(1)}` : ""}</Badge></button>; })}</div>
                  </Card>
                ))}
              </div>
            )}
            <aside aria-live="polite">
              {!node ? <Card className="text-sm text-muted">Click a node to see what it is, how well you know it, and how to study it.</Card> : (
                <Card className="space-y-3">
                  <div><Badge tone="brand" className="mb-1 capitalize">{node.type}</Badge><h2 className="text-lg font-semibold text-ink">{node.label}</h2></div>
                  {node.type === "concept" && risk.get(node.label) && (() => { const r = risk.get(node.label)!; return (
                    <>
                      <div className="flex flex-wrap items-center gap-2"><RiskBadge row={r} /><span className="text-sm text-muted">{r.assessed ? `Readiness ${r.readiness}/10` : "Not assessed yet"}</span></div>
                      <WhyList why={r.why} />
                      <div className="flex flex-wrap gap-2"><Link href={lessonHref(node.label)}><Button variant="primary" size="sm">Learn</Button></Link><Link href="/practice/review/"><Button size="sm">Practise</Button></Link><Link href={`/analyse/blast/?topic=${encodeURIComponent(node.label)}`}><Button size="sm" variant="ghost">Blast radius</Button></Link></div>
                    </>); })()}
                  {node.type === "project" && <Link href={`/learn/projects/?project=${node.project_id}`}><Button size="sm" variant="primary">Open project</Button></Link>}
                  {incident.length > 0 && (
                    <div><p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Connections</p>
                      <ul className="max-h-56 space-y-1.5 overflow-y-auto text-sm">{incident.slice(0, 14).map((e) => { const other = e.source === selected ? e.target : e.source; return <li key={e.source + e.target + e.kind}><button className="text-left hover:underline" onClick={() => setSelected(other)}>{e.source === selected ? `${e.kind} → ` : `← ${e.kind} `}<strong>{label(other)}</strong></button><span className="ml-1 text-xs text-muted" title={e.evidence.join("\n")}>{Math.round(e.confidence * 100)}%</span></li>; })}</ul>
                    </div>
                  )}
                </Card>
              )}
            </aside>
          </div>
          <p className="text-xs text-muted">Edge confidence: 100% stated on your resume, 90% imported in code, 80% declared in a dependency file or the curated concept map, below 70% inferred (dashed).</p>
        </div>
      )}
    </>
  );
}
