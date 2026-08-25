# MVP Completion Worklog

Branch: `feature/complete-mvp-gaps`  
Base: `main` @ `7bb9590825098255dda156c8d1b74dee6ff0fda4`  
Started: 2026-08-25

This document is the working source of truth for closing the incomplete or misleading parts of the AI Comment Recommender MVP. Every implementation tranche updates this file so the work can be resumed from Git alone without relying on chat history.

## Product contract

The completed MVP must:

1. Accept a supported single-video YouTube URL or manually supplied video text.
2. Resolve real YouTube metadata and best-effort public transcript context.
3. Generate enough context-aware/category-aware candidates for `top_k` rather than ranking a fixed six-comment list.
4. Safety-filter and rank the generated pool with the existing reaction model.
5. Keep UI controls truthful: visible options either affect behavior or are removed/disabled explicitly.
6. Persist analyses/recommendations/feedback so history and dashboard are backed by actual data.
7. Remove fake credits, fake usage/counts, unsupported URL claims, dead navigation, and stale-result states.
8. Provide validation/loading/fallback/result actions needed for normal use.
9. Avoid repeated YouTube metadata calls with a bounded cache.
10. Keep tests/setup/runtime documentation aligned with the implementation.

## Baseline gap checklist

Legend: `[x]` complete, `[~]` backend/partial complete, `[ ]` pending.

### P0 — correctness / product contract

- [x] Replace fixed six-comment generator with deterministic context-aware candidate generation.
- [x] Generate a pool large enough for requested counts up to 10.
- [x] Category affects backend generation and is sent from the frontend; resolved category is shown with results.
- [x] URL/manual/additional-context/category/count/mode changes clear stale recommendation state.
- [x] Backend and frontend now consistently support single-video URLs only; the misleading playlist claim is removed.

### P1 — usability / context quality

- [x] Frontend validates the same supported single-video URL shapes before enabling submit.
- [x] Best-effort public transcript/caption enrichment; failures fall back to metadata without failing the request.
- [x] 10-minute in-process YouTube context cache prevents preview + recommend from immediately repeating Data API calls.
- [x] Preview has an explicit loading state.
- [x] Preview errors expose retry and switch-to-manual fallback actions.
- [x] URL mode exposes optional `additional_context` and sends it to the backend.
- [x] Result cards support copy, regenerate, and persisted useful/not-useful feedback. Successful recommendations are automatically persisted.

### P2 — product shell / misleading mocks

- [x] HistoryStrip uses persisted `/analyses` data and can restore a previous analysis.
- [x] Dashboard uses real `/comments` and `/dashboard/summary` data with working filters, pagination, selection, and CSV export.
- [x] Sidebar shows only real MVP destinations: recommendation and dashboard.
- [x] Fake comment counts, credits, usage, brand controls, search/notification shell and the mock generation drawer are removed.
- [x] Root README documents the real URL/transcript/cache/persistence/model-readiness/runtime behavior and limitations.
- [x] Backend integration tests and frontend URL-validation regression tests are added; clean-environment test/lint/build runs in GitHub Actions CI.
- [x] Model artifact readiness is explicit through `/health`; missing/incompatible artifacts return actionable 503 errors rather than an opaque crash.

## Implementation decisions

### Candidate generation

The MVP remains provider-free: no mandatory paid LLM was introduced. `candidate_generator.py` now extracts a title/topic/keywords, resolves `social` vs `vlog` when `auto` is used, emits insight/empathy/question/casual/general variants, deduplicates them, and expands the pool past `top_k`. The existing Safety Filter and trained reaction ranker remain downstream.

A future LLM can replace this generator behind the same interface without changing the ranker contract.

### Transcript enrichment

`youtube-transcript-api==1.2.4` is used as best-effort enrichment. Korean/English are preferred; another available transcript is attempted as fallback. Transcript failures are intentionally non-fatal. Full transcript text is used only inside reference context and is not returned to the browser; the browser receives only availability/language metadata.

### YouTube cache

Real YouTube context is cached in-process by video ID for 10 minutes. Custom/injected sessions bypass the shared cache so tests remain deterministic. This removes the normal preview → recommend duplicate lookup without trusting browser-supplied metadata.

### Persistence

`src/storage/analysis_store.py` uses SQLite from the Python standard library. Default DB: `data/runtime/ai_comment.db`, overridable with `AI_COMMENT_DB_PATH`. Runtime DB files are ignored by Git.

Stored entities:

- analyses: source type/text, YouTube identity/display metadata, resolved category, timestamp
- recommendations: rank/type/text/predicted score/feedback/timestamp

### Dashboard/history data API

Implemented backend routes:

- `GET /analyses?limit=`
- `GET /analyses/{analysis_id}`
- `GET /comments?query=&type=&category=&min_score=&limit=&offset=`
- `GET /dashboard/summary`
- `POST /recommendations/{id}/feedback`

### Model readiness

Trained model files remain deployment artifacts rather than Git-tracked source. `load_ranker_model()` now caches the loaded artifact and raises `ModelNotReadyError` with `python -m src.model.train` guidance when the artifact is missing or incompatible. `/health` reports degraded status and model readiness explicitly.

## API contract after backend tranche

`POST /recommend` accepts:

- `post_text?`
- `youtube_url?`
- `additional_context?`
- `category`: `auto | social | vlog`
- `top_k`: 1–10

It returns:

- `analysis_id`
- resolved reference excerpt
- `resolved_category`
- `youtube_context` (metadata + transcript availability, not transcript body)
- persisted recommendations containing stable recommendation IDs
- candidate/safety generation counts

## Verification log

### 2026-08-25 — branch setup

- [x] Confirmed latest `main`: `7bb9590825098255dda156c8d1b74dee6ff0fda4`.
- [x] Created `feature/complete-mvp-gaps` from that exact commit.
- [x] Added this worklog before implementation changes.

### 2026-08-25 — backend completion tranche

Implemented locally and prepared for branch commit:

- context-aware/category-aware candidate generator
- variable candidate pool sufficient for top 10
- best-effort transcript enrichment
- 10-minute YouTube context cache
- SQLite analysis/recommendation/feedback persistence
- real history/comments/dashboard summary APIs
- category/additional-context recommend contract
- explicit model readiness and actionable 503 behavior
- `youtube-transcript-api==1.2.4` dependency
- runtime DB gitignore rule

Verification executed in an isolated local package using real new modules and minimal stubs only for unrelated heavy model dependencies:

- `test_candidate_generator.py`
- `test_analysis_store.py`
- `test_youtube_context.py`
- `test_api_integration.py`
- Result: **21 passed**
- Python `py_compile` on changed backend modules: **passed**

The API integration test mocks only the model ranking function; it exercises FastAPI request validation, recommendation persistence, 10-item responses, history, comment filtering, feedback and KPI summary end-to-end against a temporary SQLite DB.

## Frontend completion tranche

Implemented:

- [x] Truthful single-video URL validation and supported-format hint
- [x] preview loading + retry + manual fallback
- [x] optional additional context in URL mode
- [x] category request wiring and resolved-category display
- [x] stale-result invalidation when inputs/options change
- [x] copy/regenerate/feedback actions; recommendation persistence is automatic
- [x] real HistoryStrip using `/analyses` and analysis restore
- [x] real dashboard using `/comments` + `/dashboard/summary`
- [x] functional dashboard filters/pagination/selection/CSV export
- [x] removed fake credits/counts/usage, fake brand/tone drawer, dead navigation/search/notification shell
- [x] frontend URL-validation regression test
- [x] root README update
- [x] CI workflow added for clean-environment backend pytest + frontend test/lint/build

### 2026-08-25 — frontend local verification

- TypeScript `transpileModule` syntax diagnostics over **14 changed TS/TSX files: PASS**.
- `npm test`: **2/2 passed** (supported single-video forms; playlist/other-host/malformed rejection).
- Local full `npm ci` / lint / Vite build could not be executed because repository `node_modules` are not installed in the execution container. This is not treated as a green build; the new GitHub Actions workflow performs those checks in a clean dependency environment.
- `frontend/.test-dist/` is ignored because the zero-dependency test script compiles the URL utility there before Node's built-in test runner executes.

### 2026-08-25 — finalization resumed

- [x] Re-read branch HEAD and this worklog before resuming.
- [~] Frontend/docs/CI tranche is prepared locally and is being committed next.
- [ ] GitHub Actions results will be recorded here; failures will be fixed before merge.
- [ ] After CI, final diff/README gap audit will be run before PR merge.

### 2026-08-25 — CI attempt 1

- Frontend dependency install: **passed**.
- Frontend `npm test`: **failed before executing tests** with TypeScript 6 `TS5112` because a source file was passed directly while `tsconfig.json` exists.
- Root cause: the zero-dependency URL test compile command was compatible with the local global TypeScript used during scratch verification but not the repository TypeScript 6 compiler.
- Fix plan: add a dedicated `frontend/tsconfig.test.json` and compile with `tsc -p tsconfig.test.json`; then re-run CI.
- Backend job was still running when this failure was recorded.

### Remaining finalization

- [ ] Commit frontend/docs/CI tranche to `feature/complete-mvp-gaps`.
- [ ] Confirm GitHub Actions backend/frontend jobs.
- [ ] Compare final branch against current `main`.
- [ ] Open PR and merge to `main`.
- [ ] Verify `main` merge commit and verify `feature/complete-mvp-gaps` still exists after merge.

## Completion rule

The branch is complete only when every baseline gap is either implemented and tested, or intentionally removed/disabled with its rationale documented here so the UI never claims unsupported behavior.

**Do not delete `feature/complete-mvp-gaps` after merge.**
