<div align="center">

# Convergence

**Decision intelligence for high-stakes financial transactions.** CHP-governed multi-agent analysis for M&A integration, capital raises, restructurings, and IPO readiness — with every decision traceable from EXPLORING to LOCKED.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## The Problem

High-stakes financial decisions — mergers, capital raises, restructurings, IPOs — share a common failure mode: **decision opacity**. Teams build spreadsheets, run analyses, and present recommendations, but nobody can trace *why* a specific number landed where it did, *which assumptions were tested*, or *who validated the conclusion*.

Convergence solves this with a multi-agent decision pipeline wrapped in the **Consensus Hardening Protocol (CHP)** — ensuring every recommendation passes adversarial review, foundation disclosure, and explicit lock progression before it reaches the board.

---

## What Convergence Does

Convergence runs 3 agents per workstream through a **Cognitive Mesh** (expansion/compression reasoning) and **CHP decision governance** (EXPLORING → PROVISIONAL_LOCK → LOCKED):

```
Integration Mesh (3 agents per workstream)
    → Cognitive Mesh Protocol (expansion/compression reasoning)
    → Consensus Hardening Protocol (EXPLORING → PROVISIONAL_LOCK → LOCKED)
    → Convergence Dashboard (health, risks, milestones, decisions)
```

### Reference Implementation: M&A Integration

| Workstream | Finance Agent | Strategy Agent | Compliance Agent |
|---|---|---|---|
| **Chart of Accounts Mapping** | Account mapping, KPI alignment | Management view alignment | Restatement estimates |
| **Close Harmonization** | Close calendar, reconciliation gaps | Policy alignment | Audit readiness |
| **Systems Integration** | System dependency map, cutover risks | Migration plan | Security review |
| **Synergy Tracking** | Synergy pipeline, value capture | Risk register | Reporting controls |

### Extending to Other Scenarios

The same 3-agent-per-workstream architecture applies to:

- **Capital Raises** — investor targeting, valuation, term sheet analysis
- **Restructurings** — debt analysis, stakeholder impact, creditor negotiation
- **IPO Readiness** — S-1 drafting, SOX compliance, auditor coordination
- **Due Diligence** — financial, legal, operational, technology workstreams

---

## CHP Decision Flow

```
DecisionCase → R0 Gate (Solvable/Scoped/Valid/Worth_it)
    → Foundation Disclosure (1-3 weakest assumptions)
    → Foundation Attack (adversarial review)
    → Score >= 70? → EXPLORING → PROVISIONAL_LOCK → LOCKED (via 3rd-party validation)
    → Score < 70?  → REFRAME_REQUIRED
    → R0 fail?     → HALT
```

### Scoring

- **Overall Health**: RED (any workstream red) / AMBER (any amber) / GREEN (all green)
- **Foundation Score**: 0-100 (>= 70 to proceed, >= 100 for clean lock)
- **Accuracy Guard**: Floor enforcement — forces human verification below threshold

---

## Quick Start

```bash
git clone https://github.com/icohangar-ops/convergence.git
cd convergence
pip install -e ".[dev]"
pytest tests/ -v

# Run API
uvicorn convergence.api.main:app --reload

# Initialize for a deal
curl -X POST http://localhost:8000/api/v1/convergence/init \
  -H "Content-Type: application/json" \
  -d '{"deal_name": "Acme-TargetCo", "deal_type": "ma_integration"}'

# Run multi-agent analysis on a workstream
curl -X POST http://localhost:8000/api/v1/workstreams/chart_of_accounts/analyze
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/convergence` | Integration health dashboard data |
| POST | `/api/v1/convergence/init` | Initialize Convergence for a deal |
| GET | `/api/v1/workstreams` | List all workstreams |
| POST | `/api/v1/workstreams/{type}/analyze` | Run multi-agent analysis |
| GET | `/api/v1/decisions` | List all CHP decisions |
| POST | `/api/v1/decisions/{id}/validate` | Third-party validation (lock promotion) |

---

## Tech Stack

| Component | Service | Purpose |
|---|---|---|
| API Backend | App Platform (Python/uvicorn) | FastAPI + CHP + Mesh engines |
| Dashboard | App Platform (Next.js) | Convergence UI |
| Database | Managed PostgreSQL 16 | Decisions, mappings, audit trail |
| Storage | Spaces (S3) | Artifacts, CSVs, board decks |
| Inference | GenAI Inference | GPT-oss-20b / Llama 3.3 70B |
| IaC | Terraform | Full infrastructure |

---

## Deployment

```bash
cd terraform/
terraform init
terraform apply -var="do_token=$DIGITALOCEAN_API_TOKEN" -var="environment=prod"
```

---

## Project Structure

```
convergence/
├── src/convergence/
│   ├── chp/                # Consensus Hardening Protocol
│   ├── mesh/               # Cognitive Mesh (agents, protocol, context, playbook)
│   ├── workstreams/        # M&A integration workstreams (reference impl)
│   ├── convergence_tower/  # Health scoring, risks, milestones
│   ├── audit/              # Signed, append-only HMAC-SHA256 audit ledger
│   ├── stigmergy/          # SQLite stigmergy board (decaying signal coordination)
│   ├── inference/          # DO GenAI client
│   ├── db/                 # SQLite/PostgreSQL persistence
│   └── api/                # FastAPI backend
├── dashboard/              # Next.js Convergence UI
├── tests/                  # 152 tests
└── terraform/              # DO infrastructure
```

---

## Signed Audit Ledger

Every agent recommendation, board narrative, and stigmergy-board write is
recorded in a **tamper-evident, append-only JSONL ledger**
(`.convergence/audit.jsonl` by default), so the post-merger-integration
reasoning trail is defensible to an audit committee, external auditor, or
regulator.

**Scheme** (extracted from the signed-ledger family — cleanmandate,
swarmfi-executor, glacier-edge-arm, compliance-as-code-agent — and strengthened
with per-record signature chaining):

- One JSON record per line, append-only, never rewritten.
- Each record is signed as `HMAC-SHA256(key, canonical_json(record) + prev_sig)`,
  where `canonical_json` is the deterministic (sorted-key) encoding of every
  field except `sig`, and `prev_sig` is the signature of the previous line — so
  any edit, deletion, or reordering breaks the chain from the first tampered
  record onward.

**Record shape:** `{ts, event, actor, inputs, sources, confidence?, rationale?, prev_sig, sig}`

**Key:** read from `AUDIT_LEDGER_KEY` (a test default is used when unset so the
offline tests run without configuration — set a real secret in production).

```python
from convergence.audit import AuditLedger

ledger = AuditLedger("audit.jsonl")             # key from AUDIT_LEDGER_KEY
sig = ledger.append(event="recommendation", actor="finance",
                    inputs={"problem": "map coa"}, sources=["trial_balance"],
                    confidence="high", rationale="Map 1:1 where clean")
intact, first_tampered_index = ledger.verify()  # (True, None) when clean
```

The ledger is wired into `EnterpriseOrchestrator` by default — every turn and
the final board narrative are signed automatically.

---

## Stigmergic Coordination

Convergence coordinates ~12 mesh agents (four workstreams × three agents).
Rather than relaying every agent's full output to the next through the LLM,
agents can coordinate **stigmergically** — by depositing and reading compact
typed signals on a shared **SQLite board** whose signals **decay over time**.
Coordination reads/writes are pure arithmetic + SQL, so peer-to-peer
coordination costs **zero LLM tokens**.

Pattern adapted from **cubiczan-swarm-pack** (scent-field pheromones) and
**swarmfi-preps** (persistent SQLite stigmergy board).

**How it works**

- **deposit(region/key, kind, strength):** an agent posts a typed signal —
  `FINDING`, `RISK_FLAG`, `DEPENDENCY_NOTE`, or `CONFIDENCE`.
- **time decay:** each signal's live strength is
  `strength · e^(−λ·elapsed)` with `λ = ln(2) / half_life` (per-type
  half-lives; risk flags linger longest). Signals also carry a hard TTL.
- **read_signals(region):** returns live signals for a key/region, strongest
  (post-decay) first; `context_for(agent)` returns the compact board view that
  is injected into an agent's context **instead of** peer transcripts.
- **evaporate() / garbage_collect():** purges signals past TTL or decayed below
  the GC threshold.

**Non-breaking and topology-preserving.** Stigmergy is opt-in via a feature
flag; the existing Kahn topological producer→consumer ordering is unchanged. The
board only changes *how context flows between turns*.

```python
from convergence.mesh.orchestrator import EnterpriseOrchestrator

# Feature-flagged: agents coordinate via the board, not LLM chatter.
orch = EnterpriseOrchestrator(agents=ws.agents, context=ws.context,
                              use_stigmergy=True)
report = orch.orchestrate("Analyze CoA mapping")   # topo order preserved
```

Direct board use:

```python
from convergence.stigmergy import StigmergyBoard, SignalType

board = StigmergyBoard()
board.deposit(agent="finance", signal_type=SignalType.RISK_FLAG,
              key="coa", content="intercompany accounts unmapped", strength=1.0)
signals = board.read(key="coa")            # decayed, strongest first
board.garbage_collect()                     # evaporate expired signals
```

---

## Running Tests

```bash
pip install pytest
PYTHONPATH=src pytest tests/ -v
```

---

## License

MIT. See [`LICENSE`](./LICENSE).

---

## CHP Governance

This repository is hardened with the [Consensus Hardening Protocol (CHP)](https://codeberg.org/cubiczan/consensus-hardening-protocol).

### Protocol Layers
- **R0 Gate**: Solvable, Scoped, Valid, Worth_it
- **Foundation Disclosure**: 1-3 weakest assumptions
- **Adversarial Layer**: Devil's advocate at Phase 0 and Round 3
- **State Machine**: EXPLORING → PROVISIONAL → PROVISIONAL_LOCK → LOCKED
- **Third-Party Validation**: Independent CONFIRM/REJECT before lock

### Domain Configuration
- **Category**: Finance (CFO Accuracy)
- **Foundation Threshold**: 100
- **CFO Accuracy Guard**: Enabled

### CHP Version
cognitive-mesh-orchestrator 0.1.0 | [Protocol Docs](https://codeberg.org/cubiczan/consensus-hardening-protocol)
