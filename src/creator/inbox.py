"""작성자 본인 영상에 달린 댓글을 분류하고, 먼저 답해야 할 순서로 정렬한다.

분류는 규칙 기반이다. 영상 반응 미리보기의 6개 반응 분류와 같은 신호(질문 표지,
불만 어휘, 리스크 어휘)를 쓰고, 욕설·혐오·위협·스팸 판정은 추천 파이프라인의
안전 필터(get_block_reason)를 그대로 재사용해 기준을 한 곳에 둔다.
"""

from __future__ import annotations

import math
import re

from src.recommender.safety_filter import get_block_reason

CATEGORIES = ("question", "complaint", "risk", "praise", "other")
CATEGORY_LABELS = {
    "question": "질문",
    "complaint": "불만·개선 요청",
    "risk": "확인 필요",
    "praise": "칭찬·응원",
    "other": "기타",
}

UNSAFE_REASONS = {"profanity", "hate_speech", "threat", "spam"}
RISK_RE = re.compile(r"(사기|거짓말|조작|불법|허위|과장\s*광고|뒷광고|신고|고소|환불|저작권)")
QUESTION_RE = re.compile(
    r"(궁금|어떻게|어디서|언제|무슨|뭔가요|뭐예요|뭐에요|인가요|나요\b|까요\b|알려\s*주|가르쳐\s*주|추천\s*해\s*주)"
)
COMPLAINT_RE = re.compile(
    r"(별로|아쉽|실망|불만|불편|비싸|최악|답답|지루|소리가\s*작|화질이\s*(별로|안\s*좋|나쁘|구리)|광고가\s*너무|너무\s*길|개선|틀렸|잘못)"
)
PRAISE_RE = re.compile(r"(감사|고마|최고|좋아요|좋네요|좋았|잘\s*봤|잘봤|응원|유익|도움|재밌|재미있|멋지|대박|힐링|만족)")

# 답이 필요한 댓글일수록 위로. 이미 작성자가 답한 댓글은 크게 내린다.
BASE_PRIORITY = {"question": 60, "risk": 50, "complaint": 45, "praise": 15, "other": 10}


def classify_inbox_comment(text: str) -> tuple[str, str | None]:
    """(분류, 안전 필터 사유)를 돌려준다. 사유는 risk일 때만 채운다."""
    normalized = (text or "").strip()
    reason = get_block_reason(normalized)
    if reason in UNSAFE_REASONS:
        return "risk", reason
    if RISK_RE.search(normalized):
        return "risk", "dispute"
    if "?" in normalized or "？" in normalized or QUESTION_RE.search(normalized):
        return "question", None
    if COMPLAINT_RE.search(normalized):
        return "complaint", None
    if PRAISE_RE.search(normalized):
        return "praise", None
    return "other", None


def _priority(category: str, *, like_count: int, reply_count: int, creator_replied: bool) -> float:
    score = BASE_PRIORITY[category]
    if creator_replied:
        score -= 40
    score += min(25.0, 6 * math.log2(1 + max(0, like_count)))
    score += min(10, 2 * max(0, reply_count))
    return round(max(0.0, score), 1)


def build_inbox(threads: list[dict], *, channel_id: str | None) -> dict:
    """댓글 스레드 목록을 받은 댓글함 항목과 요약으로 바꾼다.

    작성자 본인이 단 최상위 댓글(고정 댓글 등)은 답할 대상이 아니라서 제외한다.
    답글은 스레드당 최대 5개만 내려오므로, 그 안에 작성자 답글이 없으면 '미답변'으로 본다.
    """
    items: list[dict] = []
    own_count = 0
    for thread in threads:
        if channel_id and thread.get("author_channel_id") == channel_id:
            own_count += 1
            continue
        category, reason = classify_inbox_comment(thread.get("text", ""))
        creator_replied = bool(channel_id) and any(
            reply.get("author_channel_id") == channel_id for reply in thread.get("replies") or []
        )
        needs_reply = category in {"question", "complaint"} and not creator_replied
        items.append(
            {
                "id": thread["id"],
                "author": thread.get("author") or "",
                "text": thread.get("text") or "",
                "like_count": int(thread.get("like_count") or 0),
                "reply_count": int(thread.get("reply_count") or 0),
                "published_at": thread.get("published_at"),
                "can_reply": bool(thread.get("can_reply", True)),
                "category": category,
                "category_label": CATEGORY_LABELS[category],
                "risk_reason": reason,
                "creator_replied": creator_replied,
                "needs_reply": needs_reply,
                "priority": _priority(
                    category,
                    like_count=int(thread.get("like_count") or 0),
                    reply_count=int(thread.get("reply_count") or 0),
                    creator_replied=creator_replied,
                ),
            }
        )

    items.sort(key=lambda item: (-item["priority"], -item["like_count"]))
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "needs_reply": sum(1 for item in items if item["needs_reply"]),
            "creator_replied": sum(1 for item in items if item["creator_replied"]),
            "own_comments": own_count,
            "by_category": {key: sum(1 for item in items if item["category"] == key) for key in CATEGORIES},
        },
    }
