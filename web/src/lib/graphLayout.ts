import type { GraphEdge, GraphNode } from "./types";

export const MIN_SOLID = 0.7; // edges below this are drawn dashed: inferred, not seen

/** Columns: You, Projects, Technologies, then concepts by prerequisite depth. Pure, so it can be tested. */
export function layoutGraph(nodes: GraphNode[], edges: GraphEdge[], gapX = 260, gapY = 76) {
  const depth = new Map<string, number>();
  const prereq = edges.filter((e) => e.kind === "prerequisite");
  const concepts = nodes.filter((n) => n.type === "concept");
  for (const c of concepts) depth.set(c.id, 0);
  for (let pass = 0; pass < concepts.length; pass++) {
    let changed = false;
    for (const e of prereq) {
      const next = (depth.get(e.source) ?? 0) + 1; // the target is a prerequisite of the source, so it sits one column further right
      if (next > (depth.get(e.target) ?? 0)) { depth.set(e.target, next); changed = true; }
    }
    if (!changed) break;
  }
  const column = (n: GraphNode) => (n.type === "you" ? 0 : n.type === "project" ? 1 : n.type === "technology" ? 2 : 3 + (depth.get(n.id) ?? 0));
  const rank = new Map([...new Set(nodes.map(column))].sort((a, b) => a - b).map((c, i) => [c, i])); // no blank columns when a type is hidden
  const byColumn = new Map<number, GraphNode[]>();
  for (const n of nodes) byColumn.set(rank.get(column(n))!, [...(byColumn.get(rank.get(column(n))!) ?? []), n]);
  const positions: Record<string, { x: number; y: number }> = {};
  const tallest = Math.max(1, ...[...byColumn.values()].map((c) => c.length));
  for (const [col, list] of byColumn) {
    list.sort((a, b) => a.label.localeCompare(b.label));
    const offset = ((tallest - list.length) * gapY) / 2; // centre short columns
    list.forEach((n, i) => (positions[n.id] = { x: col * gapX, y: offset + i * gapY }));
  }
  return positions;
}

/** Nodes reachable from a project following edges forward, plus You. Used by the project filter. */
export function reachableFrom(projectNodeId: string, edges: GraphEdge[]) {
  const out = new Set<string>(["you", projectNodeId]);
  const stack = [projectNodeId];
  while (stack.length) {
    const here = stack.pop()!;
    for (const e of edges) if (e.source === here && !out.has(e.target)) { out.add(e.target); stack.push(e.target); }
  }
  return out;
}
