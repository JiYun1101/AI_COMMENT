# AI_COMMENT — staged roadmap implementation (2026-10-14)

## State: code in a feature branch, NOT deployed

The current Render service `ai-comment-api-lite` runs on a Free instance.
Its SQLite DB is ephemeral. An auto-deploy from main can erase its data.
**Do not merge this branch until the surviving data is exported or the user
has explicitly accepted that risk.** Do not treat a GitHub PR, an API response,
or browser localStorage as a durable database.

## Phase 0 implemented in this branch

1. Frontend retains model `predicted_score`, comment type, last known likes /
   replies, and 24h / 7d milestones in its existing local receipt store.
   They are labeled as historical snapshots, not fresh readings.
2. `GET /my-comments/export`: server-authenticated + verified personal
   YouTube channel; returns <=500 own comment rows with metrics and
   prediction information in portable backup format, never another channel's
   records. No write/recovery occurs on download.
3. My Comments offers an explicit **server snapshot JSON backup** action.
4. The previously supported local JSON import remains available; imported
   prediction and engagement snapshots are local-only and **cannot certify
   live measurements or ownership**. Reconnection to server still requires
   OAuth re-verification of YouTube comment ownership.

### Required infrastructure for actual durability

A persistent disk requires a **paid Render web-service plan** or use a
separately provisioned permanent database. Free Render Postgres expires in
30 days, so it does not fix durable retention. Do not create paid services,
change service plans, or write credentials without the owner's authorization.

If selecting Render persistent disk for the existing SQLite code:
- Ensure existing data is backed up *before* service upgrade / disk attachment.
- Attach disk at `/var/data`; configure
  `AI_COMMENT_DB_PATH=/var/data/ai_comment.db` and
  `YOUTUBE_OAUTH_TOKEN_PATH=/var/data/youtube_oauth_token.json`.
- Set `AI_COMMENT_STORAGE_PERSISTENT=true` only after verifying actual
  persistence across a controlled restart and checking same-channel records.
- An empty new disk does not restore deleted SQLite or lost OAuth tokens.
- Run read-only checks first, then restore only after explicit confirmation.

## Phase 1 first technical slice implemented in this branch

`GET /videos/moments?url=<YouTube URL>` groups timestamped public transcript
snippets into bounded one-minute windows. Sampling covers the video's
duration, rather than misleadingly showing only the beginning. The
recommendation page has an opt-in timeline panel linking each caption
window to the corresponding YouTube timestamp.

**Evidence contract:** `evidence=captions_only`, `frames_analyzed=false`.
The pipeline has **not analyzed video frames, inferred a visible action, used
multimodal embeddings, or fed this timeline into the ranker**.
Missing or blocked captions yield empty evidence with explicit status.

## Remaining roadmap

1. Durable database / persistent disk provisioning and recovery verification
2. Actual frame-based video understanding through an authorized multimodal
   model, with a bounded frame sampler and timestamps
3. Semantic retrieval index for caption/frame/comment embeddings with
   per-video provenance and access controls
4. Offline performance evaluation and model retraining on real feedback
5. Channel personalization, synthetic audience and creator reply extensions

## Checks

- Backend pytest including account-scoped exports and captions-only behavior
- Frontend npm test, lint and production build
- Review the new security boundaries before merging
- After the durable-storage transition, verify personal OAuth identity,
  end-to-end export, restoration and caption-preview fallback manually
