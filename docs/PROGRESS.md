# Progress

Updated at the end of every phase. See `docs/DECISIONS.md` for the reasoning
behind each choice.

## Done

### Phase 0: Foundations (2026-10-09)

- Plan, assumptions and known owner inputs posted. Written up in
  `ARCHITECTURE.md` (components, ERD, both state machine tables, timeline
  mapping, pricing formula, upload pipeline, jobs, purge, assumptions),
  `DECISIONS.md` and `OWNER_TODO.md`.
- Monorepo scaffold: `services/api` (FastAPI, uv, ruff, mypy strict, pytest),
  `apps/web` (Vite, React 19, TypeScript 5.9, Tailwind 4, Vitest, ESLint,
  Prettier), `apps/mobile` (Flutter 3.47.7, Android only, dev, staging and prod
  flavors), `packages/contracts` (OpenAPI export with drift check).
- Compose stack: Postgres 16, Redis 7, MinIO (built from pinned source), an
  optional ClamAV profile, and API, worker, beat, migrate and web services.
- Multi-stage, non-root Dockerfiles for API, worker, beat, web and MinIO.
- `Makefile` with up, down, seed, lint, test, e2e, demo, verify.
- GitHub Actions CI running the same targets.

## In progress

- Phase 1: Contracts and screens.

## Next

- Phase 2: Backend core.
- Phase 3: Integrations.
- Phase 4: Android app.
- Phase 5: Web portal.
- Phase 6: Hardening.
- Phase 7: Release readiness.

## Known limitations of the build environment

- No Android SDK in the build sandbox (`dl.google.com` is blocked), so the
  release AAB and emulator tests run only in CI (D-006).
- Docker Hub rate-limits the sandbox, so local builds use
  `DOCKER_REGISTRY=mirror.gcr.io` (D-005).
