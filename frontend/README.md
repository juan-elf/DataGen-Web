Next.js (App Router) frontend for DataGen Web. See the [repo root README](../README.md)
for the full architecture; this is just the frontend piece.

```powershell
npm install
copy .env.example .env.local   # NEXT_PUBLIC_API_URL -> your backend
npm run dev
```

- `app/page.tsx` — landing page (marketing / design-system page)
- `app/(app)/layout.tsx` — signed-in app shell: sidebar with nav rail + chat session history
- `app/(app)/upload/page.tsx` — upload a CSV/Excel file into your workspace
- `app/(app)/chat/page.tsx` — chat with the agent over your uploaded data (SSE)
- `app/(app)/report/page.tsx` — generate an autonomous insight report (SSE progress)
- `lib/api.ts` — typed client for the backend REST + SSE endpoints (attaches the
  `X-Workspace-Id` identity header — see root README "Workspace identity")
- `lib/sse.ts` — hand-rolled SSE frame parser (fetch + ReadableStream, not
  `EventSource`, since the backend's streaming endpoints are POST + need the header)
- `lib/sessions.tsx` — chat session history (localStorage, via `useSyncExternalStore`)
- `components/` — Logo, Reveal (scroll-reveal)

Design tokens (colors, Space Grotesk / Space Mono fonts) live in `app/globals.css`.
