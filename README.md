# AI Comment Recommender

YouTube 댓글 데이터에서 **반응이 좋았던 댓글의 패턴**을 학습하고, 새 게시글에 대해 안전하고 맥락에 맞는 댓글 후보를 점수화해 추천하는 MVP입니다.

현재 저장소는 다음 작업을 하나로 통합합니다.

- social issues / vlog YouTube 댓글 약 1.3만 건
- 실데이터 기반 safety filter v2
- 댓글 자체의 텍스트 피처
- 게시글-댓글 lexical context 피처
- sentence-transformers 기반 semantic similarity
- 게시글 단위 train/test 분리
- FastAPI `/score`, `/recommend`
- React + TypeScript + Vite 프론트엔드

## 설치

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

프론트엔드:

```bash
cd frontend
npm ci
```

임베딩 모델은 첫 실행 시 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`를 다운로드합니다.

## 데이터 준비와 학습

```bash
python scripts/prepare_combined_comments.py
python -m src.data.preprocess
python -m src.features.text_features
python -m src.features.embedding_features
python -m src.model.train
```

`prepare_combined_comments.py`는 `social_issues_comments.csv`와 `vlog_comments.csv`를 합쳐 `data/raw/comments.csv`를 생성합니다. 이 파일은 생성 산출물이므로 Git에서 추적하지 않습니다.

수집 데이터의 기존 `is_top_comment` 라벨을 그대로 사용합니다. `src.features.like_normalizer`는 분석/레거시용이며 기존 라벨이 있으면 덮어쓰지 않습니다.

## 모델 피처

모델은 세 종류의 피처를 사용합니다.

1. 댓글 텍스트: 길이, 문장/질문/감탄, 웃음/슬픔, URL/숫자, casual/empathy/insight/criticism score
2. lexical context: `post_comment_overlap_count`, `post_comment_jaccard`, `post_comment_coverage`, `post_comment_length_ratio`
3. semantic context: `post_comment_sim`

학습과 추론은 `src/features/feature_schema.py`의 동일한 피처 목록을 공유합니다. 저장된 모델 스키마가 현재 코드와 다르면 0으로 조용히 채우지 않고 재학습을 요구합니다.

같은 영상의 댓글이 train/test에 동시에 들어가는 누수를 막기 위해 `post_id` 기준 `GroupShuffleSplit`을 사용하고, 클래스 불균형은 학습 데이터에만 `RandomUnderSampler`를 적용합니다.

## Backend

```bash
uvicorn src.api.main:app --reload
```

- Swagger: `http://127.0.0.1:8000/docs`
- `GET /health`
- `POST /score`
- `POST /recommend`
- 점수는 0~100 범위

개발 프론트(`localhost:5173`, `127.0.0.1:5173`)에서 API를 호출할 수 있도록 CORS가 설정되어 있습니다.

## Frontend

```bash
cd frontend
npm run dev
```

기본 API 주소는 `http://localhost:8000`이며 `VITE_API_BASE_URL`로 변경할 수 있습니다.

현재 댓글 추천 화면은 실제 `POST /recommend`와 연결되어 있습니다. 다만 URL 미리보기는 아직 mock 데이터이고 Dashboard의 KPI/댓글 테이블은 seed data입니다.

## 테스트

```bash
pytest
cd frontend
npm run lint
npm run build
```

테스트에는 safety filter 회귀 케이스, 학습/추론 피처 스키마 일관성, 기존 `is_top_comment` 라벨 보존 검증이 포함됩니다.

## 전체 흐름

```text
YouTube raw datasets
→ comments.csv 생성
→ 전처리
→ shared text + lexical context features
→ embedding similarity
→ post_id 단위 train/test split
→ RandomForest 학습
→ 안전한 후보 생성/필터링
→ 동일한 feature schema로 추론
→ 점수순 추천
→ FastAPI
→ React/Vite UI
```

## 현재 한계

- 후보 댓글 생성은 아직 템플릿 기반입니다.
- 임베딩 모델 첫 실행에는 네트워크가 필요합니다.
- URL preview와 Dashboard는 일부 mock/seed data를 사용합니다.
- 모델 성능은 데이터 분포와 라벨 품질에 따라 추가 검증이 필요합니다.
