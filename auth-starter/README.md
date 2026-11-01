# Supabase protected routes starter

Self-contained React-free browser UI with Vite, Supabase Auth, per-user resume RLS and Express authenticated API. This does not replace the existing production application.

## Local setup
Copy `.env.example` to `.env` and replace `YOUR_PUBLIC_KEY`. Keep `OPENAI_API_KEY` in the server environment only. Vite reads `VITE_*` keys only.
Run `npm install`, `npm run build`, `npm test`, `npm run dev` within this directory. Run `npm run server` separately with the same server environment variables.

In Supabase Auth URL Configuration, set Site URL `http://localhost:5173` and allow redirect `http://localhost:5173/**`. Enable email/password auth and email confirmation, and set appropriate production URLs before deployment.

The SQL source is `../supabase/migrations/001_resumes.sql`, already applied to the specified Supabase project. Do not reapply it blindly; the policies are not idempotent.

Security: TLS in production, strict production ALLOWED_ORIGIN, rate limiting with a shared store when horizontally scaled, email verification, API cost quotas, data retention and deletion workflows, and tested cross-user RLS boundaries are required before production use. Environment and auth tests are preliminary, not full penetration testing.
