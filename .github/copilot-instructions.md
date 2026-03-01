# JJOELS2026H4H Repository – Copilot Instructions

These notes are aimed at any AI coding agent that lands in this workspace. The goal is to give you just enough context to start making useful changes without having to read the whole repo.

## 🧱 High‑level Architecture

* **frontend/** – a Next.js (App Router) TypeScript application. This is the only directory with substantial code right now. All UI, API clients and shared types live here.
* **backend/** – placeholder Python helper (`main.py` currently empty). The frontend assumes a JSON API running on `http://localhost:8000` or whatever `NEXT_PUBLIC_API_URL` is set to.
* **collector/** – another empty Python stub (`collector.py`) intended to stream sensor data from a BME688 device. Nothing is implemented yet.
* **ml/** + **data/** – directories for model training and datasets. They contain README files but no code yet.

The project is essentially a demo: a web dashboard that shows live gas sensor captures, model inference results and training metrics. The backend/collector pieces are to be filled in later; focus on replicating the frontend contract when you extend them.

## 🛠 Developer Workflows

1. **Frontend**
   * Start dev server:
     ```bash
     cd frontend
     npm run dev   # or yarn dev / pnpm dev / bun dev
     ```
   * Build for production: `npm run build` then `npm run start`.
   * Lint: `npm run lint` (uses ESLint with the `eslint-config-next` preset).
   * The repo uses TypeScript and Tailwind CSS; `tsconfig.json` and `tailwind.config.js` are standard.
   * There are currently no unit tests; if you add tests follow the `src/*` structure and use whatever test runner you prefer.

2. **Backend / Collector / ML**
   * These Python scripts are empty and not yet wired up. When implementing, pick any framework (FastAPI/Flask/etc.) and ensure the endpoints match the contract in `frontend/src/lib/api.ts`.
   * Use `python -m venv .venv && source .venv/bin/activate` then install necessary packages.
   * Add documentation to the respective README.md files when you implement functionality.

3. **Environment variables**
   * Frontend: `NEXT_PUBLIC_API_URL` sets the base URL for API calls; defaults to `http://localhost:8000`.
   * Backend may read from `.env` or similar, but nothing is configured yet.

## 📡 API Contract (frontend ↔ backend)

Refer to `frontend/src/lib/api.ts` for the authoritative description. Key points:

```ts
//   GET  /metrics        -> Metrics
//   GET  /captures       -> CaptureResult[]
//   POST /capture        body { seconds: number } -> CaptureResult
//   POST /infer (opt)    body { features: Record<string,number> } -> CaptureResult
```

* All responses are JSON. 4xx/5xx errors are shown by throwing an `Error` with a message.
* The client has built-in fallback mocks so the UI still renders if the backend is not running—use this pattern when adding new endpoints.
* Types are defined in `frontend/src/lib/types.ts` and should be kept stable; import them wherever possible.

## 💡 Frontend Conventions

* **Client components**: Most components are interactive and live under `src/components`. They start with `"use client";` at the top and use React hooks.
* **Pages**: The `/src/app` folder contains route components using the Next.js App Router. Add new pages as directories with a `page.tsx`. Use `export const dynamic = "force-dynamic";` when the page fetches data from the API so it doesn't get cached.
* **Shared logic**: Utility functions and types go in `src/lib`. The API client is `src/lib/api.ts` and the canonical types are in `src/lib/types.ts`; import from these instead of redefining.
* **Styling**: Tailwind CSS is the styling system. Follow the existing utility‑class patterns in components such as `CaptureButton`, `CaptureTimeline`, and `StatusBanner`. No CSS modules or styled‑components are used.
* **Data flow**: Frontend fetches from the backend via `getMetrics`, `getCaptures`, `postCapture`, and `postInfer`. All calls wrap `fetch` and fall back to mock data when the server is unreachable. When you add new endpoints, extend `api.ts` with similar guard logic so the UI still works offline.
* **Mock streams**: The homepage simulates live sensor data in a `useEffect` interval. Replace this with real streaming or websocket logic when the collector/backend are available.
* **TypeScript**: `strict` mode is enabled. Keep new props and state typed; leverage the existing types or augment them in `types.ts`.
* **Environment variables**: Use `process.env.NEXT_PUBLIC_API_URL` for the API base; defaults to `http://localhost:8000`. Frontend code should never hardcode the host.

## 🔄 Running the Full Stack

* Frontend runs on port 3000 (default Next.js). Backend is expected on port 8000.
* To test without a backend, simply run the frontend and the mock fallbacks in `api.ts` will kick in.
* When implementing the backend, ensure CORS is enabled or run both servers from the same origin.

## 📝 Backend / Collector Guidelines

* The backend/collector directories currently contain only empty Python files. When you add functionality:
  1. Pick a lightweight framework (FastAPI is convenient due to automatic JSON handling).
  2. Mirror the API contract from `frontend/src/lib/api.ts`. Example response shapes are defined in `types.ts`.
  3. Write server-side unit tests if possible and document endpoints in the README files in those directories.
  4. In `backend/main.py` you can spin up a web server that talks to whichever data store you choose; the frontend doesn't care about persistence.
* The collector script is meant to run on hardware reading a BME688 sensor. It should post JSON to the backend `/capture` endpoint or write to a shared database.

## 🛠 Miscellaneous Tips

* When adding new dependencies to the frontend, update `package.json` and run the corresponding package manager. The repo uses npm but yarn/pnpm are tolerated.
* Linting is enforced by `npm run lint`; fix issues before committing.
* There are no tests yet; when you add them keep them close to the code they cover.
* Keep typings in sync; a change to a backend response should usually be mirrored in `types.ts` and might break multiple components.

---

> ⚠️ If you are unsure where to extend the project, start by reading `frontend/src/lib/api.ts` and the components under `src/components`. That gives you the full picture of how the UI expects data.
