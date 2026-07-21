import re
import unicodedata

# 욕설/비속어 — 실제 수집 데이터(social_issues/vlog)에서 기존 필터를 통과한
# 사례를 분석해 추가한 항목 포함 (시발/지랄/걸레/미친놈 등).
# 기존 목록에 있던 "혐오"/"최악"은 제외했다: "혐오와 갈등은 어디서 생기는가"
# 같은 정상적인 사회 논의나 "일본 음식은 최악"처럼 단순히 강한 부정 의견까지
# 차단해버리는 오탐이 실데이터에서 다수 확인되어, 비속어가 아닌 주제/감정
# 단어는 안전 필터 대상에서 제외한다.
PROFANITY_KEYWORDS = [
    "시발", "씨발", "씨팔", "십발", "병신", "븅신", "ㅄ", "좆", "좇",
    "개새끼", "개새", "개소리", "미친놈", "미친년", "지랄", "걸레같",
    "창녀", "닥치고", "꺼져", "멍청",
]

# 단순 부분일치로는 오탐이 나는 항목은 정규식으로 예외를 둔다.
# "닥쳐"(닥치다=입 다물다, 욕설) vs "닥쳐오다/닥쳐올"(다가오다, 무관한 동사).
# "올"은 "오"에 받침 ㄹ이 붙은 별개 음절이라 "오"만 제외하면 걸러지지
# 않으므로 두 형태를 모두 예외 처리한다.
PROFANITY_PATTERNS = [
    r"닥쳐(?!오|올)",
]
PROFANITY_RE = re.compile("|".join(PROFANITY_PATTERNS))

# 혐오/차별 표현 (특정 집단 비하). "한남"처럼 짧은 2글자 토큰은 "착한남편",
# "전역한 남편"처럼 무관한 단어 중간에 우연히 걸리는 오탐이 많아 제외하고,
# 오탐 위험이 낮은 합성 비속어(한남충 등)만 사용한다.
HATE_KEYWORDS = [
    "한남충", "김치녀", "맘충", "급식충", "틀딱", "짱깨",
    "페미나치", "장애인같",
]

# 위협/자해 조장 — 구체적 위협 문구만 매칭. "죽어라"(죽어라 노력해라 = 열심히
# 하라는 흔한 관용구), "죽인다"/"뒤진다"(이 노래 죽인다 = 최고다, 서랍을
# 뒤진다 = 뒤지다/검색하다)는 일상적으로 위협이 아닌 의미로 훨씬 더 많이
# 쓰이므로 제외하고, 오탐 위험이 낮은 명확한 위협 표현만 남긴다.
THREAT_PATTERNS = [
    r"죽여버(리겠|릴|린다|려)", r"뒤져라", r"자살해", r"자살하자",
    r"칼로\s*찔러",
]

# 스팸/홍보 — data/raw 실데이터 분석 결과 구독 유도 문구가 다수 발견되어 추가
SPAM_PATTERNS = [
    r"구독\s*(부탁|눌러|좀|해주)",
    r"좋아요\s*(부탁|눌러|좀)",
    r"https?://",
    r"카톡\s*(아이디|추가)",
    r"오픈\s*채팅",
    r"텔레그램",
    r"라인\s*아이디",
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    r"\d{2,3}[-.]\d{3,4}[-.]\d{4}",
    r"(맞팔|서이추|품앗이)",
]
SPAM_RE = re.compile("|".join(SPAM_PATTERNS), flags=re.IGNORECASE)
THREAT_RE = re.compile("|".join(THREAT_PATTERNS))


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def get_block_reason(comment: str) -> str | None:
    """댓글을 차단해야 하면 사유 문자열을, 안전하면 None을 반환.

    글자 사이에 공백/기호를 끼워 넣는 우회 표기까지 잡으려는 압축 매칭은
    시도하지 않는다: "다시 발리에" -> "다시발리에"(시발 포함), "착한 남편"
    -> "착한남편"(한남 포함)처럼 단어 경계를 넘나드는 오탐이 실데이터에서
    다수 확인된 반면, 실제 우회 표기 사례는 발견되지 않아 이득보다 손해가 컸다.
    """
    if not comment:
        return "empty"

    text = comment.strip()

    if len(text) < 5:
        return "too_short"

    if len(text) > 200:
        return "too_long"

    normalized = _normalize(text)

    for keyword in PROFANITY_KEYWORDS:
        if keyword in normalized:
            return "profanity"

    if PROFANITY_RE.search(normalized):
        return "profanity"

    for keyword in HATE_KEYWORDS:
        if keyword in normalized:
            return "hate_speech"

    if THREAT_RE.search(normalized):
        return "threat"

    if SPAM_RE.search(normalized):
        return "spam"

    return None


def is_safe_comment(comment: str) -> bool:
    return get_block_reason(comment) is None


def filter_safe_comments(candidates: list[dict]) -> list[dict]:
    safe_candidates = []

    for item in candidates:
        comment = item.get("comment", "")

        if is_safe_comment(comment):
            safe_candidates.append(item)

    return safe_candidates
