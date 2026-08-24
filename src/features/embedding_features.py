"""게시글-댓글 의미적 유사도 피처.

sentence-transformers 모델로 게시글(post_text)과 댓글(comment_text)의
임베딩을 구해 코사인 유사도를 계산하고 ``post_comment_sim`` 피처로 추가한다.

파이프라인 위치::

    preprocess → like_normalizer → text_features → embedding_features → train

``text_features`` 가 만든 ``comments_features.csv`` 를 입력으로 받아
유사도 피처를 추가한 뒤 같은 경로에 덮어쓴다. 이후 ``train`` 이 동일한
파일을 읽어 학습한다.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
from sentence_transformers import SentenceTransformer, util

from src.config import BASE_DIR, EMBEDDING_MODEL_NAME


INPUT_PATH = BASE_DIR / "data" / "processed" / "comments_features.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "comments_features.csv"

SIMILARITY_COLUMN = "post_comment_sim"

# 빈 게시글/댓글은 비교할 의미가 없으므로 중립값으로 처리한다.
NEUTRAL_SIMILARITY = 0.0


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """임베딩 모델을 한 번만 로드해 재사용한다.

    모델은 첫 호출 시 HuggingFace Hub에서 다운로드되므로 최초 실행에
    네트워크가 필요하다. 이후에는 로컬 캐시를 사용한다.
    """
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def compute_post_comment_similarity(
    post_text: str,
    comment_text: str,
    model: SentenceTransformer | None = None,
) -> float:
    """단일 (게시글, 댓글) 쌍의 코사인 유사도를 반환한다.

    빈 게시글이나 빈 댓글은 중립값으로 처리해 학습/추론이 깨지지 않도록
    한다. 반환값은 정규화 임베딩 기준 코사인 유사도로 [-1, 1] 범위.
    """
    if model is None:
        model = get_embedding_model()

    post_text = str(post_text or "").strip()
    comment_text = str(comment_text or "").strip()

    if not post_text or not comment_text:
        return NEUTRAL_SIMILARITY

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
    """DataFrame 에 게시글-댓글 유사도 피처 컬럼을 추가해 반환한다.

    양쪽 모두 값이 있는 행만 모아 배치로 인코딩한다. 같은 게시글 텍스트가
    여러 행에 반복되므로 고유 게시글만 인코딩해 행별로 매핑해 재사용한다.
    빈 게시글/댓글 행은 인코딩을 건너뛰고 ``compute_post_comment_similarity``
    와 동일하게 중립값을 채워, 학습과 추론의 처리 방식을 일치시킨다.
    """
    if post_col not in df.columns or comment_col not in df.columns:
        raise ValueError(
            f"유사도 계산에 필요한 컬럼이 없습니다: {post_col}, {comment_col}"
        )

    model = get_embedding_model()

    posts = df[post_col].fillna("").astype(str).str.strip()
    comments = df[comment_col].fillna("").astype(str).str.strip()

    valid_mask = (posts != "") & (comments != "")
    sim_values = pd.Series(NEUTRAL_SIMILARITY, index=df.index, dtype=float)

    if valid_mask.any():
        valid_posts = posts[valid_mask]
        valid_comments = comments[valid_mask]

        # 고유 게시글 임베딩을 한 번만 계산하고 행별로 매핑해 재사용.
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

        # 정규화된 임베딩이므로 행별 내적이 곧 코사인 유사도.
        similarities = (post_embeddings * comment_embeddings).sum(dim=1)
        sim_values.loc[valid_mask] = similarities.cpu().numpy().round(6)

    df = df.copy()
    df[out_col] = sim_values
    return df


def main():
    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")
    df = add_embedding_similarity(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"임베딩 유사도 피처 추가 완료: {OUTPUT_PATH}")
    print(df[[
        "post_id",
        "comment_id",
        "comment_text",
        SIMILARITY_COLUMN,
    ]].head(10))


if __name__ == "__main__":
    main()
