# BP Mobile-First Tech Stack

This stack is the default for new BP products when mission/scope does not explicitly override it.

## Policy
- Products are mobile-first by default.
- For existing projects, adapt to the existing stack.
- For greenfield projects with no declared stack, use the defaults below.

## Default Stack
- Mobile app: React Native + Expo + TypeScript
- API/backend: Python 3.12 + FastAPI + Pydantic
- Database: PostgreSQL + Alembic migrations
- Async jobs: Celery + Redis
- Realtime: WebSocket gateway via FastAPI + Redis pub/sub
- Auth: OAuth2/OIDC with JWT rotation and device binding
- Testing: Pytest (backend), Vitest + React Native Testing Library (mobile), Playwright for web surfaces
- Observability: OpenTelemetry + Prometheus + Grafana + Sentry
- CI/CD: GitHub Actions + preview builds + signed mobile release pipeline
- Infra baseline: Docker + Terraform (or Pulumi) + managed secrets

## Finance/Trading Domain Additions
- Broker/exchange adapters isolated behind a strict interface.
- Risk engine is mandatory (position limits, drawdown guard, circuit breaker).
- Human approval checkpoints for high-risk actions.
- Full audit trail for every order/decision.

## Secure-by-Default Requirements
- Secrets never in code or prompts.
- All trading actions require signed intent records.
- Idempotency keys for external order submission.
- Replay-safe event ingestion and reconciliation jobs.
