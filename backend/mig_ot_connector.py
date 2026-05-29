"""
MIG OT Connector v2 — Modbus-to-MIG Bridge
House of Galatine © 2026

The OT Connector is the HANDS. MIG Core is the BRAIN.

OT Connector receives Modbus write requests, converts them to
text commands, sends them to MIG Core for validation, and only
forwards approved commands to the PLC.

Architecture:
    User/Agent → OT Connector (port 8001)
                    ↓
                MIG Core /validate (port 8000)
                    ↓
                ALLOW → OT Connector writes to PLC
                DENY  → OT Connector blocks
                APPROVAL → OT Connector holds for operator

MIG Core must be running on port 8000.
Start MIG Core first: docker compose up
Then start OT Connector: python mig_ot_connector.py
"""

import json
import time
import os
import requests
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from pyModbusTCP.client import ModbusClient
    MODBUS_AVAILABLE = True
except ImportError:
    MODBUS_AVAILABLE = False
    print("[OT Connector] pyModbusTCP not installed. Running in validation-only mode.")
    print("[OT Connector] Install with: pip install pyModbusTCP")


# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════

CONFIG_PATH = os.environ.get("MIG_OT_CONFIG", "./configs/ot_deployment_config.json")
MIG_CORE_URL = os.environ.get("MIG_CORE_URL", "http://localhost:8000")

def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

config = load_config(CONFIG_PATH)
print(f"[OT Connector] Deployment: {config['deployment']['name']}")
print(f"[OT Connector] MIG Core: {MIG_CORE_URL}")
print(f"[OT Connector] Equipment: {len(config['equipment'])} devices")
print(f"[OT Connector] Sensors: {len(config['sensors'])} readings")


# ═══════════════════════════════════════════════════════════
# EQUIPMENT LOOKUP
# ═══════════════════════════════════════════════════════════

def get_equipment_by_register(register_address: int) -> Optional[dict]:
    """Find which equipment owns this register."""
    for eq in config["equipment"]:
        for param, reg_info in eq["registers"].items():
            if reg_info["address"] == register_address:
                return {
                    "equipment": eq,
                    "parameter": param,
                    "register_info": reg_info
                }
    return None

def get_sensor_by_register(register_address: int) -> Optional[dict]:
    """Find which sensor maps to this register."""
    for sensor in config["sensors"]:
        if sensor["register"]["address"] == register_address:
            return sensor
    return None

def register_to_text(register: int, value: int) -> str:
    """Convert a Modbus register write to a text command for MIG Core."""
    eq_info = get_equipment_by_register(register)
    
    if eq_info:
        equipment = eq_info["equipment"]
        parameter = eq_info["parameter"]
        unit = eq_info["register_info"]["unit"]
        return f"Set {equipment['name']} {parameter} to {value} {unit}"
    
    return f"Write value {value} to register {register}"

def register_to_action_type(register: int, value: int) -> str:
    """Infer MIG action type from register write context."""
    eq_info = get_equipment_by_register(register)
    
    if not eq_info:
        return "write_unknown_register"
    
    equipment = eq_info["equipment"]
    parameter = eq_info["parameter"]
    limits = equipment.get("limits", {}).get(parameter, {})
    
    # Check if this is a safety zone equipment
    if equipment.get("zone") == "zone-safety":
        return "write_safety"
    
    # Check deviation from baseline
    baseline = limits.get("baseline", 50)
    if baseline > 0:
        deviation = abs(value - baseline) / baseline * 100
        if deviation > 5:
            return "write_setpoint_major"
        else:
            return "write_setpoint_minor"
    
    return "write_generic"

def get_equipment_context(register: int, value: int) -> str:
    """Build context string for MIG Core validation."""
    eq_info = get_equipment_by_register(register)
    
    if not eq_info:
        return f"Unknown register {register}. Not mapped to any equipment."
    
    equipment = eq_info["equipment"]
    parameter = eq_info["parameter"]
    unit = eq_info["register_info"]["unit"]
    limits = equipment.get("limits", {}).get(parameter, {})
    baseline = limits.get("baseline", 50)
    deviation = abs(value - baseline) / baseline * 100 if baseline > 0 else 0
    
    context_parts = [
        f"Equipment: {equipment['name']} ({equipment['type']})",
        f"Parameter: {parameter}",
        f"Requested value: {value} {unit}",
        f"Baseline: {baseline} {unit}",
        f"Deviation: {deviation:.1f}%",
        f"Zone: {equipment.get('zone', 'unknown')}",
    ]
    
    if limits:
        context_parts.append(f"Safe range: {limits.get('min_safe', '?')}-{limits.get('max_safe', '?')} {unit}")
        if limits.get("trip"):
            context_parts.append(f"Trip limit: {limits['trip']} {unit}")
    
    failure_modes = equipment.get("failure_modes", [])
    if failure_modes:
        context_parts.append(f"Failure risks: {'; '.join(failure_modes[:2])}")
    
    return " | ".join(context_parts)


# ═══════════════════════════════════════════════════════════
# MIG CORE CLIENT
# ═══════════════════════════════════════════════════════════

def call_mig_core(text: str, action_type: str, stage: str, 
                   zone: str = None, context: str = "") -> dict:
    """Send a validation request to MIG Core and get the decision."""
    try:
        response = requests.post(
            f"{MIG_CORE_URL}/validate",
            json={
                "text": text,
                "action_type": action_type,
                "stage": stage,
                "zone": zone,
                "context": context,
                "source": "ot_connector"
            },
            timeout=5
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            # MIG Core returned error — fail-closed
            return {
                "decision": "DENY",
                "decision_id": f"dec_failsafe_{int(time.time() * 1000)}",
                "risk_score": 100,
                "flags": ["MIG_CORE_ERROR"],
                "checks": [{"name": "MIG Core", "status": "fail", 
                           "detail": f"MIG Core returned status {response.status_code}"}],
                "matched_policy": "Fail-closed — MIG Core error",
                "policy_id": "FAIL_CLOSED",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    except requests.exceptions.ConnectionError:
        # MIG Core unreachable — fail-closed
        return {
            "decision": "DENY",
            "decision_id": f"dec_failsafe_{int(time.time() * 1000)}",
            "risk_score": 100,
            "flags": ["MIG_CORE_UNREACHABLE"],
            "checks": [{"name": "MIG Core", "status": "fail",
                        "detail": f"Cannot connect to MIG Core at {MIG_CORE_URL}. Fail-closed."}],
            "matched_policy": "Fail-closed — MIG Core unreachable",
            "policy_id": "FAIL_CLOSED",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except requests.exceptions.Timeout:
        return {
            "decision": "DENY",
            "decision_id": f"dec_failsafe_{int(time.time() * 1000)}",
            "risk_score": 100,
            "flags": ["MIG_CORE_TIMEOUT"],
            "checks": [{"name": "MIG Core", "status": "fail",
                        "detail": "MIG Core response timeout. Fail-closed."}],
            "matched_policy": "Fail-closed — MIG Core timeout",
            "policy_id": "FAIL_CLOSED",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ═══════════════════════════════════════════════════════════
# PLC CONNECTION
# ═══════════════════════════════════════════════════════════

class PLCProxy:
    """Connects to PLC via Modbus TCP. Only forwards MIG-approved commands."""
    
    def __init__(self, host: str, port: int = 502):
        self.host = host
        self.port = port
        self.client = None
        self.connected = False
        
        if MODBUS_AVAILABLE:
            self.client = ModbusClient(host=host, port=port, auto_open=True, timeout=5)
            if self.client.open():
                self.connected = True
                print(f"[OT Connector] Connected to PLC at {host}:{port}")
            else:
                print(f"[OT Connector] WARNING: Cannot connect to PLC at {host}:{port}")
    
    def read_register(self, address: int, count: int = 1) -> Optional[list]:
        if not self.client:
            return None
        return self.client.read_holding_registers(address, count)
    
    def read_input(self, address: int, count: int = 1) -> Optional[list]:
        if not self.client:
            return None
        return self.client.read_input_registers(address, count)
    
    def write_register(self, address: int, value: int) -> bool:
        if not self.client:
            return False
        return self.client.write_single_register(address, value)
    
    def get_current_value(self, address: int) -> Optional[int]:
        result = self.read_register(address, 1)
        if result and len(result) > 0:
            return result[0]
        return None


# ═══════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="MIG OT Connector",
    description="Modbus-to-MIG Bridge — Routes all validation through MIG Core",
    version="2.0.0"
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Current operational mode
current_mode = config["modes"]["current"]

# PLC connection
plc_proxy = None
plc_host = config["plc_connection"]["host"]
if plc_host != "PLC_IP_HERE" and MODBUS_AVAILABLE:
    plc_proxy = PLCProxy(plc_host, config["plc_connection"]["port"])

# Track pending approvals
pending_approvals = {}

# Audit log
audit_log = []


class WriteCommand(BaseModel):
    register: int
    value: int
    source: str = "operator"

class ReadCommand(BaseModel):
    register: int
    source: str = "operator"

class TextCommand(BaseModel):
    text: str
    source: str = "operator"

class ModeChange(BaseModel):
    mode: str

class ApproveCommand(BaseModel):
    decision_id: str
    approved_by: str

class RejectCommand(BaseModel):
    decision_id: str
    rejected_by: str
    reason: str = ""


@app.get("/health")
def health():
    # Check MIG Core connection
    mig_core_status = "unknown"
    try:
        r = requests.get(f"{MIG_CORE_URL}/health", timeout=3)
        if r.status_code == 200:
            mig_core_status = "connected"
        else:
            mig_core_status = "error"
    except:
        mig_core_status = "unreachable"
    
    return {
        "status": "healthy",
        "version": "2.0.0",
        "deployment": config["deployment"]["name"],
        "mig_core": mig_core_status,
        "mig_core_url": MIG_CORE_URL,
        "plc_connected": plc_proxy.connected if plc_proxy else False,
        "plc_host": plc_host,
        "equipment_count": len(config["equipment"]),
        "sensor_count": len(config["sensors"]),
        "current_mode": current_mode,
        "pending_approvals": len(pending_approvals),
        "total_decisions": len(audit_log)
    }


@app.post("/write")
def write_to_plc(cmd: WriteCommand):
    """
    Validate a Modbus write through MIG Core, then execute if approved.
    
    Flow:
    1. Convert register+value to text command
    2. Send to MIG Core /validate
    3. If ALLOW → write to PLC
    4. If DENY → block
    5. If APPROVAL → hold for operator
    """
    
    # Step 1: Convert to text command
    text = register_to_text(cmd.register, cmd.value)
    action_type = register_to_action_type(cmd.register, cmd.value)
    context = get_equipment_context(cmd.register, cmd.value)
    
    # Get equipment zone if available
    eq_info = get_equipment_by_register(cmd.register)
    zone = eq_info["equipment"].get("zone") if eq_info else None
    
    # Step 2: Send to MIG Core for validation
    mig_result = call_mig_core(
        text=text,
        action_type=action_type,
        stage=current_mode,
        zone=zone,
        context=context
    )
    
    # Build response
    response = {
        "command": {
            "register": cmd.register,
            "value": cmd.value,
            "text": text,
            "action_type": action_type,
            "source": cmd.source
        },
        "equipment": {
            "id": eq_info["equipment"]["id"],
            "name": eq_info["equipment"]["name"],
            "type": eq_info["equipment"]["type"],
            "parameter": eq_info["parameter"],
            "unit": eq_info["register_info"]["unit"]
        } if eq_info else None,
        "context": context,
        "mig_validation": mig_result,
        "decision": mig_result["decision"],
        "executed": False,
        "execution_detail": ""
    }
    
    # Step 3: Execute based on MIG Core decision
    if mig_result["decision"] == "ALLOW":
        if plc_proxy and plc_proxy.connected:
            success = plc_proxy.write_register(cmd.register, cmd.value)
            response["executed"] = success
            response["execution_detail"] = "Command forwarded to PLC — MIG Core approved" if success else "PLC write failed"
            
            # Read back to confirm
            if success:
                readback = plc_proxy.get_current_value(cmd.register)
                response["plc_readback"] = readback
        else:
            response["executed"] = False
            response["execution_detail"] = "MIG Core approved — no PLC connected (validation-only mode)"
    
    elif mig_result["decision"] == "APPROVAL":
        # Store for operator approval
        decision_id = mig_result.get("decision_id", f"dec_{int(time.time() * 1000)}")
        pending_approvals[decision_id] = {
            "command": cmd.dict(),
            "text": text,
            "equipment": response["equipment"],
            "context": context,
            "mig_result": mig_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "pending"
        }
        response["executed"] = False
        response["execution_detail"] = f"Command held for operator approval — decision ID: {decision_id}"
    
    else:  # DENY
        response["executed"] = False
        response["execution_detail"] = "Command BLOCKED by MIG Core — PLC never received this command"
    
    # Log
    audit_log.append(response)
    
    return response


@app.post("/text")
def validate_text_command(cmd: TextCommand):
    """
    Send a text command directly to MIG Core for validation.
    Useful for testing without specifying registers.
    """
    mig_result = call_mig_core(
        text=cmd.text,
        action_type="",
        stage=current_mode,
        context=f"Source: {cmd.source}"
    )
    
    return {
        "command": cmd.text,
        "source": cmd.source,
        "mig_validation": mig_result,
        "decision": mig_result["decision"]
    }


@app.post("/read")
def read_from_plc(cmd: ReadCommand):
    """Read from PLC — reads are generally allowed without MIG validation."""
    
    sensor = get_sensor_by_register(cmd.register)
    eq_info = get_equipment_by_register(cmd.register)
    
    target_name = "unknown"
    if sensor:
        target_name = sensor["name"]
    elif eq_info:
        target_name = f"{eq_info['equipment']['name']} — {eq_info['parameter']}"
    
    value = None
    if plc_proxy and plc_proxy.connected:
        if sensor and sensor["register"]["type"] == "input":
            raw = plc_proxy.read_input(cmd.register, 1)
        else:
            raw = plc_proxy.read_register(cmd.register, 1)
        value = raw[0] if raw else None
    
    return {
        "decision": "ALLOW",
        "register": cmd.register,
        "target": target_name,
        "value": value,
        "detail": f"Read from register {cmd.register} ({target_name}). Non-destructive operation."
    }


@app.post("/approve")
def approve_pending(cmd: ApproveCommand):
    """Operator approves a pending command — executes the write to PLC."""
    
    if cmd.decision_id not in pending_approvals:
        raise HTTPException(status_code=404, detail="Decision not found in pending approvals")
    
    pending = pending_approvals[cmd.decision_id]
    
    if pending["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Decision already {pending['status']}")
    
    # Execute the write
    original_cmd = pending["command"]
    executed = False
    readback = None
    
    if plc_proxy and plc_proxy.connected:
        executed = plc_proxy.write_register(original_cmd["register"], original_cmd["value"])
        if executed:
            readback = plc_proxy.get_current_value(original_cmd["register"])
    
    # Update pending status
    pending["status"] = "approved"
    pending["approved_by"] = cmd.approved_by
    pending["approved_at"] = datetime.now(timezone.utc).isoformat()
    pending["executed"] = executed
    pending["plc_readback"] = readback
    
    # Also approve in MIG Core audit
    try:
        requests.post(f"{MIG_CORE_URL}/approve", json={
            "decision_id": cmd.decision_id,
            "approved_by": cmd.approved_by
        }, timeout=3)
    except:
        pass
    
    return {
        "status": "approved",
        "decision_id": cmd.decision_id,
        "approved_by": cmd.approved_by,
        "command": pending["text"],
        "executed": executed,
        "plc_readback": readback,
        "detail": "Command approved and forwarded to PLC" if executed else "Command approved — no PLC connected"
    }


@app.post("/reject")
def reject_pending(cmd: RejectCommand):
    """Operator rejects a pending command."""
    
    if cmd.decision_id not in pending_approvals:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    pending = pending_approvals[cmd.decision_id]
    pending["status"] = "rejected"
    pending["rejected_by"] = cmd.rejected_by
    pending["reject_reason"] = cmd.reason
    pending["rejected_at"] = datetime.now(timezone.utc).isoformat()
    
    # Also reject in MIG Core audit
    try:
        requests.post(f"{MIG_CORE_URL}/reject", json={
            "decision_id": cmd.decision_id,
            "rejected_by": cmd.rejected_by,
            "reason": cmd.reason
        }, timeout=3)
    except:
        pass
    
    return {
        "status": "rejected",
        "decision_id": cmd.decision_id,
        "rejected_by": cmd.rejected_by,
        "reason": cmd.reason,
        "command": pending["text"]
    }


@app.get("/pending")
def get_pending_approvals():
    """List all commands waiting for operator approval."""
    pending = {k: v for k, v in pending_approvals.items() if v["status"] == "pending"}
    return {
        "count": len(pending),
        "pending": pending
    }


@app.get("/status")
def get_plant_status():
    """Read all sensor and equipment values from PLC."""
    status = {
        "deployment": config["deployment"]["name"],
        "mode": current_mode,
        "mig_core": MIG_CORE_URL,
        "plc_connected": plc_proxy.connected if plc_proxy else False,
        "sensors": {},
        "equipment": {}
    }
    
    for sensor in config["sensors"]:
        addr = sensor["register"]["address"]
        value = None
        if plc_proxy and plc_proxy.connected:
            if sensor["register"]["type"] == "input":
                raw = plc_proxy.read_input(addr, 1)
            else:
                raw = plc_proxy.read_register(addr, 1)
            value = raw[0] if raw else None
        
        status["sensors"][sensor["id"]] = {
            "name": sensor["name"],
            "value": value,
            "unit": sensor["unit"],
            "normal_range": sensor["normal_range"]
        }
    
    for eq in config["equipment"]:
        eq_status = {"name": eq["name"], "type": eq["type"], "parameters": {}}
        for param, reg_info in eq["registers"].items():
            value = None
            if plc_proxy and plc_proxy.connected:
                raw = plc_proxy.read_register(reg_info["address"], 1)
                value = raw[0] if raw else None
            eq_status["parameters"][param] = {
                "value": value,
                "unit": reg_info["unit"],
                "limits": eq.get("limits", {}).get(param, {})
            }
        status["equipment"][eq["id"]] = eq_status
    
    return status


@app.post("/mode")
def change_mode(cmd: ModeChange):
    """Change operational mode."""
    global current_mode
    available = config["modes"]["available"]
    
    if cmd.mode not in available:
        raise HTTPException(status_code=400, 
                          detail=f"Invalid mode. Available: {available}")
    
    old_mode = current_mode
    current_mode = cmd.mode
    
    return {"status": "mode_changed", "from": old_mode, "to": current_mode}


@app.get("/equipment")
def list_equipment():
    return {"equipment": config["equipment"], "count": len(config["equipment"])}


@app.get("/sensors")
def list_sensors():
    return {"sensors": config["sensors"], "count": len(config["sensors"])}


@app.get("/audit")
def get_audit(limit: int = 50):
    return {
        "count": len(audit_log[-limit:]),
        "decisions": list(reversed(audit_log[-limit:]))
    }


@app.get("/config")
def get_config():
    return {
        "deployment": config["deployment"],
        "equipment_count": len(config["equipment"]),
        "sensor_count": len(config["sensors"]),
        "current_mode": current_mode,
        "available_modes": config["modes"]["available"],
        "mig_core_url": MIG_CORE_URL,
        "plc_host": plc_host
    }


if __name__ == "__main__":
    import uvicorn
    
    # Verify MIG Core is reachable
    mig_status = "UNKNOWN"
    try:
        r = requests.get(f"{MIG_CORE_URL}/health", timeout=3)
        if r.status_code == 200:
            mig_data = r.json()
            mig_status = f"CONNECTED ({mig_data.get('policy_count', '?')} policies)"
        else:
            mig_status = "ERROR"
    except:
        mig_status = "UNREACHABLE — start MIG Core first!"
    
    print(f"""
╔══════════════════════════════════════════════════════╗
║  MIG OT Connector v2.0.0                            ║
║  Modbus-to-MIG Bridge                                ║
║  House of Galatine                                   ║
║                                                      ║
║  MIG Core:   {mig_status:<38} ║
║  PLC:        {plc_host:<38} ║
║  Equipment:  {len(config['equipment']):<38} ║
║  Sensors:    {len(config['sensors']):<38} ║
║  Mode:       {current_mode:<38} ║
║                                                      ║
║  Brain: MIG Core validates every command             ║
║  Hands: OT Connector talks to the PLC               ║
║                                                      ║
║  "Nothing reaches the controller without approval."  ║
╚══════════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=8001)
              
