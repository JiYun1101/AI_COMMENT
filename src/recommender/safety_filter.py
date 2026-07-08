BLOCKED_KEYWORDS = [
    "죽어",
    "꺼져",
    "멍청",
    "병신",
    "혐오",
    "최악",
    "개새",
    "닥쳐",
]


def is_safe_comment(comment: str) -> bool:
    if not comment:
        return False

    text = comment.strip()

    if len(text) < 5:
        return False

    if len(text) > 200:
        return False

    for keyword in BLOCKED_KEYWORDS:
        if keyword in text:
            return False

    return True


def filter_safe_comments(candidates: list[dict]) -> list[dict]:
    safe_candidates = []

    for item in candidates:
        comment = item.get("comment", "")

        if is_safe_comment(comment):
            safe_candidates.append(item)

    return safe_candidates