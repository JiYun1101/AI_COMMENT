"""게시글-댓글 의미적 유사도 피처.

기본 로컬/고메모리 환경에서는 sentence-transformers 임베딩 코사인 유사도를
사용합니다. 저메모리 배포 환경에서는 ``AI_COMMENT_LIGHTWEIGHT_SIMILARITY=1``로
설정해 토큰 빈도 기반 cosine similarity를 사용합니다. 학습과 추론이 같은 환경
변수를 사용하면 동일한 피처 정의를 유지하면서 PyTorch 모델의 런타임 메모리
사용을 피할 수 있습니다.
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from functools import lru_cache
from typing import Any

import pandas as pd

from src.config import BASE_DIR, EMBEDDING_MODEL_NAME


INPUT_PATH = BASE_DIR / "data" / "processed" / "comments_features.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "comments_features.csv"

SIMILARITY_COLUMN = "post_comment_sim"
NEUTRAL_SIMILARITY = 0.0
_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")


def _use_lightweight_similarity() -> bool:
    return (os.getenv("AI_COMMENT_LIGHTWEIGHT_SIMILARITY") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _lightweight_similarity(post_text: str, comment_text: str) -> float:
    """메모리 사용이 작은 토큰 빈도 cosine similarity."""
    post_tokens = Counter(token.lower() for token in _TOKEN_RE.findall(post_text))
    comment_tokens = Counter(token.lower() for token in _TOKEN_RE.findall(comment_text))
    if not post_tokens or not comment_tokens:
        return NEUTRAL_SIMILARITY

    shared = post_tokens.keys() & comment_tokens.keys()
    dot = sum(post_tokens[token] * comment_tokens[token] for token in shared)
    post_norm = math.sqrt(sum(value * value for value in post_tokens.values()))
    comment_norm = math.sqrt(sum(value * value for value in comment_tokens.values()))
    if not post_norm or not comment_norm:
        return NEUTRAL_SIMILARITY
    return round(dot / (post_norm * comment_norm), 6)


@lru_cache(maxsize=1)
def get_embedding_model() -> Any:
    """sentence-transformers 모델을 지연 로딩해 저메모리 모드에서 torch import를 피한다."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def compute_post_comment_similarity(
    post_text: str,
    comment_text: str,
    model: Any | None = None,
) -> float:
    post_text = str(post_text or "").strip()
    comment_text = str(comment_text or "").strip()
    if not post_text or not comment_text:
        return NEUTRAL_SIMILARITY

    if _use_lightweight_similarity():
        return _lightweight_similarity(post_text, comment_text)

    if model is None:
        model = get_embedding_model()

    from sentence_transformers import util

    embeddings = model.encode(
        [post_text, comment_text],
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    similarity = float(util.cos_sim(embeddings[0], embeddings[1]))
    return round(similarity, 6)


def add_embedding_similarity(
    df: pd.DataFrame,
    post_col: str = "post_text",
    comment_col: str = "comment_text",
    out_col: str = SIMILARITY_COLUMN,
    batch_size: int = 64,
) -> pd.DataFrame:
    if post_col not in df.columns or comment_col not in df.columns:
        raise ValueError(
            f"유사도 계산에 필요한 컬럼이 없습니다: {post_col}, {comment_col}"
        )

    posts = df[post_col].fillna("").astype(str).str.strip()
    comments = df[comment_col].fillna("").astype(str).str.strip()
    valid_mask = (posts != "") & (comments != "")
    sim_values = pd.Series(NEUTRAL_SIMILARITY, index=df.index, dtype=float)

    if valid_mask.any() and _use_lightweight_similarity():
        sim_values.loc[valid_mask] = [
            _lightweight_similarity(post, comment)
            for post, comment in zip(posts[valid_mask], comments[valid_mask])
        ]
    elif valid_mask.any():
        model = get_embedding_model()
        valid_posts = posts[valid_mask]
        valid_comments = comments[valid_mask]

        unique_posts = list(dict.fromkeys(valid_posts.tolist()))
        unique_post_embeddings = model.encode(
            unique_posts,
            convert_to_tensor=True,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=False,
        )
        post_index = {text: i for i, text in enumerate(unique_posts)}
        post_embeddings = unique_post_embeddings[
            [post_index[text] for text in valid_posts]
        ]
        comment_embeddings = model.encode(
            valid_comments.tolist(),
            convert_to_tensor=True,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=False,
        )
        similarities = (post_embeddings * comment_embeddings).sum(dim=1)
        sim_values.loc[valid_mask] = similarities.cpu().numpy().round(6)

    result = df.copy()
    result[out_col] = sim_values
    return result


def main():
    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")
    df = add_embedding_similarity(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    mode = "lightweight" if _use_lightweight_similarity() else "sentence-transformers"
    print(f"유사도 피처 추가 완료 ({mode}): {OUTPUT_PATH}")
    print(df[["post_id", "comment_id", "comment_text", SIMILARITY_COLUMN]].head(10))


if __name__ == "__main__":
    main()
