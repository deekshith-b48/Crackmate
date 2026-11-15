"""Resume technology claims judged against the real code, in evidence tiers. Deterministic: no model.

High    imported in the project's code (the strongest evidence we can find without reading it).
Medium  declared in a dependency or config file.
Low     claimed on the resume but not found anywhere in the attached repository.
Unchecked  no repository attached, so we cannot say either way.
"""
from core.career.ontology import TECH_CONCEPTS, canon

TIERS = {"High": "Imported in your code.", "Medium": "Declared in a dependency or config file.",
         "Low": "Not found in the attached repository. It may live elsewhere, but expect to be asked where.",
         "Unchecked": "No repository attached, so this cannot be checked yet."}
ORDER = {"Low": 0, "Unchecked": 1, "Medium": 2, "High": 3}


def _tier(found, has_repo):
    if not has_repo:
        return "Unchecked"
    if found is None:
        return "Low"
    return "High" if found["confidence"] >= 0.9 else "Medium"


def rows(profile, repo_facts, signals):
    """One row per (project, technology) you state, plus listed skills that no project mentions."""
    by_topic = {t["topic"]: t for t in signals["topics"]}
    out, in_projects = [], set()

    def add(project_id, project, tech, found, has_repo):
        concepts = [c for c in TECH_CONCEPTS[tech] if c in by_topic]
        scored = [by_topic[c]["readiness"] for c in concepts if by_topic[c]["readiness"] is not None]
        weakest = max(concepts, key=lambda c: by_topic[c]["risk"], default=None)
        tier = _tier(found, has_repo)
        out.append({"project_id": project_id, "project": project, "technology": tech, "tier": tier, "tier_note": TIERS[tier],
                    "evidence": (found or {}).get("evidence", []), "confidence": (found or {}).get("confidence"),
                    "readiness": round(sum(scored) / len(scored), 1) if scored else None,
                    "risk": max((by_topic[c]["risk"] for c in concepts), default=0.0), "weakest_concept": weakest})

    for project in profile.projects:
        facts = repo_facts.get(project.id)
        found = {t["name"]: t for t in (facts or {}).get("technologies", [])}
        for tech in dict.fromkeys(canon(t) for t in project.technologies):
            if tech in TECH_CONCEPTS:
                in_projects.add(tech)
                add(project.id, project.title, tech, found.get(tech), facts is not None)
    for skill in (s for group in profile.skills.model_dump().values() for s in group):
        tech = canon(skill)
        if tech in TECH_CONCEPTS and tech not in in_projects:
            in_projects.add(tech)
            add("", "Skills section", tech, None, False)
    return sorted(out, key=lambda r: (ORDER[r["tier"]], -r["risk"], r["technology"]))
