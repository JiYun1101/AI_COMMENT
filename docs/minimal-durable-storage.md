# Minimum durable YouTube data (phase 1)

The application can fetch public video metadata, comment text, current like counts,
and reply counts from YouTube after verifying account ownership. **Do not**
retain these values forever solely for caching.

Store irrecoverable application state:
- Verified YouTube channel ID, YouTube video ID, and published comment ID
- Publishing timestamp, local recommendation ID, and predicted score
- Optional 24h/7d engagement measurements (historical snapshots cannot be reconstructed later)
- Encrypted OAuth refresh credential when a future durable token implementation is available (not implemented here)

Implemented: private Supabase table `ai_comment_private.comment_receipts` and
optional server-side write using `DATABASE_URL`. The receipt writer is guarded
by the verified channel ID. It does not persist access tokens.

**This is not yet a full SQLite-to-PostgreSQL cutover.** Local SQLite still
powers analytics, listing, comment edits/deletions, and session handshakes.
Receipt retrieval exists as a backend helper, but UI recovery from it is not
wired yet. Keep the feature branch unmerged until read/recovery and credentials
are deployed and verified.

To activate later: put a Supabase Postgres pooler URI in Render's backend-only
`DATABASE_URL` secret environment variable. Never put it in GitHub, frontend
`VITE_*` settings, logs, or this document. Test connectivity and owner-scoped
queries before rolling out. A DB failure after YouTube has posted must never
trigger an automatic second YouTube write.
