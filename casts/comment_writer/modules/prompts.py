"""Optional regenerate feedback; actual prompts stay in src/llm provider clients."""
def build_revision_feedback(*, blocked=None, duplicate_count: int = 0, shortfall: int = 0) -> str:
    reasons = sorted({str(x.get("reason")) for x in (blocked or []) if x.get("reason")})
    parts = []
    if reasons:
        parts.append(f"Candidates blocked by: {', '.join(reasons)}.")
    if duplicate_count:
        parts.append(f"{duplicate_count} duplicate comments were removed.")
    if shortfall:
        parts.append(f"{shortfall} more unique safe comments are needed.")
    return " ".join(parts)
