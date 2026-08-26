# LLM Context Generation Migration

Branch: `feature/llm-context-generation`
Base: `main` @ `bdb50bc8002bdd65fa12a05f2766e5220ccd915d`

## Goal

Replace the fixed keyword/template candidate generator with an LLM candidate generator **without delegating analysis to the LLM**.

The intended contract is:

1. Scripts/API code collect objective YouTube metadata and transcript context.
2. Deterministic classifiers derive category, format, temporal, audience-orientation, and popularity features.
3. Historical-comment code selects and summarizes relevant previously collected comments.
4. Only the final creative step is delegated to an LLM.
5. Existing safety filtering and reaction-score ranking remain downstream guardrails.

In short: **analysis is code; creation is LLM**.

---

## Pre-implementation audit

### Existing behavior that must remain

- Single-video YouTube URL validation and preview.
- Title/description/channel/statistics/transcript collection.
- Manual-text recommendation path.
- Safety filtering before ranking.
- Reaction prediction/ranking and Top-K selection.
- SQLite analysis/history/dashboard/feedback persistence.
- Clear readiness failures instead of silent fallback to fake results.

### Existing behavior that must be replaced

- `social` / `vlog` keyword-only category inference as the primary taxonomy.
- Fixed Korean sentence templates in `candidate_generator.py`.
- Deterministic filler variants such as `(1)`, `(2)`.
- Treating a generated candidate type mix as permanently hard-coded.

### Design risks checked before coding

- YouTube's official category and our own content labels are different concepts and must be stored separately.
- Public YouTube APIs do **not** expose the actual age/gender distribution of arbitrary viewers. We must only derive *content target/orientation* from explicit content signals and official flags; never infer private attributes of individual viewers/commenters.
- `madeForKids` and age-restriction are strong official signals; other age/orientation labels are heuristics and must be marked as such.
- Hype/virality must be derived from age-normalized engagement signals, not absolute views alone.
- A single current API snapshot cannot measure true velocity/acceleration. The first implementation can compute snapshot-normalized proxies and must explicitly distinguish them from multi-snapshot velocity.
- Existing historical datasets cover only `social_issues` and `vlog`; retrieval can use them, but ranker confidence must not be presented as equally validated for Music/Gaming/Sports/etc.
- LLM output must be strict JSON-like structured data, deduplicated, length-bounded, and safety-filtered.
- LLM failures must return an actionable readiness/service error; no hidden fixed-template fallback, because that would violate the migration goal.
- Historical comments are references for style/statistics, not text to copy. Exact/near duplicates must be rejected before ranking.
- Manual input has less metadata than YouTube input; the context builder must degrade gracefully rather than invent fields.

---

## Target pipeline

```text
YouTube URL / manual text
        |
        v
Context collection (script/code)
        |
        +-- official YouTube category/topic/tags
        +-- title/description/transcript
        +-- format/live/duration/language
        +-- official audience flags
        +-- publication time / freshness
        +-- views/likes/comments/subscribers
        |
        v
Deterministic context classifier
        |
        +-- official_category
        +-- topics[]
        +-- content_styles[]
        +-- format
        +-- target_age[] (heuristic, content-level only)
        +-- audience_orientation (heuristic, content-level only)
        +-- freshness
        +-- engagement/hype proxy
        |
        v
Historical comment retriever
        |
        +-- matched examples
        +-- length/style/question/casual statistics
        +-- top-comment examples
        |
        v
GenerationContext JSON
        |
        v
LLM candidate generation ONLY
        |
        v
Deduplication / validation
        |
        v
Safety filter
        |
        v
Existing reaction ranker
        |
        v
Top-K + persistence
```

---

## GenerationContext contract

The LLM should receive a compact structured object rather than raw application state.

```json
{
  "source": {
    "type": "youtube",
    "title": "...",
    "description": "...",
    "transcript_excerpt": "...",
    "language": "ko"
  },
  "youtube": {
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
    "orientation_confidence": 0.8
  },
  "temporal": {
    "published_at": "...",
    "age_hours": 12.4,
    "freshness": "breaking",
    "weekday": "wednesday",
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
    "keywords": ["AI", "개발자", "커리어"],
    "content_styles": ["educational", "discussion"]
  },
  "historical_comments": {
    "matched_count": 80,
    "preferred_length": [20, 70],
    "question_ratio": 0.18,
    "casual_ratio": 0.26,
    "reference_examples": ["..."]
  }
}
```

The LLM response contract is deliberately smaller:

```json
{
  "candidates": [
    {"type": "insight", "comment": "..."},
    {"type": "question", "comment": "..."}
  ]
}
```

Allowed types remain `insight`, `empathy`, `question`, `casual`, and `general` so downstream UI/ranking remains compatible.

---

## Taxonomy

### 1. Official YouTube category

Primary category should come from YouTube `snippet.categoryId`. A cached category-name mapping should preserve the platform-defined category independently from our own labels.

Examples include Music, Gaming, Sports, News & Politics, Entertainment, Comedy, Education, Science & Technology, Howto & Style, Travel & Events, People & Blogs, Film & Animation, Autos & Vehicles, Pets & Animals, etc.

Do not collapse these back into only `social` / `vlog`.

### 2. Topic labels

Use deterministic keyword/rule classification over title + description + tags + transcript, augmented by YouTube `topicDetails` when available.

Initial topic vocabulary should be broad and multi-label, e.g.:

- AI / software / hardware / mobile / science
- career / education / finance / economy / politics / law
- beauty / fashion / food / travel / fitness / health / relationships
- music / film / animation / gaming / sports / animals / autos
- lifestyle / daily-life / shopping / review / tutorial / news

Unknown content remains `other`; never force it into a wrong binary class.

### 3. Content style

Multi-label classification from textual cues:

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

### 4. Format

Derived from URL/status/duration:

- `short`
- `standard`
- `long_form`

Broadcast:

- `uploaded`
- `live`
- `upcoming`
- `archived_live`

### 5. Audience descriptors

Official:

- `made_for_kids`
- `age_restricted`

Content-level heuristics only:

- target age: `children`, `teens`, `young_adult`, `adult`, `mature`, `broad`, `unknown`
- orientation: `general`, `female_oriented`, `male_oriented`, `mixed`, `unknown`

These describe the **content's explicit target/orientation**, not an inferred viewer identity.

### 6. Freshness

Derived from `publishedAt`:

- breaking: <24 h
- fresh: 1–3 d
- recent: 3–7 d
- current: 7–30 d
- established: 1–6 mo
- old: 6–24 mo
- evergreen: >24 mo

Also preserve weekday/month/season so the generator can avoid temporally impossible phrases.

### 7. Popularity / hype

Single-snapshot proxies:

- views_per_hour
- likes_per_1000_views
- comments_per_1000_views
- views_per_subscriber

Normalize these into a bounded `hype_score` and label (`normal`, `active`, `hot`, `viral`). The first implementation must label its basis `single_snapshot_proxy`.

Future enhancement: persist repeated snapshots to calculate true view/like/comment velocity and acceleration.

---

## Historical comment retrieval

Current repository data contains two datasets:

- `social_issues_comments.csv`
- `vlog_comments.csv`

The retriever must:

1. Load available datasets lazily and tolerate missing files.
2. Select examples using keyword overlap and available category compatibility; do not pretend the two datasets cover every official YouTube category.
3. Prefer `is_top_comment=1` examples when available.
4. Produce summary statistics (length range, question ratio, casual marker ratio) in code.
5. Send only a small number of representative references to the LLM.
6. Reject generated exact/near duplicates of reference comments.

The historical dataset influences **generation style and references**, while the existing ML ranker continues to score candidates afterward.

---

## LLM provider contract

Initial implementation uses the OpenAI Responses API through an isolated client module and environment configuration:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (explicitly configurable; do not hard-code business logic to one model)
- optional `OPENAI_BASE_URL`

Only the LLM client module knows the provider protocol. Context building, retrieval, validation, safety, ranking, persistence, and API schemas remain provider-independent.

Readiness behavior:

- Missing API key/model -> clear `LLMNotReadyError` -> HTTP 503.
- Network/provider failure -> `LLMGenerationError` -> HTTP 502/503 as appropriate.
- Invalid/non-JSON response -> generation error; do not silently substitute fixed templates.

---

## LLM prompt requirements

The prompt must explicitly require:

- Produce natural comments that could realistically be posted under this specific video.
- Use provided context; do not invent facts not supported by the context.
- Use historical examples only as style/reference signals; never copy them.
- Match language and temporal context.
- Avoid forced keyword insertion and broken Korean particles.
- Generate diverse types and phrasings.
- Do not include numbering markers such as `(1)` in comment text.
- Return the requested candidate count or more, up to a bounded maximum.
- Return structured JSON only.

---

## Implementation checklist

### Context collection
- [ ] Expand `YouTubeVideoContext` with official category/tags/language/likes/comments/kids/age/topic/live metadata.
- [ ] Preserve existing preview fields for frontend compatibility.
- [ ] Add category-name resolution/cache without making preview fragile.

### Deterministic context
- [ ] Add reusable `GenerationContext` builder.
- [ ] Add topic/content-style classifier.
- [ ] Add format/broadcast classifier.
- [ ] Add freshness/date features.
- [ ] Add audience content-orientation heuristics with confidence.
- [ ] Add popularity/hype proxy and explicit basis.
- [ ] Support manual-text context with unknown/null metadata.

### Historical comments
- [ ] Add lazy historical dataset loader/retriever.
- [ ] Add code-derived profile statistics.
- [ ] Limit examples and remove unsafe/empty records.

### LLM generation
- [ ] Isolate provider client.
- [ ] Replace fixed templates with LLM candidates.
- [ ] Validate allowed types, length, duplicates, and near-copy references.
- [ ] Do not hide LLM configuration/provider failures.

### Existing pipeline
- [ ] Safety filter remains before scoring.
- [ ] Existing reaction ranker remains after LLM generation.
- [ ] API returns context/generation metadata without breaking existing fields.
- [ ] Health reports LLM readiness separately from ranker readiness.

### Frontend
- [ ] Preserve existing flow.
- [ ] Replace binary category selector with `auto` + official/category-aware behavior or remove misleading manual binary choices.
- [ ] Display useful resolved context (official category / freshness / format) rather than only social/vlog.

### Tests
- [ ] Context classifier tests.
- [ ] Historical retrieval tests.
- [ ] LLM response validation tests with fake provider response.
- [ ] YouTube enriched-context tests.
- [ ] API integration test with LLM/ranker mocked at provider boundary.
- [ ] Existing regression tests.
- [ ] Frontend test/lint/build.
- [ ] Final branch-vs-main audit.
- [ ] PR CI success before merge.
- [ ] Verify `main` after merge.
- [ ] Verify `feature/llm-context-generation` still exists after merge.

---

## Post-implementation audit (fill after coding)

Pending. This section must be updated after implementation with:

- actual files changed;
- any deviations from this design;
- tests and CI results;
- limitations that remain;
- confirmation that no fixed-template candidate path is reachable;
- merge and retained-branch verification.
