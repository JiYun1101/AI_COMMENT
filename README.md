# AI Comment Recommender

YouTube 영상의 맥락을 코드로 수집·분류하고, 기존 댓글 데이터의 반응 패턴을 참고해 **LLM이 새 댓글 후보만 생성**한 뒤 안전 필터와 반응 예측 모델로 상위 댓글을 추천하는 MVP입니다.

핵심 원칙은 **분석은 코드, 창작은 LLM**입니다. LLM에게 영상 장르나 시청자 특성을 임의로 판단시키지 않고, YouTube API·자막·규칙 기반 분류·시간/반응 지표·기존 댓글 통계를 먼저 `GenerationContext`로 만든 뒤 생성 단계에만 전달합니다.

상세 설계와 구현 감사 기록은 [`LLM_CONTEXT_GENERATION_README.md`](./LLM_CONTEXT_GENERATION_README.md)를 참고하세요.

## 시스템 흐름

```text
YouTube URL / 직접 입력
        ↓
YouTube metadata + optional public transcript
        ↓
Deterministic GenerationContext
  ├─ YouTube 공식 category / topic / tags
  ├─ topic / content-style multi-label
  ├─ short / standard / long-form / live
  ├─ made-for-kids / age-restriction
  ├─ 콘텐츠 target-age / orientation heuristic
  ├─ freshness / weekday / season
  ├─ views / likes / comments / subscribers
  └─ single-snapshot hype proxy
        ↓
기존 댓글 retrieval + 통계 요약
        ↓
OpenAI Responses API
새 댓글 후보 생성만 수행
        ↓
중복 / 기존 댓글 근접 복제 검증
        ↓
Safety Filter
        ↓
기존 reaction prediction model
        ↓
Top-K ranking
        ↓
SQLite 분석/맥락/결과 저장
        ↓
FastAPI → React/Vite UI
```

## 현재 지원 범위

### 입력과 YouTube context

- 단일 YouTube 영상 URL: `youtube.com/watch`, `youtu.be`, `/shorts/`, `/embed/`, `/live/`
- YouTube Data API 기반 실제 metadata
  - 제목/설명/채널/썸네일
  - 조회수/좋아요/댓글 수/구독자 수
  - 길이/게시 시각/tags/default language
  - `snippet.categoryId`와 category 이름
  - `topicDetails`
  - `status.madeForKids`
  - YouTube age restriction
  - live/upcoming/archived-live 신호
- 공개 자막 best-effort 반영 (`youtube-transcript-api`)
- 10분 인프로세스 YouTube context cache
- 직접 입력과 추가 사용자 맥락
- 재생목록 URL은 지원하지 않음

### Script 기반 분류

공식 YouTube category와 자체 파생 label을 분리합니다.

- **공식 category**: Music, Gaming, Sports, News & Politics, Education, Science & Technology, Howto & Style, Travel & Events, People & Blogs 등 YouTube `categoryId` 기준
- **topic multi-label**: AI, software, hardware, mobile, career, education, finance, politics, beauty, fashion, food, travel, fitness, music, film, gaming, sports 등
- **content style**: educational, tutorial, review, comparison, discussion, interview, commentary, news, reaction, vlog, challenge, performance, highlights, unboxing 등
- **format**: short / short-like / standard / long-form
- **broadcast**: uploaded / live / upcoming / archived-live
- **freshness**: breaking / fresh / recent / current / established / old / evergreen
- **audience descriptor**:
  - 공식 신호: made-for-kids, age-restricted
  - 파생 신호: target age와 content orientation
- **popularity/hype proxy**: views/hour, likes per 1K views, comments per 1K views, views/subscriber

> `target_age`와 `orientation`은 실제 시청자의 나이/성별을 추정하지 않습니다. 제목·설명·자막 등 콘텐츠에 명시된 대상 신호를 분류한 **콘텐츠 수준 heuristic**입니다.

> 현재 `hype_score`는 한 시점의 API snapshot을 이용한 상대 proxy입니다. 실제 조회수 성장 속도/가속도를 측정하려면 시간별 snapshot 저장이 추가로 필요합니다.

## YouTube category 동기화

자주 쓰이는 category ID 이름은 기본값을 포함하지만, 지역별 최신 category 목록을 runtime cache로 갱신할 수 있습니다.

```bash
python scripts/sync_youtube_categories.py --region KR
```

결과는 기본적으로 `data/runtime/youtube_categories.json`에 저장되며 Git에는 포함하지 않습니다.

## 기존 댓글 데이터 활용

현재 저장소에는 다음 실제 YouTube 댓글 데이터가 있습니다.

- `data/raw/social_issues_comments.csv`
- `data/raw/vlog_comments.csv`

LLM에 이 데이터를 통째로 전달하지 않습니다. `historical_comments.py`가 현재 영상과 관련성이 있는 댓글을 선택하고 코드로 다음을 계산합니다.

- 참조 댓글 수와 legacy dataset coverage
- 선호 댓글 길이 구간과 median
- 질문형 비율
- casual marker 비율
- 반응이 좋았던 소수의 reference examples

LLM은 이 정보를 **스타일 참고용**으로만 사용합니다. 생성 후에는 기존 reference와 매우 유사한 문장을 제거합니다.

### 현재 데이터 분포 한계

기존 historical dataset과 reaction ranker 학습 데이터는 주로 `social_issues`와 `vlog`에 집중되어 있습니다. LLM 생성과 YouTube context 분류는 Music/Gaming/Sports/Beauty 등으로 확장되었지만, **기존 reaction score가 모든 새 장르에서 같은 수준으로 검증됐다는 의미는 아닙니다.** 다장르 댓글 수집과 ranker 재학습은 후속 데이터 작업입니다.

## LLM 생성

후보 생성기는 더 이상 고정 문장 template을 사용하지 않습니다.

`src/recommender/candidate_generator.py`는 이미 만들어진 `GenerationContext`를 LLM provider에 넘겨 후보 pool을 요청하는 얇은 경계입니다. provider 구현은 `src/llm/openai_client.py`에 격리되어 있습니다.

현재 provider는 OpenAI Responses API를 사용하며 다음 환경 변수가 필요합니다.

```bash
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=your_selected_model
OPENAI_BASE_URL=https://api.openai.com/v1
```

모델 이름은 코드에 고정하지 않습니다. 운영 비용/품질 요구에 따라 `OPENAI_MODEL`로 명시적으로 선택합니다.

LLM은 다음 규칙을 받습니다.

- 이미 수집된 context를 사용하고 장르를 다시 임의 분류하지 않기
- context에 없는 사실 만들지 않기
- 기존 댓글을 복사/근접 패러프레이즈하지 않기
- 원문 언어·영상 시점·format에 맞추기
- 강제 keyword 삽입이나 깨진 한국어 조사 피하기
- insight / empathy / question / casual / general 후보를 자연스럽게 다양화하기
- `(1)`, `(2)` 같은 template 흔적을 넣지 않기
- comment candidate 구조의 JSON만 반환하기

응답은 다시 애플리케이션에서 type/길이/중복/근접 복제를 검증합니다. LLM 오류나 설정 누락 시 고정 template으로 조용히 되돌아가지 않고 502/503 오류를 반환합니다.

## 설치

Python:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

프로젝트 루트 `.env.local` 예시:

```bash
YOUTUBE_API_KEY=your_youtube_data_api_key
YOUTUBE_CATEGORY_REGION=KR
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=your_selected_model
OPENAI_BASE_URL=https://api.openai.com/v1
```

Frontend:

```bash
cd frontend
npm ci
```

## Ranker 모델 및 데이터 준비

학습된 모델 산출물(`models/*.joblib`, `models/*.pkl`)은 Git에 커밋하지 않습니다. 새 checkout에서는 아래 순서로 데이터를 준비하고 모델을 학습해야 reaction ranker가 ready 상태가 됩니다.

```bash
python scripts/prepare_combined_comments.py
python -m src.data.preprocess
python -m src.features.text_features
python -m src.features.embedding_features
python -m src.model.train
```

임베딩 모델 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`는 첫 사용 시 내려받고 이후 로컬 cache를 사용합니다.

## 실행

Backend:

```bash
uvicorn src.api.main:app --reload
```

- Swagger: `http://127.0.0.1:8000/docs`
- API 기본 주소: `http://localhost:8000`
- 개발 CORS: `localhost:5173`, `127.0.0.1:5173`

Frontend:

```bash
cd frontend
npm run dev
```

다른 API 주소를 쓰려면 `VITE_API_BASE_URL`을 설정합니다.

## Readiness

`GET /health`는 각각을 분리해 보여줍니다.

- reaction model readiness
- LLM configuration readiness
- YouTube API key configuration
- storage readiness

추천 생성에는 LLM과 reaction model이 모두 필요합니다. YouTube URL 입력에는 추가로 `YOUTUBE_API_KEY`가 필요하지만 직접 입력은 YouTube key 없이 사용할 수 있습니다.

## API

### 상태 / 추천

- `GET /health`
- `POST /score`
- `GET /videos/preview?url=...`
- `POST /recommend`

YouTube 예시:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "additional_context": "초보 개발자 관점에서 자연스럽게",
  "top_k": 5
}
```

직접 입력 예시:

```json
{
  "post_text": "영상 제목이나 스크립트...",
  "additional_context": "꼭 반영할 관점",
  "top_k": 5
}
```

`category`는 구버전 client 호환용 optional hint로만 남아 있습니다. YouTube의 primary category와 파생 맥락은 서버가 자동 구성합니다.

추천 응답에는 기존 필드와 함께 축약된 `context`가 포함됩니다.

- primary / official category
- topics
- content styles
- format / broadcast
- freshness
- hype label/score
- historical match count/coverage

### 기록 / 대시보드

- `GET /analyses?limit=3`
- `GET /analyses/{analysis_id}`
- `GET /comments?query=&type=&category=&min_score=&limit=&offset=`
- `GET /dashboard/summary`
- `POST /recommendations/{recommendation_id}/feedback`

분석 시점의 `GenerationContext`, 추가 맥락, 요청 개수도 SQLite에 snapshot으로 저장해 과거 분석을 다시 열 때 원 요청 상태를 복원합니다.

기본 DB는 `data/runtime/ai_comment.db`이며 `AI_COMMENT_DB_PATH`로 바꿀 수 있습니다.

## 테스트

Backend:

```bash
pytest -q
```

LLM 테스트는 실제 API key를 사용하지 않고 provider boundary를 fake response로 검증합니다. Context classifier, historical retriever, enriched YouTube metadata, persistence, API integration도 회귀 테스트합니다.

Frontend:

```bash
cd frontend
npm test
npm run lint
npm run build
```

GitHub Actions는 push/PR마다 backend pytest와 frontend test/lint/build, production dependency audit를 실행합니다.

## 현재 한계

- 실제 LLM E2E 호출은 유효한 `OPENAI_API_KEY`와 `OPENAI_MODEL`이 있어야 합니다. CI는 외부 과금/불안정성을 피하기 위해 fake provider boundary를 사용합니다.
- 공개 자막은 best-effort이며 YouTube 측 상태/IP 정책에 따라 실패할 수 있습니다.
- 공식 category는 YouTube `categoryId`를 우선하며, topic/style/audience labels는 코드 기반 heuristic입니다.
- hype는 현재 single-snapshot proxy입니다. 실제 trend velocity는 아직 수집하지 않습니다.
- historical/ranker 데이터는 아직 social-issues/vlog 중심이므로 새 장르까지 데이터 재수집/재학습이 필요합니다.
- SQLite는 로컬/단일 인스턴스 MVP 저장소입니다.
- 모델 artifact는 source control에 포함하지 않으므로 production에서는 별도 versioned artifact 배포가 필요합니다.

## 설계 및 구현 감사 기록

LLM 전환의 기획, 사전 검토, 구현 체크리스트, 구현 후 감사와 제한사항은 [`LLM_CONTEXT_GENERATION_README.md`](./LLM_CONTEXT_GENERATION_README.md)에 기록합니다.
