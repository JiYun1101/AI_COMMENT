from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DATA_PATH = BASE_DIR / "data" / "raw" / "comments.csv"
PROCESSED_DATA_PATH = BASE_DIR / "data" / "processed" / "comments_processed.csv"

EMBEDDING_MODEL_NAME = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

REQUIRED_COLUMNS = [
    "post_id",
    "post_text",
    "comment_id",
    "comment_text",
    "like_count",
    "created_at",
    "platform",
]
