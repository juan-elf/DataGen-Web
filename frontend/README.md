Next.js (App Router) frontend for DataGen Web. See the [repo root README](../README.md)
for the full architecture; this is just the frontend piece.

```powershell
npm install
copy .env.example .env.local   # NEXT_PUBLIC_API_URL -> your backend
npm run dev
```

- `app/page.tsx` — upload a CSV/Excel file into your workspace
- `app/chat/page.tsx` — chat with the agent over your uploaded data (SSE)
- `app/report/page.tsx` — generate an autonomous insight report (SSE progress)
- `lib/api.ts` — typed client for the backend's REST + SSE endpoints
- `lib/sse.ts` — hand-rolled SSE frame parser (fetch + ReadableStream, not
  `EventSource`, since the backend's streaming endpoints are POST + cookie-authed)

No design system applied here on purpose — plug in your own.
