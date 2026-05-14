import { useState, useEffect, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from "recharts";
import { Activity, DollarSign, TrendingUp, AlertTriangle, Play, RefreshCw, Zap, Globe, Target, ArrowUpRight, ArrowDownRight, Pause } from "lucide-react";

const API = "http://localhost:8000/api/v1";

// Static demo data (engine snapshot from live run)
const DEMO_SNAPSHOT = {
  timestamp: "2026-04-03T23:47:07",
  total_spend: 158485.87,
  total_revenue: 769808.02,
  blended_roas: 4.86,
  total_conversions: 1455,
  num_campaigns: 22,
  num_active_campaigns: 22,
  platform_breakdown: {
    google_ads: { spend: 87469.18, revenue: 373232.92, roas: 4.27 },
    meta_ads: { spend: 71016.69, revenue: 396575.10, roas: 5.58 },
  },
};

const DEMO_ACTIONS = [
  { platform: "meta_ads", campaign_id: "m_0008", action_type: "increase_budget", old_value: 550, new_value: 660, reason: "Lookalike - High LTV: ROAS=5.98, Composite=0.76", confidence: 0.95, confidence_level: "high" },
  { platform: "meta_ads", campaign_id: "m_0002", action_type: "increase_budget", old_value: 450, new_value: 540, reason: "Retargeting - MOF: ROAS=7.96, Composite=0.75", confidence: 0.95, confidence_level: "high" },
  { platform: "google_ads", campaign_id: "g_0008", action_type: "increase_budget", old_value: 1000, new_value: 1200, reason: "Performance Max: ROAS=5.93, Composite=0.74", confidence: 0.94, confidence_level: "high" },
  { platform: "google_ads", campaign_id: "g_0001", action_type: "increase_budget", old_value: 500, new_value: 600, reason: "Brand - Search: ROAS=6.92, Composite=0.74", confidence: 0.94, confidence_level: "high" },
  { platform: "google_ads", campaign_id: "g_0004", action_type: "increase_budget", old_value: 400, new_value: 480, reason: "Retargeting - RLSA: ROAS=6.73, Composite=0.73", confidence: 0.92, confidence_level: "high" },
  { platform: "google_ads", campaign_id: "g_0011", action_type: "pause_campaign", old_value: 200, new_value: 0, reason: "Low-Performer Test: ROAS=0.36 — emergency stop", confidence: 0.95, confidence_level: "high" },
  { platform: "meta_ads", campaign_id: "m_0009", action_type: "pause_campaign", old_value: 200, new_value: 0, reason: "Brand Awareness: ROAS=0.41 — emergency stop", confidence: 0.95, confidence_level: "high" },
  { platform: "google_ads", campaign_id: "g_0003", action_type: "decrease_budget", old_value: 1200, new_value: 960, reason: "Platform reallocation: Shopping - All", confidence: 0.93, confidence_level: "high" },
  { platform: "google_ads", campaign_id: "g_0002", action_type: "decrease_budget", old_value: 800, new_value: 640, reason: "Platform reallocation: Generic - Search", confidence: 0.93, confidence_level: "high" },
  { platform: "meta_ads", campaign_id: "m_0001", action_type: "increase_budget", old_value: 600, new_value: 720, reason: "Platform reallocation: Prospecting - TOF", confidence: 0.93, confidence_level: "high" },
];

const DEMO_CAMPAIGNS = [
  { name: "RLSA - Cart Abandoners", platform: "google_ads", roas: 9.54, spend: 5670.40, revenue: 54087.62, conversions: 167, daily_budget: 450, status: "active" },
  { name: "Retargeting - MOF", platform: "meta_ads", roas: 7.96, spend: 5862.75, revenue: 46667.49, conversions: 95, daily_budget: 450, status: "active" },
  { name: "Catalog - Retargeting", platform: "meta_ads", roas: 7.82, spend: 6720.50, revenue: 52534.31, conversions: 118, daily_budget: 500, status: "active" },
  { name: "Brand - Search", platform: "google_ads", roas: 6.92, spend: 6430.25, revenue: 44497.33, conversions: 132, daily_budget: 500, status: "active" },
  { name: "Retargeting - RLSA", platform: "google_ads", roas: 6.73, spend: 5012.80, revenue: 33736.14, conversions: 82, daily_budget: 400, status: "active" },
  { name: "Conversion - BOFU", platform: "meta_ads", roas: 6.45, spend: 10528.40, revenue: 67908.18, conversions: 156, daily_budget: 800, status: "active" },
  { name: "Lookalike - High LTV", platform: "meta_ads", roas: 5.98, spend: 7315.50, revenue: 43726.69, conversions: 97, daily_budget: 550, status: "active" },
  { name: "Performance Max", platform: "google_ads", roas: 5.93, spend: 13160.00, revenue: 78038.80, conversions: 126, daily_budget: 1000, status: "active" },
  { name: "Dynamic Product Ads", platform: "meta_ads", roas: 5.62, spend: 11718.90, revenue: 65860.22, conversions: 145, daily_budget: 900, status: "active" },
  { name: "Shopping - All Products", platform: "google_ads", roas: 4.81, spend: 15624.00, revenue: 75151.44, conversions: 112, daily_budget: 1200, status: "active" },
  { name: "Lookalike - Purchasers", platform: "meta_ads", roas: 4.52, spend: 9128.00, revenue: 41258.56, conversions: 82, daily_budget: 700, status: "active" },
  { name: "DSA - All Pages", platform: "google_ads", roas: 3.91, spend: 3275.00, revenue: 12805.25, conversions: 48, daily_budget: 250, status: "active" },
  { name: "Generic - Search", platform: "google_ads", roas: 3.48, spend: 10640.00, revenue: 37027.20, conversions: 73, daily_budget: 800, status: "active" },
  { name: "Prospecting - TOF", platform: "meta_ads", roas: 3.25, spend: 7860.00, revenue: 25545.00, conversions: 62, daily_budget: 600, status: "active" },
  { name: "Interest - Skincare", platform: "meta_ads", roas: 2.84, spend: 5240.00, revenue: 14881.60, conversions: 38, daily_budget: 400, status: "active" },
  { name: "YouTube - Brand", platform: "google_ads", roas: 2.56, spend: 4550.00, revenue: 11648.00, conversions: 35, daily_budget: 350, status: "active" },
  { name: "New Product Launch", platform: "google_ads", roas: 2.12, spend: 9170.00, revenue: 19440.40, conversions: 42, daily_budget: 700, status: "active" },
  { name: "Competitor - Search", platform: "google_ads", roas: 1.87, spend: 3780.00, revenue: 7068.60, conversions: 24, daily_budget: 300, status: "active" },
  { name: "Display - Prospecting", platform: "google_ads", roas: 1.12, spend: 7560.00, revenue: 8467.20, conversions: 14, daily_budget: 600, status: "active" },
  { name: "Broad - Video Views", platform: "meta_ads", roas: 1.05, spend: 3870.00, revenue: 4063.50, conversions: 11, daily_budget: 300, status: "active" },
  { name: "Low-Performer Test", platform: "google_ads", roas: 0.36, spend: 2576.00, revenue: 927.36, conversions: 4, daily_budget: 200, status: "paused" },
  { name: "Brand Awareness", platform: "meta_ads", roas: 0.41, spend: 2520.00, revenue: 1033.20, conversions: 5, daily_budget: 200, status: "paused" },
];

const COLORS = {
  google: "#4285F4",
  meta: "#0081FB",
  increase: "#10b981",
  decrease: "#ef4444",
  pause: "#f59e0b",
  bg: "#0f172a",
  card: "#1e293b",
  cardHover: "#334155",
  border: "#334155",
  text: "#f8fafc",
  textMuted: "#94a3b8",
  accent: "#6366f1",
};

const PIE_COLORS = ["#4285F4", "#0081FB"];

function StatCard({ icon: Icon, label, value, subvalue, color = COLORS.accent }) {
  return (
    <div style={{ background: COLORS.card, borderRadius: 12, padding: "20px 24px", border: `1px solid ${COLORS.border}`, flex: 1, minWidth: 200 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <div style={{ background: `${color}22`, borderRadius: 8, padding: 6, display: "flex" }}>
          <Icon size={18} color={color} />
        </div>
        <span style={{ color: COLORS.textMuted, fontSize: 13, fontWeight: 500 }}>{label}</span>
      </div>
      <div style={{ color: COLORS.text, fontSize: 28, fontWeight: 700, letterSpacing: -0.5 }}>{value}</div>
      {subvalue && <div style={{ color: COLORS.textMuted, fontSize: 12, marginTop: 4 }}>{subvalue}</div>}
    </div>
  );
}

function ActionBadge({ type }) {
  const styles = {
    increase_budget: { bg: "#10b98122", color: "#10b981", icon: ArrowUpRight, text: "Increase" },
    decrease_budget: { bg: "#ef444422", color: "#ef4444", icon: ArrowDownRight, text: "Decrease" },
    pause_campaign: { bg: "#f59e0b22", color: "#f59e0b", icon: Pause, text: "Pause" },
  };
  const s = styles[type] || styles.increase_budget;
  const Icon = s.icon;
  return (
    <span style={{ background: s.bg, color: s.color, padding: "4px 10px", borderRadius: 6, fontSize: 12, fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4 }}>
      <Icon size={12} /> {s.text}
    </span>
  );
}

function PlatformBadge({ platform }) {
  const isGoogle = platform === "google_ads";
  return (
    <span style={{ background: isGoogle ? "#4285F422" : "#0081FB22", color: isGoogle ? "#4285F4" : "#0081FB", padding: "3px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
      {isGoogle ? "Google" : "Meta"}
    </span>
  );
}

export default function ROASDashboard() {
  const [snapshot] = useState(DEMO_SNAPSHOT);
  const [actions] = useState(DEMO_ACTIONS);
  const [campaigns] = useState(DEMO_CAMPAIGNS);
  const [activeTab, setActiveTab] = useState("overview");

  const platformData = [
    { name: "Google Ads", spend: snapshot.platform_breakdown.google_ads.spend, revenue: snapshot.platform_breakdown.google_ads.revenue, roas: snapshot.platform_breakdown.google_ads.roas },
    { name: "Meta Ads", spend: snapshot.platform_breakdown.meta_ads.spend, revenue: snapshot.platform_breakdown.meta_ads.revenue, roas: snapshot.platform_breakdown.meta_ads.roas },
  ];

  const spendPie = [
    { name: "Google Ads", value: snapshot.platform_breakdown.google_ads.spend },
    { name: "Meta Ads", value: snapshot.platform_breakdown.meta_ads.spend },
  ];

  const topCampaigns = [...campaigns].sort((a, b) => b.roas - a.roas).slice(0, 10);

  const campaignChartData = topCampaigns.map(c => ({
    name: c.name.length > 20 ? c.name.substring(0, 18) + "..." : c.name,
    ROAS: c.roas,
    platform: c.platform,
  }));

  const actionSummary = {
    increases: actions.filter(a => a.action_type === "increase_budget").length,
    decreases: actions.filter(a => a.action_type === "decrease_budget").length,
    pauses: actions.filter(a => a.action_type === "pause_campaign").length,
  };

  const tabs = [
    { id: "overview", label: "Overview", icon: Activity },
    { id: "campaigns", label: "Campaigns", icon: Target },
    { id: "actions", label: "Actions", icon: Zap },
  ];

  return (
    <div style={{ background: COLORS.bg, minHeight: "100vh", color: COLORS.text, fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" }}>
      {/* Header */}
      <div style={{ background: COLORS.card, borderBottom: `1px solid ${COLORS.border}`, padding: "16px 32px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: `${COLORS.accent}33`, borderRadius: 10, padding: 8, display: "flex" }}>
            <TrendingUp size={22} color={COLORS.accent} />
          </div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: -0.3 }}>ROAS Optimization Engine</div>
            <div style={{ fontSize: 12, color: COLORS.textMuted }}>Demo Mode — Simulated Data</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: "#10b98122", color: "#10b981", padding: "6px 14px", borderRadius: 20, fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 6, height: 6, borderRadius: 3, background: "#10b981" }} /> Engine Running
          </div>
          <div style={{ color: COLORS.textMuted, fontSize: 12 }}>
            Last cycle: {new Date(snapshot.timestamp).toLocaleTimeString()}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ padding: "0 32px", background: COLORS.card, borderBottom: `1px solid ${COLORS.border}`, display: "flex", gap: 0 }}>
        {tabs.map(tab => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{ background: "none", border: "none", padding: "12px 20px", color: active ? COLORS.accent : COLORS.textMuted, borderBottom: active ? `2px solid ${COLORS.accent}` : "2px solid transparent", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 600, transition: "all 0.2s" }}>
              <Icon size={15} /> {tab.label}
            </button>
          );
        })}
      </div>

      <div style={{ padding: 32, maxWidth: 1400, margin: "0 auto" }}>

        {/* ── OVERVIEW TAB ── */}
        {activeTab === "overview" && (
          <>
            {/* KPI Cards */}
            <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
              <StatCard icon={DollarSign} label="Total Spend" value={`$${(snapshot.total_spend / 1000).toFixed(1)}K`} subvalue="14-day lookback" color="#6366f1" />
              <StatCard icon={TrendingUp} label="Total Revenue" value={`$${(snapshot.total_revenue / 1000).toFixed(1)}K`} subvalue={`${snapshot.total_conversions.toLocaleString()} conversions`} color="#10b981" />
              <StatCard icon={Target} label="Blended ROAS" value={`${snapshot.blended_roas.toFixed(2)}x`} subvalue="Target: 4.00x" color={snapshot.blended_roas >= 4 ? "#10b981" : "#f59e0b"} />
              <StatCard icon={Activity} label="Active Campaigns" value={`${snapshot.num_active_campaigns}/${snapshot.num_campaigns}`} subvalue={`${actionSummary.pauses} paused this cycle`} color="#8b5cf6" />
            </div>

            {/* Charts Row */}
            <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
              {/* Platform Spend vs Revenue */}
              <div style={{ background: COLORS.card, borderRadius: 12, padding: 24, border: `1px solid ${COLORS.border}`, flex: 2, minWidth: 400 }}>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Platform Performance</div>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={platformData} barGap={8}>
                    <CartesianGrid strokeDasharray="3 3" stroke={COLORS.border} />
                    <XAxis dataKey="name" stroke={COLORS.textMuted} fontSize={12} />
                    <YAxis stroke={COLORS.textMuted} fontSize={11} tickFormatter={v => `$${(v / 1000).toFixed(0)}K`} />
                    <Tooltip contentStyle={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 8 }} formatter={v => `$${v.toLocaleString()}`} />
                    <Legend />
                    <Bar dataKey="spend" fill="#6366f1" name="Spend" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="revenue" fill="#10b981" name="Revenue" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Spend Split Pie */}
              <div style={{ background: COLORS.card, borderRadius: 12, padding: 24, border: `1px solid ${COLORS.border}`, flex: 1, minWidth: 280 }}>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Budget Split</div>
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie data={spendPie} cx="50%" cy="50%" innerRadius={55} outerRadius={90} paddingAngle={4} dataKey="value">
                      {spendPie.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
                    </Pie>
                    <Tooltip contentStyle={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 8 }} formatter={v => `$${v.toLocaleString()}`} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top Campaigns by ROAS */}
            <div style={{ background: COLORS.card, borderRadius: 12, padding: 24, border: `1px solid ${COLORS.border}` }}>
              <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Top 10 Campaigns by ROAS</div>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={campaignChartData} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={COLORS.border} horizontal={false} />
                  <XAxis type="number" stroke={COLORS.textMuted} fontSize={11} />
                  <YAxis dataKey="name" type="category" width={160} stroke={COLORS.textMuted} fontSize={11} />
                  <Tooltip contentStyle={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 8 }} formatter={v => `${v.toFixed(2)}x`} />
                  <Bar dataKey="ROAS" radius={[0, 4, 4, 0]}>
                    {campaignChartData.map((entry, i) => <Cell key={i} fill={entry.platform === "google_ads" ? "#4285F4" : "#0081FB"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}

        {/* ── CAMPAIGNS TAB ── */}
        {activeTab === "campaigns" && (
          <div style={{ background: COLORS.card, borderRadius: 12, border: `1px solid ${COLORS.border}`, overflow: "hidden" }}>
            <div style={{ padding: "16px 24px", borderBottom: `1px solid ${COLORS.border}`, fontSize: 15, fontWeight: 600 }}>
              All Campaigns ({campaigns.length})
            </div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                    {["Campaign", "Platform", "Status", "ROAS", "Spend", "Revenue", "Conv.", "Daily Budget"].map(h => (
                      <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 0.5 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((c, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${COLORS.border}`, transition: "background 0.15s" }}
                        onMouseEnter={e => e.currentTarget.style.background = COLORS.cardHover}
                        onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                      <td style={{ padding: "12px 16px", fontSize: 13, fontWeight: 500 }}>{c.name}</td>
                      <td style={{ padding: "12px 16px" }}><PlatformBadge platform={c.platform} /></td>
                      <td style={{ padding: "12px 16px" }}>
                        <span style={{ color: c.status === "active" ? "#10b981" : "#f59e0b", fontSize: 12, fontWeight: 600 }}>
                          {c.status === "active" ? "Active" : "Paused"}
                        </span>
                      </td>
                      <td style={{ padding: "12px 16px", fontWeight: 600, color: c.roas >= 4 ? "#10b981" : c.roas >= 1.5 ? "#f59e0b" : "#ef4444" }}>{c.roas.toFixed(2)}x</td>
                      <td style={{ padding: "12px 16px", fontSize: 13 }}>${c.spend.toLocaleString()}</td>
                      <td style={{ padding: "12px 16px", fontSize: 13 }}>${c.revenue.toLocaleString()}</td>
                      <td style={{ padding: "12px 16px", fontSize: 13 }}>{c.conversions}</td>
                      <td style={{ padding: "12px 16px", fontSize: 13 }}>${c.daily_budget}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── ACTIONS TAB ── */}
        {activeTab === "actions" && (
          <>
            {/* Action summary */}
            <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
              <StatCard icon={ArrowUpRight} label="Budget Increases" value={actionSummary.increases} color="#10b981" />
              <StatCard icon={ArrowDownRight} label="Budget Decreases" value={actionSummary.decreases} color="#ef4444" />
              <StatCard icon={AlertTriangle} label="Campaigns Paused" value={actionSummary.pauses} subvalue="Emergency stops" color="#f59e0b" />
            </div>

            {/* Action log */}
            <div style={{ background: COLORS.card, borderRadius: 12, border: `1px solid ${COLORS.border}`, overflow: "hidden" }}>
              <div style={{ padding: "16px 24px", borderBottom: `1px solid ${COLORS.border}`, fontSize: 15, fontWeight: 600 }}>
                Optimization Actions ({actions.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                {actions.map((a, i) => (
                  <div key={i} style={{ padding: "14px 24px", borderBottom: `1px solid ${COLORS.border}`, display: "flex", alignItems: "center", gap: 16, transition: "background 0.15s" }}
                       onMouseEnter={e => e.currentTarget.style.background = COLORS.cardHover}
                       onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                    <PlatformBadge platform={a.platform} />
                    <ActionBadge type={a.action_type} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{a.reason}</div>
                      {a.old_value > 0 && a.action_type !== "pause_campaign" && (
                        <div style={{ fontSize: 11, color: COLORS.textMuted, marginTop: 2 }}>
                          ${a.old_value} → ${a.new_value} ({a.new_value > a.old_value ? "+" : ""}{(((a.new_value - a.old_value) / a.old_value) * 100).toFixed(0)}%)
                        </div>
                      )}
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: a.confidence >= 0.9 ? "#10b981" : "#f59e0b" }}>
                        {(a.confidence * 100).toFixed(0)}% confidence
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
