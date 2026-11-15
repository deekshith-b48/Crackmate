import { describe, expect, it } from "vitest";
import { layoutGraph, reachableFrom } from "./graphLayout";
import type { GraphEdge, GraphNode } from "./types";

const n = (id: string, type: GraphNode["type"], label = id): GraphNode => ({ id, type, label });
const e = (source: string, target: string, kind: string, confidence = 1): GraphEdge => ({ source, target, kind, confidence, evidence: [] });
const nodes = [n("you", "you"), n("project:a", "project"), n("project:b", "project"), n("tech:react", "technology"), n("tech:redis", "technology"),
  n("concept:Caching", "concept"), n("concept:Hash tables", "concept"), n("concept:Arrays", "concept")];
const edges = [e("you", "project:a", "built"), e("you", "project:b", "built"), e("project:a", "tech:react", "uses"), e("project:b", "tech:redis", "uses"),
  e("tech:redis", "concept:Caching", "requires"), e("concept:Caching", "concept:Hash tables", "prerequisite"), e("concept:Hash tables", "concept:Arrays", "prerequisite")];

describe("layoutGraph", () => {
  const pos = layoutGraph(nodes, edges);
  it("orders columns you, project, technology, concept", () => {
    expect(pos["you"].x).toBeLessThan(pos["project:a"].x);
    expect(pos["project:a"].x).toBeLessThan(pos["tech:react"].x);
    expect(pos["tech:redis"].x).toBeLessThan(pos["concept:Caching"].x);
  });
  it("puts prerequisites one column further right, however deep the chain", () => {
    expect(pos["concept:Hash tables"].x).toBeGreaterThan(pos["concept:Caching"].x);
    expect(pos["concept:Arrays"].x).toBeGreaterThan(pos["concept:Hash tables"].x);
  });
  it("never stacks two nodes on the same spot", () => {
    const spots = Object.values(pos).map((p) => `${p.x},${p.y}`);
    expect(new Set(spots).size).toBe(spots.length);
  });
  it("survives a prerequisite cycle instead of looping forever", () => {
    const cyclic = [...edges, e("concept:Arrays", "concept:Caching", "prerequisite")];
    expect(Object.keys(layoutGraph(nodes, cyclic)).length).toBe(nodes.length);
  });
});

describe("reachableFrom", () => {
  it("follows a project forward to its technologies and concepts only", () => {
    const set = reachableFrom("project:b", edges);
    expect(set.has("tech:redis") && set.has("concept:Arrays") && set.has("you")).toBe(true);
    expect(set.has("project:a") || set.has("tech:react")).toBe(false);
  });
});

describe("layoutGraph with hidden types", () => {
  it("closes the gap left by a hidden column", () => {
    const some = nodes.filter((x) => x.type !== "technology");
    const pos = layoutGraph(some, edges.filter((x) => !x.source.startsWith("tech:") && !x.target.startsWith("tech:")), 100);
    expect(pos["concept:Caching"].x - pos["project:a"].x).toBe(100);
  });
});
