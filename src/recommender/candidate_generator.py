from __future__ import annotations

import re
from collections import Counter

SUPPORTED_CATEGORIES = {"auto", "social", "vlog"}

_STOPWORDS = {
    "그리고", "하지만", "그래서", "이번", "영상", "대한", "대해", "관련", "내용", "정리",
    "이야기", "합니다", "했습니다", "있는", "없는", "하는", "되는", "것", "수", "더",
    "the", "and", "for", "with", "this", "that", "from", "about", "video", "youtube",
    "제목", "채널", "설명", "자막", "스크립트",
}

_SOCIAL_HINTS = {
    "정책", "사회", "경제", "정치", "노동", "교육", "부동산", "AI", "인공지능", "개발자",
    "기술", "산업", "법", "제도", "문제", "이슈", "환경", "기후", "커리어", "취업",
}

_VLOG_HINTS = {
    "브이로그", "vlog", "일상", "여행", "먹방", "카페", "맛집", "언박싱", "후기", "리뷰",
    "루틴", "운동", "메이크업", "쇼핑", "데이트", "제주", "서울", "부산", "여름", "겨울",
}

_TITLE_RE = re.compile(r"^제목:\s*(.+)$", re.MULTILINE)
_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9+#.-]{2,}")


def _clean_phrase(value: str, limit: int = 64) -> str:
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n-–—|:·")
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _extract_title(post_text: str) -> str:
    match = _TITLE_RE.search(post_text)
    if match:
        return _clean_phrase(match.group(1))

    first_line = next((line.strip() for line in post_text.splitlines() if line.strip()), "")
    first_line = re.sub(r"^(제목|설명|채널|스크립트|자막):\s*", "", first_line)
    return _clean_phrase(first_line or "이 주제")


def _extract_keywords(post_text: str, limit: int = 5) -> list[str]:
    tokens = []
    for raw in _TOKEN_RE.findall(post_text):
        token = raw.strip(".-").lower()
        if len(token) < 2 or token in _STOPWORDS or token.isdigit():
            continue
        tokens.append(token)

    counts = Counter(tokens)
    ranked = sorted(counts, key=lambda token: (-counts[token], tokens.index(token)))
    return ranked[:limit]


def infer_category(post_text: str) -> str:
    lowered = post_text.lower()
    social_score = sum(1 for hint in _SOCIAL_HINTS if hint.lower() in lowered)
    vlog_score = sum(1 for hint in _VLOG_HINTS if hint.lower() in lowered)
    return "vlog" if vlog_score > social_score else "social"


def _context_values(post_text: str, category: str) -> tuple[str, str, str, str]:
    title = _extract_title(post_text)
    keywords = _extract_keywords(post_text)
    primary = keywords[0] if keywords else title
    secondary = keywords[1] if len(keywords) > 1 else primary
    resolved_category = infer_category(post_text) if category == "auto" else category
    return title, primary, secondary, resolved_category


def _candidate_templates(category: str) -> list[tuple[str, str]]:
    common = [
        ("insight", "‘{title}’라는 주제를 이렇게 풀어낸 관점이 특히 인상적이네요."),
        ("insight", "{primary}를 단순한 결론보다 과정과 맥락으로 보여준 점이 좋았습니다."),
        ("insight", "{primary}와 {secondary}를 같이 보니 왜 이 주제가 중요한지 더 선명해지네요."),
        ("insight", "결국 {primary}를 볼 때 한 가지 기준보다 여러 조건을 함께 봐야 한다는 생각이 듭니다."),
        ("empathy", "{primary} 부분은 비슷한 고민을 해본 사람이라면 정말 공감할 것 같아요."),
        ("empathy", "설명만 듣는 것보다 실제 맥락과 함께 보니 {primary}가 훨씬 와닿네요."),
        ("empathy", "이 주제를 어렵게만 느꼈는데 영상 흐름대로 보니 이해가 훨씬 잘 됐어요."),
        ("question", "{primary}를 실제 상황에 적용할 때 가장 먼저 확인해야 할 조건은 무엇일까요?"),
        ("question", "{secondary}까지 고려하면 결론이 달라지는 경우도 있을지 궁금합니다."),
        ("question", "이 주제를 처음 접하는 사람이라면 {primary}부터 보는 게 좋을까요?"),
        ("casual", "{primary} 얘기 나오는 부분에서 바로 집중하게 되네요 ㅋㅋ 생각보다 현실적인 주제인 듯해요."),
        ("casual", "제목 보고 들어왔는데 {primary} 부분이 제일 기억에 남네요."),
        ("general", "핵심이 잘 정리되어 있어서 {primary} 관련해서 다시 찾아보고 싶어졌습니다."),
        ("general", "정보 밀도는 높은데 흐름이 자연스러워서 끝까지 보기 좋았어요."),
        ("general", "{primary}에 관심 있는 사람에게 공유하기 좋은 영상이네요."),
    ]

    if category == "vlog":
        return common + [
            ("casual", "{primary} 장면 분위기가 좋아서 저도 한번 직접 해보고 싶어지네요 ㅋㅋ"),
            ("casual", "이런 디테일 때문에 브이로그 보는 맛이 있는 것 같아요."),
            ("empathy", "{primary}에서 느껴지는 현실적인 분위기가 과하게 꾸민 느낌이 아니라 더 좋네요."),
            ("question", "{primary} 관련해서 실제로 가장 만족했던 선택은 뭐였는지 궁금해요!"),
            ("question", "다음 편에서도 {secondary} 관련 과정이나 비하인드도 보여주실 예정인가요?"),
            ("general", "편집이 과하지 않아서 {primary} 자체에 집중해서 보기 좋았습니다."),
            ("general", "비슷한 계획 있는 사람에게는 {primary} 부분이 특히 참고가 될 것 같아요."),
            ("empathy", "직접 해본 사람만 알 법한 포인트가 보여서 더 공감됐어요."),
            ("casual", "{title} 제목 그대로 기대한 내용이 잘 담겨 있어서 만족스럽네요."),
        ]

    return common + [
        ("insight", "{primary} 논의에서 결국 중요한 건 찬반보다 어떤 기준으로 판단하느냐인 것 같아요."),
        ("insight", "{primary}를 개인의 선택 문제로만 보지 않고 구조적인 맥락까지 연결한 점이 좋았습니다."),
        ("insight", "{secondary} 관점까지 같이 놓고 보면 같은 현상도 꽤 다르게 해석될 수 있겠네요."),
        ("question", "{primary}에 대해 반대 입장에서는 어떤 근거를 가장 중요하게 보는지도 궁금합니다."),
        ("question", "장기적으로 {primary}가 바뀐다면 가장 먼저 영향을 받을 부분은 어디일까요?"),
        ("empathy", "{primary}를 둘러싼 답답함을 느껴본 사람들에게는 특히 와닿을 내용 같아요."),
        ("general", "주장을 강하게 밀기보다 근거와 맥락을 같이 보여줘서 보기 편했습니다."),
        ("general", "{primary} 관련해서 의견이 달라도 한번쯤 생각해볼 지점이 있는 영상이네요."),
        ("casual", "댓글에서 {primary} 얘기가 많이 나올 것 같네요. 생각할 거리가 꽤 많았습니다."),
    ]


def generate_candidates(
    post_text: str,
    *,
    category: str = "auto",
    minimum_count: int = 10,
) -> list[dict]:
    """Generate deterministic, context-aware candidates for ranking."""
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError(f"지원되지 않는 category입니다: {category}")

    title, primary, secondary, resolved_category = _context_values(post_text, category)
    values = {"title": title, "primary": primary, "secondary": secondary}
    templates = _candidate_templates(resolved_category)
    target_pool_size = max(minimum_count * 2, 20)
    candidates: list[dict] = []
    seen: set[str] = set()

    for comment_type, template in templates:
        comment = _clean_phrase(template.format(**values), limit=190)
        if comment in seen:
            continue
        seen.add(comment)
        candidates.append({"type": comment_type, "comment": comment})

    variant_index = 1
    variant_types = ["insight", "empathy", "question", "casual", "general"]
    while len(candidates) < target_pool_size:
        comment_type = variant_types[(variant_index - 1) % len(variant_types)]
        if comment_type == "insight":
            text = f"{primary}를 볼 때 {secondary}까지 함께 고려해야 한다는 점이 이번 영상의 중요한 포인트 {variant_index}인 것 같아요."
        elif comment_type == "empathy":
            text = f"{primary} 부분은 실제 경험과 연결해서 보면 더 공감되는 지점이 많은 것 같아요 ({variant_index})."
        elif comment_type == "question":
            text = f"{primary}와 관련해 상황이 달라졌을 때도 같은 판단이 가능한지 궁금합니다 ({variant_index})."
        elif comment_type == "casual":
            text = f"{primary} 얘기는 볼수록 생각할 거리가 많네요 ㅋㅋ 특히 {secondary} 부분이 기억에 남아요 ({variant_index})."
        else:
            text = f"{primary}와 {secondary}를 함께 정리해줘서 핵심을 따라가기 좋았습니다 ({variant_index})."
        comment = _clean_phrase(text, limit=190)
        if comment not in seen:
            seen.add(comment)
            candidates.append({"type": comment_type, "comment": comment})
        variant_index += 1

    return candidates
