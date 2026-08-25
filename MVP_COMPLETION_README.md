# MVP Completion Worklog

Branch: `feature/complete-mvp-gaps`
Base: `main` @ `7bb9590825098255dda156c8d1b74dee6ff0fda4`
Started: 2026-08-25

This document is the working source of truth for closing the incomplete or misleading parts of the current AI Comment Recommender MVP. Every implementation step in this branch should update this file so that the branch can be resumed from the repository without relying on chat history.

## Product contract

The completed MVP should do the following:

1. Accept a supported YouTube video URL or manually supplied video text.
2. Resolve real video context from YouTube and optionally enrich it with a transcript when publicly available.
3. Generate enough context-aware, category-aware comment candidates for the requested `top_k` instead of reusing a fixed six-comment list.
4. Safety-filter and rank those candidates with the existing reaction model.
5. Make UI options truthful: every visible category/count/action either affects the request or is explicitly unavailable/removed.
6. Persist recommendation analyses so recent history and the dashboard are backed by actual data rather than seed/mock data.
7. Avoid misleading dead navigation, fake credits, fake usage counts, unsupported URL claims, and stale results.
8. Provide frontend validation/loading/fallback states and useful result actions.
9. Avoid unnecessary repeated YouTube lookups with a bounded cache.
10. Cover the critical backend flow with tests and keep project setup/documentation aligned with actual behavior.

## Baseline gaps found on `main`

### P0 — correctness / product-contract gaps

- [ ] Candidate generation ignores input context and always returns the same six comments.
- [ ] UI allows 3–10 recommendations but backend can return at most six candidates.
- [ ] Category selector changes local UI state only; category is not sent to or used by the backend.
- [ ] Changing URL/manual input/mode can leave stale recommendation results visible.
- [ ] UI advertises playlist URLs although backend does not support playlist lookup.

### P1 — usability / context-quality gaps

- [ ] URL validity is checked too late; any non-empty URL enables submission.
- [ ] Public transcript/caption context is not attempted.
- [ ] Preview and recommendation independently re-fetch the same YouTube video/channel metadata.
- [ ] Preview lookup has no loading indicator.
- [ ] YouTube lookup failures do not offer retry/manual-input fallback.
- [ ] URL mode has no optional user-supplied context field to supplement sparse metadata.
- [ ] Result cards have no copy/regenerate/save/feedback actions.

### P2 — misleading mock / incomplete product-shell gaps

- [ ] Recent-analysis cards are hard-coded mock data and do not open real analyses.
- [ ] Dashboard KPIs/table/filter controls use seed data instead of backend data.
- [ ] Most sidebar destinations are dead buttons with no route.
- [ ] Comment count, credit balance, and monthly usage are hard-coded decorative values.
- [ ] Root README still says YouTube preview is mocked even though it is now real.
- [ ] Critical `/recommend` integration path and frontend interactions lack dedicated tests.
- [ ] Model artifact bootstrapping/deployment expectations are not explicit enough for a fresh checkout.

## Implementation decisions

These decisions keep the branch useful without introducing a mandatory paid LLM dependency.

### Candidate generation

Implement a deterministic context-aware generator that:

- extracts salient title/description/transcript terms,
- uses category-specific candidate families,
- creates more candidates than `top_k`,
- includes insight, empathy, question, casual, and general variants,
- deduplicates candidates,
- remains fully testable/offline,
- preserves the existing safety-filter + model-ranking pipeline.

A future LLM provider may replace this generator behind the same interface, but this branch must not require one to satisfy the MVP contract.

### Transcript enrichment

Attempt public transcript retrieval as best-effort enrichment. Failure to retrieve captions must never block preview or recommendation; title/channel/description remain the fallback reference context. The UI/API should make transcript availability explicit rather than pretending it is guaranteed.

### Persistence

Use a lightweight local SQLite store built on Python's standard library. It will persist recommendation analyses and recommendation rows without requiring an external database. Runtime DB files must remain ignored by Git.

### Dashboard/history

Back both from the same persisted analyses. Filters should affect real data. Features that are not part of this MVP (organization/team admin, brand management, full export center, etc.) should be hidden or clearly disabled rather than rendered as fake working controls.

### Credits

Remove fake credit accounting from the current UI until there is a real billing/usage source. Do not replace one mock with another.

### Model artifact readiness

The codebase currently ignores trained `models/*.joblib`/`*.pkl` artifacts. This branch will make startup/readiness behavior and setup instructions explicit, and expose a readiness endpoint/state where practical. It will not commit a large trained artifact or fabricate one.

## Target API additions/changes

Planned shape (may be refined during implementation):

- `POST /recommend`
  - input: `post_text?`, `youtube_url?`, `additional_context?`, `category`, `top_k`
  - output: recommendations + resolved context + persisted `analysis_id`
- `GET /videos/preview?url=...`
  - cached metadata, transcript availability summary
- `GET /analyses?limit=...`
  - real recent analyses
- `GET /analyses/{analysis_id}`
  - analysis detail
- `GET /comments`
  - persisted recommendation rows with filters
- `GET /dashboard/summary`
  - real KPI summary derived from persisted analyses
- `POST /recommendations/{id}/feedback`
  - lightweight useful/not-useful feedback persistence
- `GET /health` / readiness information

## Target frontend behavior

- Valid YouTube URL required before URL-mode submit is enabled.
- Preview shows an explicit loading state and error state with retry + switch-to-manual actions.
- Input/mode changes clear stale results.
- URL mode includes optional extra context.
- Category selection is included in requests and affects generation.
- Request count is always satisfiable when enough safe candidates remain; response count is shown truthfully otherwise.
- Result cards support copy and useful/not-useful feedback; rerun uses current input/options.
- Recent analyses and dashboard use backend data.
- Unsupported/dead product-shell controls are removed or disabled with honest labeling.
- Fake credits/usage/counts are removed.

## Verification plan

Backend:

- unit tests for context-aware candidate generation
- URL parsing/YouTube context regression tests
- API integration tests with YouTube/model dependencies mocked
- persistence/filter/KPI tests
- safety-filter regression suite
- Python compile checks

Frontend:

- TypeScript build/typecheck
- lint where dependencies are available
- interaction logic review for validation/loading/stale-result behavior

Environment constraints encountered in prior work:

- GitHub connector is available for repository reads/writes.
- The execution container may not have outbound GitHub/network access and may not have repo `node_modules` or `sentence-transformers` preinstalled.
- When full runtime tests are impossible in the container, this document must record exactly what was and was not run; no green status should be implied without execution.

## Work log

### 2026-08-25 — branch setup

- [x] Confirmed latest `main` head: `7bb9590825098255dda156c8d1b74dee6ff0fda4`.
- [x] Created `feature/complete-mvp-gaps` from that exact commit.
- [x] Added this worklog before implementation changes.
- [ ] Inspect remaining backend/frontend files needed for implementation.
- [ ] Implement backend completion work.
- [ ] Implement frontend completion work.
- [ ] Add/update tests.
- [ ] Update root README/setup docs.
- [ ] Run available verification.
- [ ] Open PR, merge to `main`, and keep this feature branch after merge as requested.

## Final completion checklist

This branch is complete only when every baseline gap above is either:

1. implemented and tested, or
2. intentionally removed/disabled with an explicit rationale recorded here so the UI no longer misrepresents support.

Do not delete `feature/complete-mvp-gaps` after merge.
