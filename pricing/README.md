# OCI Pricing Agent — Docker (OCI GenAI Edition)

## Quick start — 2 commands

```bash
bash setup-env.sh            # reads ~/.oci/config → writes .env
docker compose up -d --build # build image + start container
```

Open **http://localhost:8742**

---

## What setup-env.sh does

Reads your `~/.oci/config` **[DEFAULT]** profile and automatically fills `.env` with:

| .env field | Source |
|---|---|
| `OCI_USER` | `user=` in config |
| `OCI_TENANCY` | `tenancy=` in config |
| `OCI_FINGERPRINT` | `fingerprint=` in config |
| `OCI_REGION` | `region=` in config |
| `OCI_PRIVATE_KEY` | reads `key_file=` path, inlines the PEM |
| `OCI_COMPARTMENT` | kept from previous `.env`, or defaults to tenancy |
| `OCI_GENAI_MODEL` | kept from previous `.env`, or defaults to Llama 3.1 70B |

To use a different OCI profile:
```bash
OCI_CLI_PROFILE=MYPROFILE bash setup-env.sh
```

To use a different compartment, edit `.env` after running the script:
```
OCI_COMPARTMENT=ocid1.compartment.oc1..xxx
```

---

## Architecture

```
Browser → localhost:8742 (Docker)
              │
              ├── GET /              → index.html
              ├── GET /api/v1/health         → catalog status
              ├── GET /api/v1/catalog/*      → OCI price catalogs (RAM)
              ├── POST /api/v1/chat          → OCI GenAI inference endpoint
              └── POST /api/v1/assistant     → deterministic assistant orchestration
              │
              ├──→ oracle.com        (catalogs, at startup + every 6h)
              └──→ inference.generativeai.{region}.oci.oraclecloud.com
```

Detailed technical docs:

- [Docs Guide](./docs/README.md)
- [Architecture](./docs/core/ARCHITECTURE.md)
- [Execution Plan](./docs/planning/EXECUTION_PLAN.md)
- [Coverage Roadmap](./docs/planning/COVERAGE_ROADMAP.md)
- [Improvement Milestones](./docs/planning/IMPROVEMENT_MILESTONES.md)
- [OpenAPI Contract](./docs/contracts/openapi.yaml)

Tracking convention:

- `Done`: implemented and validated in runtime
- `In Progress`: partly implemented, still incomplete
- `Next`: prioritized next work

---

## Current Direction

This repo is being evolved toward a professional OCI estimation architecture:

- `GenAI` for interpreting text, images, and uploaded files
- `service registry + workbook/catalog metadata` for service matching
- `deterministic pricing engine` for final calculation
- `clarification-first behavior` for ambiguous licensing and sizing cases

The goal is broad OCI service coverage with auditable pricing, not prompt-only quoting.

Rule artifacts now live under `pricing/data/rule-registry/`:

- `rules.json`
- `vm_shape_rules.json`
- `service_family_rules.json`
- `followup_capability_matrix.json`
- `coverage_matrix.json`

These artifacts are generated from the workbook/PDF extracts plus explicit shape metadata and declarative family metadata. `coverage_matrix.json` now also includes `computeVariantAudit`, which highlights compute-family services present in the price extracts but not yet represented in the explicit VM shape registry. `followup_capability_matrix.json` exposes the supported follow-up behavior per family so tests and future tooling can inspect it directly.

---

## Commands

```bash
bash setup-env.sh                        # refresh .env from ~/.oci/config
docker compose up -d --build             # first time (build image)
docker compose up -d                     # subsequent starts
docker compose down                      # stop
docker compose logs -f                   # live logs
curl http://localhost:8742/api/v1/health    # catalog + OCI status
curl -X POST localhost:8742/api/v1/catalog/reload  # force catalog refresh
curl -X POST localhost:8742/api/v1/assistant -H 'Content-Type: application/json' -d '{"text":"Quote 2 OCPUs of FastConnect 10 Gbps"}'
python3 tools/build_vm_shape_rules.py    # regenerate calculator-style VM shape rules
node tools/build_coverage_artifacts.js   # regenerate service family rules + coverage matrix
```

---

## Updating OCI credentials

If you rotate your API key, just re-run the setup script and restart:
```bash
bash setup-env.sh
docker compose up -d
```

---

## Troubleshooting

| Symptom | Solution |
|---|---|
| `OCI config not found` | Run `oci setup config` first |
| `authentication error` in chat | Check fingerprint matches your key in OCI Console |
| `403 / not authorized` | Verify IAM policy allows GenAI in the compartment |
| Catalogs not loading | `docker compose logs -f` to see the error |
| Port 8742 occupied | Change `"8742:8742"` → `"9000:8742"` in docker-compose.yml |
