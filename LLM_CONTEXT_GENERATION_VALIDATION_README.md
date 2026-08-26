# LLM Context Generation — Validation / Anomaly Audit

Branch: `feature/llm-context-generation`

이 문서는 `LLM_CONTEXT_GENERATION_README.md`의 설계/구현 기록과 별개로, LLM 전환 과정에서 발견한 **오탐 가능성, 상태 이상, LLM 입력/출력 위험, 데이터 편향, 외부 의존성, 의도적으로 남긴 제한**을 추적한다.

핵심 원칙은 다음과 같다.

1. 영상 분류와 맥락 수집은 deterministic code/script가 담당한다.
2. LLM은 완성된 `GenerationContext`를 읽고 **새 댓글 후보를 작성하는 일만** 담당한다.
3. `해결됨`은 코드 수정뿐 아니라 회귀 테스트 또는 명확한 검증 근거가 있어야 한다.
4. public API/data로 해결할 수 없는 부분은 숨기지 않고 `의도된 제한` 또는 `운영 위험`으로 남긴다.
5. merge 전 이 문서, `LLM_CONTEXT_GENERATION_README.md`, root `README.md`를 처음부터 끝까지 다시 읽고 코드와 대조한다.
6. merge 후에는 `main` 코드/CI와 retained feature branch를 다시 확인한다.

## 상태 정의

- **해결됨**: 방어 코드 + 회귀 검증이 존재한다.
- **의도된 제한**: 현재 API/data/설계상 완전 해결 대상이 아니며 과장하지 않아야 한다.
- **운영 위험**: 실제 provider/배포 환경에서만 완전 검증할 수 있다.
- **후속 후보**: MVP merge를 막지는 않지만 다음 데이터/제품 작업으로 남긴다.

---

# 1. 오탐 가능성

## FP-01 — 짧은 ASCII keyword substring 오탐

상태: **해결됨**

기존 위험:

- `ai`가 `chair`, `detail`, `training` 내부에서 매칭
- `car`가 더 긴 영단어 일부에 매칭
- `man`이 `woman` 내부에서 매칭되어 female/male이 동시에 잡힘

대응:

- ASCII keyword는 단순 substring 대신 `_keyword_present()`의 영숫자 word boundary로 판정한다.
- topic/style/age/orientation matcher가 같은 규칙을 사용한다.

회귀 테스트:

- `Chair design details and interior styling` → `ai`, `autos` 없음
- 독립된 `AI tools for software teams` → `ai`, `software` 존재
- `Women fashion ... woman ...` → `female_oriented`, `mixed` 아님

## FP-02 — YouTube `topicDetails` 수집 후 미사용

상태: **해결됨**

기존 위험:

- 영상 title/description이 짧아도 `topicDetails`가 명확할 수 있는데 metadata를 수집만 하고 derived classifier가 사용하지 않음.

대응:

- topic URL/path의 마지막 slug를 decode/normalize해 derived topic classifier 입력에 추가한다.
- official category와 derived topic은 별도 필드로 유지한다.

회귀 테스트:

- title에 `music`이 없어도 topicDetails가 `/Music`이면 `music` topic 생성.

## FP-03 — target age를 실제 viewer age로 오해

상태: **의도된 제한**

- public YouTube Data API가 임의 영상의 실제 시청자 연령 분포를 제공한다는 전제로 설계하지 않는다.
- `target_age`는 제목/설명/자막에 명시된 대상에 대한 **콘텐츠 수준 heuristic**이다.
- `madeForKids` / age restriction은 공식 신호다.
- 그 외 heuristic confidence는 1.0으로 만들지 않는다.
- `basis=official_flags_plus_explicit_content_heuristics`를 저장한다.

금지:

- “실제 시청자 20대” 같은 표현
- 댓글 작성자 이름/사진/문체로 나이 추정

## FP-04 — orientation을 실제 개인 성별로 오해

상태: **의도된 제한**

- `general`, `female_oriented`, `male_oriented`, `mixed`는 콘텐츠의 명시적 지향만 나타낸다.
- commenter 개인의 성별을 추정하지 않는다.
- ASCII `woman`/`man` substring 오탐은 FP-01에서 방어한다.

## FP-05 — 한국어 substring heuristic 오탐

상태: **의도된 제한**

- 한국어에 영문과 같은 ASCII word boundary를 일괄 적용하면 조사/복합어 recall이 크게 떨어질 수 있다.
- 현재 한국어 topic/style/age rule 일부는 substring이다.
- 짧고 오탐이 큰 단어는 vocabulary에서 피하고, derived multi-label은 official category를 덮어쓰지 않는다.

후속 후보:

- 형태소 분석
- embedding classifier
- labeled validation set 기반 threshold 조정

## FP-06 — Official category와 derived topic/style 충돌

상태: **해결됨**

- YouTube `category_id/category_name`과 자체 `topics/content_styles`를 별도 필드로 저장한다.
- YouTube URL이면 primary category는 official category를 우선한다.
- LLM은 category를 다시 결정하지 않는다.

## FP-07 — YouTube category map 지역/시점 변화

상태: **의도된 제한**

- built-in category map은 preview 안정성을 위한 fallback이다.
- `scripts/sync_youtube_categories.py --region KR`로 runtime category map을 동기화할 수 있다.
- category sync 실패가 video preview 전체 실패로 이어지지 않는다.

---

# 2. 상태 이상 / 흐름 이상

## ST-01 — `additional_context` 중복 반영

상태: **해결됨**

기존 위험:

- API reference text에 추가 맥락을 붙이고 `build_generation_context(additional_context=...)`에도 다시 넣어 classification/retrieval/ranking에서 같은 정보가 중복될 수 있었다.

현재:

- `source_reference_text`에는 원 영상/직접입력만 들어간다.
- 추가 맥락은 context builder에 별도 field로 한 번 전달한다.
- ranker reference에도 정확히 한 번만 append한다.

회귀 테스트:

- API integration test가 source/additional context 분리와 ranking/response 내 1회 반영을 확인한다.

## ST-02 — URL → manual 전환 시 상태 혼합

상태: **해결됨**

- additional context를 manual text로 복사하지 않는다.
- manual input과 additional context는 독립 state다.
- 두 모드 모두 additional-context field를 별도로 제공한다.

## ST-03 — History restore의 stale context/count

상태: **해결됨**

SQLite `analyses`에 다음 snapshot을 저장한다.

- `context_json`
- `requested_count`
- `additional_context`

History load에서 당시 추가 맥락, 요청 개수, context summary를 복원한다.

## ST-04 — `다시 생성`이 동일 fixed template 결과 반복

상태: **해결됨**

- fixed template generator를 제거했다.
- 버튼을 `새 후보 생성`으로 바꾸고 LLM candidate generation을 다시 호출한다.

주의:

- provider가 유사한 답을 다시 생성할 가능성까지 애플리케이션이 0으로 만들 수는 없다.

## ST-05 — 새 후보 생성이 새 analysis row를 만듦

상태: **의도된 제한**

- 현재는 명시적으로 새 generation을 실행하면 별도 analysis로 저장한다.
- deterministic template 시절처럼 “완전히 같은 후보를 저장하는 가짜 재생성”은 아니다.

후속 후보:

- `parent_analysis_id`
- `regeneration_group_id`

## ST-06 — model / LLM / YouTube / storage readiness 혼동

상태: **해결됨**

Backend:

- `/health`가 model, llm, youtube, storage 상태를 분리한다.
- model artifact 누락 → `ModelNotReadyError`
- LLM key/model 누락 → `LLMNotReadyError`
- YouTube key 누락 → URL path의 `YouTubeConfigurationError`

Frontend:

- 추천 화면에서 `/health` preflight를 수행한다.
- model/LLM/storage 미준비 시 원인을 표시하고 submit을 막는다.
- URL 모드는 YouTube API 설정을 추가로 요구한다.
- **manual 모드는 YouTube key 없이 허용한다.**
- backend health 자체를 읽지 못하면 연결 상태 메시지와 함께 submit을 막는다.

회귀 테스트:

- manual + YouTube unconfigured → 허용
- URL + YouTube unconfigured → 차단
- model/LLM/backend failure → 사전 차단

## ST-07 — transcript 없음과 transcript fetch 실패 상태가 동일

상태: **의도된 제한**

- transcript는 best-effort이며 실패해도 title/description/tags로 계속 진행한다.
- 현재 `unavailable`과 일시적인 `fetch_failed`를 별도 상태로 나누지는 않는다.

후속 후보:

```text
transcript_status = available | unavailable | fetch_failed
```

## ST-08 — LLM candidate 부족

상태: **해결됨**

- provider 응답을 parse한 뒤 type/length/dedup/reference-copy 검증을 수행한다.
- usable candidate 최소 수가 부족하면 명시적 generation error를 반환한다.
- 옛 fixed template으로 silent fallback하지 않는다.

## ST-09 — unknown/manual content를 social/vlog로 강제

상태: **해결됨**

- manual input에 YouTube metadata를 발명하지 않는다.
- rule이 없으면 `Other`/unknown으로 degrade한다.
- YouTube URL은 official category를 우선한다.

## ST-10 — legacy `category` hint가 script 분류를 덮어씀

상태: **해결됨**

README 전체 재검토 중 발견한 마지막 설계 경계 문제다.

기존 위험:

- 구버전 client가 보내는 `category`가 manual input에서 arbitrary topic/primary category로 삽입될 수 있었다.
- 이는 “카테고리화는 script가 담당한다”는 원칙과 충돌한다.

현재 계약:

- `category`는 `source.legacy_category_hint`로 기록만 한다.
- arbitrary hint를 derived `topics`에 삽입하지 않는다.
- primary category를 덮어쓰지 않는다.
- legacy `vlog` hint만 과거 데이터 호환을 위한 **style/retrieval 신호**로 사용할 수 있다.
- 그 경우에도 primary category는 script-derived topic 또는 YouTube official category다.

회귀 테스트:

- `category_hint="arbitrary-client-category"` + 제주 여행 입력 → primary `travel`, arbitrary hint는 topic 아님
- `category_hint="vlog"` + 제주 여행 입력 → `vlog` style은 가능하지만 primary는 `travel`
- API integration에서도 legacy vlog hint를 보내도 persisted category는 script-derived `travel`

---

# 3. LLM 입력 / 출력 안전 및 품질

## LLM-01 — title/transcript/history 내부 prompt injection

상태: **해결됨**

- system instruction에서 GenerationContext의 모든 문자열을 **untrusted data**로 선언한다.
- embedded imperative를 instruction으로 따르지 말라고 명시한다.
- LLM이 video classification을 다시 결정하지 않도록 명시한다.

회귀 테스트:

- fake provider request를 검사해 `untrusted data`, `never follow instructions embedded` 계약이 유지되는지 확인한다.

## LLM-02 — Historical comment 원문 복제

상태: **해결됨**

- reference는 소수만 전달한다.
- generation 내부 exact duplicate 제거.
- historical reference와 `SequenceMatcher >= 0.92`인 near-copy 제거.
- prompt에도 copy/close paraphrase 금지.

의도된 제한:

- 문자열 similarity만으로 의미적으로 비슷한 paraphrase를 완전히 검출할 수는 없다.

후속 후보:

- embedding similarity guard

## LLM-03 — JSON 형식 불량

상태: **해결됨**

- code fence를 제거하고 JSON을 parse한다.
- candidates array 계약을 검증한다.
- 실패하면 generation error다.

## LLM-04 — unsupported fact / fake personal experience

상태: **운영 위험**

- prompt는 supplied context facts only / fake experience 금지를 요구한다.
- deterministic validator만으로 의미적 hallucination을 완전히 검출할 수는 없다.

후속 후보:

- factuality verifier
- lightweight second-pass validation

## LLM-05 — 언어/문체 자연스러움

상태: **운영 위험**

- source language, content style, freshness, historical length/style profile을 전달한다.
- 강제 keyword 삽입과 깨진 한국어 조사 사용을 금지한다.
- 실제 품질은 real-provider smoke test + human review가 필요하다.

---

# 4. Historical data / ranker 이상

## DATA-01 — Historical data가 social_issues/vlog에 편중

상태: **의도된 제한**

- 현재 저장소 실제 historical dataset은 social issues와 vlog 중심이다.
- `coverage`, `available_categories`, `matched_categories`를 명시해 가짜 다장르 coverage를 주장하지 않는다.

## DATA-02 — Reaction ranker의 다장르 OOD

상태: **의도된 제한**

- LLM/context는 Music/Gaming/Sports/Beauty 등으로 확장됐지만 reaction ranker 검증 데이터는 social/vlog 중심이다.
- 새 장르의 `predicted_score`를 동일한 신뢰도로 검증했다고 주장하지 않는다.

후속:

1. YouTube official category별 영상/댓글 수집
2. category/topic/style enrichment
3. engagement normalization 재검토
4. category-balanced split/retrain
5. per-category metrics

## DATA-03 — `is_top_comment` label의 exposure/timing bias

상태: **의도된 제한**

- 현재 같은 영상 내 like_count 상위 15%를 positive label로 사용한다.
- 좋아요는 게시 시점, 노출 위치, 채널 규모 등의 영향을 받는다.

후속:

- comment age/video age normalization
- reply/like exposure 보정

## DATA-04 — Unsafe historical comment가 LLM reference/profile에 들어감

상태: **해결됨**

README/code 재감사에서 발견한 누락이다.

- 처음 구현에서는 historical CSV row가 빈 값/길이만 통과하면 profile/reference 후보가 될 수 있었다.
- 반응이 높아도 욕설/혐오/스팸을 LLM style reference로 쓰면 안 된다.

대응:

- `_load_dataset()`에서 `is_safe_comment()`를 적용한다.
- unsafe row는 profile 통계와 reference examples 양쪽 모두에서 제외한다.
- historical text는 통과 후에도 LLM에선 untrusted data다.

회귀 테스트:

- 높은 like_count를 가진 unsafe row가 `matched_count`/reference에서 제외됨.

---

# 5. 시간 / 인기도 이상

## POP-01 — Hype를 실제 viral velocity로 오해

상태: **의도된 제한**

현재 지표:

- views/hour
- likes per 1K views
- comments per 1K views
- views/subscriber

이를 bounded single-snapshot proxy로 조합하고:

```text
hype_basis = single_snapshot_proxy
```

를 저장한다.

금지 표현:

- 실제 성장 가속도
- 실시간 트렌드 속도
- 정확한 viral probability

## POP-02 — 오래된 영상의 views/hour는 lifetime average

상태: **의도된 제한**

- 현재 views/hour는 총 조회수 / 게시 후 경과시간이다.
- 최근 몇 시간 실제 속도가 아니다.

후속:

```text
video_stats_snapshot
- video_id
- collected_at
- view_count
- like_count
- comment_count
```

을 저장해 Δviews/Δtime을 계산한다.

## POP-03 — subscriber 비공개/0

상태: **해결됨**

- subscriber가 없으면 views/subscriber component를 제외하고 남은 available component만으로 proxy를 계산한다.

---

# 6. 외부 의존성 / 운영 상태

## EXT-01 — YouTube API key 없음

상태: **운영 위험**

- URL preview/recommend는 사용할 수 없다.
- manual path는 사용할 수 있다.
- frontend가 URL 모드에서 사전에 안내한다.

## EXT-02 — OpenAI key/model 없음

상태: **운영 위험**

- candidate generation을 사용할 수 없다.
- `/health` + frontend preflight로 명확히 노출한다.

## EXT-03 — reaction model artifact 없음/불일치

상태: **운영 위험**

- ranking을 사용할 수 없다.
- model readiness + frontend preflight로 표시한다.

## EXT-04 — transcript API cloud/IP failure

상태: **운영 위험**

- `youtube-transcript-api`는 best-effort dependency다.
- 실패 시 metadata-only로 degrade한다.

## EXT-05 — CI에서 실제 OpenAI/YouTube E2E 미실행

상태: **의도된 제한**

이유:

- 비용
- rate limit
- 외부 서비스 변동성
- secret 보호

대신 fake provider/session boundary와 deterministic integration regression을 사용한다.

실제 배포 전에는 별도 smoke E2E가 필요하다.

---

# 7. 회귀 검증 목록

구현되어 있는 검증:

- [x] ASCII short-keyword substring false positive
- [x] standalone ASCII keyword positive
- [x] `woman`/`man` orientation false positive
- [x] YouTube topicDetails → derived topic
- [x] manual input은 YouTube metadata를 발명하지 않음
- [x] legacy category hint가 primary/topic을 덮어쓰지 않음
- [x] additional_context source/context 분리 및 1회 반영
- [x] prompt의 untrusted-data boundary
- [x] LLM JSON/type/length/dedup/reference-copy validation
- [x] unsafe historical reference 제외
- [x] historical missing dataset graceful degradation
- [x] frontend readiness: manual은 YouTube key 불필요
- [x] frontend readiness: URL은 YouTube key 필요
- [x] frontend readiness: model/LLM/backend 상태 실패 사전 차단
- [x] history의 context/additional context/requested count persistence
- [x] 기존 safety/ranker/dashboard/feedback regression
- [x] frontend test/lint/build/audit

확인된 이전 clean CI:

- `11b1ae6...` — backend 44 passed + frontend green
- `1064a749...` / workflow `32931538728` — backend **51 passed** + frontend test/lint/build/audit green

최신 legacy-category regression commit 이후의 **최종 branch CI 결과를 merge gate에서 다시 확인**한다.

---

# 8. Merge Gate

아래가 모두 충족되어야 `main`에 반영한다.

- [x] fixed template generator 제거
- [x] classification/context는 code/script가 담당
- [x] LLM은 candidate creation only
- [x] official category와 derived labels 분리
- [x] ASCII false-positive regression
- [x] topicDetails regression
- [x] legacy category override 제거/regression
- [x] additional-context duplicate 제거/regression
- [x] historical reference safety/regression
- [x] prompt injection data-boundary regression
- [x] frontend readiness preflight/regression
- [ ] 최신 feature HEAD push CI green
- [ ] `main...feature` behind 0 재확인
- [ ] `LLM_CONTEXT_GENERATION_README.md` 전체 최종 재독
- [ ] 이 validation README 전체 최종 재독
- [ ] root `README.md` 전체 최종 재독
- [ ] 문서 주장과 실제 feature 코드 대조 완료
- [ ] fixed template reachable path 없음 최종 검색
- [ ] social/vlog가 새 primary taxonomy로 남지 않음 최종 확인
- [ ] 실제 viewer demographic을 주장하지 않음 최종 확인
- [ ] hype를 real velocity로 주장하지 않음 최종 확인
- [ ] PR 생성
- [ ] PR-triggered CI green
- [ ] PR merge
- [ ] merge된 `main` code/README 재검증
- [ ] merge commit/main CI green 확인
- [ ] `feature/llm-context-generation` branch 존치 확인

> **Feature branch는 merge 후 삭제하지 않는다.**

---

# 9. 반영 후 기록

Merge 완료 후 실제 GitHub 상태로 기록/검증한다.

- feature final implementation head: pending
- implementation PR: pending
- PR-triggered CI: pending
- main merge SHA: pending
- main code/README verification: pending
- main CI: pending
- retained feature branch verification: pending

Merge SHA는 merge 전에 알 수 없으므로 임의로 예측하지 않는다. 필요하면 merge 후 retained feature branch에서 이 문서를 갱신하고 docs-only follow-up PR로 `main`에도 반영한다.

---

# 10. 최종 검증 절차

마지막 보고 전 반드시 다음을 처음부터 끝까지 다시 읽는다.

1. `LLM_CONTEXT_GENERATION_README.md`
2. `LLM_CONTEXT_GENERATION_VALIDATION_README.md`
3. root `README.md`

그리고 다음 실제 코드와 대조한다.

- `src/recommender/generation_context.py`
- `src/recommender/historical_comments.py`
- `src/recommender/candidate_generator.py`
- `src/llm/openai_client.py`
- `src/recommender/ranker.py`
- `src/api/main.py`
- `src/storage/analysis_store.py`
- `frontend/src/api/client.ts`
- `frontend/src/utils/readiness.ts`
- `frontend/src/pages/RecommendPage.tsx`

문서보다 코드가 부족하면 코드를 수정한다. 코드보다 문서가 과장되어 있으면 문서를 수정한다. 그 뒤 CI를 다시 확인한다.
