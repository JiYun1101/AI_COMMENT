import re
from pathlib import Path

import joblib
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = BASE_DIR / "models" / "comment_ranker.joblib"


FALLBACK_FEATURE_COLUMNS = [
    "comment_length",
    "word_count",
    "sentence_count",
    "question_count",
    "exclamation_count",
    "laugh_count",
    "sad_count",
    "has_question",
    "has_url",
    "has_number",
    "casual_score",
    "empathy_score",
    "insight_score",
    "criticism_score",
    "post_comment_overlap_count",
    "post_comment_jaccard",
    "post_comment_coverage",
    "post_comment_length_ratio",
]


TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]+")
KOREAN_PARTICLES = [
    "으로부터",
    "으로서",
    "으로써",
    "에게서",
    "한테서",
    "에서는",
    "에서",
    "에게",
    "한테",
    "으로",
    "라고",
    "처럼",
    "보다",
    "부터",
    "까지",
    "마다",
    "조차",
    "마저",
    "밖에",
    "이나",
    "나",
    "이랑",
    "랑",
    "하고",
    "와",
    "과",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "에",
    "의",
    "도",
    "만",
    "로",
]
URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)


CASUAL_KEYWORDS = [
    "ㅋㅋ",
    "ㅎㅎ",
    "진짜",
    "완전",
    "대박",
    "와",
    "헐",
    "ㄹㅇ",
]

EMPATHY_KEYWORDS = [
    "공감",
    "와닿",
    "맞아요",
    "저도",
    "나도",
    "진짜",
    "그렇죠",
    "이해",
]

INSIGHT_KEYWORDS = [
    "핵심",
    "결국",
    "중요",
    "관점",
    "설계",
    "정의",
    "본질",
    "방향",
    "구조",
    "문제 정의",
]

CRITICISM_KEYWORDS = [
    "별로",
    "문제다",
    "아쉽",
    "비판",
    "틀렸",
    "최악",
    "이상하다",
    "불편",
]


def count_keywords(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def tokenize_text(text: str) -> set[str]:
    if not isinstance(text, str):
        return set()

    tokens = TOKEN_PATTERN.findall(text.lower())

    return {
        token
        for token in tokens
        if len(token) >= 2
    }

def normalize_token(token: str) -> str:
    token = token.lower().strip()

    for particle in KOREAN_PARTICLES:
        if token.endswith(particle) and len(token) > len(particle) + 1:
            token = token[: -len(particle)]
            break

    return token


def tokenize_text(text: str) -> set[str]:
    if not isinstance(text, str):
        return set()

    raw_tokens = TOKEN_PATTERN.findall(text.lower())

    tokens = set()

    for token in raw_tokens:
        normalized = normalize_token(token)

        if len(normalized) >= 2:
            tokens.add(normalized)

    return tokens

def calculate_context_features(post_text: str, comment_text: str) -> dict:
    post_tokens = tokenize_text(post_text)
    comment_tokens = tokenize_text(comment_text)

    if not post_tokens or not comment_tokens:
        return {
            "post_comment_overlap_count": 0,
            "post_comment_jaccard": 0.0,
            "post_comment_coverage": 0.0,
            "post_comment_length_ratio": 0.0,
        }

    intersection = post_tokens & comment_tokens
    union = post_tokens | comment_tokens

    post_length = max(len(str(post_text)), 1)
    comment_length = len(str(comment_text))

    return {
        "post_comment_overlap_count": len(intersection),
        "post_comment_jaccard": len(intersection) / len(union),
        "post_comment_coverage": len(intersection) / len(post_tokens),
        "post_comment_length_ratio": comment_length / post_length,
    }

def calculate_context_score(post_text: str, comment_text: str) -> float:
    context = calculate_context_features(post_text, comment_text)

    overlap_count = context["post_comment_overlap_count"]
    jaccard = context["post_comment_jaccard"]
    coverage = context["post_comment_coverage"]

    overlap_score = min(overlap_count / 2, 1.0)
    jaccard_score = min(jaccard * 5, 1.0)
    coverage_score = min(coverage * 3, 1.0)

    context_score = (
        overlap_score * 0.45
        + jaccard_score * 0.25
        + coverage_score * 0.30
    )

    return max(0.0, min(context_score, 1.0))
    
def extract_simple_features(post_text: str, comment: str) -> dict:
    post_text = post_text or ""
    comment = comment or ""

    features = {
        "comment_length": len(comment),
        "word_count": len(comment.split()),
        "sentence_count": max(
            1,
            comment.count(".") + comment.count("!") + comment.count("?"),
        ),
        "question_count": comment.count("?"),
        "exclamation_count": comment.count("!"),
        "laugh_count": comment.count("ㅋㅋ") + comment.count("ㅎㅎ"),
        "sad_count": (
            comment.count("ㅠㅠ")
            + comment.count("ㅜㅜ")
            + comment.count("ㅠ")
            + comment.count("ㅜ")
        ),
        "has_question": int("?" in comment),
        "has_url": int(bool(URL_PATTERN.search(comment))),
        "has_number": int(any(char.isdigit() for char in comment)),
        "casual_score": count_keywords(comment, CASUAL_KEYWORDS),
        "empathy_score": count_keywords(comment, EMPATHY_KEYWORDS),
        "insight_score": count_keywords(comment, INSIGHT_KEYWORDS),
        "criticism_score": count_keywords(comment, CRITICISM_KEYWORDS),
    }

    features.update(calculate_context_features(post_text, comment))

    return features


def load_ranker_model():
    loaded = joblib.load(MODEL_PATH)

    if isinstance(loaded, dict):
        model = loaded.get("model")

        if model is None:
            raise ValueError(
                "comment_ranker.joblib이 dict로 저장되어 있지만 'model' 키가 없습니다."
            )

        feature_columns = loaded.get("feature_columns", FALLBACK_FEATURE_COLUMNS)

        return model, feature_columns

    return loaded, FALLBACK_FEATURE_COLUMNS


def score_comments(post_text: str, comments: list[str]) -> list[dict]:
    model, feature_columns = load_ranker_model()

    rows = [
        extract_simple_features(post_text, comment)
        for comment in comments
    ]

    X = pd.DataFrame(rows)

    for column in feature_columns:
        if column not in X.columns:
            X[column] = 0

    X = X[feature_columns].fillna(0)

    if hasattr(model, "predict_proba"):
        model_scores = model.predict_proba(X)[:, 1]
    else:
        model_scores = model.predict(X)

    context_scores = [
        calculate_context_score(post_text, comment)
        for comment in comments
    ]

    scores = []

    for model_score, context_score in zip(model_scores, context_scores):
        final_score = (model_score * 0.60) + (context_score * 0.40)

        # 게시글과 거의 안 맞는 댓글은 품질이 좋아도 추천 점수 하락
        if context_score == 0:
            final_score *= 0.55
        elif context_score < 0.15:
            final_score *= 0.75

        scores.append(final_score)

    results = []

    for comment, score in zip(comments, scores):
        results.append(
            {
                "comment": comment,
                "score": round(float(score) * 100, 2),
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)

    return results


if __name__ == "__main__":
    sample_post = "AI 시대에 개발자는 어떻게 살아남아야 할까?"
    sample_comments = [
        "결국 문제를 정의하는 능력이 중요해질 것 같아요.",
        "좋은 글 감사합니다.",
        "이건 생각보다 현실적인 문제라 더 와닿네요 ㅋㅋ",
    ]

    result = score_comments(
        post_text=sample_post,
        comments=sample_comments,
    )

    print("댓글 후보 점수화 결과")

    for item in result:
        print(item)