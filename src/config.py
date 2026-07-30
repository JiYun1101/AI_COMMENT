from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DATA_PATH = BASE_DIR / "data" / "raw" / "comments.csv"
PROCESSED_DATA_PATH = BASE_DIR / "data" / "processed" / "comments_processed.csv"

# 게시글-댓글 의미 유사도 계산에 사용할 sentence-transformers 모델.
# 한국어가 포함된 다국어 경량 모델(MiniLM)을 기본값으로 사용.
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

REQUIRED_COLUMNS = [
    "post_id",
    "post_text",
    "comment_id",
    "comment_text",
    "like_count",
    "created_at",
    "platform",
]