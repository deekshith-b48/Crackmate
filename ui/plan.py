"""Local schedule inputs and study-plan display."""
from datetime import datetime, time, timedelta

import streamlit as st

from core.export import NOTICE, item_markdown, parse_item
from core.planning import PlanInput, plan_request
from ui.common import download, safe_markdown


def plan_status(app, item, requests, attempts, *, now=None):
    if item is None:
        return False
    plan = parse_item(item)
    if (now or datetime.now()) >= plan.inputs.interview:
        return False
    try:
        request = plan_request(app.profile, plan.inputs, attempts, requests)
    except ValueError:
        return False
    return app.material.current(app.record, request, item)


def jump_to(slot):
    kind, primary, secondary = slot.split(":", 2)
    if kind == "project":
        st.session_state["Project"] = primary
        st.session_state["Project section"] = secondary
        page = "Projects"
    else:
        st.session_state["Difficulty"] = primary
        st.session_state["Topic"] = secondary
        page = "Skills"
    st.session_state["navigation_target"] = page
    st.rerun()


def render(app):
    st.title("Preparation plan")
    st.caption("Fit the highest-priority material into your actual study time before the interview.")
    record = app.record
    item = app.store.item(record.id, "plan")
    previous = parse_item(item) if item else None
    now = datetime.now().replace(second=0, microsecond=0)
    attempts = app.store.attempts(record.id)
    lessons = [entry for entry in app.store.items(record.id) if entry.kind in ("project", "skill")]
    interview = previous.inputs.interview if previous else datetime.combine(now.date() + timedelta(days=1), time(10))
    with st.form(f"plan:{record.id}:{record.revision}"):
        date_column, time_column, hours_column = st.columns(3)
        date = date_column.date_input("Interview date", interview.date(), min_value=min(now.date(), interview.date()))
        when = time_column.time_input("Interview time (local)", interview.time(), step=60)
        hours = hours_column.number_input(
            "Available study hours", min_value=0.25, max_value=24.0, step=0.25,
            value=previous.inputs.budget / 60 if previous else 2.0,
        )
        weak = st.text_area("Weak areas (optional)", previous.inputs.weak_areas if previous else "", max_chars=1500)
        role = st.text_area("Additional role context (optional)", previous.inputs.role_context if previous else "", max_chars=1500)
        st.caption("The schedule starts at the current local time, reserves 23:00–07:00 for sleep, and leaves 15 minutes before the interview.")
        first, second = st.columns(2)
        generate = first.form_submit_button("Build plan", type="primary", disabled=not app.settings.api_key)
        redo = second.form_submit_button("Regenerate plan", disabled=not app.settings.api_key or item is None)

    fresh = False
    if generate or redo:
        def build(progress):
            # Keep saved windows for identical inputs or explicit regeneration before the first window expires.
            base_start = now
            interview_at = datetime.combine(date, when)
            budget = round(hours * 60)
            if previous and previous.inputs.interview > now:
                saved = previous.inputs
                unchanged = (interview_at, budget, weak.strip(), role.strip()) == (
                    saved.interview, saved.budget, saved.weak_areas, saved.role_context
                )
                if unchanged and not redo:
                    old_request = plan_request(app.profile, saved, attempts, lessons)
                    if app.material.current(record, old_request, item):
                        return item, False
                if unchanged and previous.windows and previous.windows[0].start >= now:
                    base_start = saved.start
            inputs = PlanInput(start=base_start, interview=interview_at, budget=budget, weak_areas=weak, role_context=role)
            request = plan_request(app.profile, inputs, attempts, lessons)
            return app.material.generate(record, request, regenerate=redo, progress=progress)
        result = app.action(build, "Checking time and generating a plan…")
        if result:
            item, fresh = result
    if not item:
        st.info("Build a plan to see what to study, why it matters, and how to check your progress.")
        return

    current = plan_status(app, item, lessons, attempts, now=now)
    if not current:
        st.warning("Outdated · Profile, resources, practice results, model settings, or interview timing changed.")
    else:
        st.caption("Newly generated and saved" if fresh else "Saved plan")
    plan = parse_item(item)
    total = sum(block.duration_minutes for block in plan.blocks)
    until = max(0, int((plan.inputs.interview - now).total_seconds() // 60))
    st.subheader("Study schedule")
    elapsed, budget = st.columns(2)
    elapsed.metric("Time until interview", f"{until // 60}h {until % 60}m")
    budget.metric("Planned study time", f"{total // 60}h {total % 60}m")
    st.caption("Ten-minute breaks between nearby blocks. Times are in your computer’s local time.")
    for index, (window, block) in enumerate(zip(plan.windows, plan.blocks, strict=True), 1):
        timing = f"{window.start:%a %d %b %H:%M}–{window.end:%H:%M}"
        with st.expander(f"{timing} · {block.duration_minutes} min · {block.topic}", expanded=index == 1):
            st.markdown("**Reason**")
            safe_markdown(block.reason)
            st.markdown("**Measurable outcome**")
            safe_markdown(block.outcome)
            slot = plan.links.get(block.reference)
            if current and slot and st.button("Open relevant lesson", key=f"plan-link:{index}"):
                jump_to(slot)
    download("Download preparation plan", NOTICE + "\n\n" + item_markdown(item, outdated=not current),
             "crackmate-plan.md", "plan-download")
