"""Company mode: which DSA problems a company tags most."""
from core.company import FALLBACK_TOPICS, WINDOWS, companies, focus_topics, problems
import streamlit as st


def render(app):
    st.title("Company DSA")
    st.caption("Problems a company is reported to tag most often. Frequencies are community-reported and relative, "
               "never a guarantee. Use them to decide where to spend your DSA time.")
    try:
        names = companies()
    except ValueError as exc:
        st.warning(f"{exc} Showing general DSA topics instead.")
        st.write(", ".join(FALLBACK_TOPICS))
        return
    mine = (app.record.profile.company or "").casefold() if app.record else ""
    index = next((i for i, n in enumerate(names) if n.casefold() == mine), 0)
    company = st.selectbox("Company", names, index=index)
    window = st.radio("Time window", list(WINDOWS), index=len(WINDOWS) - 1, horizontal=True)
    levels = st.multiselect("Difficulty", ["Easy", "Medium", "Hard"], default=["Easy", "Medium", "Hard"])
    try:
        rows = [r for r in problems(company, window) if r["Difficulty"] in levels][:30]
    except ValueError as exc:
        st.warning(str(exc))
        return
    if not rows:
        st.info("No problems for this choice. Try another time window.")
        return
    st.markdown("#### Focus topics")
    st.write(" · ".join(f"{topic} ({n})" for topic, n in focus_topics(rows)))
    st.dataframe(rows, hide_index=True, column_config={
        "Frequency": st.column_config.NumberColumn(format="%.0f"),
        "Link": st.column_config.LinkColumn("LeetCode", display_text="Open")})
    st.caption("Data: [liquidslr/leetcode-company-wise-problems](https://github.com/liquidslr/leetcode-company-wise-problems), "
               "fetched live and cached for 24 hours. Problem statements stay on LeetCode.")
