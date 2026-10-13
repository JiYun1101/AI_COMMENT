# Private UI server pairing

AI_COMMENT currently runs as a single-owner MVP. Its stored YouTube OAuth credentials and comment histories are shared server-side. Never share an invitation URL publicly.

Private Render backend environment variables:
- API_AUTH_TOKEN: high-entropy master signing secret (32 bytes or more)
- API_PAIRING_TOKEN: separate random invitation code (32 bytes or more)
- API_PAIRING_EXPIRES_AT: Unix timestamp for a short-lived invitation

Only the invitation, never the master signing secret, is privately given to the owner. Open /account/connect#pair=INVITATION in the browser. The page immediately strips the fragment from the address bar and presents a server connection button. After an explicit click, POST /auth/connect exchanges the invitation for a 30-day HMAC-signed session (acs1). The GET /auth/session endpoint verifies the issued credential before the frontend stores it. Other protected routes continue using X-API-Key.

The invitation remains reusable until expiry. Anyone with the invite could connect during this time; rotating API_AUTH_TOKEN invalidates all active sessions. Sessions stored in browser localStorage are subject to XSS and are only suitable for a personal MVP. For multiple users, implement proper per-user login and isolated OAuth token storage. YouTube and OpenAI APIs require separate integration setup.
