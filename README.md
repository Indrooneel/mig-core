# MIG Core

**The execution boundary for critical infrastructure.**

One command to deploy. Every command validated before it reaches a controller. Fail-closed by default.

```bash
docker compose up
```

That's it. MIG Core backend API is running on port 8000. React frontend runs in a separate terminal on port 3000.

---

## What is MIG Core?

MIG Core is a deterministic command validation engine that sits at the IT-OT boundary. It validates every command — human, automated, or adversarial — against operational safety policy before reaching the controller.

Three possible outcomes:

- **ALLOW** — command is safe, proceed
- **DENY** — command is blocked, controller never sees it
- **APPROVAL** — command held for operator confirmation

No AI. No machine learning. No cloud dependency. Pure policy matching. Deterministic. Auditable. Fail-closed.

---

## Quick Start

### Backend (Docker)

```bash
git clone https://github.com/Indrooneel/mig-core.git
cd mig-core
docker compose up
```

Backend API is now running at `http://localhost:8000`

### Frontend (React)

In a separate terminal:

```bash
cd mig-core/frontend
npm install
npm start
```

Frontend is now running at `http://localhost:3000`

---

## Try It

### Validate a command

```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"text": "Set pump speed to 5000 RPM"}'
```

Response:
```json
{
  "decision": "DENY",
  "policy_id": "POL-OT-DENY-002",
  "risk_score": 100,
  "matched_policy": "Setpoint changes exceeding 5% are blocked",
  "flags": ["PAYLOAD_HIGH_RISK", "SETPOINT_DEVIATION"]
}
```

### Read sensor (safe)

```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"text": "Read current pump speed from PLC"}'
```

Response:
```json
{
  "decision": "ALLOW",
  "policy_id": "POL-OT-ALLOW-001",
  "risk_score": 10
}
```

### View audit trail

```bash
curl http://localhost:8000/audit
```

### Check health

```bash
curl http://localhost:8000/health
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/validate` | Validate a command against policies |
| POST | `/approve` | Approve a pending decision |
| POST | `/reject` | Reject a pending decision |
| GET | `/policies` | List all policies |
| POST | `/policies` | Add a new policy |
| DELETE | `/policies/{id}` | Remove a policy |
| GET | `/zones` | List all zones |
| GET | `/audit` | View decision history |
| GET | `/audit/stats` | Decision statistics |
| GET | `/audit/{id}` | View specific decision |
| GET | `/health` | System status |
| GET | `/stats` | Full statistics |

---

## Policies

MIG Core ships with default OT policies. Customize by editing `policies/default_ot_policies.json` or adding new JSON files to the `policies/` directory.

Example policy:
```json
{
  "id": "POL-OT-DENY-002",
  "description": "Setpoint changes exceeding 5% are blocked",
  "action_type": "write_setpoint_major",
  "direction": "DENY",
  "enforcement": "critical",
  "notify": ["safety_officer"],
  "keywords": ["set", "write", "change", "speed", "pressure"]
}
```

Add policies through the API:
```bash
curl -X POST http://localhost:8000/policies \
  -H "Content-Type: application/json" \
  -d '{
    "id": "CUSTOM-001",
    "description": "Block all writes to zone 3",
    "action_type": "write_zone3",
    "direction": "DENY",
    "enforcement": "critical",
    "notify": ["supervisor"],
    "keywords": ["zone 3", "zone three"]
  }'
```

---

## Zones

MIG Core supports Purdue Model zone-based enforcement:

| Zone | Purdue Level | Description |
|------|-------------|-------------|
| Safety | Level 1 - SIS | All writes blocked |
| Control | Level 1-2 | Firmware and config export blocked |
| Supervisory | Level 2-3 | Standard access |
| DMZ | Level 3.5 | MIG operates here |

---

## Architecture

```
Command Source (any)
        │
        ▼
┌──────────────────────┐
│     MIG Core          │
│                       │
│  PII Detection        │
│  Action Inference     │
│  Payload Inspection   │
│  Policy Matching      │
│  Stage Check          │
│  Zone Check           │
│  Override Evaluation  │
│  Setpoint Analysis    │
│  Decision + Audit     │
│                       │
│  ALLOW → forward      │
│  DENY  → block        │
│  APPROVAL → hold      │
└──────────────────────┘
        │
        ▼
Controller / Target System
```

---

## Built By

**House of Galatine** — AI cybersecurity for critical infrastructure.

- Website: [houseofgalatine.com](https://houseofgalatine.com)
- Playground: [houseofgalatine.com/playground](https://houseofgalatine.com/playground)
- Architecture Docs: [github.com/Indrooneel/mig-architecture](https://github.com/Indrooneel/mig-architecture)

---

## License

Copyright (c) 2026 House of Galatine. All rights reserved.

MIG Core is available for evaluation and non-commercial use.
For commercial licensing, contact: neel@houseofgalatine.com
