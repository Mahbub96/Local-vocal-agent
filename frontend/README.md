# Frontend (Aurora UI)

React + TypeScript + Vite client for Local Vocal Assistant.

## Run

From `frontend/`:

```bash
npm install
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Or from project root (recommended):

```bash
./start.sh
```

## Build

```bash
npm run build
```

## API Base

Frontend uses:

- `VITE_API_BASE` env variable when provided
- fallback: `http://localhost:8000/api/v1`

For local aligned setup, backend should run on `127.0.0.1:8000` and CORS should allow frontend origin.

## UI Architecture

- `src/App.tsx`: root composition only
- `src/hooks/useAuroraDashboard.ts`: API/state orchestration
- `src/services/api.ts`: API helpers
- `src/components/*`: small reusable UI components
- `src/theme/theme.ts` + `src/theme/theme.js`: design tokens
- `src/styles/*`: token/base/layout/components CSS split

## Notes

- Polling was removed from dashboard hook to avoid unnecessary background API calls.
- Data updates occur on initial load, session changes, and explicit user actions.
