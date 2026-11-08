# apps/api

Backend API + auth for the Control Tower Core (Group 1).

- **Stack:** Fastify + TypeScript.
- **Deploys** to Render via `.github/workflows/deploy-staging.yml` /
  `deploy-production.yml` (staging auto-deploys on merge to `main`,
  production is manual-dispatch/tag-only — **no reviewer gate currently enforced**, see root README).
- **Owner:** `@Sundeep-PV` (see `.github/CODEOWNERS`).

```bash
npm install            # from repo root
npm run dev --workspace=apps/api     # tsx watch, local dev
npm run build --workspace=apps/api   # tsc -> dist/
npm run start --workspace=apps/api   # node dist/index.js
```

`GET /health` returns `{"status":"ok","service":"quantinnel-api"}` — the only
route so far. Lint is a placeholder (`npm run lint`) until a real ESLint
config is added; typecheck and build are real (`tsc`).

Replace `src/index.ts` with the real service.
