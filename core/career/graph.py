"""The skill knowledge graph: You, Projects, Technologies and Concepts, joined by confidence-scored edges."""
from core.career.ontology import ONTOLOGY_CONFIDENCE, REQUIRES, TECH_CONCEPTS, canon

STATED, IN_CODE, IN_DEPS, INFERRED = 1.0, 0.9, 0.8, 0.5  # how we learned a link: resume, code import, manifest, guess
MIN_SOLID = 0.7  # edges below this are drawn dashed in the UI


def build(profile, repo_facts):
    """repo_facts: {project_id: detect() output}. Returns {"nodes", "edges", "unsupported", "undeclared"}."""
    nodes, edges = {}, {}

    def node(ident, kind, label, **meta):
        nodes.setdefault(ident, {"id": ident, "type": kind, "label": label, **meta})
        return ident

    def edge(source, target, kind, confidence, evidence):
        key = (source, target, kind)
        row = edges.setdefault(key, {"source": source, "target": target, "kind": kind, "confidence": 0.0, "evidence": []})
        row["confidence"] = max(row["confidence"], confidence)
        if evidence not in row["evidence"]:
            row["evidence"].append(evidence)

    you = node("you", "you", profile.name or "You")
    unsupported, undeclared = [], []
    for project in profile.projects:
        pid = node("project:" + project.id, "project", project.title, project_id=project.id)
        edge(you, pid, "built", STATED, "resume")
        stated = {canon(t) for t in project.technologies}
        found = {t["name"]: t for t in (repo_facts.get(project.id) or {}).get("technologies", [])}
        for key in stated | set(found):
            if key not in TECH_CONCEPTS:
                continue
            tid = node("tech:" + key, "technology", key)
            if key in stated:
                edge(pid, tid, "uses", STATED, "resume")
            for ev in (found.get(key) or {}).get("evidence", []):
                edge(pid, tid, "uses", found[key]["confidence"], f"{ev['kind']}: {ev['file']}")
        if project.id in repo_facts:  # only judge claims when we actually read the code
            unsupported += [{"project_id": project.id, "project": project.title, "technology": k} for k in sorted(stated - set(found)) if k in TECH_CONCEPTS]
            undeclared += [{"project_id": project.id, "project": project.title, "technology": k} for k in sorted(set(found) - stated)]
    for skill in (s for group in profile.skills.model_dump().values() for s in group):  # skills listed without a project
        key = canon(skill)
        if key in TECH_CONCEPTS:
            edge(you, node("tech:" + key, "technology", key), "knows", STATED, "resume skills")

    for tid in [n for n in nodes if n.startswith("tech:")]:
        for concept in TECH_CONCEPTS[nodes[tid]["label"]]:
            edge(tid, node("concept:" + concept, "concept", concept), "requires", ONTOLOGY_CONFIDENCE, "ontology")
    queue = [n for n in nodes if n.startswith("concept:")]
    while queue:  # pull in prerequisites so "what must I know first" is part of the graph
        cid = queue.pop()
        for need in REQUIRES.get(nodes[cid]["label"], []):
            new = "concept:" + need not in nodes
            edge(cid, node("concept:" + need, "concept", need), "prerequisite", 1.0, "ontology")
            if new:
                queue.append("concept:" + need)
    return {"nodes": list(nodes.values()), "edges": list(edges.values()), "unsupported": unsupported, "undeclared": undeclared}


def adjacency(graph, kind):
    out = {}
    for e in graph["edges"]:
        if e["kind"] == kind:
            out.setdefault(e["source"], []).append(e["target"])
    return out


def reach(graph):
    """For each concept: the set of project ids whose technologies depend on it, directly or through prerequisites."""
    uses, requires, prereq = adjacency(graph, "uses"), adjacency(graph, "requires"), adjacency(graph, "prerequisite")
    result = {}
    for project in (n["id"] for n in graph["nodes"] if n["type"] == "project"):
        seen, stack = set(), [c for t in uses.get(project, []) for c in requires.get(t, [])]
        while stack:
            c = stack.pop()
            if c not in seen:
                seen.add(c)
                stack.extend(prereq.get(c, []))
        for c in seen:
            result.setdefault(c, set()).add(project)
    return result


def blast_radius(graph, topic):
    """Everything that depends on a concept: other concepts, technologies and projects."""
    target = "concept:" + topic
    reverse = {}
    for e in graph["edges"]:
        if e["kind"] in ("prerequisite", "requires"):
            reverse.setdefault(e["target"], []).append(e["source"])
    for e in graph["edges"]:
        if e["kind"] == "uses":
            reverse.setdefault(e["target"], []).append(e["source"])
    seen, stack = set(), [target]
    while stack:
        for parent in reverse.get(stack.pop(), []):
            if parent not in seen:
                seen.add(parent)
                stack.append(parent)
    by = {n["id"]: n for n in graph["nodes"]}
    pick = lambda kind: sorted(by[i]["label"] for i in seen if by[i]["type"] == kind)
    return {"topic": topic, "concepts": pick("concept"), "technologies": pick("technology"), "projects": pick("project")}
