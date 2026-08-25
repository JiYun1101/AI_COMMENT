# MVP Completion Worklog

Branch: `feature/complete-mvp-gaps`  
Base: `main` @ `7bb9590825098255dda156c8d1b74dee6ff0fda4`  
Started: 2026-08-25

This document is the working source of truth for closing incomplete or misleading parts of the AI Comment Recommender MVP. Every implementation tranche updates this file so work can be resumed from Git without chat history.

## Product contract

The completed MVP must accept a supported single-video YouTube URL or manual text, resolve real metadata plus best-effort transcript context, generate enough context/category-aware candidates for the requested count, safety-filter and rank them, persist real analyses/recommendations/feedback, and expose only UI controls that genuinely work.

## Baseline gap checklist

Legend: `[x]` complete, `[~]` backend/partial complete, `[ ]` pending.

### P0 — correctness / product contract

- [x] Replace fixed six-comment generator with context-aware candidate generation.
- [x] Generate enough candidates for requested counts up to 10.
- [~] Category affects backend generation; frontend wiring pending.
- [ ] Clear stale recommendations when input/mode changes.
- [~] Backend supports single-video URLs only; frontend playlist claim still pending removal.

### P1 — usability / context quality

- [ ] Frontend URL validation before submit.
- [x] Best-effort public transcript enrichment with metadata fallback.
- [x] 10-minute in-process YouTube context cache prevents normal preview/recommend duplicate lookup.
- [ ] Preview loading state.
- [ ] Preview retry/manual fallback UI.
- [~] Backend accepts `additional_context`; frontend field pending.
- [~] Feedback persistence API exists; frontend copy/regenerate/feedback actions pending.

### P2 — product shell / misleading mocks

- [~] SQLite persistence + real history APIs implemented; HistoryStrip UI pending.
- [~] Real comments/KPI APIs implemented; dashboard UI pending.
- [ ] Remove/hide dead sidebar destinations.
- [ ] Remove fake comment count, credits and monthly usage.
- [ ] Update root README.
- [~] Backend integration tests added; frontend interaction tests pending.
- [x] Model artifact readiness is explicit through `/health`; missing/incompatible artifacts yield actionable 503 errors.

## Implementation decisions

### Candidate generation

No mandatory paid LLM was introduced. The generator extracts a title/topic/keywords, resolves `social` vs `vlog` when `auto` is used, emits insight/empathy/question/casual/general variants, deduplicates them and expands the pool beyond `top_k`. The existing Safety Filter and reaction ranker stay downstream. A future LLM can replace the generator behind the same interface.

### Transcript enrichment and cache

`youtube-transcript-api==1.2.4` is a best-effort enrichment. Korean/English are preferred and another available transcript is attempted as fallback. Transcript failures are non-fatal. Full transcript text is used only in server-side reference context; the browser receives availability/language metadata. YouTube context is cached by video ID for 10 minutes. Injected test sessions bypass the shared cache.

### Persistence

`src/storage/analysis_store.py` uses SQLite. Default DB is `data/runtime/ai_comment.db`, overridable with `AI_COMMENT_DB_PATH`; runtime DB files are ignored by Git. Analyses store source/video/category/timestamp data. Recommendations store rank/type/text/predicted score/feedback.

### Real data APIs

Implemented:

- `GET /analyses?limit=`
- `GET /analyses/{analysis_id}`
- `GET /comments?query=&type=&category=&min_score=&limit=&offset=`
- `GET /dashboard/summary`
- `POST /recommendations/{id}/feedback`

`POST /recommend` now accepts `post_text?`, `youtube_url?`, `additional_context?`, `category: auto|social|vlog`, and `top_k: 1..10`. It returns an `analysis_id`, resolved category, metadata/transcript availability, persisted recommendation IDs and generation/safety counts.

### Model readiness

Trained model files remain deployment artifacts rather than Git-tracked source. `load_ranker_model()` caches the loaded artifact and raises `ModelNotReadyError` with `python -m src.model.train` guidance when missing/incompatible. `/health` reports degraded status and readiness explicitly.

## Verification log

### 2026-08-25 — branch setup

- [x] Confirmed latest `main`: `7bb9590825098255dda156c8d1b74dee6ff0fda4`.
- [x] Created `feature/complete-mvp-gaps` from that commit.
- [x] Added this worklog before implementation.

### 2026-08-25 — backend completion tranche

Implemented:

- context/category-aware candidate generator and top-10-capable pool
- best-effort public transcript enrichment
- 10-minute YouTube context cache
- SQLite analysis/recommendation/feedback persistence
- real history/comments/dashboard summary APIs
- category/additional-context recommend contract
- explicit model readiness/actionable 503 behavior
- transcript dependency and runtime DB gitignore

Verification executed in an isolated local package using the real new modules and minimal stubs only for unrelated heavy model dependencies:

- `test_candidate_generator.py`
- `test_analysis_store.py`
- `test_youtube_context.py`
- `test_api_integration.py`
- Result: **21 passed**
- Python `py_compile` on changed backend modules: **passed**

The API integration test mocks only model ranking; it exercises FastAPI validation, 10-item recommendation persistence, history, filtering, feedback and KPI summary against temporary SQLite.

## Remaining frontend tranche

- [ ] truthful URL validation/supported-format hint
- [ ] preview loading + retry + manual fallback
- [ ] optional extra context in URL mode
- [ ] category request wiring/resolved-category display
- [ ] stale result clearing
- [ ] copy/regenerate/feedback; persistence is automatic save
- [ ] real HistoryStrip using `/analyses`
- [ ] real dashboard using `/comments` + `/dashboard/summary`
- [ ] functional dashboard filters/pagination/CSV export
- [ ] remove fake credits/counts/usage and dead navigation/search/notification shell
- [ ] frontend Node/TypeScript interaction tests and build/type checks
- [ ] root README update and final verification
- [ ] PR → `main` merge; keep this branch after merge

## Completion rule

Every baseline gap must be implemented/tested or intentionally removed/disabled so the UI never claims unsupported behavior.

**Do not delete `feature/complete-mvp-gaps` after merge.**
