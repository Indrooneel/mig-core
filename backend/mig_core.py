"""
MIG Core — Execution Control Engine
House of Galatine © 2026

The execution boundary. Nothing reaches the controller without approval.

This is the open-core version of MIG. No Neo4j. No embeddings. No AI.
Pure deterministic policy matching with JSON policies and SQLite audit.

Deploy with: docker compose up
Configure through: the web dashboard or JSON policy files
"""

import json
import time
import sqlite3
import os
import re
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel


# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════

POLICY_DIR = os.environ.get("MIG_POLICY_DIR", "./policies")
AUDIT_DB = os.environ.get("MIG_AUDIT_DB", "./data/audit.db")
VERSION = "1.0.0"
MODE = "fail-closed"


# ═══════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="MIG Core",
    description="Execution Control Engine — House of Galatine",
    version=VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════

class ValidateRequest(BaseModel):
    text: str
    action_type: Optional[str] = None
    stage: Optional[str] = "running"
    context: Optional[str] = ""
    source: Optional[str] = "unknown"
    zone: Optional[str] = None

class ApproveRequest(BaseModel):
    decision_id: str
    approved_by: str

class RejectRequest(BaseModel):
    decision_id: str
    rejected_by: str
    reason: Optional[str] = ""

class PolicyCreate(BaseModel):
    id: str
    description: str
    action_type: str
    direction: str  # ALLOW, DENY, APPROVAL
    enforcement: Optional[str] = "standard"
    notify: Optional[list] = []
    zone: Optional[str] = None
    stage_blocked: Optional[list] = []
    max_deviation_percent: Optional[float] = None
    keywords: Optional[list] = []

class ZoneCreate(BaseModel):
    id: str
    name: str
    purdue_level: Optional[str] = None
    description: Optional[str] = ""
    allowed_sources: Optional[list] = []
    blocked_actions: Optional[list] = []


# ═══════════════════════════════════════════════════════════
# POLICY ENGINE
# ═══════════════════════════════════════════════════════════

class PolicyEngine:
    def __init__(self, policy_dir: str):
        self.policy_dir = policy_dir
        self.policies = []
        self.zones = []
        self.load_policies()

    def load_policies(self):
        self.policies = []
        self.zones = []
        policy_path = Path(self.policy_dir)
        
        # Check if folder doesn't exist OR is empty
        if not policy_path.exists() or not any(policy_path.iterdir()):
            policy_path.mkdir(parents=True, exist_ok=True)
            self._create_default_policies()

        for f in policy_path.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                if "policies" in data:
                    self.policies.extend(data["policies"])
                if "zones" in data:
                    self.zones.extend(data["zones"])
            except Exception as e:
                print(f"Error loading {f}: {e}")

        print(f"[MIG Core] Loaded {len(self.policies)} policies, {len(self.zones)} zones")

    def _create_default_policies(self):
        default = {
            "organization": "Default OT Plant",
            "vertical": "OT/ICS",
            "version": "1.0",
            "policies": [
                {
                    "id": "POL-OT-ALLOW-001",
                    "description": "Reading sensor values is permitted as a non-destructive operation",
                    "action_type": "read_sensor",
                    "direction": "ALLOW",
                    "enforcement": "standard",
                    "notify": [],
                    "keywords": ["read", "sensor", "monitor", "status", "check", "current", "measure", "temperature", "pressure", "flow"]
                },
                {
                    "id": "POL-OT-ALLOW-002",
                    "description": "Reading alarm history and event logs is permitted",
                    "action_type": "read_alarm",
                    "direction": "ALLOW",
                    "enforcement": "standard",
                    "notify": [],
                    "keywords": ["alarm", "history", "event", "log"]
                },
                {
                    "id": "POL-OT-APPR-001",
                    "description": "Setpoint changes within 5% require operator confirmation",
                    "action_type": "write_setpoint_minor",
                    "direction": "APPROVAL",
                    "enforcement": "elevated",
                    "notify": ["shift_operator"],
                    "keywords": ["set", "adjust", "change", "modify"],
                    "max_deviation_percent": 5.0
                },
                {
                    "id": "POL-OT-DENY-001",
                    "description": "Writing to safety instrumented system registers is never allowed",
                    "action_type": "write_safety",
                    "direction": "DENY",
                    "enforcement": "critical",
                    "notify": ["safety_officer", "plant_supervisor"],
                    "keywords": ["safety", "sis", "emergency", "shutdown", "interlock", "trip"]
                },
                {
                    "id": "POL-OT-DENY-002",
                    "description": "Setpoint changes exceeding 5% are blocked as they risk process instability",
                    "action_type": "write_setpoint_major",
                    "direction": "DENY",
                    "enforcement": "critical",
                    "notify": ["control_engineer", "safety_officer"],
                    "keywords": ["set", "write", "change", "modify", "speed", "pressure", "temperature"],
                    "max_deviation_percent": 5.0
                },
                {
                    "id": "POL-OT-DENY-003",
                    "description": "Firmware updates during production are never allowed",
                    "action_type": "firmware_production",
                    "direction": "DENY",
                    "enforcement": "critical",
                    "notify": ["control_engineer", "plant_supervisor"],
                    "keywords": ["firmware", "upload", "flash", "update", "program", "deploy"],
                    "stage_blocked": ["running", "startup"]
                },
                {
                    "id": "POL-OT-DENY-004",
                    "description": "Exporting configuration outside OT network is never allowed",
                    "action_type": "export_external",
                    "direction": "DENY",
                    "enforcement": "critical",
                    "notify": ["ciso", "plant_supervisor"],
                    "keywords": ["export", "external", "outside", "internet", "remote", "send out"]
                },
                {
                    "id": "POL-OT-DENY-005",
                    "description": "Remote vendor write access without local operator co-authorization is blocked",
                    "action_type": "vendor_remote_write",
                    "direction": "DENY",
                    "enforcement": "critical",
                    "notify": ["shift_operator", "ciso"],
                    "keywords": ["vendor", "remote", "third party"]
                }
            ],
            "zones": [
                {
                    "id": "zone-safety",
                    "name": "Safety Zone",
                    "purdue_level": "Level 1 - SIS",
                    "description": "Safety Instrumented Systems — last line of defense",
                    "allowed_sources": [],
                    "blocked_actions": ["write", "modify", "update", "upload"]
                },
                {
                    "id": "zone-control",
                    "name": "Control Zone",
                    "purdue_level": "Level 1-2",
                    "description": "PLCs, DCS, RTUs — direct process control",
                    "allowed_sources": ["operator", "engineer"],
                    "blocked_actions": ["firmware_upload", "config_export"]
                },
                {
                    "id": "zone-supervisory",
                    "name": "Supervisory Zone",
                    "purdue_level": "Level 2-3",
                    "description": "SCADA, HMI, Historian — operational visibility",
                    "allowed_sources": ["operator", "engineer", "supervisor"],
                    "blocked_actions": []
                },
                {
                    "id": "zone-dmz",
                    "name": "Industrial DMZ",
                    "purdue_level": "Level 3.5",
                    "description": "MIG operates here — the execution boundary",
                    "allowed_sources": ["mig"],
                    "blocked_actions": []
                }
            ]
        }

        path = Path(self.policy_dir) / "default_ot_policies.json"
        path.write_text(json.dumps(default, indent=2))
        self.policies = default["policies"]
        self.zones = default["zones"]

    def add_policy(self, policy: dict):
        self.policies.append(policy)
        self._save_custom_policies()

    def remove_policy(self, policy_id: str):
        self.policies = [p for p in self.policies if p["id"] != policy_id]
        self._save_custom_policies()

    def update_policy(self, policy_id: str, updates: dict):
        for i, p in enumerate(self.policies):
            if p["id"] == policy_id:
                self.policies[i].update(updates)
                break
        self._save_custom_policies()

    def add_zone(self, zone: dict):
        self.zones.append(zone)
        self._save_custom_policies()

    def _save_custom_policies(self):
        path = Path(self.policy_dir) / "custom_policies.json"
        path.write_text(json.dumps({
            "policies": [p for p in self.policies if p.get("custom")],
            "zones": [z for z in self.zones if z.get("custom")]
        }, indent=2))

    def get_all_policies(self):
        return self.policies

    def get_all_zones(self):
        return self.zones


# ═══════════════════════════════════════════════════════════
# VALIDATION ENGINE
# ═══════════════════════════════════════════════════════════

class ValidationEngine:
    # PII patterns
    PII_PATTERNS = [
        (r'[\w.+-]+@[\w-]+\.[\w.]+', 'email'),
        (r'\b\d{3}-\d{2}-\d{4}\b', 'ssn'),
        (r'\b\d{4}\s?\d{4}\s?\d{4}\b', 'card_number'),
        (r'\b\d{12}\b', 'aadhaar'),
    ]
    PII_KEYWORDS = ["personal data", "salary", "ssn", "passport", "bank account",
                    "credit card", "social security", "medical", "compensation"]

    # Data sensitivity
    SENSITIVITY_MAP = {
        "read": "low", "sensor": "low", "monitor": "low", "status": "low",
        "write": "high", "register": "high", "set": "high", "modify": "high",
        "firmware": "critical", "upload": "critical", "flash": "critical",
        "safety": "critical", "sis": "critical", "emergency": "critical",
        "config": "critical", "export": "critical", "topology": "critical",
    }

    DESTINATION_KEYWORDS = {
        "external": ["external", "outside", "internet", "cloud", "remote", "offsite", "send out"],
        "safety": ["safety", "sis", "emergency", "shutdown", "interlock"],
        "control": ["plc", "controller", "register", "actuator", "coil"],
        "supervisory": ["scada", "hmi", "historian", "operator station"],
    }

    def __init__(self, policy_engine: PolicyEngine):
        self.policy_engine = policy_engine

    def validate(self, req: ValidateRequest) -> dict:
        text = req.text
        lower = text.lower()
        timestamp = datetime.now(timezone.utc).isoformat()
        decision_id = f"dec_{int(time.time() * 1000)}"

        checks = []
        flags = []
        risk_score = 10
        decision = "ALLOW"
        matched_policy = None

        # ── STEP 1: PII Detection ──
        pii_found = []
        for pattern, pii_type in self.PII_PATTERNS:
            if re.search(pattern, lower):
                pii_found.append(pii_type)
        for kw in self.PII_KEYWORDS:
            if kw in lower:
                pii_found.append(f"keyword:{kw}")

        is_external = any(kw in lower for kw in self.DESTINATION_KEYWORDS["external"])

        if pii_found:
            flags.append("PII_DETECTED")
            if is_external:
                flags.append("PII_EXTERNAL_RISK")
                risk_score = max(risk_score, 80)
            checks.append({"name": "PII Detection", "status": "flag" if not is_external else "fail",
                          "detail": f"Detected: {', '.join(set(pii_found))}"})
        else:
            checks.append({"name": "PII Detection", "status": "pass", "detail": "No sensitive data patterns detected"})

        # ── STEP 2: Action Inference ──
        action_type = req.action_type or self._infer_action(lower)
        checks.append({"name": "Action Inference", "status": "pass",
                       "detail": f"Inferred: {action_type}"})

        # ── STEP 3: Payload Analysis ──
        sensitivity = "low"
        for word, sens in self.SENSITIVITY_MAP.items():
            if word in lower:
                if self._sens_rank(sens) > self._sens_rank(sensitivity):
                    sensitivity = sens

        destination = "internal"
        for dest, keywords in self.DESTINATION_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                destination = dest
                break

        if sensitivity == "critical":
            risk_score = max(risk_score, 70)
        elif sensitivity == "high":
            risk_score = max(risk_score, 40)

        if destination == "external":
            risk_score = max(risk_score, 80)
        elif destination == "safety":
            risk_score = max(risk_score, 70)

        if risk_score >= 70:
            flags.append("PAYLOAD_HIGH_RISK")
        elif risk_score >= 40:
            flags.append("PAYLOAD_MEDIUM_RISK")

        checks.append({"name": "Payload Inspection", "status": "fail" if risk_score >= 70 else "flag" if risk_score >= 40 else "pass",
                       "detail": f"Sensitivity: {sensitivity} | Destination: {destination} | Risk: {risk_score}"})

        # ── STEP 4: Policy Matching ──
        matched_policy = self._match_policy(lower, action_type, req.stage)

        if matched_policy:
            decision = matched_policy["direction"]
            checks.append({"name": "Policy Match", "status": "pass" if decision == "ALLOW" else "fail" if decision == "DENY" else "flag",
                          "detail": f"{matched_policy['id']}: {matched_policy['description'][:80]}"})
        else:
            decision = "DENY"
            flags.append("NO_POLICY_MATCH")
            checks.append({"name": "Policy Match", "status": "fail",
                          "detail": "No matching policy — fail-closed → DENY"})

        # ── STEP 5: Stage Check ──
        if matched_policy and "stage_blocked" in matched_policy:
            if req.stage in matched_policy.get("stage_blocked", []):
                decision = "DENY"
                flags.append("STAGE_BLOCKED")
                checks.append({"name": "Stage Check", "status": "fail",
                              "detail": f"Action blocked during '{req.stage}' mode"})
            else:
                checks.append({"name": "Stage Check", "status": "pass",
                              "detail": f"Valid for '{req.stage}' mode"})
        else:
            checks.append({"name": "Stage Check", "status": "pass",
                          "detail": f"Mode: {req.stage}"})

        # ── STEP 6: Zone Check ──
        if req.zone:
            zone = next((z for z in self.policy_engine.zones if z["id"] == req.zone), None)
            if zone:
                action_word = action_type.split("_")[0] if action_type else ""
                if action_word in zone.get("blocked_actions", []):
                    decision = "DENY"
                    flags.append("ZONE_VIOLATION")
                    checks.append({"name": "Zone Check", "status": "fail",
                                  "detail": f"Action '{action_word}' blocked in {zone['name']}"})
                else:
                    checks.append({"name": "Zone Check", "status": "pass",
                                  "detail": f"Permitted in {zone['name']}"})
            else:
                checks.append({"name": "Zone Check", "status": "pass", "detail": "Zone not specified"})
        else:
            checks.append({"name": "Zone Check", "status": "pass", "detail": "No zone constraint"})

        # ── STEP 7: Overrides ──
        if pii_found and is_external and decision == "ALLOW":
            decision = "DENY"
            flags.append("PII_OVERRIDE")
            checks.append({"name": "Override", "status": "fail", "detail": "PII + external → DENY override"})
        elif risk_score >= 80 and decision == "ALLOW":
            decision = "APPROVAL"
            flags.append("RISK_ESCALATION")
            checks.append({"name": "Override", "status": "flag", "detail": f"High risk ({risk_score}) → escalated to APPROVAL"})
        elif risk_score >= 90 and decision == "APPROVAL":
            decision = "DENY"
            flags.append("RISK_OVERRIDE")
            checks.append({"name": "Override", "status": "fail", "detail": f"Critical risk ({risk_score}) → overridden to DENY"})
        else:
            checks.append({"name": "Override", "status": "pass", "detail": "No override needed"})

        # ── STEP 8: Setpoint Deviation Check ──
        deviation = self._extract_deviation(lower)
        if deviation is not None and deviation > 5.0 and decision != "DENY":
            decision = "DENY"
            risk_score = 100
            flags.append("SETPOINT_DEVIATION")
            matched_policy = next((p for p in self.policy_engine.policies if p["id"] == "POL-OT-DENY-002"), matched_policy)
            checks.append({"name": "Setpoint Check", "status": "fail",
                          "detail": f"Deviation: {deviation:.0f}% exceeds 5% threshold"})
        elif deviation is not None:
            checks.append({"name": "Setpoint Check", "status": "pass",
                          "detail": f"Deviation: {deviation:.1f}% within safe bounds"})

        # ── Final ──
        checks.append({"name": "Decision", "status": "pass" if decision == "ALLOW" else "fail" if decision == "DENY" else "flag",
                       "detail": f"Final: {decision} | Risk: {risk_score}/100"})

        result = {
            "decision": decision,
            "decision_id": decision_id,
            "policy_id": matched_policy["id"] if matched_policy else "FAIL_CLOSED",
            "matched_policy": matched_policy["description"] if matched_policy else "No matching policy — fail-closed",
            "risk_score": risk_score,
            "flags": flags,
            "checks": checks,
            "enforcement": {
                "level": matched_policy.get("enforcement", "critical") if matched_policy else "critical",
                "notify": matched_policy.get("notify", []) if matched_policy else ["security_team"],
                "requires": ["operator_confirmation"] if decision == "APPROVAL" else [],
            },
            "source": req.source,
            "stage": req.stage,
            "zone": req.zone,
            "timestamp": timestamp,
        }

        return result

    def _infer_action(self, text: str) -> str:
        if re.search(r'read|monitor|check|status|current|sensor|measure', text):
            return "read_sensor"
        if re.search(r'safety|sis|emergency|shutdown|interlock|trip', text):
            return "write_safety"
        if re.search(r'firmware|upload|flash|deploy|install', text) and re.search(r'program|update|controller', text):
            return "firmware_production"
        if re.search(r'export|send', text) and re.search(r'external|outside|internet|remote', text):
            return "export_external"
        if re.search(r'vendor|remote', text) and re.search(r'write|set|modify|command', text):
            return "vendor_remote_write"
        if re.search(r'set|change|adjust|write|modify', text) and re.search(r'speed|pressure|temperature|flow|level|rpm|kpa', text):
            num = re.search(r'(\d+)', text)
            if num:
                val = int(num.group(1))
                if val > 100:  # likely dangerous for most OT setpoints
                    return "write_setpoint_major"
            return "write_setpoint_minor"
        if re.search(r'set|write|change|modify', text):
            return "write_generic"
        return "unknown"

    def _match_policy(self, text: str, action_type: str, stage: str) -> Optional[dict]:
        # First try exact action_type match
        for p in self.policy_engine.policies:
            if p.get("action_type") == action_type:
                return p

        # Then try keyword matching — most specific (DENY) first
        deny_policies = [p for p in self.policy_engine.policies if p["direction"] == "DENY"]
        approval_policies = [p for p in self.policy_engine.policies if p["direction"] == "APPROVAL"]
        allow_policies = [p for p in self.policy_engine.policies if p["direction"] == "ALLOW"]

        for p in deny_policies:
            keywords = p.get("keywords", [])
            if keywords and any(kw in text for kw in keywords):
                return p

        for p in approval_policies:
            keywords = p.get("keywords", [])
            if keywords and any(kw in text for kw in keywords):
                return p

        for p in allow_policies:
            keywords = p.get("keywords", [])
            if keywords and any(kw in text for kw in keywords):
                return p

        return None

    def _extract_deviation(self, text: str) -> Optional[float]:
        num_match = re.search(r'(\d+)\s*(rpm|kpa|degrees?|percent|%|psi|bar|mpa)', text)
        if num_match:
            val = int(num_match.group(1))
            baseline = 50  # configurable per deployment
            if baseline > 0:
                return abs(val - baseline) / baseline * 100
        # Also catch bare numbers with setpoint context
        if re.search(r'set|write|change|adjust', text):
            num_match = re.search(r'to\s+(\d+)', text)
            if num_match:
                val = int(num_match.group(1))
                baseline = 50
                if val > 200 and baseline > 0:  # likely dangerous
                    return abs(val - baseline) / baseline * 100
        return None

    def _sens_rank(self, s: str) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(s, 0)


# ═══════════════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════════════

class AuditLog:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                input_text TEXT,
                decision TEXT,
                policy_id TEXT,
                matched_policy TEXT,
                risk_score INTEGER,
                flags TEXT,
                checks TEXT,
                source TEXT,
                stage TEXT,
                zone TEXT,
                enforcement TEXT,
                status TEXT DEFAULT 'final',
                approved_by TEXT,
                rejected_by TEXT,
                reject_reason TEXT,
                timestamp TEXT
            )
        """)
        self.conn.commit()

    def log(self, result: dict, input_text: str):
        self.conn.execute("""
            INSERT OR REPLACE INTO decisions 
            (id, input_text, decision, policy_id, matched_policy, risk_score, 
             flags, checks, source, stage, zone, enforcement, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result["decision_id"],
            input_text,
            result["decision"],
            result["policy_id"],
            result["matched_policy"],
            result["risk_score"],
            json.dumps(result["flags"]),
            json.dumps(result["checks"]),
            result.get("source", "unknown"),
            result.get("stage", "running"),
            result.get("zone"),
            json.dumps(result["enforcement"]),
            result["timestamp"],
        ))
        self.conn.commit()

    def approve(self, decision_id: str, approved_by: str) -> bool:
        cur = self.conn.execute("UPDATE decisions SET status='approved', approved_by=? WHERE id=?",
                                (approved_by, decision_id))
        self.conn.commit()
        return cur.rowcount > 0

    def reject(self, decision_id: str, rejected_by: str, reason: str) -> bool:
        cur = self.conn.execute("UPDATE decisions SET status='rejected', rejected_by=?, reject_reason=? WHERE id=?",
                                (rejected_by, decision_id, reason))
        self.conn.commit()
        return cur.rowcount > 0

    def get_recent(self, limit: int = 50) -> list:
        cur = self.conn.execute(
            "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?", (limit,))
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            d["flags"] = json.loads(d["flags"]) if d["flags"] else []
            d["checks"] = json.loads(d["checks"]) if d["checks"] else []
            d["enforcement"] = json.loads(d["enforcement"]) if d["enforcement"] else {}
            results.append(d)
        return results

    def get_by_id(self, decision_id: str) -> Optional[dict]:
        cur = self.conn.execute("SELECT * FROM decisions WHERE id=?", (decision_id,))
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        if row:
            d = dict(zip(cols, row))
            d["flags"] = json.loads(d["flags"]) if d["flags"] else []
            d["checks"] = json.loads(d["checks"]) if d["checks"] else []
            d["enforcement"] = json.loads(d["enforcement"]) if d["enforcement"] else {}
            return d
        return None

    def get_stats(self) -> dict:
        cur = self.conn.execute("SELECT COUNT(*) FROM decisions")
        total = cur.fetchone()[0]
        cur = self.conn.execute("SELECT decision, COUNT(*) FROM decisions GROUP BY decision")
        by_decision = dict(cur.fetchall())
        return {
            "total": total,
            "allowed": by_decision.get("ALLOW", 0),
            "denied": by_decision.get("DENY", 0),
            "approval": by_decision.get("APPROVAL", 0),
            "approved": by_decision.get("APPROVED", 0),
            "rejected": by_decision.get("REJECTED", 0),
        }


# ═══════════════════════════════════════════════════════════
# INIT
# ═══════════════════════════════════════════════════════════

policy_engine = PolicyEngine(POLICY_DIR)
validation_engine = ValidationEngine(policy_engine)
audit_log = AuditLog(AUDIT_DB)


# ═══════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════

@app.get("/health")
def health():
    stats = audit_log.get_stats()
    return {
        "status": "healthy",
        "version": VERSION,
        "mode": MODE,
        "policy_count": len(policy_engine.policies),
        "zone_count": len(policy_engine.zones),
        "total_decisions": stats["total"],
    }


@app.post("/validate")
def validate(req: ValidateRequest):
    result = validation_engine.validate(req)
    audit_log.log(result, req.text)
    return result


@app.post("/approve")
def approve(req: ApproveRequest):
    success = audit_log.approve(req.decision_id, req.approved_by)
    if not success:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"status": "approved", "decision_id": req.decision_id, "approved_by": req.approved_by}


@app.post("/reject")
def reject(req: RejectRequest):
    success = audit_log.reject(req.decision_id, req.rejected_by, req.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"status": "rejected", "decision_id": req.decision_id, "rejected_by": req.rejected_by}


# ── Policy Management ──

@app.get("/policies")
def list_policies():
    return {"policies": policy_engine.get_all_policies(), "count": len(policy_engine.policies)}


@app.post("/policies")
def create_policy(policy: PolicyCreate):
    p = policy.dict()
    p["custom"] = True
    policy_engine.add_policy(p)
    return {"status": "created", "policy": p}


@app.delete("/policies/{policy_id}")
def delete_policy(policy_id: str):
    policy_engine.remove_policy(policy_id)
    return {"status": "deleted", "policy_id": policy_id}


# ── Zone Management ──

@app.get("/zones")
def list_zones():
    return {"zones": policy_engine.get_all_zones(), "count": len(policy_engine.zones)}


@app.post("/zones")
def create_zone(zone: ZoneCreate):
    z = zone.dict()
    z["custom"] = True
    policy_engine.add_zone(z)
    return {"status": "created", "zone": z}


# ── Audit ──

@app.get("/audit")
def get_audit(limit: int = 50):
    decisions = audit_log.get_recent(limit)
    return {"count": len(decisions), "decisions": decisions}


@app.get("/audit/stats")
def get_audit_stats():
    return audit_log.get_stats()


@app.get("/audit/{decision_id}")
def get_decision(decision_id: str):
    d = audit_log.get_by_id(decision_id)
    if not d:
        raise HTTPException(status_code=404, detail="Decision not found")
    return d


# ── Stats ──

@app.get("/stats")
def get_stats():
    return {
        "mig": {
            "version": VERSION,
            "mode": MODE,
            "policy_count": len(policy_engine.policies),
            "zone_count": len(policy_engine.zones),
        },
        "audit": audit_log.get_stats(),
    }


# ═══════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════
# Serve frontend in production
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    print(f"""
╔══════════════════════════════════════════════╗
║  MIG Core v{VERSION}                           ║
║  Execution Control Engine                    ║
║  House of Galatine                           ║
║                                              ║
║  Mode: {MODE}                          ║
║  Policies: {len(policy_engine.policies):<3}                              ║
║  Zones: {len(policy_engine.zones):<3}                                 ║
║                                              ║
║  "Nothing executes without MIG approval."    ║
╚══════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=8000)
