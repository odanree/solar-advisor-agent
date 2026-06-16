# solar-advisor-agent

Composite-data LangGraph agent that answers solar-economics questions by combining four sources:

1. **Solar Cost Explorer GraphQL** (own deployment) — $/W cost bands by state, system size, panel tier, installer type
2. **NREL PVWatts v8** — annual production estimate for a given lat/lon + system size
3. **DSIRE** — solar incentive programs by state (federal tax credit + state rebates)
4. **EIA** — state-level residential electricity prices

## Intents (MVP)

- `cost_lookup` — direct $/W lookup against Solar Cost Explorer GraphQL.
- `payback_estimate` — composite: pulls cost band → production estimate → incentives → rate, returns payback years with grounded citations to each source.

Future intents (out of MVP scope): `incentive_lookup`, `production_estimate`, `compare_locations`.

## Architecture

```
POST /api/v1/query
  → classify_intent (Claude Haiku)
    → cost_lookup OR payback_estimate
      → source clients (httpx async, respx-mocked in CI)
        → answer composer (Claude Sonnet, with citations)
          → governance node (provenance flags, data freshness disclaimers)
            → return {answer, intent, citations, trace_id}
```

Built on the same shape as [oc-realestate-intel](https://github.com/odanree/oc-realestate-intel): LangGraph supervisor + intent routing, Langfuse traces, evalkit golden-set CI gating, agent-governance runtime.

## Setup

```bash
cp .env.example .env
# fill in ANTHROPIC_API_KEY, NREL_API_KEY, EIA_API_KEY
pip install -e ".[dev,eval]"
pytest -q                                  # all HTTP mocked, no live calls
uvicorn advisor.api.main:app --reload
```

Smoke test:
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"question": "What is the median $/W for a 6 kW standard system in California?"}'
```

## Eval

```bash
python -m advisor.eval.run                 # runs golden_set.yaml through evalkit
```

CI gates merges on faithfulness floor (see `.github/workflows/ci.yml`).

## Deployment

Lives in [portfolio-infra](https://github.com/odanree/portfolio-infra)'s `docker-compose.yml` as `solar-advisor-api`. Caddy fronts the API on `solar-advisor.danhle.net` (DNS-only in Cloudflare so Caddy can handle TLS-ALPN directly).

## License

MIT
