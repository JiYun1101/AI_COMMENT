# LLM Context Generation — Validation / Anomaly Audit

Branch: `feature/llm-context-generation`

이 문서는 `LLM_CONTEXT_GENERATION_README.md`의 설계/구현 기록과 별개로, **오탐 가능성·상태 이상·외부 의존성·검증 범위**를 추적하는 검증용 README다.

작업 원칙:

1. 분류/맥락 수집은 deterministic code/script가 담당한다.
2. LLM은 주어진 `GenerationContext`를 바탕으로 새 댓글을 쓰는 일만 담당한다.
3. 이 문서에서 `해결됨`으로 표시하는 항목은 코드 수정만으로 끝내지 않고 회귀 테스트 또는 명확한 검증 근거를 남긴다.
4. 실제로 해결할 수 없는 데이터/운영 한계는 숨기지 않고 `의도된 제한`으로 남긴다.
5. merge 전 이 문서와 `LLM_CONTEXT_GENERATION_README.md` 전체를 다시 읽고 체크한다.
6. merge 후에는 `main`의 실제 코드/CI/branch 상태를 다시 확인한다.

---

# 1. 상태 분류

- `해결됨`: 코드에 방어가 있고 회귀 검증이 존재함.
- `테스트 필요`: 코드 수정은 되었거나 방향은 정해졌지만 명시적 회귀 테스트가 아직 부족함.
- `의도된 제한`: 현재 데이터/API 특성 때문에 완전 해결 대상이 아님. UI/README에서 과장하지 않아야 함.
- `운영 위험`: local test만으로 보장할 수 없고 실제 provider/배포 환경에서 관찰해야 함.
- `미발견`: 현재 감사에서 재현되지 않았지만 계속 감시할 항목.

---

# 2. 오탐 가능성 (False Positive / Misclassification)

## FP-01 — 짧은 영어 topic keyword의 substring 오탐

상태: `테스트 필요`

문제 예:

- `ai`가 `chair`, `detail`, `training` 같은 단어 내부에서 우연히 매칭
- `car`가 더 긴 영단어 일부에 들어가 autos topic으로 잘못 분류
- `man`이 `woman` 내부에서 매칭되어 male/female orientation이 동시에 잡힘

대응:

- ASCII keyword는 단순 `in` 대신 영숫자 word boundary를 사용하는 `_keyword_present()`로 판정.
- topic/style/age/orientation 공통 matcher가 이 함수를 사용.

종료 조건:

- `chair design`이 AI로 분류되지 않는 테스트.
- `women fashion`이 `female_oriented`이고 `mixed`가 되지 않는 테스트.
- 독립된 `AI`, `man` 토큰은 계속 정상 매칭되는 테스트.

## FP-02 — YouTube `topicDetails`를 수집하고도 derived topic에 반영하지 않는 누락

상태: `테스트 필요`

문제:

- 영상 title/description이 짧더라도 YouTube topicDetails가 명확한 경우가 있다.
- metadata를 수집만 하고 classifier가 사용하지 않으면 정보 손실.

대응:

- topic URL/path의 마지막 slug를 decode/normalize하여 classifier 입력에 추가.
- official category는 그대로 보존하고 topicDetails는 derived multi-label 신호에만 사용.

종료 조건:

- title에 `music`이 없어도 topicDetails가 `/Music`이면 `music` topic이 생성되는 테스트.

## FP-03 — Content target age heuristic을 실제 viewer age로 오해할 위험

상태: `의도된 제한`

문제:

- `신입`, `대학생`, `육아`, `은퇴` 등의 단어는 콘텐츠 대상의 힌트일 뿐 실제 시청자 연령 분포가 아니다.
- `신입`은 신입사원 외의 의미도 가능하다.

대응:

- 필드 이름을 `target_age`로 유지.
- `basis=official_flags_plus_explicit_content_heuristics` 저장.
- madeForKids / age restriction 외에는 confidence를 1.0으로 만들지 않음.
- README/UI에서 viewer demographic이라는 표현 금지.

검증 기준:

- 코드/문서/API에서 실제 시청자 연령이라고 주장하는 표현이 없는지 최종 검색.

## FP-04 — 성별 관련 분류를 개인 성별 추정으로 오해할 위험

상태: `의도된 제한`

대응:

- `orientation`은 콘텐츠의 명시적 지향만 표현.
- commenter 이름/사진/문체를 이용한 개인 성별 추정 로직 없음.
- `general/female_oriented/male_oriented/mixed`만 사용.

검증 기준:

- 개인 user/commenter demographic inference 코드가 없는지 최종 검색.

## FP-05 — 한국어 keyword substring 오탐

상태: `의도된 제한`

문제:

- 한국어는 조사/복합어 때문에 영문과 동일한 word-boundary를 적용하면 오히려 recall이 크게 떨어질 수 있다.
- 현재 한국어 규칙은 substring 기반이다.

대응:

- 짧고 오탐이 큰 단어는 rule vocabulary에서 피한다.
- multi-label + confidence-less derived label로 사용하며 official category를 덮어쓰지 않는다.
- 장기적으로 형태소 분석/embedding classifier 도입 후보.

## FP-06 — Official YouTube category와 자체 topic/style 충돌

상태: `해결됨`

대응:

- `youtube.category_id/category_name`과 `content.topics/content_styles`를 별도 필드로 보존.
- primary category는 YouTube URL이면 official category를 우선.
- LLM에게 재분류 권한을 주지 않음.

## FP-07 — category mapping의 지역/시점 변화

상태: `의도된 제한`

대응:

- built-in fallback map은 preview 안정성을 위한 fallback.
- `scripts/sync_youtube_categories.py`로 runtime category map 동기화 가능.
- category sync 실패가 영상 preview 전체 실패로 이어지지 않음.

---

# 3. 상태 이상 (State / Flow Anomaly)

## ST-01 — `additional_context` 중복 반영

상태: `테스트 필요`

기존 위험:

- API가 reference text에 `추가 맥락:`을 붙인 뒤 `build_generation_context(... additional_context=...)`에도 다시 전달하면 동일 정보가 두 번 classification/retrieval에 들어갈 수 있음.

현재 대응:

- `source_reference_text`는 영상/직접입력 원문만 포함.
- `additional_context`는 GenerationContext builder에 별도 필드로 한 번 전달.
- ranker reference에는 필요한 경우 한 번만 append.

종료 조건:

- API integration test에서 context builder에 전달되는 source text와 additional context가 분리돼 있음을 검증.

## ST-02 — URL → 직접입력 전환 시 additional context가 본문으로 복사되는 상태 혼합

상태: `해결됨`

기존 위험:

- preview 실패 후 직접입력으로 전환할 때 additional context를 manual text로 복사하면 역할이 섞임.

대응:

- manual input과 additional context를 독립 state로 유지.
- 두 모드 모두 additional context field를 별도로 제공.

## ST-03 — History restore 시 stale context/count가 남는 문제

상태: `해결됨`

대응:

- SQLite에 `context_json`, `requested_count`, `additional_context` 저장.
- history load에서 requested count와 additional context 복원.
- 당시 context summary도 저장 context에서 재구성.

## ST-04 — `새 후보 생성`이 기존처럼 동일 template을 재생성

상태: `해결됨`

대응:

- fixed deterministic template path 제거.
- 버튼은 LLM을 다시 호출하여 새 candidate pool을 생성.

주의:

- provider가 temperature/모델 정책상 유사한 답을 반환할 가능성은 존재하며 애플리케이션이 완전한 다양성을 보장할 수는 없음.

## ST-05 — 새 후보 생성 시 새로운 analysis row 생성

상태: `의도된 제한`

현재 의미:

- 사용자가 명시적으로 새 후보를 생성하면 별도의 generation 결과로 저장한다.
- 이전 deterministic generator 때의 “같은 결과인데 중복 저장”과 달리 현재는 generation provenance가 다른 실행이다.

후속 후보:

- parent_analysis_id / regeneration_group_id를 추가하면 동일 요청의 세대 관계를 묶을 수 있음.

## ST-06 — model/LLM/YouTube readiness 혼동

상태: `해결됨`

대응:

- `/health`가 model, llm, youtube, storage를 분리해서 반환.
- LLM key/model 누락은 LLMNotReadyError.
- model artifact 누락은 ModelNotReadyError.
- YouTube key 누락은 URL context path의 YouTubeConfigurationError.

## ST-07 — transcript 없음과 transcript fetch 실패의 UI 상태가 동일

상태: `의도된 제한`

현재:

- transcript는 best-effort.
- 실패해도 title/description/tags로 계속 진행.

남은 문제:

- “공개 자막 자체가 없음”과 “일시적인 transcript fetch 실패”를 세분하지 않는다.

후속:

- `transcript_status = available | unavailable | fetch_failed` 같은 상태 필드 추가 후보.

## ST-08 — LLM 응답 candidate가 요청량보다 부족

상태: `해결됨`

대응:

- structured response parse 후 type/length/dedupe/reference-copy 검증.
- usable candidate 최소 수 미달이면 명시적 generation error.
- 옛 template fallback 없음.

## ST-09 — unknown/manual content를 억지 category로 강제

상태: `해결됨`

대응:

- manual input에 YouTube metadata를 발명하지 않음.
- topic rule이 없으면 `Other`/unknown 계열로 degrade.
- YouTube URL은 official category를 우선.

---

# 4. LLM 입력/출력 안전 및 품질 이상

## LLM-01 — transcript/title/history 내부 prompt injection

상태: `해결됨`

위험:

- 영상 제목/설명/자막 또는 과거 댓글에 “이전 지시를 무시하라” 같은 문자열이 있을 수 있음.

대응:

- system instruction에서 GenerationContext 모든 field를 untrusted data로 선언.
- embedded imperative를 instruction으로 따르지 말라고 명시.
- LLM이 video classification을 다시 결정하지 않도록 명시.

## LLM-02 — Historical comment 원문 복제

상태: `해결됨`

대응:

- reference는 소수만 전달.
- exact duplicate 제거.
- `SequenceMatcher >= 0.92` near-copy 제거.
- LLM prompt에도 copy/paraphrase 금지 명시.

한계:

- 문자열 similarity는 의미적 paraphrase를 완전히 검출하지 못함.
- 필요 시 embedding similarity guard를 후속 추가.

## LLM-03 — JSON 형식 불량

상태: `해결됨`

대응:

- JSON parse/코드펜스 정리.
- candidates 배열 계약 검증.
- 실패 시 generation error.

## LLM-04 — unsupported fact / fake personal experience

상태: `운영 위험`

대응:

- prompt에서 supplied context facts only / fake experience 금지.
- deterministic post-validator로 모든 의미적 hallucination을 완전히 검증할 수는 없음.

후속:

- factuality verifier 또는 2단계 lightweight validation 고려.

## LLM-05 — 언어/문체 부자연스러움

상태: `운영 위험`

대응:

- source language, content style, historical length/style profile을 context에 전달.
- 강제 keyword 삽입/깨진 조사 금지.

실제 품질 검증은 real provider E2E와 human review가 필요.

---

# 5. 데이터/랭킹 이상

## DATA-01 — Historical dataset이 social_issues/vlog에 편중

상태: `의도된 제한`

영향:

- Music/Gaming/Sports 등에서는 historical profile coverage가 약하거나 legacy dataset에 기대게 됨.

대응:

- `coverage`, `available_categories`, `matched_categories`를 명시.
- fake multi-category coverage를 주장하지 않음.

## DATA-02 — Reaction ranker의 다장르 OOD(out-of-distribution)

상태: `의도된 제한`

영향:

- LLM generator는 다장르가 가능하지만 reaction score의 검증 데이터는 여전히 social/vlog 중심.

후속:

- 공식 category별 댓글 수집.
- category/topic/style metadata enrichment.
- category-balanced split/retrain.
- category별 metric 보고.

## DATA-03 — `is_top_comment` label이 like_count 기반 상대 라벨

상태: `의도된 제한`

현재 데이터 의미:

- 동일 영상 내 좋아요 상위 15%가 positive label.
- 좋아요는 노출 위치, 게시 시간, 채널 규모 등에 영향받음.

후속:

- comment age, video age, reply/like normalization 재검토.

---

# 6. 시간/인기도 이상

## POP-01 — Hype를 실제 viral velocity로 오해

상태: `의도된 제한`

현재:

- `views_per_hour`, likes/comments per 1K views, views/subscriber의 bounded single-snapshot proxy.
- `hype_basis=single_snapshot_proxy` 저장.

금지 표현:

- 실제 성장 가속도
- 실시간 트렌드 속도
- 정확한 viral probability

## POP-02 — 오래된 영상의 views/hour가 lifetime average라는 한계

상태: `의도된 제한`

- 현재 views/hour는 게시 이후 총 조회수 / 경과시간.
- 최근 몇 시간의 실제 속도가 아님.

후속:

- video_stats_snapshot 시계열 저장 후 Δviews/Δtime 계산.

## POP-03 — subscriber count 비공개/0

상태: `해결됨`

- subscriber가 없거나 숨겨져 있으면 views_per_subscriber를 계산하지 않고 나머지 available component로 proxy 계산.

---

# 7. 외부 의존성 / 운영 상태

## EXT-01 — YouTube API key 없음

상태: `운영 위험`

- URL preview/recommend path 불가.
- manual path는 YouTube API 없이도 context 생성 가능.

## EXT-02 — OpenAI key/model 없음

상태: `운영 위험`

- candidate generation 불가.
- `/health`에서 별도 readiness로 노출.

## EXT-03 — reaction model artifact 없음/불일치

상태: `운영 위험`

- ranking 불가.
- model readiness가 별도 상태로 노출.

## EXT-04 — transcript API cloud/IP failure

상태: `운영 위험`

- transcript는 공식 Data API quota와 별개인 best-effort dependency.
- 실패 시 metadata-only로 degrade.

## EXT-05 — CI에서 실제 OpenAI/YouTube E2E를 실행하지 않음

상태: `의도된 제한`

이유:

- 비용, rate limit, 외부 서비스 변동성, secret 노출 방지.

대신:

- fake provider/session boundary test.
- 실제 배포 전 별도 smoke E2E 필요.

---

# 8. 이번 검증에서 추가할 회귀 테스트

- [ ] ASCII short keyword substring false positive
- [ ] `woman`/`man` orientation false positive
- [ ] YouTube topicDetails → derived topic 반영
- [ ] explicit standalone ASCII keyword 정상 positive
- [ ] additional_context source/context 분리
- [ ] prompt가 GenerationContext를 untrusted data로 취급한다는 계약 유지
- [ ] 기존 regression 전체 green
- [ ] frontend test/lint/build/audit green

---

# 9. Merge Gate

아래가 모두 충족되기 전에는 `main`에 반영하지 않는다.

- [ ] 위 신규 회귀 테스트 추가
- [ ] branch push CI green
- [ ] `main...feature/llm-context-generation` behind 0
- [ ] `LLM_CONTEXT_GENERATION_README.md` 전체 재검토
- [ ] 이 validation README 전체 재검토
- [ ] fixed template reachable path 없음
- [ ] social/vlog가 새 primary taxonomy로 남아 있지 않음
- [ ] 실제 viewer demographic을 주장하는 코드/문서 없음
- [ ] hype를 real velocity로 주장하는 코드/문서 없음
- [ ] PR 생성
- [ ] PR-triggered CI green
- [ ] PR merge
- [ ] merge된 `main`의 candidate path/context README 재확인
- [ ] merge 후 main CI 상태 확인
- [ ] `feature/llm-context-generation` branch 존치 확인

> Feature branch는 merge 후 **삭제하지 않는다.**

---

# 10. Merge 후 기록

Merge 완료 후 아래를 실제 SHA/CI 결과로 채운다.

- feature final head: pending
- PR: pending
- PR CI: pending
- main merge SHA: pending
- main verification: pending
- retained feature branch verification: pending

---

# 11. 최종 검증 방법

마지막 보고 전에 다음 문서를 처음부터 끝까지 다시 읽는다.

1. `LLM_CONTEXT_GENERATION_README.md`
2. `LLM_CONTEXT_GENERATION_VALIDATION_README.md`
3. root `README.md`

그리고 문서의 주장과 실제 `main` 코드가 일치하는지 비교한다. 문서보다 코드가 부족하면 코드를 수정하고, 코드보다 문서가 과장되어 있으면 문서를 수정한다.
