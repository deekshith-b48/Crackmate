"use client";
import "@xyflow/react/dist/style.css";
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { useMemo } from "react";
import { cn } from "@/lib/cn";
import { useTheme } from "@/lib/theme";
import { MIN_SOLID, layoutGraph } from "@/lib/graphLayout";
import type { CareerGraph, RiskRow } from "@/lib/types";

type Data = { label: string; type: string; risk?: number; assessed?: boolean; selected: boolean; scale: number };

const base = "rounded-[10px] border text-center font-medium shadow-none transition-shadow";
function GraphNode({ data }: NodeProps<Node<Data>>) {
  const risk = data.risk ?? 0;
  const tone = risk >= 6 ? "border-red-300 bg-bad-tint text-bad" : risk >= 3 ? "border-amber-300 bg-warn-tint text-warn" : "border-green-300 bg-good-tint text-good";
  const px = (data.type === "concept" ? (risk >= 6 ? 15 : risk >= 3 ? 14 : 12) : 14) * data.scale; // size = interview risk, times your text-size choice
  const style = data.type === "you" ? "border-brand-600 bg-brand-600 text-white" : data.type === "project" ? "border-brand-200 bg-brand-100 text-brand-700"
    : data.type === "technology" ? "border-slate-300 bg-slate-100 text-slate-700" : cn(tone, data.assessed === false && "border-dashed");
  return (
    <div className={cn(base, style, data.selected && "ring-2 ring-brand-600 ring-offset-2 ring-offset-surface")} style={{ fontSize: px, padding: "0.45em 0.85em", maxWidth: `${15 * data.scale}em`, lineHeight: 1.25 }}>
      <Handle type="target" position={Position.Left} className="!size-1.5 !border-0 !bg-slate-400" />
      {data.label}
      <Handle type="source" position={Position.Right} className="!size-1.5 !border-0 !bg-slate-400" />
    </div>
  );
}
const nodeTypes = { card: GraphNode };

/** Interactive skill graph. Node colour = type (concepts: risk), node size = risk, edge thickness = confidence, dashed = inferred. */
export function KnowledgeGraph({ graph, risk, visible, selected, onSelect, scale = 1, compact = false, className }: { graph: CareerGraph; risk: Map<string, RiskRow>; visible: Set<string>; selected?: string | null; onSelect?: (id: string | null) => void; scale?: number; compact?: boolean; className?: string }) {
  const { theme } = useTheme();
  const { nodes, edges } = useMemo(() => {
    const shown = graph.nodes.filter((n) => visible.has(n.id));
    const ids = new Set(shown.map((n) => n.id));
    const shownEdges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    const pos = layoutGraph(shown, shownEdges, 260 * scale, 76 * scale);
    const nodes: Node<Data>[] = shown.map((n) => {
      const r = n.type === "concept" ? risk.get(n.label) : undefined;
      return { id: n.id, type: "card", position: pos[n.id], ariaLabel: `${n.type}: ${n.label}${r ? `, interview risk ${r.risk.toFixed(1)} out of 10` : ""}`, data: { label: n.label, type: n.type, risk: r?.risk, assessed: r?.assessed, selected: selected === n.id, scale } };
    });
    const edges: Edge[] = shownEdges.map((e) => {
      const on = selected != null && (e.source === selected || e.target === selected); // spotlight the selected node's connections
      const colour = on ? (theme === "dark" ? "#c084fc" : "#9333ea") : "#94a3b8";
      return {
        id: `${e.source}>${e.target}>${e.kind}`, source: e.source, target: e.target, type: "default", zIndex: on ? 10 : 0,
        style: { stroke: colour, strokeWidth: 1 + e.confidence * 2, strokeDasharray: e.confidence < MIN_SOLID ? "5 4" : undefined, opacity: selected == null || on ? 0.9 : 0.15 },
        markerEnd: { type: MarkerType.ArrowClosed, color: colour, width: 14, height: 14 },
      };
    });
    return { nodes, edges };
  }, [graph, risk, visible, selected, scale, theme]);

  return (
    <div className={cn("overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface", className ?? "h-[680px]")} role={compact ? "img" : "application"} aria-label="Skill knowledge graph">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} colorMode={theme} style={{ background: "transparent" }} fitView fitViewOptions={{ padding: compact ? 0.05 : 0.15, minZoom: compact || scale <= 1 ? 0.1 : 0.55 }} minZoom={0.1} maxZoom={1.8}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable={!compact} nodesFocusable={!compact}
        panOnDrag={!compact} zoomOnScroll={!compact} zoomOnPinch={!compact} zoomOnDoubleClick={!compact} preventScrolling={!compact}
        onNodeClick={compact ? undefined : (_, n) => onSelect?.(n.id)} onPaneClick={compact ? undefined : () => onSelect?.(null)} proOptions={{ hideAttribution: true }}>
        <Background color={theme === "dark" ? "#263145" : "#e2e8f0"} gap={20} />
        {!compact && <Controls showInteractive={false} />}
      </ReactFlow>
    </div>
  );
}
