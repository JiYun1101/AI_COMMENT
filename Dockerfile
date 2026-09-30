FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Build the ranking artifact into the image so production does not depend on
# a git-tracked binary model file.
RUN python scripts/prepare_combined_comments.py \
    && python -m src.data.preprocess \
    && python -m src.features.text_features \
    && python -m src.features.embedding_features \
    && python -m src.model.train

CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
