# MVP Completion Worklog

Branch: `feature/complete-mvp-gaps`  
Base: `main` @ `7bb9590825098255dda156c8d1b74dee6ff0fda4`  
Started: 2026-08-25

This file is the durable source of truth for closing the incomplete or misleading parts of the AI Comment Recommender MVP. Implementation decisions, failures, fixes, tests, and final verification are recorded here so the work is recoverable from Git alone.

## Completion contract

The completed MVP must:

1. Accept a supported single-video YouTube URL or manually supplied video text.
2. Resolve real YouTube metadata and best-effort public transcript context.
3. Generate enough context-aware/category-aware candidates for `top_k`, instead of ranking a fixed six-comment list.
4. Safety-filter and rank generated candidates with the existing reaction model.
5. Ensure every visible option affects behavior, or remove it.
6. Persist analyses, recommendations, and feedback so history/dashboard are real.
7. Remove fake credits, fake usage/counts, unsupported URL claims, dead navigation, and stale-result states.
8. Provide validation, loading, fallback, copy/regenerate/feedback actions needed for normal use.
9. Avoid duplicate preview/recommend YouTube metadata work with bounded caching.
10. Keep tests, CI, runtime behavior, and README documentation aligned.

## Gap checklist

### P0 — correctness / product contract

- [x] Fixed six-comment generator replaced by deterministic context-aware candidate generation.
- [x] Candidate pool is large enough for requested counts up to 10.
- [x] `auto/social/vlog` category changes backend candidate generation and is sent by the frontend.
- [x] URL/manual/additional-context/category/count/mode changes invalidate stale results.
- [x] Frontend/backend consistently support single-video URLs only; misleading playlist support removed.

### P1 — usability / context quality

- [x] Frontend validates the same single-video URL forms as backend before enabling submit.
- [x] Best-effort public transcript enrichment; transcript failure falls back to metadata without failing the request.
- [x] 10-minute in-process YouTube context cache avoids normal preview → recommend duplicate lookup.
- [x] Preview loading state, retry, and switch-to-manual fallback implemented.
- [x] URL mode supports optional `additional_context`.
- [x] Result cards support copy, regenerate, persisted useful/not-useful feedback, and automatic analysis persistence.

### P2 — misleading shell / mock removal

- [x] Recent-history strip is backed by persisted `/analyses` data and restores an analysis.
- [x] Dashboard is backed by `/comments` and `/dashboard/summary` with real filters, pagination, selection, and CSV export.
- [x] Sidebar exposes only implemented MVP destinations.
- [x] Fake comment counts, credits, usage, brand/tone controls, search/notification shell, and mock generation drawer removed.
- [x] Root README updated to real URL/transcript/cache/persistence/model-readiness behavior.
- [x] Backend integration/regression tests and frontend URL-validation tests added.
- [x] Model artifact readiness is explicit through `/health`; missing/incompatible artifacts return actionable 503 errors.

## Implementation decisions

### Candidate generation

The MVP remains provider-free: no mandatory paid LLM was introduced. `candidate_generator.py` extracts title/topic/keywords, resolves `social` vs `vlog` when `auto` is selected, emits insight/empathy/question/casual/general variants, deduplicates the pool, and expands it beyond `top_k`. The existing Safety Filter and trained reaction ranker remain downstream.

A future LLM can replace the generator behind the same interface without changing the ranking contract.

### YouTube context and transcript

`youtube-transcript-api==1.2.4` provides best-effort public caption enrichment. Korean/English are preferred and another available transcript is attempted as fallback. Transcript failures are non-fatal. Transcript text is used in ranking reference context but not returned to the browser; the browser receives only availability/language metadata.

Real YouTube context is cached in-process by video ID for 10 minutes. Injected sessions bypass shared cache so tests remain deterministic.

### Persistence

`src/storage/analysis_store.py` uses SQLite. Default database: `data/runtime/ai_comment.db`, overridable by `AI_COMMENT_DB_PATH`; runtime DBs are gitignored.

Stored data:

- analyses: source type/text, YouTube identity/display metadata, resolved category, timestamp
- recommendations: rank/type/text/predicted score/feedback/timestamp

Implemented data APIs:

- `GET /analyses?limit=`
- `GET /analyses/{analysis_id}`
- `GET /comments?query=&type=&category=&min_score=&limit=&offset=`
- `GET /dashboard/summary`
- `POST /recommendations/{id}/feedback`

### Model readiness

Model files remain deployment artifacts rather than Git-tracked source. `load_ranker_model()` caches the loaded artifact and raises `ModelNotReadyError` with `python -m src.model.train` guidance when the artifact is missing or incompatible. `/health` reports `degraded` instead of allowing an opaque recommendation crash.

## Recommendation API contract

`POST /recommend` accepts:

- `post_text?`
- `youtube_url?`
- `additional_context?`
- `category: auto | social | vlog`
- `top_k: 1..10`

It returns:

- `analysis_id`
- reference-text excerpt
- `resolved_category`
- YouTube metadata + transcript availability metadata
- persisted recommendations with stable IDs
- candidate/safety generation counts

## Change / verification log

### 2026-08-25 — branch setup

- [x] Confirmed `main` at `7bb9590825098255dda156c8d1b74dee6ff0fda4`.
- [x] Created `feature/complete-mvp-gaps` from that exact commit.
- [x] Added this worklog before implementation changes.

### Backend tranche

Implemented context/category candidate generation, variable candidate pool, transcript enrichment, YouTube cache, SQLite persistence, history/dashboard APIs, category/additional-context contract, and explicit model readiness.

Initial isolated verification:

- `test_candidate_generator.py`
- `test_analysis_store.py`
- `test_youtube_context.py`
- `test_api_integration.py`
- **21 passed**
- changed backend modules `py_compile`: **passed**

### Frontend tranche

Implemented truthful URL validation, preview loading/retry/fallback, additional context, category wiring, stale-result invalidation, copy/regenerate/feedback, real history, real dashboard/filter/pagination/CSV, shell cleanup, root README update, and CI.

Initial local verification:

- syntax diagnostics across 14 changed TS/TSX files: **passed**
- frontend URL validation: **2/2 passed**

### CI attempt 1

Frontend clean runner reached dependency install, then `npm test` failed before tests with TypeScript 6 `TS5112`: direct source compilation conflicted with repository `tsconfig.json`.

Fix: added dedicated `frontend/tsconfig.test.json` and changed the test command to `tsc -p tsconfig.test.json`.

Backend clean runner separately exposed a portability problem: all tests failed collection with `ModuleNotFoundError: No module named 'src'`.

### CI attempt 2

Dedicated frontend test config was read, but TypeScript 6 raised `TS5011` because `rootDir` was not explicit.

Fix: set `rootDir: src/utils`, making the compiled test target deterministic at `.test-dist/youtube.js`.

### Backend clean-checkout portability fix

The backend collection failure was caused by implicit local import-path behavior. Added repository `pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

This fixes the documented `pytest -q` command itself rather than adding a CI-only `PYTHONPATH` workaround.

### Clean CI after functional fixes

GitHub Actions run `32830244389` became fully green:

- backend: **37 passed, 1 warning in 4.75s**
- frontend URL tests: **2/2 passed**
- frontend lint: **0 warnings, 0 errors**
- frontend production build: **passed**

The Python warning is an upstream `StarletteDeprecationWarning` emitted by FastAPI/Starlette test-client internals about `httpx`; it does not indicate an application test failure and is recorded rather than hidden.

### Final source audit

- [x] Compared frontend request/response types against FastAPI and SQLite response shapes.
- [x] Re-searched source for `mock`, `seed`, unsupported playlist claims, fake credits/counts/usage, and dead-button patterns.
- [x] Remaining `mock`/`fake` mentions are test doubles or documentation explaining removed mocks.
- [x] Playlist wording explicitly states unsupported.
- [x] Visible revised MVP buttons have actual handlers or submit behavior.
- [x] `main` remained at the branch base during the audit.

### Final dependency / CI hygiene audit

The full `npm ci` dependency tree reports one high-severity advisory, so production dependencies were separately audited instead of assuming it was runtime-relevant.

CI was hardened to:

- `actions/checkout@v7`
- `actions/setup-python@v7`
- `actions/setup-node@v7`
- `npm audit --omit=dev --audit-level=high`

GitHub Actions run `32830699389` completed green:

- frontend dependency install: **passed**
- production dependency audit: **0 vulnerabilities**
- frontend URL tests: **2/2 passed**
- frontend lint: **0 warnings, 0 errors**
- frontend production build: **passed**
- backend dependency install: **passed**
- backend `pytest -q`: **passed**

Therefore the one high advisory printed by the unfiltered npm install is confined to dev/build tooling, not the shipped production dependency set. The production audit remains a CI gate for high-severity runtime advisories.

### Final branch comparison and PR validation

Before PR creation, the branch comparison was:

- status vs `main`: **ahead**
- ahead by: **14 commits**
- behind by: **0 commits**
- merge base: `7bb9590825098255dda156c8d1b74dee6ff0fda4`

PR #4, `Complete MVP gaps and replace misleading mocks`, was opened from `feature/complete-mvp-gaps` to `main`. GitHub recomputed the PR as **mergeable**.

PR-triggered CI run `32831018588` on code/worklog head `19c56ac2a9027742f9f5f66efa5b8f60ac19335b` completed green:

- frontend: dependency install, production dependency audit, 2 URL tests, lint, and production build all **passed**
- backend: dependency install and full pytest suite **passed**

This final README-only commit records that validation; it intentionally uses `[skip ci]` because it changes no executable source, dependency, workflow, or test code.

## Remaining finalization

- [x] All baseline product gaps implemented or intentionally removed.
- [x] Clean backend tests green.
- [x] Clean frontend tests/lint/build green.
- [x] Production dependency audit green.
- [x] CI action-runtime deprecation cleaned up by moving to v7 actions.
- [x] Final branch audit completed with `behind_by = 0` before PR creation.
- [x] PR #4 created, mergeable, and PR-triggered CI green on the executable-code head.
- [ ] Merge PR #4 to `main` using the final feature-head SHA guard.
- [ ] Verify merged `main` commit and verify `feature/complete-mvp-gaps` still exists.

## Completion rule

The work is complete only when every baseline gap is implemented/tested or intentionally removed with rationale documented here, final CI is green, the PR is merged to `main`, and `feature/complete-mvp-gaps` remains available after merge.

**Do not delete `feature/complete-mvp-gaps` after merge.**
