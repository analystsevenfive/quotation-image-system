# Quotation Studio authentication

Quotation Studio uses the same Google OAuth and `public.app_users` allowlist as Product Finder. A user must have `working_status = permanent`.

## Local setup

The web app reads `apps/web/.env.local`; FastAPI reads the root `.env` when launched from the repository root. Set `AUTH_ENABLED=true` in both environments. Copy the **same** Supabase project URL and publishable key to these variables:

| Web (Next.js) | API (FastAPI) |
| --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | `SUPABASE_URL` |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | `SUPABASE_PUBLISHABLE_KEY` |

Restart both servers after changing environment variables. The local files are ignored by Git.

## Supabase and deployment

In Supabase Authentication → URL Configuration, add the web origin and `https://quotation-image-system.vercel.app/auth/confirm` to the allowed redirect URLs. Add the local callback URL if testing locally. Google OAuth must be enabled in the shared Supabase project.

Set the web variables and `AUTH_ENABLED=true` in Vercel. Set the API variables and `AUTH_ENABLED=true` in Render. Deploy both together: if only the web is enabled, direct Render requests remain open; if only the API is enabled, the web cannot send a user token.

The web proxy attaches the user's access token to `/api/*` requests. FastAPI checks the token with Supabase Auth and then checks `app_users`. Direct calls to Render require a valid bearer token. `/api/health` stays public. The existing `quotation_session` cookie continues to isolate each browser's quotation data. Automated sync requests can use `SYNC_SECRET` without a user token.
