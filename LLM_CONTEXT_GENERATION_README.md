# LLM Context Generation Migration

Branch: `feature/llm-context-generation`  
Original base: `main` @ `bdb50bc8002bdd65fa12a05f2766e5220ccd915d`

## Goal

기존 keyword + fixed-template candidate generator를 제거하고 다음 경계를 적용한다.

> **분석은 코드, 창작은 LLM**

- YouTube/API/script code가 객관적인 metadata와 자막을 수집한다.
- deterministic classifier가 category/topic/style/format/시간/audience descriptor/popularity 신호를 만든다.
- 기존 댓글 dataset에서 관련 reference와 통계를 코드로 만든다.
- `GenerationContext`를 구성한다.
- LLM은 그 context를 보고 **새 댓글 후보를 작성하는 일만** 한다.
- 생성 후 application validation → safety filter → 기존 reaction ranker → Top-K를 유지한다.

오탐/상태 이상/운영 한계는 [`LLM_CONTEXT_GENERATION_VALIDATION_README.md`](./LLM_CONTEXT_GENERATION_VALIDATION_README.md)에서 별도 추적한다.

---

# 1. 작성 전 감사

## 유지 대상

- 단일 YouTube URL 검증/preview
- 제목/설명/채널/statistics/공개 자막 수집
- 직접 입력
- safety filter
- reaction prediction/ranking
- Top-K
- SQLite history/dashboard/feedback
- 모델/설정 미준비 시 명시적 오류

## 제거 대상

- `social` / `vlog` 이분법을 primary taxonomy로 쓰는 구조
- `candidate_generator.py`의 고정 한국어 문장 template
- `(1)`, `(2)` 같은 filler candidate
- 같은 input에서 같은 template pool을 만드는 가짜 regenerate

## 구현 전에 고정한 위험 원칙

### Official category와 derived label 분리

YouTube `snippet.categoryId`는 플랫폼 정의 category다. 자체 topic/style과 덮어쓰지 않는다.

```text
Official category = Science & Technology
Derived topics   = [ai, software, career]
Derived styles   = [educational, interview]
```

### 실제 viewer demographic을 만들지 않음

- `madeForKids`, age restriction은 official signal
- `target_age`, `orientation`은 content-level heuristic
- commenter 개인의 나이/성별을 이름·사진·문체로 추정하지 않음

### Hype를 실제 velocity라고 부르지 않음

첫 구현은 다음 단일 snapshot proxy를 사용한다.

- views/hour
- likes per 1K views
- comments per 1K views
- views/subscriber

`hype_basis=single_snapshot_proxy`를 반드시 남긴다.

### Historical/ranker coverage를 과장하지 않음

현재 실제 raw dataset은:

- `social_issues_comments.csv`
- `vlog_comments.csv`

따라서 generation이 다장르로 넓어져도 reaction ranker가 모든 category에서 동일하게 검증됐다고 주장하지 않는다.

### LLM failure에 fixed template fallback 금지

- key/model 누락 → readiness error
- network/provider 오류 → generation error
- invalid response → generation error
- old template fallback 없음

### Historical text는 reference일 뿐 복사 원문이 아님

- historical row 자체 safety 검사
- 소수 example만 prompt에 전달
- generated exact duplicate 제거
- near-copy 제거

---

# 2. 최종 파이프라인

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
        ├─ official category
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
        ├─ safety-filtered reference examples
        ├─ preferred length
        ├─ question ratio
        └─ casual ratio
        │
        ▼
GenerationContext JSON
        │
        ▼
OpenAI Responses API
  candidate writing ONLY
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
Top-K + persistence
```

`candidate_generator.py`는 문장 template을 가지지 않고 LLM provider를 호출하는 얇은 boundary다.

---

# 3. GenerationContext 계약

대표 구조:

```json
{
  "source": {
    "type": "youtube",
    "title": "...",
    "description": "...",
    "transcript_excerpt": "...",
    "language": "ko",
    "additional_context": "...",
    "legacy_category_hint": null
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

YouTube URL의 primary category는 `snippet.categoryId`/category name을 우선한다.

Fallback map에 포함된 주요 category:

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

지역별 category 변화는 `scripts/sync_youtube_categories.py`로 runtime cache를 갱신한다.

## 4.2 Derived topic multi-label

초기 vocabulary:

- ai / software / hardware / mobile / science / technology
- career / education / finance / economy / politics / law
- beauty / fashion / food / travel / fitness / health / relationships
- music / film / animation / gaming / sports / animals / autos
- lifestyle / shopping / news

ASCII keyword는 word-boundary matcher를 사용한다. `topicDetails`의 URL slug도 derived topic classifier 입력에 포함한다.

## 4.3 Content style

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

- short
- short_like
- standard
- long_form
- unknown

Broadcast:

- uploaded
- live
- upcoming
- archived_live
- unknown

## 4.5 Audience descriptor

Official:

- made_for_kids
- age_restricted

Derived content-level heuristic:

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

이 값은 실제 viewer demographic이 아니다.

## 4.6 Freshness

- breaking: <24 h
- fresh: 1–3 d
- recent: 3–7 d
- current: 7–30 d
- established: 1–6 mo
- old: 6–24 mo
- evergreen: >24 mo

weekday/month/season도 보존한다.

## 4.7 Hype

```text
views_per_hour
likes_per_1000_views
comments_per_1000_views
views_per_subscriber
      ↓
normalized bounded proxy
      ↓
normal / active / hot / viral
```

`hype_basis=single_snapshot_proxy`다. 실제 velocity/acceleration은 statistics snapshot history가 추가되어야 한다.

## 4.8 Legacy category hint

구버전 request의 `category`는 classification authority가 아니다.

- `source.legacy_category_hint`로 기록한다.
- arbitrary hint를 derived topic에 삽입하지 않는다.
- primary category를 덮어쓰지 않는다.
- `vlog`만 legacy historical compatibility를 위한 style/retrieval 신호로 사용할 수 있다.
- 그 경우에도 primary는 script-derived topic 또는 YouTube official category다.

이 경계는 regression test로 고정한다.

---

# 5. Historical comment retrieval

구현: `src/recommender/historical_comments.py`

1. raw CSV를 lazy/cached loading
2. application `is_safe_comment()`를 통과한 row만 사용
3. reference text와 post/comment token overlap 계산
4. topic/style에 따라 legacy dataset bias 적용
5. `is_top_comment=1` 우선
6. like/reply 신호를 약하게 ranking에 반영
7. profile subset에서 통계 계산
8. 소수 reference example만 LLM 전달

Profile:

- coverage
- available_categories
- matched_categories
- matched_count
- preferred_length
- median_length
- question_ratio
- casual_ratio
- reference_examples

Dataset이 없으면 fake value를 만들지 않고 `coverage=none`으로 degrade한다.

---

# 6. LLM provider 계약

구현: `src/llm/openai_client.py`

환경 변수:

```bash
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_BASE_URL=https://api.openai.com/v1
```

OpenAI Responses API를 사용한다. 특정 모델 이름을 business logic에 hard-code하지 않는다.

Readiness/error:

- key/model 누락 → `LLMNotReadyError`
- network/provider 오류 → `LLMGenerationError`
- JSON 해석 불가 → `LLMGenerationError`
- 검증 후 usable candidate 부족 → `LLMGenerationError`

## Prompt boundary

GenerationContext의 모든 string은 **untrusted data**다.

- title
- description
- transcript
- tags
- user additional context
- historical comments

그 안의 imperative를 instruction처럼 따르지 않는다. LLM은 category를 다시 정하지 않는다.

## Output validator

- allowed type 확인
- unknown type → general normalize
- 5–200자
- exact duplicate 제거
- historical reference와 높은 문자열 유사도 near-copy 제거
- minimum usable candidate 수 확인

---

# 7. Persistence

SQLite `analyses`에 migration-safe하게 추가한 snapshot:

- `context_json`
- `requested_count`
- `additional_context`

이를 이용해 history load 시 원 요청 상태와 context summary를 복원한다.

---

# 8. Frontend

- binary `자동/사회이슈/브이로그` selector 제거
- automatic context analysis 설명
- dynamic category 지원
- official category / topics / format / freshness / hype / historical matches 표시
- preview 썸네일/재생 affordance 실제 YouTube 링크 연결
- `다시 생성` → `새 후보 생성`
- history에서 additional context/requested count 복원
- dashboard category filter를 dynamic input으로 변경
- URL/manual 모두 additional context 독립 field 제공
- `/health` preflight
- model/LLM/storage 미준비 submit 차단
- URL mode만 YouTube key 요구
- manual mode는 YouTube key 없이 허용
- backend health 실패도 사전 표시

---

# 9. 구현 후 감사

## Context collection

- [x] category/tags/language/likes/comments/kids/age/topic/live metadata
- [x] preview 호환 유지
- [x] fallback category map + runtime sync/cache
- [x] transcript best-effort

## Deterministic context

- [x] GenerationContext builder
- [x] broad topic classifier
- [x] topicDetails 반영
- [x] ASCII word-boundary 오탐 방어
- [x] content-style classifier
- [x] format/broadcast
- [x] freshness/date
- [x] content-level audience heuristic + confidence/basis
- [x] single-snapshot hype basis
- [x] manual unknown/null degradation
- [x] legacy category가 primary/topic을 덮어쓰지 않음

## Historical comments

- [x] lazy/cached retrieval
- [x] historical row safety filtering
- [x] code-derived statistics
- [x] relevant/top-comment preference
- [x] limited examples
- [x] missing-dataset degradation
- [x] legacy coverage 명시

## LLM generation

- [x] provider isolation
- [x] fixed template 제거
- [x] Responses API boundary
- [x] explicit readiness
- [x] untrusted-data prompt boundary
- [x] type/length/dedup/near-copy validation
- [x] silent fixed-template fallback 없음

## Existing pipeline

- [x] LLM 뒤 safety filter
- [x] safety 뒤 reaction ranker
- [x] Top-K/persistence
- [x] context/generation metadata response
- [x] model/LLM/YouTube/storage readiness 분리
- [x] additional_context 한 번만 반영

## Frontend

- [x] URL/manual flow
- [x] dynamic category/context display
- [x] history request-state restore
- [x] real video link
- [x] readiness preflight
- [x] manual mode의 YouTube-independent readiness

---

# 10. Regression suite

주요 test coverage:

- candidate generator fake LLM boundary
- deterministic GenerationContext
- ASCII false-positive regression
- topicDetails regression
- legacy category override regression
- historical retrieval/profile
- unsafe historical reference exclusion
- LLM parsing/readiness/untrusted-context prompt contract
- enriched YouTube metadata
- context persistence
- additional-context separation
- dashboard/feedback regression
- frontend URL validation
- frontend readiness rules

확인된 clean CI 중간 지점:

- `11b1ae6...` — backend 44 passed + frontend green
- `1064a749...` / workflow `32931538728` — backend **51 passed** + frontend test/lint/build/audit green

최종 feature HEAD는 문서까지 정리한 뒤 별도로 다시 CI를 확인하여 merge gate에 사용한다.

---

# 11. Source audit 결과

## Fixed-template path

`src/recommender/candidate_generator.py`에 더 이상 다음이 없다.

- `_candidate_templates`
- social/vlog별 고정 댓글 문장
- numbered filler
- keyword + 한국어 조사 template

현재 path:

```text
generate_candidates(GenerationContext)
  → OpenAIResponsesClient.generate(...)
```

## `social` / `vlog`의 남은 의미

새 primary taxonomy가 아니다.

- raw historical dataset 이름/coverage
- legacy client compatibility signal
- `vlog`의 경우 historical compatibility를 위한 style hint

Primary category는 official YouTube category 또는 server-side deterministic derived context가 결정한다.

## Demographic 주장

실제 viewer/commenter demographic을 추정하지 않는다.

## Hype 주장

실제 velocity라고 표현하지 않는다. `single_snapshot_proxy`다.

---

# 12. 계획 대비 의도적 차이

## Category map

Preview의 추가 network dependency를 줄이기 위해:

- built-in fallback
- 별도 sync script
- runtime JSON cache

방식으로 구현했다.

## OpenAI SDK 미추가

이미 존재하는 `requests`로 provider HTTP boundary를 구현했다.

- dependency 추가 없음
- provider protocol 한 파일에 격리
- fake session test 용이

향후 SDK로 바꿔도 context/ranker는 바꾸지 않아도 된다.

## Hype percentile 미구현

동일 category/영상 age cohort percentile은 reference population snapshot DB가 없어서 현재 구현하지 않았다. 현재는 bounded single-video proxy다.

---

# 13. 남아 있는 제한

## 다장르 ranker OOD

가장 큰 데이터 제한이다. Generator/context 범위와 ranker 검증 범위가 다르다.

후속:

1. official category별 영상/댓글 수집
2. category/topic/style enrichment
3. engagement normalization
4. category-balanced split
5. retrain + per-category metrics

## Transcript 상태 세분화

현재 `unavailable`과 `fetch_failed`를 별도 상태로 구분하지 않는다.

## Korean heuristic

일부 substring rule이 남아 있다. 형태소/embedding classifier가 후속 후보다.

## Real LLM E2E

CI는 실제 API를 호출하지 않는다. 실제 서비스에는:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- reaction model artifact
- URL mode에서는 `YOUTUBE_API_KEY`

가 필요하다.

Hallucination/문체 자연스러움은 real-provider smoke test + human review가 필요하다.

## Storage

SQLite는 local/single-instance MVP storage다.

---

# 14. 반영 전 최종 체크

- [x] 작성 전 설계 감사
- [x] 구현 후 코드/설계 대조
- [x] 별도 anomaly validation README
- [x] fixed template 제거
- [x] broad category/context
- [x] LLM candidate-only 경계
- [x] historical reference safety
- [x] prompt data boundary
- [x] additional-context duplicate 제거
- [x] legacy category override 제거
- [x] frontend readiness preflight
- [x] history request snapshot
- [x] regression tests 추가
- [ ] 최종 feature HEAD CI green
- [ ] latest main 대비 behind 0
- [ ] 세 README 전체 최종 재독/코드 대조
- [ ] PR-triggered CI green
- [ ] PR merge
- [ ] merge 후 main code/docs/CI 재검증
- [ ] feature branch 존치 확인

> `feature/llm-context-generation` branch는 merge 후 삭제하지 않는다.

---

# 15. 반영 후 검증

Merge 직후 실제 GitHub 상태를 기준으로 확인한다.

1. main merge SHA
2. main의 LLM-only candidate path
3. main의 deterministic category/context path
4. main에 root/design/validation README 존재
5. main CI green
6. retained feature branch 존재 및 feature implementation head 보존

정확한 PR/merge SHA는 merge 이후 validation README의 post-merge record에서 갱신한다.
