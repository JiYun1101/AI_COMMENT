# AI_COMMENT: protect posted comments before further deployment

Live deployment: the actual service is ai-comment-api-lite (srv-dauaq1mk1f9s73b31l5g), a Render Free Python service. It has no persistent disk. Its local SQLite records, including posted comments, analyses and feedback, and its OAuth token JSON do not survive instance replacement. The render.yaml file describes a different, disk-enabled service that was never provisioned.

DO NOT merge or deploy this fix until any remaining data on the current live instance has been exported or the user has accepted the loss. Git branches and pull requests do not replace the live service.

Recovery: existing YouTube comments can be found at https://www.youtube.com/feed/history/comment_history on the original account. Use highlighted-comment links containing both video ID (v) and comment ID (lc). This patch verifies comment ownership using the connected YouTube OAuth channel before re-attaching the record. Original model scores and generation traces cannot be recovered from YouTube; leave them empty.

The frontend now keeps a browser-local receipt of each successfully posted comment. It backs up server records when they are viewed and offers import/export. It can restore records to the server following OAuth confirmation; this is not multi-device account synchronization or a durable replacement for a real database.

For the current SQLite code, the durable deployment option is to change the actual Render service to a paid plan and attach a persistent disk at /var/data. Configure AI_COMMENT_DB_PATH=/var/data/ai_comment.db and YOUTUBE_OAUTH_TOKEN_PATH=/var/data/youtube_oauth_token.json. Set AI_COMMENT_STORAGE_PERSISTENT=true ONLY after the disk is attached and verified. This infrastructure change may incur ongoing charges and requires owner approval. Adding a new disk never restores an already-lost database.

Do not assume a Render rollback restores SQLite files. A Render Free Postgres database expires after 30 days; it is not a sustainable permanent fix without a paid upgrade and SQL migration.
