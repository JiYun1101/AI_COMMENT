# Recover pasted Google My Activity comments

This is a fallback when the original Render Free SQLite file has been discarded and the user has only copied the activity text, not the YouTube comment IDs.

1. On /my-comments, connect the original YouTube account.
2. Paste the YouTube "내 댓글" page text (comment text followed by video title + "에 남긴 댓글").
3. Click **이전 댓글 찾아서 추적**. The browser extracts title-text pairs locally (no raw activity file upload).
4. The authenticated backend searches for each **exact video title**, retrieves matching public comments, verifies exact content against the authenticated YouTube channel ID and saves ONLY verified comment IDs. Ambiguous videos and unavailable/old/edited comments are rejected and listed.
5. Once registered, use "실제 반응 새로 확인" to collect like/reply counts. No historical 24-hour/7-day metric is invented. A previously lost predicted ranker score cannot be reconstructed.

Limits: up to 20 comments on 10 videos per request; video search has a high YouTube API quota cost (typically 100 units per video), with at most 7 pages/comment. This is a **best-effort** approach: title search might not find some videos or comments may be outside the limited search window, edited, held for review or unavailable. Use direct highlighted comment URLs or Google Takeout CSV for higher-fidelity recovery.

**Data durability is still unresolved**: current deployed backend is a Free Render service without a persistent disk. Recovered server rows can be erased on restart/redeploy. The browser receipt export is optional backup and is not a substitute for permanent account-scoped storage.
