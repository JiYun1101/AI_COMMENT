# Audience Observation and Calibration MVP

This feature implements a bounded, observed-vs-generated feedback loop on top of the existing Expected Audience Reaction UI. It is **not** a calibrated probability model.

1. Existing `/recommend` generates and persists Top-K comments when its model provider is ready. `analysis_id` is the link to generated candidates.
2. `GET /audience/observed?video_id=...&analysis_id=...` independently samples **up to 100 public top-level comments**, sorted by YouTube's relevance. It works without any LLM but requires a YouTube Data API key.
3. A transparent heuristic classifier assigns intent: question/praise/confusion/complaint/purchase/risk/**other**. The result includes distribution and public comment excerpts.
4. Optional comparison uses the **saved Top-K** generated candidates and the observed comment sample. These distributions have different selection mechanisms. Difference in percentage points is a descriptive discrepancy, not accuracy, recall, or a probability forecast.
5. Authenticated `POST /audience/observations` re-fetches data from YouTube and stores a timestamped snapshot in SQLite for future retrieval. It requires server authentication. `GET /audience/observations/{video_id}` and `GET /audience/observations/snapshot/{snapshot_id}` expose the private stored audit trail.

**Data quality:** relevance-sorted, not a uniform random sample. Only the first 100 top-level comments, not all replies or timestamps. Classifier is regex-based and may mislabel sarcasm, negation, and slang. Public comments include text but no author handles. Videos with comments disabled or without API access return explicit errors. Store retention follows the SQLite database life cycle; an ephemeral hosting disk will lose data on redeploy unless persisted externally.

**Next phase:** attach metadata and multimodal scene embeddings to existing video IDs, use per-channel indexed snapshots as historical grounding, and evaluate against held-out real future data. Do not claim Agentic Video Understanding, embedding similarity, or synthetic-audience calibration is implemented in this PR.
