# AI Comment Recommender

YouTube 영상 문맥을 바탕으로 댓글 후보를 만들고, 안전 필터와 반응 예측 모델을 이용해 상위 댓글을 추천하는 MVP입니다.

현재 구현은 **외부 유료 LLM 없이도 실행 가능한 결정론적 후보 생성기**를 사용합니다. 영상 제목·설명·공개 자막(가능한 경우)과 사용자가 추가로 입력한 맥락에서 주제어를 뽑아 후보를 만든 뒤, 기존 학습 모델로 점수를 매겨 순위를 정합니다.

## 현재 지원 범위

- 단일 YouTube 영상 URL: `youtube.com/watch`, `youtu.be`, `/shorts/`, `/embed/`, `/live/`
- YouTube Data API 기반 실제 제목/설명/채널/조회수/구독자/길이/썸네일 조회
- 공개 자막 best-effort 반영 (`youtube-transcript-api`); 자막이 없거나 조회에 실패하면 제목/설명으로 계속 동작
- 10분 인프로세스 YouTube context cache
- 직접 입력 또는 URL + 추가 맥락 입력
- `auto` / `social` / `vlog` 카테고리 기반 후보 생성
- 요청 개수 1–10개, 후보 풀은 요청 수보다 크게 생성
- safety filter → lexical/embedding context features → reaction model ranking
- SQLite 기반 분석/추천/피드백 자동 저장
- 실제 최근 분석 기록, 대시보드 KPI/필터/CSV 내보내기
- 추천 댓글 복사, 재생성, 도움됨/아쉬움 피드백
- 모델 준비 상태를 `/health`에서 확인

> 재생목록 URL은 현재 지원하지 않습니다. UI와 API 모두 단일 영상 URL만 지원한다고 표시합니다.

## 시스템 흐름

```text
YouTube URL 또는 직접 입력
        ↓
YouTube metadata + optional public transcript
        ↓
reference context 구성
        ↓
context/category-aware candidate generation
        ↓
Safety Filter
        ↓
lexical + semantic context features
        ↓
reaction prediction model
        ↓
Top-K ranking
        ↓
SQLite 분석 기록 저장
        ↓
FastAPI → React/Vite UI
```

## 설치

Python:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

환경 변수는 프로젝트 루트의 `.env.local`에 둡니다.

```bash
YOUTUBE_API_KEY=your_youtube_data_api_key
```

`YOUTUBE_API_KEY`가 없으면 직접 입력 추천은 가능하지만 YouTube URL preview/recommend 요청은 503을 반환합니다.

Frontend:

```bash
cd frontend
npm ci
```

## 모델 및 데이터 준비

학습된 모델 산출물(`models/*.joblib`, `models/*.pkl`)은 Git에 커밋하지 않습니다. 새 checkout에서는 아래 순서로 데이터를 준비하고 모델을 학습해야 추천 모델이 ready 상태가 됩니다.

```bash
python scripts/prepare_combined_comments.py
python -m src.data.preprocess
python -m src.features.text_features
python -m src.features.embedding_features
python -m src.model.train
```

임베딩 모델 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`는 첫 사용 시 내려받고 이후 로컬 cache를 사용합니다.

모델 artifact가 없거나 현재 feature schema와 맞지 않으면 서버 자체는 실행되지만 `/health`가 `degraded`를 반환하고 `/score`, `/recommend`는 재학습 명령이 포함된 503 오류를 반환합니다.

## 실행

Backend:

```bash
uvicorn src.api.main:app --reload
```

- Swagger: `http://127.0.0.1:8000/docs`
- 기본 API 주소: `http://localhost:8000`
- 개발 CORS: `localhost:5173`, `127.0.0.1:5173`

Frontend:

```bash
cd frontend
npm run dev
```

다른 API 주소를 쓰려면 `VITE_API_BASE_URL`을 설정합니다.

## API

### 상태 / 추천

- `GET /health`
- `POST /score`
- `GET /videos/preview?url=...`
- `POST /recommend`

`POST /recommend` 예시:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "additional_context": "댓글은 초보 개발자 관점으로 추천",
  "category": "auto",
  "top_k": 5
}
```

직접 입력에서는 `youtube_url` 대신 `post_text`를 사용합니다.

### 기록 / 대시보드

- `GET /analyses?limit=3`
- `GET /analyses/{analysis_id}`
- `GET /comments?query=&type=&category=&min_score=&limit=&offset=`
- `GET /dashboard/summary`
- `POST /recommendations/{recommendation_id}/feedback`

분석 데이터는 기본적으로 `data/runtime/ai_comment.db`에 저장됩니다. 다른 경로를 사용하려면 `AI_COMMENT_DB_PATH`를 설정합니다. runtime DB는 Git에서 추적하지 않습니다.

## 모델 피처

랭킹 모델은 세 종류의 피처를 사용합니다.

1. 댓글 텍스트: 길이, 문장/질문/감탄, 웃음/슬픔, URL/숫자, casual/empathy/insight/criticism score
2. lexical context: `post_comment_overlap_count`, `post_comment_jaccard`, `post_comment_coverage`, `post_comment_length_ratio`
3. semantic context: `post_comment_sim`

학습과 추론은 `src/features/feature_schema.py`의 동일한 피처 목록을 공유합니다. 저장된 모델 schema가 현재 코드와 다르면 조용히 0으로 채우지 않고 재학습을 요구합니다.

같은 영상 댓글이 train/test에 동시에 들어가는 누수를 막기 위해 `post_id` 기준 `GroupShuffleSplit`을 사용하고, class imbalance는 학습 데이터에만 `RandomUnderSampler`를 적용합니다.

## 테스트

Backend:

```bash
pytest -q
```

Frontend:

```bash
cd frontend
npm test
npm run lint
npm run build
```

`npm test`는 frontend와 backend가 같은 규칙으로 단일 YouTube URL을 판정하는 핵심 URL validation 회귀 테스트를 실행합니다.

GitHub Actions의 `.github/workflows/ci.yml`은 push/PR에서 backend pytest와 frontend test/lint/build를 각각 실행합니다.

## 현재 한계와 운영 시 주의점

- 후보 생성기는 현재 provider-free deterministic generator입니다. LLM 기반 자유 생성이 필요하면 `generate_candidates()` 인터페이스 뒤에 별도 provider를 붙일 수 있습니다.
- 공개 자막 조회는 자막 제공 여부와 YouTube 측 응답에 따라 실패할 수 있으며, 실패는 추천 요청을 막지 않습니다.
- 재생목록 URL은 지원하지 않습니다.
- SQLite는 로컬/단일 인스턴스 MVP 저장소입니다. 다중 인스턴스 production 운영에는 공유 DB로 교체해야 합니다.
- 학습 모델 artifact는 source control에 포함하지 않으므로 production 배포에서는 별도 versioned artifact storage/배포 절차가 필요합니다.
- 모델 성능은 수집 데이터 분포와 label 품질에 따라 계속 검증해야 합니다.

## MVP completion 작업 기록

이번 미완성 구간 정리 작업의 범위, 결정 사항, 구현 및 검증 로그는 [`MVP_COMPLETION_README.md`](./MVP_COMPLETION_README.md)에 계속 기록합니다.
