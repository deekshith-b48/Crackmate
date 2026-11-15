"""Is a generated page still fresh, and if not, why? Deterministic: compares stored fingerprints, no model."""


def check(material, record, request, item):
    """Return (status, why) where status is 'none', 'fresh' or 'stale'."""
    if item is None:
        return "none", "Not generated yet."
    if material.current(record, request, item):
        return "fresh", "Up to date with your profile, sources and models."
    if item.model not in material.models():
        return "stale", f"Written with {item.model.split('/')[-1]}, but your configured models changed."
    code = material._enrich(record, request).context.get("code")
    if code:
        return "stale", f"Your repository (now at commit {code['commit']}) or your profile changed since this was written."
    return "stale", "Your profile, project details or knowledge-base sources changed since this was written."
