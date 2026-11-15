"""Resume Claim Checker: every resume line becomes a claim an interviewer may probe."""
import streamlit as st

from core.export import claims_markdown
from core.material import claims_request
from core.review import ClaimTicks
from core.schemas import ClaimReport
from ui.common import download, safe_markdown

def open_claims(app, limit=6):
    """Medium and high-risk claims from the current saved claim check that you have not ticked as defended."""
    request = claims_request(app.profile)
    item = app.store.item(app.record.id, request.slot)
    if not item or not app.material.current(app.record, request, item):
        return []
    report = ClaimReport.model_validate_json(item.body)
    done = ClaimTicks(app.store).get(app.record.id, item.digest)
    return [{"claim": c.claim, "likely_question": c.probe}
            for i, c in enumerate(report.claims) if i not in done and c.risk != "low"][:limit]


RISK = {"high": "🔴", "medium": "🟠", "low": "🟢"}


def render(app):
    st.title("Claim Checker")
    st.caption("Each claim is something an interviewer may probe. Questions are most likely, never guaranteed.")
    profile = app.profile
    if not (profile.projects or profile.work_experience):
        st.info("Add a project or work experience in Resume and profile first.")
        return
    request, record = claims_request(profile), app.record
    item = app.store.item(record.id, request.slot)
    current = item is not None and app.material.current(record, request, item)
    start, redo = st.columns(2)
    go = start.button("Load saved check" if current else "Check my claims", type="primary",
                      disabled=not current and not app.settings.api_key)
    again = bool(item) and redo.button("Re-check", disabled=not app.settings.api_key)
    if go or again:
        result = app.action(lambda progress: app.material.generate(
            record, request, regenerate=again, progress=progress), "Finding claims to defend…")
        if result:
            item, current = result[0], True
    if not item:
        st.info("Check your resume claims when you are ready.")
        return
    if not current:
        st.warning("Outdated · Your profile changed since this check. Re-check to update.")
    report = ClaimReport.model_validate_json(item.body)
    order = sorted(range(len(report.claims)), key=lambda i: list(RISK).index(report.claims[i].risk))
    ticks = ClaimTicks(app.store)
    saved = ticks.get(record.id, item.digest)
    key = lambda i: f"defended:{record.id}:{item.digest[:8]}:{i}"
    defended = {i for i in order if st.session_state.get(key(i), i in saved)}
    risky = sum(report.claims[i].risk == "high" and i not in defended for i in order)
    st.metric("Claims you can defend", f"{len(defended)} / {len(order)}", f"{risky} high-risk still open", delta_color="inverse")
    for i in order:
        claim = report.claims[i]
        mark = "✅" if i in defended else RISK[claim.risk]
        with st.expander(f"{mark} {claim.claim}"):
            st.caption(f"{claim.source} · {claim.kind} · {claim.risk} risk")
            safe_markdown(f"**Why it is risky:** {claim.why}")
            safe_markdown(f"**Most likely question:** {claim.probe}")
            safe_markdown(f"**Be ready to explain:** {claim.defend}")
            safe_markdown(f"**How to prepare:** {claim.prepare}")
            st.checkbox("I can defend this out loud", value=i in saved, key=key(i),
                        on_change=lambda i=i: ticks.set(record.id, item.digest, i, st.session_state[key(i)]))
    download("Download claim check", claims_markdown(report, defended), "crackmate-claims.md", "claims-download")
