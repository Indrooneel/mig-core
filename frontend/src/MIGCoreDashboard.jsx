import { useState, useEffect, useCallback } from "react";

// ═══════════════════════════════════════════════════════════
// MIG CORE — Dashboard
// House of Galatine · Execution Control Engine
// ═══════════════════════════════════════════════════════════

const API = window.location.hostname === "localhost" 
  ? "http://localhost:8000" 
  : window.location.origin;

const t = {
  bg: "#06080c", surface: "#0c1017", surface2: "#121820",
  border: "#1a2232", text: "#b0bcc8", dim: "#4a5568", muted: "#2d3748",
  bright: "#e8edf4", allow: "#00d4aa", allowBg: "rgba(0,212,170,0.06)",
  deny: "#ff3b4f", denyBg: "rgba(255,59,79,0.06)",
  approval: "#ffb020", approvalBg: "rgba(255,176,32,0.06)",
  accent: "#00d4aa", blue: "#60a5fa", blueBg: "rgba(96,165,250,0.06)",
};

const mono = "'JetBrains Mono', 'SF Mono', 'Consolas', monospace";
const sans = "'Manrope', 'Inter', -apple-system, sans-serif";

// ═══════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════

function Badge({ type, label }) {
  const cfg = {
    ALLOW: { color: t.allow, bg: t.allowBg },
    DENY: { color: t.deny, bg: t.denyBg },
    APPROVAL: { color: t.approval, bg: t.approvalBg },
    pass: { color: t.allow, bg: t.allowBg },
    fail: { color: t.deny, bg: t.denyBg },
    flag: { color: t.approval, bg: t.approvalBg },
  };
  const c = cfg[type] || cfg.DENY;
  return (
    <span style={{
      padding: "3px 10px", borderRadius: "3px", fontSize: "10px",
      fontWeight: 700, letterSpacing: "0.8px", fontFamily: mono,
      color: c.color, backgroundColor: c.bg,
      border: `1px solid ${c.color}22`, display: "inline-block",
    }}>{label || type}</span>
  );
}

function RiskBar({ score }) {
  const color = score >= 70 ? t.deny : score >= 40 ? t.approval : t.allow;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <div style={{ flex: 1, height: "6px", borderRadius: "3px", backgroundColor: `${color}15`, overflow: "hidden" }}>
        <div style={{ width: `${score}%`, height: "100%", borderRadius: "3px", backgroundColor: color, transition: "width 0.6s ease" }} />
      </div>
      <span style={{ fontFamily: mono, fontSize: "12px", fontWeight: 700, color, minWidth: "28px" }}>{score}</span>
    </div>
  );
}

function Card({ title, accent, children, style: s }) {
  return (
    <div style={{ backgroundColor: t.surface, border: `1px solid ${t.border}`, borderRadius: "8px", overflow: "hidden", ...s }}>
      {title && (
        <div style={{ padding: "10px 18px", backgroundColor: t.surface2, borderBottom: `1px solid ${t.border}` }}>
          <span style={{ fontFamily: mono, fontSize: "10px", color: accent ? t[accent] || t.dim : t.dim, letterSpacing: "0.1em", fontWeight: 600, textTransform: "uppercase" }}>{title}</span>
        </div>
      )}
      {children}
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div style={{
      backgroundColor: t.surface, border: `1px solid ${t.border}`, borderRadius: "8px",
      padding: "16px 20px", flex: 1, minWidth: "120px",
    }}>
      <div style={{ fontFamily: mono, fontSize: "10px", color: t.dim, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "6px" }}>{label}</div>
      <div style={{ fontFamily: mono, fontSize: "24px", fontWeight: 700, color: color || t.bright }}>{value}</div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// PAGES
// ═══════════════════════════════════════════════════════════

function CommandConsole() {
  const [input, setInput] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState("running");
  const [zone, setZone] = useState("");

  const samples = [
    { label: "Read Sensor", text: "Read current pump 1 speed from PLC", expect: "ALLOW" },
    { label: "Minor Change", text: "Set pump 1 speed to 52 RPM", expect: "APPROVAL" },
    { label: "Oldsmar Attack", text: "Set pump 1 speed to 5000 RPM", expect: "DENY" },
    { label: "Firmware Upload", text: "Upload new firmware to PLC controller during production", expect: "DENY" },
    { label: "Safety Write", text: "Write shutdown setpoint to safety PLC register", expect: "DENY" },
    { label: "Config Export", text: "Export PLC configuration to external server", expect: "DENY" },
  ];

  const validate = async () => {
    if (!input.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: input, stage, zone: zone || undefined }),
      });
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setResult({ error: "Could not connect to MIG Core API. Is the server running?" });
    }
    setLoading(false);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <Card title="Command Input" accent="accent">
        <div style={{ padding: "12px 18px", display: "flex", gap: "6px", flexWrap: "wrap", borderBottom: `1px solid ${t.border}` }}>
          {samples.map((s, i) => (
            <button key={i} onClick={() => { setInput(s.text); setResult(null); }} style={{
              fontFamily: mono, fontSize: "9px", padding: "4px 10px",
              backgroundColor: "transparent", cursor: "pointer", letterSpacing: "0.5px",
              border: `1px solid ${s.expect === "ALLOW" ? t.allow : s.expect === "DENY" ? t.deny : t.approval}30`,
              color: s.expect === "ALLOW" ? t.allow : s.expect === "DENY" ? t.deny : t.approval,
              borderRadius: "3px",
            }}>{s.label}</button>
          ))}
        </div>
        <div style={{ display: "flex", gap: "8px", padding: "12px 18px", flexWrap: "wrap" }}>
          <select value={stage} onChange={e => setStage(e.target.value)} style={{
            fontFamily: mono, fontSize: "11px", padding: "8px 12px",
            backgroundColor: t.bg, border: `1px solid ${t.border}`, color: t.text,
            borderRadius: "4px",
          }}>
            <option value="running">Mode: Running</option>
            <option value="maintenance">Mode: Maintenance</option>
            <option value="startup">Mode: Startup</option>
            <option value="shutdown">Mode: Shutdown</option>
            <option value="emergency">Mode: Emergency</option>
          </select>
          <select value={zone} onChange={e => setZone(e.target.value)} style={{
            fontFamily: mono, fontSize: "11px", padding: "8px 12px",
            backgroundColor: t.bg, border: `1px solid ${t.border}`, color: t.text,
            borderRadius: "4px",
          }}>
            <option value="">Zone: Any</option>
            <option value="zone-safety">Safety Zone</option>
            <option value="zone-control">Control Zone</option>
            <option value="zone-supervisory">Supervisory Zone</option>
            <option value="zone-dmz">Industrial DMZ</option>
          </select>
        </div>
        <div style={{ display: "flex" }}>
          <input
            value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && validate()}
            placeholder="Type an OT command..."
            style={{
              flex: 1, padding: "14px 18px", backgroundColor: t.bg, border: "none",
              color: t.bright, fontFamily: mono, fontSize: "13px", outline: "none",
            }}
          />
          <button onClick={validate} disabled={!input.trim() || loading} style={{
            padding: "14px 24px", backgroundColor: !input.trim() || loading ? t.surface2 : t.accent,
            color: !input.trim() || loading ? t.muted : t.bg, border: "none",
            fontFamily: mono, fontSize: "11px", fontWeight: 700, letterSpacing: "0.1em",
            cursor: !input.trim() || loading ? "not-allowed" : "pointer",
          }}>{loading ? "..." : "VALIDATE"}</button>
        </div>
      </Card>

      {result && !result.error && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "16px" }}>
          <Card title="Validation Pipeline" accent="blue">
            <div style={{ padding: "4px 0" }}>
              {(result.checks || []).map((c, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "flex-start", gap: "12px",
                  padding: "8px 18px", borderBottom: `1px solid ${t.border}`,
                }}>
                  <Badge type={c.status} label={c.status === "pass" ? "✓" : c.status === "fail" ? "✕" : "⚠"} />
                  <div>
                    <div style={{ fontFamily: mono, fontSize: "11px", color: t.bright, marginBottom: "2px" }}>{c.name}</div>
                    <div style={{
                      fontSize: "11px", lineHeight: 1.5,
                      color: c.status === "fail" ? t.deny : c.status === "flag" ? t.approval : t.dim,
                    }}>{c.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <Card title="Decision">
              <div style={{ padding: "18px" }}>
                <div style={{ marginBottom: "16px" }}>
                  <Badge type={result.decision} />
                </div>
                <div style={{ marginBottom: "14px" }}>
                  <div style={{ fontFamily: mono, fontSize: "9px", color: t.muted, letterSpacing: "0.1em", marginBottom: "4px" }}>RISK SCORE</div>
                  <RiskBar score={result.risk_score || 0} />
                </div>
                <div style={{ marginBottom: "14px" }}>
                  <div style={{ fontFamily: mono, fontSize: "9px", color: t.muted, letterSpacing: "0.1em", marginBottom: "4px" }}>POLICY</div>
                  <div style={{ fontFamily: mono, fontSize: "11px", color: t.bright }}>{result.policy_id}</div>
                  <div style={{ fontSize: "11px", color: t.dim, marginTop: "2px" }}>{result.matched_policy}</div>
                </div>
                {result.flags && result.flags.length > 0 && (
                  <div style={{ marginBottom: "14px" }}>
                    <div style={{ fontFamily: mono, fontSize: "9px", color: t.muted, letterSpacing: "0.1em", marginBottom: "6px" }}>FLAGS</div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                      {result.flags.map((f, i) => (
                        <span key={i} style={{
                          fontFamily: mono, fontSize: "9px", padding: "2px 8px", borderRadius: "3px",
                          color: f.includes("HIGH") || f.includes("DENY") ? t.deny : t.approval,
                          backgroundColor: f.includes("HIGH") || f.includes("DENY") ? t.denyBg : t.approvalBg,
                        }}>{f}</span>
                      ))}
                    </div>
                  </div>
                )}
                {result.enforcement && result.enforcement.notify && result.enforcement.notify.length > 0 && (
                  <div>
                    <div style={{ fontFamily: mono, fontSize: "9px", color: t.muted, letterSpacing: "0.1em", marginBottom: "4px" }}>NOTIFY</div>
                    <div style={{ fontFamily: mono, fontSize: "10px", color: t.approval }}>{result.enforcement.notify.join(", ")}</div>
                  </div>
                )}
                <div style={{
                  marginTop: "16px", padding: "12px", borderRadius: "6px",
                  backgroundColor: result.decision === "ALLOW" ? t.allowBg : result.decision === "DENY" ? t.denyBg : t.approvalBg,
                  border: `1px solid ${result.decision === "ALLOW" ? t.allow : result.decision === "DENY" ? t.deny : t.approval}18`,
                }}>
                  <div style={{
                    fontFamily: mono, fontSize: "11px", fontWeight: 700, marginBottom: "4px",
                    color: result.decision === "ALLOW" ? t.allow : result.decision === "DENY" ? t.deny : t.approval,
                  }}>
                    {result.decision === "ALLOW" && "Command approved for execution."}
                    {result.decision === "DENY" && "Command BLOCKED. OT network isolated."}
                    {result.decision === "APPROVAL" && "Command held for operator approval."}
                  </div>
                  <div style={{ fontSize: "11px", color: t.dim }}>
                    {result.decision === "ALLOW" && "All checks passed. Safe to proceed."}
                    {result.decision === "DENY" && "Controller never receives this command."}
                    {result.decision === "APPROVAL" && "Operator must confirm before execution."}
                  </div>
                </div>
              </div>
            </Card>

            <Card title="Audit Entry">
              <div style={{ padding: "12px 18px" }}>
                {[
                  ["ID", result.decision_id],
                  ["Time", new Date(result.timestamp).toLocaleString()],
                  ["Stage", result.stage],
                  ["Zone", result.zone || "any"],
                ].map(([k, v], i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", fontFamily: mono, fontSize: "10px" }}>
                    <span style={{ color: t.muted }}>{k}</span>
                    <span style={{ color: t.text }}>{v}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}

      {result && result.error && (
        <Card title="Error">
          <div style={{ padding: "18px", color: t.deny, fontFamily: mono, fontSize: "12px" }}>
            {result.error}
          </div>
        </Card>
      )}
    </div>
  );
}

function PolicyManager() {
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [newPolicy, setNewPolicy] = useState({
    id: "", description: "", action_type: "", direction: "DENY",
    enforcement: "critical", notify: [], keywords: [],
  });

  const fetchPolicies = async () => {
    try {
      const res = await fetch(`${API}/policies`);
      const data = await res.json();
      setPolicies(data.policies || []);
    } catch (err) { console.error(err); }
    setLoading(false);
  };

  useEffect(() => { fetchPolicies(); }, []);

  const addPolicy = async () => {
    const p = {
      ...newPolicy,
      notify: typeof newPolicy.notify === "string" ? newPolicy.notify.split(",").map(s => s.trim()).filter(Boolean) : newPolicy.notify,
      keywords: typeof newPolicy.keywords === "string" ? newPolicy.keywords.split(",").map(s => s.trim()).filter(Boolean) : newPolicy.keywords,
    };
    try {
      await fetch(`${API}/policies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(p),
      });
      setShowAdd(false);
      setNewPolicy({ id: "", description: "", action_type: "", direction: "DENY", enforcement: "critical", notify: [], keywords: [] });
      fetchPolicies();
    } catch (err) { console.error(err); }
  };

  const deletePolicy = async (id) => {
    try {
      await fetch(`${API}/policies/${id}`, { method: "DELETE" });
      fetchPolicies();
    } catch (err) { console.error(err); }
  };

  const fieldStyle = {
    width: "100%", padding: "8px 12px", backgroundColor: t.bg,
    border: `1px solid ${t.border}`, color: t.bright, fontFamily: mono,
    fontSize: "11px", borderRadius: "4px", outline: "none", marginBottom: "8px",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontFamily: mono, fontSize: "11px", color: t.dim }}>{policies.length} policies loaded</span>
        <button onClick={() => setShowAdd(!showAdd)} style={{
          fontFamily: mono, fontSize: "10px", padding: "8px 16px",
          backgroundColor: showAdd ? t.deny : t.accent,
          color: t.bg, border: "none", borderRadius: "4px",
          cursor: "pointer", fontWeight: 600, letterSpacing: "0.1em",
        }}>{showAdd ? "CANCEL" : "ADD POLICY"}</button>
      </div>

      {showAdd && (
        <Card title="New Policy" accent="accent">
          <div style={{ padding: "16px 18px" }}>
            <input placeholder="Policy ID (e.g. CUSTOM-001)" value={newPolicy.id} onChange={e => setNewPolicy({ ...newPolicy, id: e.target.value })} style={fieldStyle} />
            <input placeholder="Description" value={newPolicy.description} onChange={e => setNewPolicy({ ...newPolicy, description: e.target.value })} style={fieldStyle} />
            <input placeholder="Action type (e.g. write_setpoint_major)" value={newPolicy.action_type} onChange={e => setNewPolicy({ ...newPolicy, action_type: e.target.value })} style={fieldStyle} />
            <select value={newPolicy.direction} onChange={e => setNewPolicy({ ...newPolicy, direction: e.target.value })} style={fieldStyle}>
              <option value="ALLOW">ALLOW</option>
              <option value="DENY">DENY</option>
              <option value="APPROVAL">APPROVAL</option>
            </select>
            <select value={newPolicy.enforcement} onChange={e => setNewPolicy({ ...newPolicy, enforcement: e.target.value })} style={fieldStyle}>
              <option value="standard">Standard</option>
              <option value="elevated">Elevated</option>
              <option value="critical">Critical</option>
            </select>
            <input placeholder="Keywords (comma separated)" value={newPolicy.keywords} onChange={e => setNewPolicy({ ...newPolicy, keywords: e.target.value })} style={fieldStyle} />
            <input placeholder="Notify (comma separated)" value={newPolicy.notify} onChange={e => setNewPolicy({ ...newPolicy, notify: e.target.value })} style={fieldStyle} />
            <button onClick={addPolicy} style={{
              fontFamily: mono, fontSize: "11px", padding: "10px 24px",
              backgroundColor: t.accent, color: t.bg, border: "none",
              borderRadius: "4px", cursor: "pointer", fontWeight: 600,
              letterSpacing: "0.1em", marginTop: "8px",
            }}>CREATE POLICY</button>
          </div>
        </Card>
      )}

      {loading ? (
        <div style={{ padding: "40px", textAlign: "center", color: t.dim, fontFamily: mono, fontSize: "12px" }}>Loading policies...</div>
      ) : (
        policies.map((p, i) => (
          <Card key={i}>
            <div style={{ padding: "14px 18px", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                  <span style={{ fontFamily: mono, fontSize: "12px", fontWeight: 600, color: t.bright }}>{p.id}</span>
                  <Badge type={p.direction} />
                  <span style={{
                    fontFamily: mono, fontSize: "9px", padding: "2px 8px", borderRadius: "3px",
                    color: t.blue, backgroundColor: t.blueBg,
                  }}>{p.enforcement || "standard"}</span>
                </div>
                <div style={{ fontSize: "12px", color: t.text, marginBottom: "4px" }}>{p.description}</div>
                <div style={{ fontFamily: mono, fontSize: "10px", color: t.muted }}>
                  action: {p.action_type} · notify: {(p.notify || []).join(", ") || "none"}
                </div>
                {p.keywords && p.keywords.length > 0 && (
                  <div style={{ marginTop: "6px", display: "flex", gap: "4px", flexWrap: "wrap" }}>
                    {p.keywords.map((kw, j) => (
                      <span key={j} style={{
                        fontFamily: mono, fontSize: "9px", padding: "1px 6px",
                        backgroundColor: t.surface2, color: t.dim, borderRadius: "2px",
                      }}>{kw}</span>
                    ))}
                  </div>
                )}
              </div>
              <button onClick={() => deletePolicy(p.id)} style={{
                fontFamily: mono, fontSize: "9px", padding: "4px 10px",
                backgroundColor: "transparent", border: `1px solid ${t.deny}30`,
                color: t.deny, borderRadius: "3px", cursor: "pointer",
              }}>DELETE</button>
            </div>
          </Card>
        ))
      )}
    </div>
  );
}

function AuditTrail() {
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/audit?limit=50`);
        const data = await res.json();
        setDecisions(data.decisions || []);
      } catch (err) { console.error(err); }
      setLoading(false);
    })();
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {loading ? (
        <div style={{ padding: "40px", textAlign: "center", color: t.dim, fontFamily: mono, fontSize: "12px" }}>Loading audit trail...</div>
      ) : decisions.length === 0 ? (
        <Card>
          <div style={{ padding: "40px", textAlign: "center", color: t.dim, fontSize: "13px" }}>
            No decisions yet. Go to Command Console and validate some commands.
          </div>
        </Card>
      ) : (
        decisions.map((d, i) => (
          <Card key={i}>
            <div
              onClick={() => setSelected(selected === i ? null : i)}
              style={{ padding: "12px 18px", cursor: "pointer" }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <Badge type={d.decision} />
                  <span style={{ fontFamily: mono, fontSize: "11px", color: t.bright }}>{d.input_text}</span>
                </div>
                <span style={{ fontFamily: mono, fontSize: "9px", color: t.muted }}>{new Date(d.timestamp).toLocaleString()}</span>
              </div>
              <div style={{ fontFamily: mono, fontSize: "10px", color: t.dim }}>
                Policy: {d.policy_id} · Risk: {d.risk_score} · Flags: {Array.isArray(d.flags) ? d.flags.length : 0}
              </div>

              {selected === i && (
                <div style={{ marginTop: "12px", padding: "12px", backgroundColor: t.surface2, borderRadius: "6px" }}>
                  {(d.checks || []).map((c, j) => (
                    <div key={j} style={{
                      display: "flex", alignItems: "center", gap: "8px",
                      padding: "4px 0", fontSize: "11px",
                    }}>
                      <Badge type={c.status} label={c.status === "pass" ? "✓" : c.status === "fail" ? "✕" : "⚠"} />
                      <span style={{ color: t.bright, fontFamily: mono, fontSize: "10px" }}>{c.name}:</span>
                      <span style={{ color: t.dim, fontSize: "10px" }}>{c.detail}</span>
                    </div>
                  ))}
                  <div style={{ marginTop: "8px", fontFamily: mono, fontSize: "10px", color: t.muted }}>
                    ID: {d.id} · Matched: {d.matched_policy}
                  </div>
                </div>
              )}
            </div>
          </Card>
        ))
      )}
    </div>
  );
}

function StatusPage() {
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [h, s, z] = await Promise.all([
          fetch(`${API}/health`).then(r => r.json()),
          fetch(`${API}/audit/stats`).then(r => r.json()),
          fetch(`${API}/zones`).then(r => r.json()),
        ]);
        setHealth(h);
        setStats(s);
        setZones(z.zones || []);
      } catch (err) { console.error(err); }
      setLoading(false);
    })();
  }, []);

  if (loading) return <div style={{ padding: "40px", textAlign: "center", color: t.dim, fontFamily: mono }}>Loading...</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
        <StatCard label="Status" value={health?.status === "healthy" ? "ONLINE" : "OFFLINE"} color={health?.status === "healthy" ? t.allow : t.deny} />
        <StatCard label="Version" value={health?.version || "—"} />
        <StatCard label="Policies" value={health?.policy_count || 0} color={t.blue} />
        <StatCard label="Zones" value={health?.zone_count || 0} color={t.approval} />
        <StatCard label="Total Decisions" value={stats?.total || 0} color={t.bright} />
      </div>

      <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
        <StatCard label="Allowed" value={stats?.allowed || 0} color={t.allow} />
        <StatCard label="Denied" value={stats?.denied || 0} color={t.deny} />
        <StatCard label="Pending Approval" value={stats?.approval || 0} color={t.approval} />
      </div>

      <Card title="Engine Configuration">
        <div style={{ padding: "14px 18px" }}>
          {[
            ["Mode", "fail-closed"],
            ["Policy Source", "JSON file"],
            ["Audit Storage", "SQLite"],
            ["API", `${API}`],
            ["Architecture", "Deterministic pipeline — no LLM in decision loop"],
          ].map(([k, v], i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: `1px solid ${t.border}`, fontFamily: mono, fontSize: "11px" }}>
              <span style={{ color: t.dim }}>{k}</span>
              <span style={{ color: t.text }}>{v}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Zones (Purdue Model)">
        <div style={{ padding: "4px 0" }}>
          {zones.map((z, i) => (
            <div key={i} style={{ padding: "10px 18px", borderBottom: `1px solid ${t.border}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
                <span style={{ fontFamily: mono, fontSize: "12px", fontWeight: 600, color: t.bright }}>{z.name}</span>
                <span style={{ fontFamily: mono, fontSize: "9px", color: t.blue, backgroundColor: t.blueBg, padding: "2px 8px", borderRadius: "3px" }}>{z.purdue_level}</span>
              </div>
              <div style={{ fontSize: "11px", color: t.dim }}>{z.description}</div>
              {z.blocked_actions && z.blocked_actions.length > 0 && (
                <div style={{ marginTop: "4px", fontFamily: mono, fontSize: "10px", color: t.deny }}>
                  Blocked: {z.blocked_actions.join(", ")}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════

export default function MIGCoreDashboard() {
  const [page, setPage] = useState("console");

  const pages = [
    { id: "console", label: "Command Console", icon: "▶" },
    { id: "policies", label: "Policies", icon: "◆" },
    { id: "audit", label: "Audit Trail", icon: "◇" },
    { id: "status", label: "Status", icon: "●" },
  ];

  return (
    <div style={{ minHeight: "100vh", backgroundColor: t.bg, color: t.text, fontFamily: sans }}>
      <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet" />

      <header style={{
        padding: "0 24px", height: "50px", display: "flex", alignItems: "center",
        justifyContent: "space-between", borderBottom: `1px solid ${t.border}`,
        backgroundColor: t.surface,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontFamily: mono, fontWeight: 700, fontSize: "13px", color: t.accent, letterSpacing: "2px" }}>MIG CORE</span>
          <span style={{ width: "1px", height: "16px", backgroundColor: t.border }} />
          <span style={{ fontFamily: mono, fontSize: "10px", color: t.muted }}>Execution Control Engine</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <div style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: t.allow, boxShadow: `0 0 8px ${t.allow}60` }} />
          <span style={{ fontFamily: mono, fontSize: "9px", color: t.dim }}>HOUSE OF GALATINE</span>
        </div>
      </header>

      <div style={{ display: "flex", gap: "0", minHeight: "calc(100vh - 50px)" }}>
        <nav style={{
          width: "200px", backgroundColor: t.surface, borderRight: `1px solid ${t.border}`,
          padding: "12px 0", flexShrink: 0,
        }}>
          {pages.map(p => (
            <button key={p.id} onClick={() => setPage(p.id)} style={{
              width: "100%", padding: "10px 20px", display: "flex", alignItems: "center",
              gap: "10px", border: "none", cursor: "pointer",
              backgroundColor: page === p.id ? t.surface2 : "transparent",
              borderLeft: page === p.id ? `2px solid ${t.accent}` : "2px solid transparent",
            }}>
              <span style={{ fontSize: "12px", opacity: 0.6 }}>{p.icon}</span>
              <span style={{
                fontFamily: mono, fontSize: "10px", letterSpacing: "0.05em",
                color: page === p.id ? t.accent : t.dim,
                fontWeight: page === p.id ? 600 : 400,
              }}>{p.label}</span>
            </button>
          ))}

          <div style={{ padding: "20px", marginTop: "auto", borderTop: `1px solid ${t.border}`, position: "absolute", bottom: 0, width: "200px" }}>
            <div style={{ fontFamily: mono, fontSize: "9px", color: t.muted, lineHeight: 1.8 }}>
              <div>MIG Core v1.0.0</div>
              <div>Mode: fail-closed</div>
              <div>houseofgalatine.com</div>
            </div>
          </div>
        </nav>

        <main style={{ flex: 1, padding: "20px", overflowY: "auto" }}>
          {page === "console" && <CommandConsole />}
          {page === "policies" && <PolicyManager />}
          {page === "audit" && <AuditTrail />}
          {page === "status" && <StatusPage />}
        </main>
      </div>
    </div>
  );
}
