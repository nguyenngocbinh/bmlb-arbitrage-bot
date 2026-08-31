# Architecture

BMLB Arbitrage Bot follows a domain-oriented application structure inspired by the organization principles used by OmniRoute.

## Runtime layout

```text
app/
├── core/          # configuration, logging, environment, shared errors
├── exchanges/     # exchange connectivity
├── arbitrage/     # arbitrage strategies and bot implementations
├── trading/       # orders, balances, multi-pair orchestration
├── risk/          # risk controls and rate limiting
├── persistence/   # database and persisted trading state
├── recovery/      # interrupted-session recovery
├── notifications/ # Telegram and notification adapters
├── backtesting/   # replay, recording and analytics
└── web/           # FastAPI dashboard and templates
```

## Design rules

1. Business logic belongs under `app/`.
2. Code is grouped by business domain, not by generic `*_service` naming.
3. `cli/` is the application entry surface; runtime modules should not depend on CLI parsing.
4. `tests/` mirrors the application domains.
5. `.github/agents`, `.github/instructions`, `.github/prompts` and `.github/skills` contain development workflow automation and AI guidance, not runtime code.
6. Compatibility modules at the old paths are temporary shims and should not receive new business logic.

## Import direction

```text
CLI / Web
   │
   ▼
Arbitrage ───────► Trading ───────► Exchanges
   │                  │
   ▼                  ▼
Risk              Persistence
   │
   ▼
Notifications / Recovery
```

Shared infrastructure in `app/core` should remain dependency-light. Domain modules should import the smallest lower-level capability they need.

## Migration policy

The refactor is intentionally incremental. Existing imports such as `from services...` and `from bots...` remain available through compatibility shims while the application moves to `app.*` imports. New code must use the `app.*` namespace.
