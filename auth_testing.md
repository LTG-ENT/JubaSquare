# Emergent Google Auth – Testing Notes (JubaSquare)
- Flow: Login/Signup "Continue with Google" -> https://auth.emergentagent.com/?redirect=<origin>/ -> lands at /#session_id=...
- Frontend OAuthHashGate (App.js) renders AuthCallback which POSTs /api/auth/google-session {session_id}.
- Backend exchanges session_id with Emergent session-data, finds/creates user by email (new = customer, email_verified), stores user_sessions row, returns the app's normal JWT {token, user} + access_token cookie.
- Existing app auth (JWT, /api/auth/me with Bearer or access_token cookie) is unchanged.
- Test: bogus session_id -> 401. To test gated pages, use normal JWT login creds from /app/memory/test_credentials.md.
