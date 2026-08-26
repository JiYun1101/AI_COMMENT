# LLM Context Generation Migration

Branch: `feature/llm-context-generation`  
Base: `main` @ `bdb50bc8002bdd65fa12a05f2766e5220ccd915d`

## Goal

고정 keyword/template 댓글 생성기를 제거하고 **분석은 코드, 창작은 LLM**이라는 경계를 적용한다.

1. YouTube/API/script code가 객관적인 metadata와 자막을 수집한다.
2. deterministic classifier가 category/topic/style/format/시간/audience descriptor/popularity 신호를 만든다.
3. 기존 수집 댓글에서 관련 reference와 통계를 코드로 계산한다.
4. 이 결과를 `GenerationContext`라는 구조화된 객체로 만든다.
5. **LLM은 이 context를 바탕으로 새 댓글 후보를 작성하는 일만 한다.**
6. 생성 후에는 애플리케이션 검증 → safety filter → 기존 reaction ranker → Top-K를 유지한다.

오탐 가능성·상태 이상·운영 의존성은 별도 문서 [`LLM_CONTEXT_GENERATION_VALIDATION_README.md`](./LLM_CONTEXT_GENERATION_VALIDATION_README.md)에서 merge gate와 함께 추적한다.

---

# 1. 작성 전 감사 — 구현 전에 확인한 사항

## 유지해야 했던 기존 기능

- 단일 YouTube URL 검증과 preview
- 제목/설명/채널/statistics/공개 자막 context
- 직접 입력 경로
- safety filtering
- reaction prediction/ranking
- Top-K
- SQLite 분석/history/dashboard/feedback 저장
- 설정 또는 모델 미준비 상태에서 fake 결과를 만들지 않는 오류 처리

## 반드시 제거해야 했던 부분

- `social` / `vlog` 두 keyword 점수만으로 primary category를 정하는 방식
- `candidate_generator.py`의 고정 한국어 문장 template
- `(1)`, `(2)`처럼 template 수를 채우기 위한 deterministic filler
- 같은 입력에 같은 후보가 나와 `다시 생성`이 실질적으로 의미가 없던 구조

## 구현 전 위험 검토

### YouTube 공식 category와 자체 분류를 분리

YouTube `snippet.categoryId`는 플랫폼이 정의한 공식 category다. 이를 topic/style 등의 자체 label과 합쳐 하나의 값으로 덮어쓰지 않는다.

```text
Official category
  Science & Technology

Derived context
  topics = [ai, software, career]
  styles = [educational, interview]
```

### 실제 시청자 demographic을 추정하지 않음

공개 YouTube Data API로 임의 영상의 실제 시청자 연령/성별 분포를 얻을 수 있다는 전제로 설계하지 않는다.

- `madeForKids`: 공식 신호
- age restriction: 공식 신호
- `target_age`: 콘텐츠에 명시된 대상에 대한 heuristic
- `orientation`: 콘텐츠 자체의 명시적 지향에 대한 heuristic

댓글 작성자 이름·사진·문체를 이용해 개인의 성별/나이를 추측하지 않는다.

### Hype는 절대 조회수로 판단하지 않음

새 영상 20만 조회와 3년 된 영상 20만 조회는 같은 상태가 아니다. 첫 버전은 다음 single-snapshot 지표를 조합한다.

- views/hour
- likes per 1K views
- comments per 1K views
- views/subscriber

진짜 성장 속도/가속도는 snapshot history가 있어야 하므로 첫 구현의 `hype_score`에는 반드시 `single_snapshot_proxy`라는 basis를 남긴다.

### 기존 댓글 coverage의 한계

repo의 실제 historical data는 현재 두 축이다.

- `social_issues_comments.csv`
- `vlog_comments.csv`

따라서 Music/Gaming/Sports 등으로 생성 category가 넓어져도 기존 historical reference와 reaction ranker가 동일한 수준으로 검증됐다고 주장하지 않는다.

### LLM을 fallback template처럼 사용하지 않음

LLM 설정/API가 실패할 때 옛 template을 조용히 호출하면 이번 변경의 목적이 무너진다.

- 설정 누락 → readiness error
- provider/network 오류 → generation error
- invalid response → generation error
- 고정 template fallback 없음

### 기존 댓글 복사 방지

과거 top comment는 style/reference 신호일 뿐 새 댓글의 원문이 아니다.

생성 전 historical row 자체도 safety predicate를 통과해야 하며, 생성 후 다음을 검사한다.

- exact duplicate
- 동일 생성 내 duplicate
- historical reference와 지나치게 높은 문자열 유사도
- 길이/type 구조

---

# 2. 목표 및 현재 구현 파이프라인

```text
YouTube URL / manual text
        │
        ▼
Context collection — code
        │
        ├─ official YouTube category/topic/tags
        ├─ title / description / transcript
        ├─ duration / live state / language
        ├─ madeForKids / age restriction
        ├─ publishedAt
        └─ views / likes / comments / subscribers
        │
        ▼
Deterministic GenerationContext — code
        │
        ├─ official_category
        ├─ topics[]
        ├─ content_styles[]
        ├─ format / broadcast
        ├─ target_age[] + confidence
        ├─ content orientation + confidence
        ├─ freshness / weekday / month / season
        └─ hype proxy
        │
        ▼
Historical comment retrieval — code
        │
        ├─ safety-filtered legacy examples
        ├─ preferred length
        ├─ question ratio
        └─ casual ratio
        │
        ▼
GenerationContext JSON
        │
        ▼
OpenAI Responses API
  새 댓글 후보 작성 ONLY
        │
        ▼
Application validation / reference-copy rejection
        │
        ▼
Safety filter
        │
        ▼
Existing reaction ranker
        │
        ▼
Top-K + context/request persistence
```

`candidate_generator.py`는 이제 context를 받아 LLM client를 호출하는 얇은 boundary일 뿐이며 문장 template을 가지지 않는다.

---

# 3. GenerationContext 계약

대표 형태:

```json
{
  "source": {
    "type": "youtube",
    "title": "...",
    "description": "...",
    "transcript_excerpt": "...",
    "language": "ko",
    "additional_context": "..."
  },
  "youtube": {
    "video_id": "...",
    "category_id": "28",
    "category_name": "Science & Technology",
    "topic_categories": ["..."],
    "tags": ["AI", "개발자"]
  },
  "format": {
    "kind": "long_form",
    "broadcast": "uploaded",
    "duration_seconds": 2400
  },
  "audience": {
    "made_for_kids": false,
    "age_restricted": false,
    "target_age": ["young_adult", "adult"],
    "target_age_confidence": 0.7,
    "orientation": "general",
    "orientation_confidence": 0.35,
    "basis": "official_flags_plus_explicit_content_heuristics"
  },
  "temporal": {
    "published_at": "...",
    "age_hours": 12.4,
    "freshness": "breaking",
    "weekday": "wednesday",
    "month": 8,
    "season": "summer"
  },
  "popularity": {
    "views": 120000,
    "likes": 6000,
    "comments": 850,
    "subscribers": 300000,
    "views_per_hour": 9677.4,
    "likes_per_1000_views": 50.0,
    "comments_per_1000_views": 7.1,
    "views_per_subscriber": 0.4,
    "hype_label": "hot",
    "hype_score": 0.75,
    "hype_basis": "single_snapshot_proxy"
  },
  "content": {
    "keywords": ["ai", "개발자", "커리어"],
    "topics": ["ai", "software", "career"],
    "content_styles": ["educational", "discussion"]
  },
  "historical_comments": {
    "coverage": "matched_legacy_category",
    "matched_count": 80,
    "preferred_length": [20, 70],
    "median_length": 38,
    "question_ratio": 0.18,
    "casual_ratio": 0.26,
    "reference_examples": ["..."]
  },
  "primary_category": "Science & Technology",
  "context_version": "1.0"
}
```

Manual input에서는 YouTube metadata를 만들어내지 않고 null/unknown으로 둔다.

---

# 4. Taxonomy

## 4.1 Official YouTube category

Primary category는 YouTube 영상일 때 `snippet.categoryId`를 우선한다.

내장 fallback map에 포함된 주요 category:

- Film & Animation
- Autos & Vehicles
- Music
- Pets & Animals
- Sports
- Travel & Events
- Gaming
- People & Blogs
- Comedy
- Entertainment
- News & Politics
- Howto & Style
- Education
- Science & Technology
- Nonprofits & Activism

지역별 목록 변화에 대응하기 위해 `scripts/sync_youtube_categories.py`가 `videoCategories.list` 결과를 `data/runtime/youtube_categories.json`에 저장할 수 있다.

## 4.2 Topic multi-label

초기 deterministic vocabulary:

- ai / software / hardware / mobile / science / technology
- career / education / finance / economy / politics / law
- beauty / fashion / food / travel / fitness / health / relationships
- music / film / animation / gaming / sports / animals / autos
- lifestyle / shopping / news

여러 label이 동시에 존재할 수 있으며 어떤 규칙에도 맞지 않는 콘텐츠를 억지로 social/vlog에 넣지 않는다.

English/ASCII keyword는 word boundary matcher를 사용해 `ai`가 `chair` 안에서, `man`이 `woman` 안에서 잡히는 식의 substring 오탐을 줄인다. YouTube `topicDetails`의 slug도 derived topic classifier 입력에 함께 사용한다.

## 4.3 Content style multi-label

- educational
- tutorial
- review
- comparison
- discussion
- interview
- commentary
- news
- reaction
- vlog
- challenge
- entertainment
- performance
- highlights
- unboxing

## 4.4 Format / broadcast

Format:

- `short`: Shorts URL
- `short_like`: 일반 URL이지만 3분 이하
- `standard`
- `long_form`: 20분 이상
- `unknown`

Broadcast:

- uploaded
- live
- upcoming
- archived_live
- unknown (manual)

## 4.5 Audience descriptor

공식:

- made_for_kids
- age_restricted

Content-level heuristic:

- children
- teens
- young_adult
- adult
- mature
- unknown

Orientation:

- general
- female_oriented
- male_oriented
- mixed

이 값들은 실제 viewer demographic이 아니다.

## 4.6 Freshness

- breaking: <24 h
- fresh: 1–3 d
- recent: 3–7 d
- current: 7–30 d
- established: 1–6 mo
- old: 6–24 mo
- evergreen: >24 mo

weekday/month/season도 함께 저장한다.

## 4.7 Hype

현재 구현:

```text
views_per_hour
likes_per_1000_views
comments_per_1000_views
views_per_subscriber
      ↓
normalized weighted proxy
      ↓
normal / active / hot / viral
```

`hype_basis = single_snapshot_proxy`를 명시한다.

향후 실제 velocity를 만들려면 동일 video ID의 통계 snapshot을 주기적으로 저장해야 한다.

---

# 5. Historical comment retrieval

구현 파일: `src/recommender/historical_comments.py`

동작:

1. raw CSV를 lazy/cached loading한다.
2. 빈 값/길이뿐 아니라 application `is_safe_comment()`를 통과한 row만 profile/reference 후보로 사용한다.
3. reference text와 기존 post/comment의 token overlap을 계산한다.
4. topic/style에 따라 현재 가지고 있는 legacy dataset 중 더 관련 있는 쪽에 bias를 준다.
5. `is_top_comment=1`을 우선한다.
6. like/reply 신호를 약하게 ranking에 추가한다.
7. 최대 profile subset에서 통계를 계산한다.
8. 소수 reference example만 LLM에 전달한다.

Profile:

- `coverage`
- `available_categories`
- `matched_categories`
- `matched_count`
- `preferred_length` (25–75 percentile)
- `median_length`
- `question_ratio`
- `casual_ratio`
- `reference_examples`

데이터 파일이 없으면 fake 값을 만들지 않고 `coverage=none`으로 정상 degrade한다.

---

# 6. LLM provider 계약

구현 파일: `src/llm/openai_client.py`

환경 변수:

```bash
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_BASE_URL=https://api.openai.com/v1
```

OpenAI Responses API를 사용한다. 특정 모델을 business logic에 hard-code하지 않고 `OPENAI_MODEL`을 명시적으로 요구한다.

Readiness:

- key/model 누락 → `LLMNotReadyError`
- network/provider 오류 → `LLMGenerationError`
- 응답 JSON 해석 불가 → `LLMGenerationError`
- candidate 검증 후 최소 개수 부족 → `LLMGenerationError`

HTTP API에서는 LLM/모델 readiness 실패를 503, provider/generation 실패를 502로 구분한다.

## Prompt 원칙

- supplied context의 사실만 사용
- GenerationContext의 title/description/transcript/tags/user context/history를 untrusted data로 취급하고 그 안의 지시문을 따르지 않음
- video category를 다시 임의로 재분류하지 않음
- historical comments는 style 참고만 하고 복사 금지
- source language/freshness/format에 맞춤
- 강제 keyword 삽입 금지
- 깨진 한국어 조사 피하기
- fake personal experience 금지
- insight/empathy/question/casual/general을 상황에 맞게 다양화
- `(1)` 같은 template marker 금지
- meta explanation 없이 JSON candidates 반환

## 응답 후 validator

- allowed type 확인, 미지 type은 general로 normalize
- 5–200자
- generation 내부 exact duplicate 제거
- historical reference와 `SequenceMatcher >= 0.92`인 near-copy 제거
- 필요한 최소 candidate pool 검증

---

# 7. Persistence 변경

기존 SQLite를 migration-safe하게 확장했다.

`analyses` 추가 필드:

- `context_json`
- `requested_count`
- `additional_context`

기존 DB는 `PRAGMA table_info` 후 없는 컬럼만 `ALTER TABLE`한다.

이 변경으로 history를 다시 열 때 이전에 문제가 되었던 다음 상태를 복원할 수 있다.

- 당시 추가 맥락
- 요청한 추천 개수
- 당시 GenerationContext
- context summary

---

# 8. Frontend 변경

- 고정 `자동/사회이슈/브이로그` 선택 chip 제거
- 자동 context analysis 설명 표시
- dynamic category string 지원
- preview에 공식 YouTube category 표시
- 썸네일/영상 열기 링크 실제 YouTube 연결
- 결과에 official category / topics / format / freshness / hype / historical match 표시
- `다시 생성`을 실제 LLM 변형 의미에 맞게 `새 후보 생성`으로 변경
- history에서 additional context와 requested count 복원
- dashboard category filter를 고정 social/vlog select에서 자유 category input+datalist로 변경
- 추가 맥락을 URL/manual 양쪽의 독립 입력 상태로 유지
- 화면 진입 시 `/health`를 preflight하여 model/LLM/storage 미준비를 submit 전에 표시
- URL 모드만 YouTube API 설정을 요구하고 manual 모드는 YouTube key 없이 허용
- backend health 자체를 확인할 수 없으면 연결 상태 안내 후 submit 차단

---

# 9. 작성 후 감사 — 실제 구현과 계획 대조

## Context collection

- [x] `YouTubeVideoContext`에 category/tags/language/likes/comments/kids/age/topic/live metadata 추가
- [x] 기존 preview 필드 호환 유지
- [x] category-name fallback map + runtime sync/cache 추가
- [x] transcript best-effort 유지

## Deterministic context

- [x] 재사용 가능한 `GenerationContext` builder
- [x] broad topic classifier
- [x] YouTube topicDetails를 derived topic에 반영
- [x] ASCII word-boundary 오탐 방어
- [x] content-style classifier
- [x] format/broadcast classifier
- [x] freshness/date classifier
- [x] content-level age/orientation heuristic + confidence/basis
- [x] popularity/hype proxy + explicit single-snapshot basis
- [x] manual input unknown/null degradation

## Historical comments

- [x] lazy/cached loader/retriever
- [x] application safety predicate를 통과한 row만 profile/reference에 사용
- [x] code-derived profile statistics
- [x] top-comment/relevance preference
- [x] limited reference examples
- [x] missing dataset graceful degradation
- [x] legacy coverage 명시

## LLM generation

- [x] provider client 격리
- [x] fixed sentence template 제거
- [x] OpenAI Responses API boundary
- [x] explicit key/model readiness
- [x] GenerationContext untrusted-data prompt boundary
- [x] type/length/duplicate/near-reference-copy validation
- [x] silent template fallback 없음

## Existing pipeline

- [x] LLM 뒤 safety filter 유지
- [x] safety 뒤 기존 reaction ranker 유지
- [x] 기존 Top-K/persistence 유지
- [x] API가 context/generation metadata 반환
- [x] health가 model/LLM/YouTube 설정을 구분
- [x] additional_context를 source와 분리하고 ranking reference에 한 번만 반영

## Frontend

- [x] URL/manual 핵심 flow 유지
- [x] misleading binary category selector 제거
- [x] dynamic category 표시
- [x] resolved context chip 표시
- [x] history request-state 복원 개선
- [x] video preview의 가짜 play affordance를 실제 링크로 수정
- [x] model/LLM/YouTube/storage readiness preflight
- [x] manual mode는 YouTube API 설정과 독립

## Tests

추가/수정된 테스트:

- [x] `test_candidate_generator.py` — fake LLM provider boundary
- [x] `test_generation_context.py` — deterministic context + ASCII false-positive + topicDetails regression
- [x] `test_historical_comments.py` — historical retrieval/profile + unsafe reference exclusion
- [x] `test_llm_client.py` — provider response parsing/validation/readiness + untrusted-context prompt contract
- [x] `test_youtube_context.py` — enriched YouTube metadata
- [x] `test_api_integration.py` — context persistence + additional-context separation + dashboard/feedback regression
- [x] frontend readiness utility tests
- [x] 기존 regression suite

### 1차 clean GitHub Actions 결과

Branch head `11b1ae6cd5912335e57ff58614a4b09ddddc9b0d`, workflow run `32924459725`:

- Backend: **44 passed**, 1 upstream Starlette/TestClient deprecation warning
- Frontend tests: success
- Frontend lint: success
- Frontend production build: success
- Frontend production dependency audit: success

### 재감사 후 코드 HEAD CI

Branch head `1064a749bd009662bd74771ef35de8ec82207e62`, workflow run `32931538728`:

- Backend: **51 passed**, 1 upstream Starlette/TestClient deprecation warning
- Frontend tests: success
- Frontend lint: success
- Frontend production build: success
- Frontend production dependency audit: success

외부 OpenAI/YouTube credentials를 CI에 요구하지 않는다. provider와 YouTube context는 fake session/provider boundary로 검증한다.

최종 README 정리 commit 뒤에도 branch CI를 다시 확인한 뒤 PR을 생성한다.

---

# 10. 구현 후 source audit

## Fixed-template path

확인 결과 `src/recommender/candidate_generator.py`에는 더 이상:

- `_candidate_templates`
- social/vlog별 고정 댓글 문장
- numbered filler candidate
- keyword를 조사에 직접 끼워 넣는 template

가 존재하지 않는다.

현재 candidate path:

```text
generate_candidates(GenerationContext)
  → OpenAIResponsesClient.generate(...)
```

LLM 실패 시 이전 template으로 돌아가는 reachable fallback은 없다.

## Social/vlog 호환 값

`social`/`vlog`는 두 곳에서만 legacy compatibility 의미를 가진다.

1. 이전 client가 보내던 `category` hint
2. 현재 historical CSV dataset coverage

새 YouTube URL 요청의 primary taxonomy는 공식 YouTube category를 우선한다.

## 실제 demographic 주장 여부

코드/README/UI 어디에서도 `target_age`/orientation을 실제 시청자 demographic으로 표현하지 않는다. `basis=official_flags_plus_explicit_content_heuristics`를 context에 기록한다.

## Hype 주장 범위

실제 trend velocity라고 표현하지 않는다. `hype_basis=single_snapshot_proxy`가 저장된다.

---

# 11. 계획 대비 의도적 차이

### YouTube category map

계획에서는 API category lookup을 생각했으나 preview의 추가 network dependency를 줄이기 위해:

- 자주 쓰이는 category ID의 built-in fallback
- 별도 `sync_youtube_categories.py`
- runtime JSON cache

방식으로 구현했다.

따라서 category sync 실패가 영상 preview 자체를 깨뜨리지 않는다.

### OpenAI SDK dependency를 추가하지 않음

현재 repo에 이미 `requests`가 있으므로 provider boundary를 raw Responses API HTTP로 구현했다.

장점:

- dependency 추가 없음
- provider protocol이 한 파일에 고립됨
- fake session 테스트가 쉬움

향후 공식 SDK로 변경해도 다른 context/ranker 코드는 바꿀 필요가 없다.

### Hype percentile

초기 기획의 “동일 장르/동일 연령 영상 percentile”은 현재 자체 reference population snapshot DB가 없어서 완전하게 구현하지 않았다.

현재는 bounded single-video proxy다. 이를 percentile/velocity로 발전시키려면 별도의 statistics snapshot collection job이 필요하다.

---

# 12. 남아 있는 제한 및 후속 데이터 작업

## 다장르 ranker validation

가장 큰 제한이다.

Context/LLM generator는 YouTube 공식 category와 broad topics를 받아 Music/Gaming/Sports/Beauty 등에서도 생성할 수 있다. 그러나 현재 reaction ranker의 학습 source는 social-issues/vlog 중심이다.

후속:

1. 공식 YouTube category별 대표 영상 수집
2. category/topic/style metadata와 함께 댓글 수집
3. engagement normalization 재검토
4. category-balanced split
5. ranker retrain + per-category metrics

## Hype history

실제 viral velocity를 위해서는:

```text
video_stats_snapshot
- video_id
- collected_at
- view_count
- like_count
- comment_count
```

같은 시계열 저장 구조가 필요하다.

## Transcript

공개 자막은 `youtube-transcript-api` 기반 best-effort이므로 클라우드 IP/YouTube 상태에 따라 실패할 수 있다. 자막 실패 시 title/description/tags metadata로 계속 진행한다. 현재는 “자막 없음”과 “자막 fetch 실패”를 별도 status로 구분하지 않는다.

## Korean heuristic

한국어 topic/style/age rule 일부는 substring 기반이다. 영문처럼 모든 단어에 ASCII word boundary를 적용하면 조사/복합어 recall을 해칠 수 있어 현재는 의도적으로 남겨두었다. 향후 형태소 분석 또는 embedding classifier 후보가 있다.

## LLM real E2E

CI는 비용과 외부 서비스 불안정성을 피하기 위해 실제 API 호출을 하지 않는다. 실제 서비스 동작에는 다음이 필요하다.

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- reaction model artifact
- YouTube URL 경로라면 `YOUTUBE_API_KEY`

의미적 hallucination과 최종 문체 자연스러움은 fake-provider CI로 완전히 증명할 수 없으므로 실제 provider smoke test와 human review가 별도로 필요하다.

## Storage

SQLite는 MVP/local single-instance persistence다. multi-instance/user-account 서비스가 되면 별도 production DB/ownership 설계가 필요하다.

---

# 13. 반영 전 최종 체크리스트

- [x] 설계 README를 구현 전에 작성
- [x] 구현 후 코드와 설계 대조
- [x] 별도 validation/anomaly README 작성
- [x] 고정 template generator 제거 확인
- [x] broad category/context path 확인
- [x] 기존 댓글 retrieval을 LLM 생성 이전 script 단계로 분리
- [x] historical reference 자체 safety filtering
- [x] LLM은 새 candidate 작성에만 사용
- [x] GenerationContext를 untrusted data로 다루는 prompt boundary
- [x] 생성 후 safety filter 유지
- [x] 생성 후 reaction ranker 유지
- [x] 기존 DB migration 고려
- [x] history request snapshot 저장/복원
- [x] additional_context 중복 제거
- [x] frontend dynamic category 반영
- [x] frontend readiness preflight
- [x] backend 1차 clean CI: 44 passed
- [x] 재감사 코드 HEAD CI: 51 passed
- [x] frontend 코드 HEAD CI: test/lint/build/audit success
- [ ] 최종 README 정리 commit 이후 최종 branch CI success
- [ ] branch가 latest main 대비 behind 0인지 재확인
- [ ] 세 README 전체 최종 재검토
- [ ] PR 생성
- [ ] PR-triggered CI success
- [ ] PR merge
- [ ] merge 후 main SHA/내용 확인
- [ ] merge 후 `feature/llm-context-generation` branch가 삭제되지 않았는지 확인

> **중요:** PR merge 시 `feature/llm-context-generation` branch를 삭제하지 않는다.

---

# 14. 반영 후 확인 절차

Merge 직후 다음을 다시 읽고 확인한다.

1. `main` branch가 PR merge commit을 가리키는지
2. `main`의 `candidate_generator.py`가 LLM-only path인지
3. `main`에 root README, 이 README, validation README가 존재하는지
4. `main` CI가 green인지
5. `feature/llm-context-generation` branch가 그대로 존재하는지
6. branch가 merge된 최종 feature head를 보존하는지

이 단계는 merge 이후 실제 GitHub 상태를 기준으로 수행하며 최종 작업 보고에 SHA와 함께 기록한다.
