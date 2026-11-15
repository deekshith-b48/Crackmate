"""The Interview Brief: one Markdown file with everything you have prepared. Deterministic: it only gathers saved data."""
import json
from datetime import date

from api.services import artifacts, career
from core.export import NOTICE, clean

MISSING = "_Not generated yet._"


def _saved(core, record, kind, project_id=""):
    try:
        return artifacts.state(core, record, kind, project_id)["data"]
    except ValueError:
        return None  # e.g. nothing to build it from yet


def _answers(core, record, topics, per_topic=2):
    """First saved questions and answers for each topic that has a lesson."""
    out = []
    for topic in topics:
        for item in core.store.items(record.id):
            if item.kind == "skill" and item.title.split(" · ")[0] == topic:
                for q in json.loads(item.body).get("questions", [])[:per_topic]:
                    out.append((topic, q["question"], q["answer"]))
                break
    return out


def build(core, record):
    profile, signals = record.profile, career.signals(core, record)
    cards = {c["project_id"]: c for c in career.overview(core, record)}
    risks = [t for t in signals["topics"] if t["risk"] > 0][:8]
    lines = [f"# Interview brief: {profile.name or 'Candidate'}", f"{profile.role or 'Target role not set'}" + (f" at {profile.company}" if profile.company else "") + f" · prepared {date.today():%d %b %Y}", NOTICE]
    check = {"pitches": [0, len(profile.projects)], "decisions": [0, 0], "lessons": 0, "claim_check": False, "repos": len(cards) and sum(1 for c in cards.values() if c["repo"])}

    lines += ["## Snapshot", profile.summary or "_Add a summary in Resume and profile._"]
    skills = [f"**{k.replace('_', ' ').title()}:** {', '.join(v)}" for k, v in profile.skills.model_dump().items() if v]
    lines += ["\n".join(f"- {s}" for s in skills)] if skills else []
    lines += [f"**Readiness:** {signals['overall'] if signals['overall'] is not None else 'not assessed yet'}"
              + (f"/10 across {signals['assessed']} of {signals['total']} topics" if signals["overall"] is not None else "") + "."]

    lines += ["## Your projects"]
    for p in profile.projects:
        card = cards.get(p.id, {})
        lines += [f"### {p.title}", f"Stack: {', '.join(p.technologies) or 'not listed'}." + (f" You wrote about {round(card['repo']['ownership']['share'] * 100)}% of the added lines." if card.get("repo") and card["repo"]["ownership"]["identified"] else "")]
        pitch = _saved(core, record, "pitch", p.id)
        lines += ["**2-minute pitch**", pitch["pitch"] if pitch else MISSING]
        check["pitches"][0] += bool(pitch)
        if card.get("repo"):
            hot = card["repo"]["hotspots"][:3]
            lines += ["**Talking points (where the hard problems were):** " + (", ".join(f"`{h['path']}`" for h in hot) or "not enough history yet.")]
            if card["repo"]["secrets"]:
                lines += [f"**Security flag:** {len(card['repo']['secrets'])} possible committed secret(s). Rotate and remove them before any interview."]
            decisions = _saved(core, record, "decisions", p.id)
            check["decisions"][1] += 1
            check["decisions"][0] += bool(decisions)
            for d in (decisions or {}).get("decisions", [])[:3]:
                lines += [f"**Decision: {d['title']}** ({d['confidence']} confidence)\n\nLikely question: {d['tradeoff_question']}\n\nAnswer: {d['answer']}"]

    lines += ["## Top interview risks (study these first)"]
    lines += ["\n".join(f"{i}. **{t['topic']}**: risk {t['risk']}/10, " + (f"readiness {t['readiness']}/10" if t["assessed"] else "not assessed yet") for i, t in enumerate(risks, 1))] if risks else [MISSING]

    claims = [r for r in career.claims(core, record) if r["tier"] in ("Low", "Unchecked")]
    claim_check = _saved(core, record, "claims")
    lines += ["## Resume claims to be ready to defend"]
    lines += ["\n".join(f"- **{r['technology']}** ({r['project']}): {r['tier_note']}" for r in claims[:8])] if claims else ["Every technology you list is backed by code you attached."]
    if claim_check:
        check["claim_check"] = True
        state = artifacts.state(core, record, "claims")
        ticked = set(state.get("ticked", []))
        open_claims = [c for i, c in enumerate(claim_check["claims"]) if i not in ticked and c["risk"] != "low"][:6]
        lines += ["\n".join(f"- {c['claim']}\n  - Likely question: {c['probe']}" for c in open_claims)] if open_claims else []

    answers = _answers(core, record, [t["topic"] for t in risks[:5]])
    check["lessons"] = len({a[0] for a in answers})
    lines += ["## Key answers to rehearse"]
    lines += ["\n\n".join(f"**{q}** _({topic})_\n\n{a}" for topic, q, a in answers)] if answers else [MISSING + " Generate lessons for your top risks to fill this in."]

    lines += ["## Honesty note", "Questions are the most likely ones, never guaranteed. Anything marked (Assumption) is inferred, not stated in your resume or code."]
    return {"markdown": clean("\n\n".join(l for l in lines if l)) + "\n", "checklist": check}
