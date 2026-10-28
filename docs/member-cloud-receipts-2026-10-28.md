# Member-scoped published-comment cloud receipt backup

This is a **safe partial mitigation**, not an automatic SQLite-to-Postgres migration.

## Actual deployed database

Supabase project `tyhpdlxbnsecjbyhdzuw` contains
`public.ai_comment_published_receipts`. Created 2026-10-28 by migration
`add_owner_scoped_published_comment_receipt_backup`. The primary key
is `(user_id, comment_id)`, referencing `auth.users`. **RLS is enabled**,
and policies constrain authenticated reads/inserts/updates/deletes to their
own `auth.uid()`. The anonymous role has no table privileges.
The project security advisor returned no warnings after the migration.

Receipt columns: video ID, comment ID, comment text, optional URL, posting
timestamp, optional local recommendation ID, and owner Supabase user ID.
No OAuth credentials, refresh/access tokens, Render API tokens or Supabase
secret keys enter this table.

## App behavior

- With a **Supabase-signed-in member in personal YouTube mode**, after the
  server confirms the **actual YouTube post** the browser stores its local
  receipt and then independently tries Supabase cloud backup.
- Failure of the second (cloud) write must **never** report the actual
  YouTube publication as failed or retry the YouTube post. The UI distinguishes
  local/cloud/server outcomes, including when the post succeeded.
- On **내 댓글 성과** use **Supabase에 게시 기록 백업** to copy existing
  locally saved receipts. This manual action requires a connected YouTube
  identity; the receipt rows themselves are NOT re-verified as belonging
  to that channel. Only use receipts you personally created.
- **내 계정 클라우드 백업 가져오기** restores only to this browser's local
  recovery store; it must not impersonate a YouTube account or republish a
  comment. Server recovery still requires independent OAuth ownership checks.
- Guest and demo histories remain local/server only. Signing out or
  changing Supabase accounts must not copy previous users' receipts to the
  new account automatically.

## Data safety and remaining limitations

The existing Render **ai-comment-api-lite** service still has ephemeral
SQLite and JSON OAuth token state. It **has not been restarted or redeployed**
as part of this change, and `AI_COMMENT_STORAGE_PERSISTENT` stays false.

**Not durable yet:** YouTube refresh tokens, SQLite analyses/feedback,
published comment reaction measurements at 24 hours / 7 days, video snapshot
history, model trace histories and browser OAuth session if not backed up
elsewhere. Supabase receipt backup is not a proof of YouTube comment ownership,
nor automatic OAuth channel linking.

For full persistence, first safely export any live SQLite/OAuth data, then
either (a) add a paid Render persistent disk and set **both**
`AI_COMMENT_DB_PATH` and `YOUTUBE_OAUTH_TOKEN_PATH` on the mounted volume,
or (b) migrate all server store read/write paths, OAuth state and snapshots
to durable Postgres. A `DATABASE_URL` environment variable alone does **not**
make the current SQLite implementation durable. Do not mark
`AI_COMMENT_STORAGE_PERSISTENT=true` before verifying all actual storage
paths, safe restore and retention.

**No actual YouTube comment was published to test this feature.**
Verified: frontend tests, Render deployment and public backend health.
End-to-end member cloud save/restore still requires a real signed-in
member and should be validated before relying on it for disaster recovery.
