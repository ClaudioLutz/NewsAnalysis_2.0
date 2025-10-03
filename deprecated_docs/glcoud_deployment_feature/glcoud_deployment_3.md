Here’s the short, researched answer to “best + simplest” for a small front page that requires sign-in, deployed on Cloud Run.

# The simplest **and** safest: let Google handle auth (no passwords)

If this is for internal use (your team/organisation), don’t build login at all—put your service behind **Identity-Aware Proxy (IAP)**. Users sign in with their Google/Workspace accounts, you keep **zero** passwords, and your app only reads who the user is from headers (or verifies the signed JWT). One toggle on Cloud Run enables it. ([Google Cloud][1])

**How to do it (high level):**

1. Deploy your service to Cloud Run with auth required and IAP enabled (Console or `gcloud ... --iap`). Then grant specific users/groups the “IAP-secured Web App User” role. ([Google Cloud][1])
2. In your FastAPI code, read the identity from `X-Goog-Authenticated-User-*` or, better, **verify** the `x-goog-iap-jwt-assertion` header using Google’s library and your IAP audience (client ID). ([Google Cloud][2])

Why this is “best + simplest”:

* No password storage, reset flows, lockouts, or CSRF tokens for login pages.
* Strong, managed auth enforced **before** traffic reaches your container. ([Google Cloud][3])

# If you must roll username/password (external users, no Google IDs)

Keep it minimal and follow OWASP. Here’s the shortest safe checklist:

**Passwords & storage**

* Hash passwords with **Argon2id** (preferred) or bcrypt as a fallback. OWASP’s current recommendation for Argon2id: ≥19 MiB memory, iterations = 2, parallelism = 1. In Python use `argon2-cffi` or Passlib’s Argon2. ([OWASP Cheat Sheet Series][4])

**Sessions & cookies**

* Use server-side sessions if possible (e.g., Redis via `starlette-session`), otherwise Starlette’s signed cookie sessions with strict cookie flags. Set `HttpOnly`, `Secure`, and `SameSite=Lax` (or `Strict` if you can). Also enforce HTTPS and HSTS. ([Starlette][5])

**CSRF**

* For form POSTs, include a CSRF token and keep `SameSite=Lax/Strict` on the session cookie. ([OWASP Cheat Sheet Series][6])

**Brute-force & credential stuffing**

* Add throttling/lockout after several failed logins and consider MFA where practical; these are OWASP-recommended controls. ([OWASP Cheat Sheet Series][7])

**Secrets**

* Don’t put secrets (admin hashes, keys) in the image or plain env vars. Use **Secret Manager** and inject into Cloud Run (volume or env with pinned versions). ([Google Cloud][8])

**FastAPI specifics**

* If you ever need token-based auth for APIs, follow FastAPI’s OAuth2/JWT tutorial (use password hashing, not plaintext). ([FastAPI][9])
* For cookie/form handling, Starlette notes you need `python-multipart` (forms) and `itsdangerous` (sessions). ([Starlette][10])

---

## Recommended path for you

Given you’re deploying to Cloud Run and just need a gated front page, I recommend **Option A (IAP)**. You’ll get a login wall in minutes, no password handling, and cleaner code. If you later need customer logins, we can layer app-level auth with Argon2id + CSRF + lockouts using the checklist above.

If you want, I’ll translate this into exact commands (enable IAP, set principals) and drop in a tiny FastAPI snippet that verifies the IAP JWT header.

[1]: https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run?utm_source=chatgpt.com "Configure IAP for Cloud Run  |  Cloud Run Documentation  |  Google Cloud"
[2]: https://cloud.google.com/iap/docs/identity-howto?utm_source=chatgpt.com "Getting the user's identity  |  Identity-Aware Proxy  |  Google Cloud"
[3]: https://cloud.google.com/run/docs/authenticating/end-users?utm_source=chatgpt.com "Authenticating users  |  Cloud Run Documentation  |  Google Cloud"
[4]: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html?utm_source=chatgpt.com "Password Storage - OWASP Cheat Sheet Series"
[5]: https://www.starlette.io/middleware/?utm_source=chatgpt.com "Middleware - Starlette"
[6]: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html?utm_source=chatgpt.com "Cross-Site Request Forgery Prevention - OWASP Cheat Sheet Series"
[7]: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html?utm_source=chatgpt.com "Authentication - OWASP Cheat Sheet Series"
[8]: https://cloud.google.com/run/docs/configuring/services/secrets?utm_source=chatgpt.com "Configure secrets for services  |  Cloud Run Documentation  |  Google Cloud"
[9]: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/?utm_source=chatgpt.com "OAuth2 with Password (and hashing), Bearer with JWT tokens - FastAPI"
[10]: https://www.starlette.io/?utm_source=chatgpt.com "Starlette"
