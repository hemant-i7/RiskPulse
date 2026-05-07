"""
RiskPulse — Renewal Risk Intelligence  ·  Contentstack BizOps
Run : streamlit run app.py
"""

import ast, os, subprocess, sys, time
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import anthropic as _anthropic
    _ANTHROPIC_OK = True
except ImportError:
    _ANTHROPIC_OK = False

# ── credentials ───────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass
try:
    for k, v in st.secrets.items(): os.environ.setdefault(k, str(v))
except Exception:
    pass

DATA_DIR   = Path(__file__).parent
OUTPUT_DIR = DATA_DIR / "output"

TIER_META = {
    "High":   {"color": "#f87171", "dim": "#7f1d1d", "glow": "rgba(248,113,113,.15)", "icon": "●"},
    "Medium": {"color": "#fbbf24", "dim": "#78350f", "glow": "rgba(251,191,36,.12)",  "icon": "●"},
    "Low":    {"color": "#34d399", "dim": "#064e3b", "glow": "rgba(52,211,153,.12)",   "icon": "●"},
}

st.set_page_config(
    page_title="RiskPulse",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════ CSS ══════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── reset / dark base ── */
html, body, .stApp, [class*="css"] {
  font-family: 'Inter', system-ui, sans-serif;
  background: #0c0c14 !important;
  color: #d4d4e8;
}
#MainMenu, footer, header { visibility: hidden !important; }
.block-container { padding: 1.8rem 2.2rem 3rem !important; max-width: 1300px !important; }

/* ── sidebar ── */
section[data-testid="stSidebar"] {
  background: #08080f !important;
  border-right: 1px solid #1a1a2e !important;
}
section[data-testid="stSidebar"] > div { padding: 24px 18px !important; }
section[data-testid="stSidebar"] * { color: #c8c8e0 !important; }
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] .stSelectbox > div > div {
  background: #13131f !important; border: 1px solid #252538 !important;
  color: #e0e0f0 !important; border-radius: 8px !important;
}
section[data-testid="stSidebar"] label {
  color: #44445a !important; font-size: 10px !important;
  text-transform: uppercase !important; letter-spacing: .8px !important; font-weight: 600 !important;
}
section[data-testid="stSidebar"] hr { border-color: #1a1a2e !important; margin: 14px 0 !important; }

/* ── tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important; border-bottom: 1px solid #1a1a2e !important;
  gap: 0 !important; padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important; color: #44445a !important;
  border-radius: 0 !important; border-bottom: 2px solid transparent !important;
  font-size: 13px !important; font-weight: 500 !important;
  padding: 10px 20px !important; margin-right: 4px !important;
}
.stTabs [aria-selected="true"] {
  color: #a5b4fc !important; border-bottom: 2px solid #6366f1 !important;
  background: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 24px 0 0 !important; }

/* ── expanders ── */
details { background: #13131f !important; border: 1px solid #1a1a2e !important; border-radius: 12px !important; margin-bottom: 8px !important; }
details summary { padding: 14px 18px !important; cursor: pointer; list-style: none; }
details summary::-webkit-details-marker { display: none; }
details[open] { border-color: #252538 !important; }
details[open] summary { border-bottom: 1px solid #1a1a2e; }

/* ── metric widget dark ── */
[data-testid="stMetric"] { background: #13131f; border: 1px solid #1a1a2e; border-radius: 12px; padding: 16px 18px; }
[data-testid="stMetricLabel"] { color: #44445a !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: .6px; }
[data-testid="stMetricValue"] { color: #e0e0f4 !important; font-size: 28px !important; font-weight: 700 !important; }
[data-testid="stMetricDelta"] { font-size: 12px !important; }

/* ── dataframe ── */
.stDataFrame thead th { background: #13131f !important; color: #44445a !important; font-size: 11px !important; text-transform: uppercase !important; letter-spacing: .5px !important; }
.stDataFrame tbody td { background: #0c0c14 !important; color: #c8c8e0 !important; border-color: #1a1a2e !important; }

/* ── buttons ── */
.stButton > button[kind="primary"] {
  background: #4f46e5 !important; color: #fff !important; border: none !important;
  border-radius: 8px !important; font-weight: 600 !important; font-size: 13px !important;
}
.stButton > button[kind="primary"]:hover { background: #4338ca !important; }
.stDownloadButton > button { background: #13131f !important; border: 1px solid #252538 !important; color: #c8c8e0 !important; border-radius: 8px !important; }

/* ── scrollbars ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0c0c14; }
::-webkit-scrollbar-thumb { background: #252538; border-radius: 9999px; }

/* ── custom blocks ── */
.banner {
  background: linear-gradient(120deg,#0e0c2e,#111432,#0c1040);
  border: 1px solid #1e1c50; border-radius: 16px;
  padding: 24px 28px; margin-bottom: 22px;
}
.banner-title { font-size: 20px; font-weight: 700; color: #c7d2fe; margin-bottom: 4px; }
.banner-sub   { font-size: 13px; color: #5558a0; }
.banner-sub strong { color: #818cf8; }

.kpi-strip { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:22px; }
.kpi-box {
  background: #13131f; border: 1px solid #1a1a2e; border-radius: 12px;
  padding: 16px 18px; position: relative; overflow: hidden;
}
.kpi-box::after {
  content:''; position:absolute; top:0; left:0; right:0; height:2px;
}
.kpi-lbl { font-size: 10px; color: #44445a; text-transform: uppercase; letter-spacing:.8px; font-weight:600; }
.kpi-val { font-size: 28px; font-weight: 700; color: #e0e0f4; margin: 6px 0 3px; line-height:1; }
.kpi-hint{ font-size: 11px; color: #44445a; }

.row-card {
  background: #13131f; border: 1px solid #1a1a2e;
  border-radius: 12px; margin-bottom: 8px;
  overflow: hidden;
}
.row-header {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 18px; cursor: pointer;
}
.row-body { padding: 0 18px 16px; border-top: 1px solid #1a1a2e; }

.tier-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.acct-title { font-size: 14px; font-weight: 600; color: #e0e0f4; flex: 1; }
.acct-arr   { font-size: 13px; color: #6b6b8a; }

.score-pill {
  display: inline-flex; align-items: center; justify-content: center;
  width: 42px; height: 24px; border-radius: 6px;
  font-size: 12px; font-weight: 700;
}
.days-chip {
  display: inline-block; padding: 2px 8px; border-radius: 6px;
  font-size: 11px; font-weight: 500; white-space: nowrap;
}

.track { height: 4px; background: #1a1a2e; border-radius: 9999px; overflow: hidden; margin: 3px 0; }
.fill  { height: 4px; border-radius: 9999px; }

.stat-mini { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin: 14px 0 4px; }
.stat-mini-cell {
  background: #0c0c14; border: 1px solid #1a1a2e; border-radius: 8px;
  padding: 10px 12px; border-top-width: 2px;
}
.stat-mini-cell.c-usage  { border-top-color: #6366f1; }
.stat-mini-cell.c-users  { border-top-color: #0ea5e9; }
.stat-mini-cell.c-nps    { border-top-color: #a78bfa; }
.stat-mini-cell.c-p1     { border-top-color: #f97316; }
.stat-mini-lbl  { font-size: 10px; color: #44445a; text-transform:uppercase; letter-spacing:.5px; }
.stat-mini-val  { font-size: 18px; font-weight: 700; color: #e0e0f4; margin-top:4px; }
.stat-mini-hint { font-size: 10px; color: #2e2e4a; margin-top:3px; font-style:italic; }

.signal-tag {
  display:inline-block; padding:2px 9px; border-radius:6px;
  font-size:11px; background:#0f0f22; border:1px solid #1e1e38; color:#7070a0;
  margin:2px 3px 2px 0;
}
.signal-tag.critical {
  background:#1a0808; border-color:#4a1010; color:#f87171;
}
.sdk-tag {
  display:inline-block; padding:2px 9px; border-radius:6px;
  font-size:11px; background:#1a0e00; border:1px solid #4a2e00; color:#f97316;
  margin:2px 3px 2px 0;
}
.sdk-tag-ok {
  display:inline-block; padding:2px 9px; border-radius:6px;
  font-size:11px; background:#071a10; border:1px solid #0d4020; color:#34d399;
  margin:2px 3px 2px 0;
}

.annot {
  font-size:11px; color:#2e2e48; font-style:italic; margin-top:6px;
  padding-left:2px; line-height:1.5;
}

.expl-text { font-size: 13px; color: #7070a0; line-height: 1.65; margin-bottom: 12px; }
.action-line {
  display:flex; gap:10px; align-items:flex-start;
  background:#0d0d22; border-left:2px solid #6366f1; border-radius:0 8px 8px 0;
  padding:10px 14px;
}
.action-line span { font-size:13px; color:#a5b4fc; line-height:1.55; }

.sdk-row {
  display:flex; align-items:center; gap:8px;
  background:#0a0a18; border:1px solid #1a1a2e; border-radius:8px;
  padding:8px 12px; margin: 8px 0 12px; font-size:12px;
}
.sdk-row-label { color:#44445a; }
.sdk-row-val   { font-family:monospace; font-size:12px; }

.score-bar-wrap { margin: 4px 0 16px; }
.score-bar-bg   { height:3px; background:#1a1a2e; border-radius:9999px; overflow:hidden; }
.score-bar-fill { height:3px; border-radius:9999px; }

.insight-block {
  background:#0e0e22; border:1px solid #1e1c50; border-radius:12px;
  padding:18px 22px; margin-bottom:22px;
}
.insight-eyebrow { font-size:10px; font-weight:600; color:#4f46e5; text-transform:uppercase; letter-spacing:1px; margin-bottom:8px; }
.insight-body    { font-size:14px; color:#8b90c8; line-height:1.7; }

.section-label { font-size:10px; font-weight:600; color:#44445a; text-transform:uppercase; letter-spacing:.8px; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid #1a1a2e; }

.hbar-wrap { margin-bottom:10px; }
.hbar-top  { display:flex; justify-content:space-between; margin-bottom:4px; }
.hbar-name { font-size:12px; color:#8888a8; }
.hbar-right{ font-size:12px; color:#44445a; }
.hbar-bg   { height:6px; background:#1a1a2e; border-radius:9999px; overflow:hidden; }
.hbar-fill { height:6px; border-radius:9999px; }

.tl-col { background:#13131f; border:1px solid #1a1a2e; border-radius:12px; overflow:hidden; }
.tl-head { padding:12px 16px; border-bottom:1px solid #1a1a2e; }
.tl-hl   { font-size:10px; font-weight:600; letter-spacing:.8px; text-transform:uppercase; }
.tl-num  { font-size:26px; font-weight:700; margin-top:2px; }
.tl-body { padding:10px 16px; }
.tl-item { font-size:12px; color:#6b6b8a; padding:5px 0; border-bottom:1px solid #1a1a2e; }
.tl-item:last-child { border-bottom:none; }
</style>
""", unsafe_allow_html=True)


# ── utils ─────────────────────────────────────────────────────────────────────
def safe_list(v):
    if isinstance(v, list): return v
    if pd.isna(v) or str(v).strip() == "": return []
    try:    return ast.literal_eval(str(v))
    except: return []

def score_color(score, tier):
    return TIER_META.get(tier, TIER_META["Low"])["color"]

def days_chip(days):
    try: d = int(days)
    except: return ""
    if d <= 7:  return f'<span class="days-chip" style="background:#3b0d0d;color:#f87171;border:1px solid #7f1d1d;">⚡ {d}d</span>'
    if d <= 30: return f'<span class="days-chip" style="background:#2a1500;color:#fbbf24;border:1px solid #78350f;">⏰ {d}d</span>'
    return          f'<span class="days-chip" style="background:#111118;color:#44445a;border:1px solid #1a1a2e;">{d}d</span>'

def run_pipeline(as_of, top_k, prov, key, mdl):
    env = {**os.environ, "LLM_PROVIDER": prov, "LLM_MODEL": mdl,
           ("ANTHROPIC_API_KEY" if prov == "anthropic" else "OPENAI_API_KEY"): key}
    r = subprocess.run(
        [sys.executable, str(DATA_DIR/"renewal_intelligence.py"),
         "--data-dir", str(DATA_DIR), "--as-of-date", as_of,
         "--output-dir", str(OUTPUT_DIR), "--top-k", str(top_k)],
        env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr or "Pipeline failed.")

def load_df():
    p = OUTPUT_DIR / "renewal_risk_ranked.csv"
    return pd.read_csv(p) if p.exists() else None

def last_run_time() -> str:
    p = OUTPUT_DIR / "renewal_risk_ranked.csv"
    if not p.exists(): return ""
    t = p.stat().st_mtime
    return time.strftime("%d %b %Y, %I:%M %p", time.localtime(t))

def input_file_counts() -> dict:
    files = {
        "accounts.csv":       "accounts",
        "usage_metrics.csv":  "usage rows",
        "support_tickets.csv":"tickets",
        "nps_responses.csv":  "NPS responses",
    }
    out = {}
    for fname, label in files.items():
        p = DATA_DIR / fname
        if p.exists():
            rows = len(p.read_text(encoding="utf-8").strip().splitlines()) - 1
            out[label] = rows
    return out

def load_insight():
    p = OUTPUT_DIR / "renewal_risk_report.md"
    if not p.exists(): return ""
    t = p.read_text(encoding="utf-8")
    s, e = t.find("## Non-obvious insight"), t.find("## Top at-risk accounts")
    return t[s+len("## Non-obvious insight"):e].strip() if s != -1 and e != -1 else ""


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div style="margin-bottom:20px;">
  <div style="font-size:15px;font-weight:700;color:#c7d2fe;">Renewal Risk</div>
  <div style="font-size:10px;color:#2e2e4a;text-transform:uppercase;letter-spacing:.8px;margin-top:2px;">BizOps Intelligence</div>
</div>""", unsafe_allow_html=True)
    st.divider()

    as_of_date = st.date_input("Analysis date", value=date.today())

    provider = st.selectbox("LLM provider", ["anthropic", "openai"])
    default_key = os.getenv("ANTHROPIC_API_KEY","") if provider=="anthropic" else os.getenv("OPENAI_API_KEY","")
    api_key = st.text_input("API key", value=default_key, type="password", placeholder="Paste key…")
    default_model = "claude-sonnet-4-6" if provider=="anthropic" else "gpt-4o-mini"
    model = st.text_input("Model", value=default_model)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    top_k = st.slider("Accounts in markdown report", 5, 30, 15,
                      help="How many accounts to include in the saved renewal_risk_report.md file. Does NOT affect what you see in this dashboard — the dashboard always shows all accounts.")
    run_btn = st.button("▶  Run Analysis", type="primary", use_container_width=True)

    st.divider()
    st.markdown("""
<div style="font-size:10px;color:#44445a;text-transform:uppercase;letter-spacing:.8px;
            font-weight:600;margin-bottom:8px;">Input files (given)</div>
<div style="font-size:11px;color:#2e2e4a;line-height:2.2;">
  📄 accounts.csv<br>
  📄 usage_metrics.csv<br>
  📄 support_tickets.csv<br>
  📄 nps_responses.csv<br>
  📄 csm_notes.txt<br>
  📄 changelog.md
</div>
<div style="height:10px;"></div>
<div style="font-size:10px;color:#44445a;text-transform:uppercase;letter-spacing:.8px;
            font-weight:600;margin-bottom:8px;">Generated by pipeline</div>
<div style="font-size:11px;color:#2e2e4a;line-height:2.2;">
  ✅ Risk score (0–100)<br>
  ✅ Tier: High / Medium / Low<br>
  ✅ AI explanation per account<br>
  ✅ Recommended next action<br>
  ✅ Non-obvious insight
</div>""", unsafe_allow_html=True)


# ── banner ────────────────────────────────────────────────────────────────────
last_run = last_run_time()

steps = [
    ("📁", "6 data files"),
    ("⚙️", "14 risk signals"),
    ("🤖", "Claude AI"),
    ("📊", "Dashboard"),
]
steps_html = " &nbsp;→&nbsp; ".join(
    f'<span style="color:#818cf8;">{icon}</span>'
    f'<span style="color:#44445a;margin-left:5px;">{label}</span>'
    for icon, label in steps
)

st.markdown(f"""
<div style="background:linear-gradient(120deg,#0e0c2e,#111432);
            border:1px solid #1e1e50;border-radius:14px;
            padding:14px 22px;margin-bottom:22px;
            display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
  <div>
    <span style="font-size:15px;font-weight:700;color:#c7d2fe;">RiskPulse</span>
    <span style="font-size:13px;color:#44445a;margin-left:12px;">
      {steps_html}
    </span>
  </div>
  {"<span style='font-size:11px;color:#44445a;'>Last run &nbsp;<strong style=\"color:#818cf8;\">" + last_run + "</strong></span>" if last_run else ""}
</div>""", unsafe_allow_html=True)

# ── run ───────────────────────────────────────────────────────────────────────
if run_btn:
    with st.spinner("Running analysis — LLM calls take ~60 s…"):
        try:
            run_pipeline(str(as_of_date), top_k, provider, api_key, model)
            st.session_state["ran"] = True
            st.success("Done.", icon="✅")
        except RuntimeError as e:
            st.error(str(e))

df = load_df()

if df is None:
    st.markdown("""
<div style="background:#13131f;border:1px dashed #1a1a2e;border-radius:14px;
            padding:60px 40px;text-align:center;">
  <div style="font-size:28px;margin-bottom:10px;">🚀</div>
  <div style="font-size:15px;font-weight:600;color:#6b6b8a;">No analysis run yet</div>
  <div style="font-size:13px;color:#44445a;margin-top:6px;line-height:1.8;">
    The 6 input data files are ready in this folder.<br>
    Click <span style="color:#818cf8;font-weight:600;">▶ Run Analysis</span> in the sidebar
    to run the pipeline and generate risk scores + AI explanations.
  </div>
</div>""", unsafe_allow_html=True)
    st.stop()


# ── metrics ───────────────────────────────────────────────────────────────────
total     = len(df)
high_n    = int((df["risk_tier"]=="High").sum())
med_n     = int((df["risk_tier"]=="Medium").sum())
low_n     = int((df["risk_tier"]=="Low").sum())
high_arr  = int(df.loc[df["risk_tier"]=="High","arr"].sum())
total_arr = int(df["arr"].sum())
sdk3_n    = int(df.get("sdk_version_latest","").str.lower().str.startswith("v3",na=False).sum()) if "sdk_version_latest" in df else 0

def kpi_box(col, label, val, hint, accent):
    col.markdown(f"""
<div class="kpi-box" style="border-top:2px solid {accent};">
  <div class="kpi-lbl">{label}</div>
  <div class="kpi-val">{val}</div>
  <div class="kpi-hint">{hint}</div>
</div>""", unsafe_allow_html=True)

k = st.columns(5)
kpi_box(k[0], "Due (90 days)",  str(total),    f"as of {as_of_date}",           "#6366f1")
kpi_box(k[1], "🔴 High Risk",   str(high_n),   f"${high_arr/1000:.0f}K ARR",    "#f87171")
kpi_box(k[2], "🟡 Medium Risk", str(med_n),    "accounts",                       "#fbbf24")
kpi_box(k[3], "🟢 Low Risk",    str(low_n),    "accounts",                       "#34d399")
kpi_box(k[4], "⚠️ SDK v3",     str(sdk3_n),   "security deadline risk",         "#f97316")

st.markdown("<br>", unsafe_allow_html=True)

# ── tabs ──────────────────────────────────────────────────────────────────────
t1, t2, t3, t4, t5 = st.tabs(["  🔍  Accounts  ", "  📈  Dashboard  ", "  🔖  Changelog Risk  ", "  📋  Data  ", "  💬  Ask AI  "])


# ═══════════════════════════════════════════ ACCOUNTS ════════════════════════
with t1:
    # filter bar
    c1, c2, c3, c4 = st.columns([2,2,2,3])
    with c1:
        tier_f = st.multiselect("Tier", ["High","Medium","Low"], default=["High","Medium","Low"])
    with c2:
        csm_opts = sorted(df["csm_name"].dropna().unique()) if "csm_name" in df.columns else []
        csm_f = st.multiselect("CSM owner", csm_opts, default=csm_opts)
    with c3:
        sort_f = st.selectbox("Sort by", ["Risk score ↓","ARR ↓","Days left ↑"])
    with c4:
        q = st.text_input("Search", placeholder="Account name…", label_visibility="collapsed")

    view = df[df["risk_tier"].isin(tier_f)].copy()
    if csm_opts and csm_f: view = view[view["csm_name"].isin(csm_f)]
    if q: view = view[view["account_name"].str.contains(q, case=False, na=False)]
    if   sort_f == "ARR ↓":       view = view.sort_values("arr", ascending=False)
    elif sort_f == "Days left ↑":  view = view.sort_values("days_to_renewal", ascending=True)
    else:                          view = view.sort_values("risk_score", ascending=False)

    st.caption(f"{len(view)} accounts")

    for _, row in view.iterrows():
        tier   = str(row["risk_tier"])
        tm     = TIER_META.get(tier, TIER_META["Low"])
        score  = int(row["risk_score"])
        arr    = int(row["arr"])
        days   = row.get("days_to_renewal", "?")
        sdk    = str(row.get("sdk_version_latest",""))
        expl   = str(row.get("risk_explanation",""))
        action = str(row.get("recommended_action",""))
        nps    = float(row.get("nps_score",0) or 0)
        p1     = int(row.get("p1_tickets",0) or 0)
        dec    = float(row.get("avg_api_decline_ratio",0) or 0)
        users  = int(row.get("active_users_last_month",0) or 0)
        open_t = int(row.get("open_tickets",0) or 0)
        csm    = str(row.get("csm_name","—"))
        plan   = str(row.get("plan_tier","—"))
        region = str(row.get("region","—"))
        signals= safe_list(row.get("heuristic_reasons",[]))

        # colour helpers
        dec_c  = "#f87171" if dec>=.3 else "#fbbf24" if dec>=.15 else "#34d399"
        usr_c  = "#f87171" if users<=3 else "#e0e0f4"
        nps_c  = "#f87171" if nps and nps<=6 else "#fbbf24" if nps and nps<8 else "#34d399"
        nps_v  = f"{nps:.1f}" if nps else "—"
        p1_c   = "#f87171" if p1>=2 else "#fbbf24" if p1==1 else "#e0e0f4"

        # expander label — clearly labelled
        tier_icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(tier, "")
        try:
            days_label = f"Renews in {int(days)}d"
        except Exception:
            days_label = "—"
        label = (
            f"{tier_icon} {row['account_name']}"
            f"   |   ARR ${arr:,}"
            f"   |   Risk {tier}"
            f"   |   Score {score}/100"
            f"   |   {days_label}"
        )
        with st.expander(label, expanded=(tier == "High")):

            # ── top meta row ──────────────────────────────────────────────────
            st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            flex-wrap:wrap;gap:8px;padding:4px 0 10px;">
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
    <span style="font-size:10px;font-weight:700;color:{tm['color']};
                 background:{tm['dim']}33;border:1px solid {tm['dim']}88;
                 padding:3px 10px;border-radius:6px;letter-spacing:.5px;">{tier.upper()}</span>
    {days_chip(days)}
    <span style="font-size:11px;color:#2e2e48;background:#0f0f1e;
                 border:1px solid #1a1a2e;padding:2px 9px;border-radius:6px;">
      {plan}
    </span>
    <span style="font-size:12px;color:#44445a;">{region} &nbsp;·&nbsp; CSM: {csm}</span>
  </div>
  <div style="font-size:12px;color:#44445a;">
    Risk score &nbsp;<strong style="color:{tm['color']};font-size:15px;">{score}</strong>
    <span style="color:#2e2e48;">/100</span>
  </div>
</div>
<div class="score-bar-wrap">
  <div class="score-bar-bg">
    <div class="score-bar-fill" style="width:{score}%;background:{tm['color']};"></div>
  </div>
</div>
""", unsafe_allow_html=True)

            # ── SDK version row ───────────────────────────────────────────────
            is_v3 = sdk.lower().startswith("v3")
            sdk_color  = "#f97316" if is_v3 else "#34d399"
            sdk_bg     = "#1a0e00" if is_v3 else "#071a10"
            sdk_border = "#4a2e00" if is_v3 else "#0d4020"
            sdk_note   = "⚠ sunset breach — dead endpoints in prod" if is_v3 else "✓ current, CVE-2026-1102 exposure check needed" if not sdk.startswith("v4.3.2") else "✓ patched"
            st.markdown(f"""
<div class="sdk-row">
  <span class="sdk-row-label">SDK version</span>
  <span class="sdk-row-val" style="color:{sdk_color};background:{sdk_bg};
        border:1px solid {sdk_border};padding:1px 8px;border-radius:5px;">{sdk}</span>
  <span style="color:#2e2e48;font-size:11px;">{sdk_note}</span>
</div>""", unsafe_allow_html=True)

            # ── 4 stat cells with color accents + hints ───────────────────────
            dec_hint = "above threshold — churn signal" if dec >= .3 else "moderate decline" if dec >= .15 else "stable"
            usr_hint = "shelfware risk" if users <= 3 else "low adoption" if users <= 6 else "healthy"
            nps_hint = "detractor" if nps and nps <= 6 else "passive" if nps and nps < 8 else "promoter" if nps else "no response"
            p1_hint  = "critical — near renewal" if p1 >= 2 else "one open P1" if p1 == 1 else "no open P1s"

            st.markdown(f"""
<div class="stat-mini">
  <div class="stat-mini-cell c-usage">
    <div class="stat-mini-lbl">API Decline</div>
    <div class="stat-mini-val" style="color:{dec_c};">{dec:.0%}</div>
    <div class="stat-mini-hint">{dec_hint}</div>
  </div>
  <div class="stat-mini-cell c-users">
    <div class="stat-mini-lbl">Active Users</div>
    <div class="stat-mini-val" style="color:{usr_c};">{users}</div>
    <div class="stat-mini-hint">{usr_hint}</div>
  </div>
  <div class="stat-mini-cell c-nps">
    <div class="stat-mini-lbl">NPS Score</div>
    <div class="stat-mini-val" style="color:{nps_c};">{nps_v}</div>
    <div class="stat-mini-hint">{nps_hint}</div>
  </div>
  <div class="stat-mini-cell c-p1">
    <div class="stat-mini-lbl">Open P1s</div>
    <div class="stat-mini-val" style="color:{p1_c};">{p1}</div>
    <div class="stat-mini-hint">{p1_hint}</div>
  </div>
</div>
<div class="annot">
  ARR ${arr:,} &nbsp;·&nbsp; {int(open_t)} open tickets total &nbsp;·&nbsp; {len(signals)} risk signal{"s" if len(signals)!=1 else ""} fired
</div>
""", unsafe_allow_html=True)

            # ── signals ───────────────────────────────────────────────────────
            CRITICAL_SIGS = {"Multiple P1 incidents indicate severe product pain.",
                             "Account is still on SDK v3.x near security/deprecation deadlines."}
            sig_html = "".join(
                f'<span class="signal-tag{"  critical" if s in CRITICAL_SIGS else ""}">{s}</span>'
                for s in signals[:5]
            )
            if sig_html or sdk_html:
                st.markdown(f'<div style="margin:10px 0 12px;">{sig_html}{sdk_html}</div>',
                            unsafe_allow_html=True)

            # ── explanation ───────────────────────────────────────────────────
            if expl and expl not in ("nan", ""):
                st.markdown(f"""
<div style="font-size:10px;font-weight:600;color:#2e2e48;text-transform:uppercase;
            letter-spacing:.7px;margin-bottom:5px;">AI Analysis</div>
<div class="expl-text">{expl}</div>""", unsafe_allow_html=True)

            # ── action ────────────────────────────────────────────────────────
            if action and action not in ("nan", ""):
                st.markdown(f"""
<div class="action-line">
  <span>→ &nbsp;<strong style="color:#818cf8;">Recommended action:</strong> &nbsp;{action}</span>
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════ DASHBOARD (minimal) ═════════════
with t2:

    # ── Non-obvious insight ───────────────────────────────────────────────────
    insight = load_insight()
    if insight:
        st.markdown(f"""
<div style="background:linear-gradient(120deg,#0b0b24,#0f1130);
            border:1px solid #262660;border-radius:14px;padding:22px 26px;margin-bottom:24px;
            display:flex;gap:18px;align-items:flex-start;">
  <div style="font-size:28px;flex-shrink:0;margin-top:2px;">💡</div>
  <div>
    <div style="font-size:10px;font-weight:700;color:#4f46e5;text-transform:uppercase;
                letter-spacing:1px;margin-bottom:7px;">Non-Obvious Insight</div>
    <div style="font-size:14px;color:#a5b4fc;line-height:1.75;">{insight}</div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── Row 1: 3 summary cards ────────────────────────────────────────────────
    ra, rb, rc = st.columns(3, gap="medium")

    # ── ARR summary ──
    with ra:
        at_risk_arr = int(df.loc[df["risk_tier"].isin(["High","Medium"]), "arr"].sum())
        med_arr     = int(df.loc[df["risk_tier"]=="Medium","arr"].sum())
        pct_at_risk = at_risk_arr / total_arr * 100 if total_arr else 0
        high_pct    = high_arr / total_arr * 100 if total_arr else 0
        med_pct     = med_arr  / total_arr * 100 if total_arr else 0
        low_arr     = int(df.loc[df["risk_tier"]=="Low","arr"].sum())
        low_pct     = max(0, 100 - high_pct - med_pct)

        arr_rows = ""
        for lbl, val, pct, c in [
            ("High",   high_arr, high_pct, "#f87171"),
            ("Medium", med_arr,  med_pct,  "#fbbf24"),
            ("Low",    low_arr,  low_pct,  "#34d399"),
        ]:
            arr_rows += f"""
<div style="margin-bottom:8px;">
  <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
    <span style="font-size:12px;color:{c};">&#9679; {lbl}</span>
    <span style="font-size:12px;color:#6b6b8a;">${val/1000:.0f}K &nbsp;&middot;&nbsp; {pct:.0f}%</span>
  </div>
  <div style="height:3px;background:#1a1a2e;border-radius:9999px;overflow:hidden;">
    <div style="width:{pct:.0f}%;height:3px;background:{c};border-radius:9999px;"></div>
  </div>
</div>"""

        st.markdown(f"""
<div style="background:#13131f;border:1px solid #1a1a2e;border-radius:14px;padding:20px;">
  <div style="font-size:10px;font-weight:700;color:#44445a;text-transform:uppercase;
              letter-spacing:.8px;margin-bottom:14px;">ARR Breakdown</div>
  <div style="font-size:28px;font-weight:700;color:#f87171;margin-bottom:2px;">
    ${at_risk_arr/1000:.0f}K
  </div>
  <div style="font-size:11px;color:#44445a;margin-bottom:16px;">at risk &nbsp;&middot;&nbsp; {pct_at_risk:.0f}% of total</div>
  {arr_rows}
</div>""", unsafe_allow_html=True)

    # ── Signal frequency ──
    with rb:
        from collections import Counter
        all_sigs = []
        for v in df["heuristic_reasons"]: all_sigs.extend(safe_list(v))
        freq = Counter(all_sigs).most_common(6)
        st.markdown("""
<div style="font-size:10px;font-weight:700;color:#44445a;text-transform:uppercase;
            letter-spacing:.8px;margin-bottom:14px;">Top Risk Signals This Quarter</div>""",
            unsafe_allow_html=True)
        short_map = {
            "Usage is declining materially over the last 6 months.": "Usage declining",
            "Multiple P1 incidents indicate severe product pain.":    "Multiple P1 tickets",
            "Support ticket volume is elevated.":                     "High ticket volume",
            "Open support issues remain unresolved near renewal.":    "Open tickets at renewal",
            "Adoption is weak (few active users/workflows).":         "Weak adoption",
            "NPS indicates detractor sentiment.":                     "NPS detractor",
            "Account is still on SDK v3.x near security/deprecation deadlines.": "SDK v3 risk",
            "NPS is passive, not strongly positive.":                 "NPS passive",
            "Note competitor mention detected in CSM notes.":         "Competitor mentioned",
            "Note budget pressure detected in CSM notes.":            "Budget pressure",
        }
        sig_colors = ["#f87171","#f87171","#fbbf24","#fbbf24","#6366f1","#6366f1"]
        max_f = freq[0][1] if freq else 1
        for i,(sig,cnt) in enumerate(freq):
            c2 = sig_colors[i] if i < len(sig_colors) else "#6366f1"
            label = short_map.get(sig, sig[:40])
            pct2 = cnt/max_f*100
            st.markdown(f"""
<div style="margin-bottom:10px;">
  <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
    <span style="font-size:12px;color:#8888a8;">{label}</span>
    <span style="font-size:12px;font-weight:700;color:{c2};">{cnt}</span>
  </div>
  <div style="height:4px;background:#1a1a2e;border-radius:9999px;overflow:hidden;">
    <div style="width:{pct2:.0f}%;height:4px;background:{c2};border-radius:9999px;"></div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── Top 6 leaderboard ──
    with rc:
        st.markdown("""
<div style="font-size:10px;font-weight:700;color:#44445a;text-transform:uppercase;
            letter-spacing:.8px;margin-bottom:14px;">Top Accounts by Risk Score</div>""",
            unsafe_allow_html=True)
        top6 = df.nlargest(6,"risk_score")[["account_name","risk_score","risk_tier","arr","days_to_renewal"]]
        for rank,(_, r) in enumerate(top6.iterrows(), 1):
            tm2 = TIER_META.get(r["risk_tier"], TIER_META["Low"])
            sc  = int(r["risk_score"])
            try:   dys = int(r["days_to_renewal"])
            except: dys = 0
            urgent = dys <= 7
            st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;
            background:#0f0f1e;border:1px solid {'#3b1919' if urgent else '#1a1a2e'};
            border-radius:8px;margin-bottom:6px;">
  <div style="font-size:11px;color:#2a2a4a;width:14px;font-weight:700;">{rank}</div>
  <div style="flex:1;min-width:0;">
    <div style="font-size:12px;font-weight:600;color:#c8c8e0;white-space:nowrap;
                overflow:hidden;text-overflow:ellipsis;">{r['account_name']}</div>
    <div style="font-size:10px;color:#44445a;margin-top:2px;">
      ${int(r['arr']):,} · {dys}d{'  ⚡' if urgent else ''}
    </div>
  </div>
  <div style="font-size:15px;font-weight:700;color:{tm2['color']};flex-shrink:0;">{sc}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 2: CSM workload (full width) ─────────────────────────────────────
    se_col, _ = st.columns([1, 1], gap="medium")
    with se_col:
        st.markdown("""
<div style="font-size:10px;font-weight:700;color:#44445a;text-transform:uppercase;
            letter-spacing:.8px;margin-bottom:14px;">CSM Workload — At-Risk ARR</div>""", unsafe_allow_html=True)

        if "csm_name" in df.columns:
            at_risk_df = df[df["risk_tier"].isin(["High","Medium"])]
            if len(at_risk_df):
                cload = (at_risk_df.groupby("csm_name")
                                   .agg(n=("account_id","count"),
                                        arr=("arr","sum"),
                                        high=("risk_tier", lambda x: (x=="High").sum()))
                                   .sort_values("arr",ascending=False).reset_index())
                max_a = cload["arr"].max()
                for _, r in cload.iterrows():
                    pct = r["arr"]/max_a*100
                    high_n2 = int(r["high"])
                    initials = "".join(w[0].upper() for w in str(r["csm_name"]).split()[:2])
                    st.markdown(f"""
<div style="background:#0f0f1e;border:1px solid #1a1a2e;border-radius:10px;
            padding:12px 14px;margin-bottom:8px;display:flex;align-items:center;gap:12px;">
  <div style="width:34px;height:34px;border-radius:50%;background:#1e1e3a;border:1px solid #2a2a50;
              display:flex;align-items:center;justify-content:center;
              font-size:11px;font-weight:700;color:#818cf8;flex-shrink:0;">{initials}</div>
  <div style="flex:1;min-width:0;">
    <div style="font-size:12px;font-weight:600;color:#c8c8e0;white-space:nowrap;
                overflow:hidden;text-overflow:ellipsis;">{r['csm_name']}</div>
    <div style="height:4px;background:#1a1a2e;border-radius:9999px;overflow:hidden;margin-top:5px;">
      <div style="width:{pct:.0f}%;height:4px;background:#6366f1;border-radius:9999px;opacity:.7;"></div>
    </div>
  </div>
  <div style="text-align:right;flex-shrink:0;">
    <div style="font-size:13px;font-weight:700;color:#818cf8;">{int(r['n'])}</div>
    <div style="font-size:10px;color:#44445a;">{high_n2} high</div>
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 3: Renewal timeline ────────────────────────────────────────────────
    st.markdown("""
<div style="font-size:10px;font-weight:700;color:#44445a;text-transform:uppercase;
            letter-spacing:.8px;margin-bottom:14px;">Renewal Timeline — Next 90 Days</div>""",
    unsafe_allow_html=True)

    buckets    = {"0–7 days":[], "8–30 days":[], "31–60 days":[], "61–90 days":[]}
    bkt_colors = ["#f87171","#f97316","#fbbf24","#34d399"]
    bkt_bg     = ["#2d0a0a","#1c0d00","#2d1f00","#00231a"]
    bkt_border = ["#5c1a1a","#4a2e00","#5c3d00","#0a4030"]

    for _, r in df.iterrows():
        try: d = int(r["days_to_renewal"])
        except: continue
        tier_icon = {"High":"🔴","Medium":"🟡","Low":"🟢"}.get(str(r["risk_tier"]),"")
        entry = (str(r["account_name"]), int(r["arr"]), str(r["risk_tier"]), int(r["risk_score"]))
        if   d <= 7:  buckets["0–7 days"].append(entry)
        elif d <= 30: buckets["8–30 days"].append(entry)
        elif d <= 60: buckets["31–60 days"].append(entry)
        else:         buckets["61–90 days"].append(entry)

    for col, (lbl, items), c, bg, bd in zip(
        st.columns(4), buckets.items(), bkt_colors, bkt_bg, bkt_border
    ):
        total_bucket_arr = sum(a for _, a, _, _ in items)
        rows_html = ""
        for name, arr2, tier2, sc2 in items:
            tm2 = TIER_META.get(tier2, TIER_META["Low"])
            rows_html += f"""
<div style="padding:7px 0;border-bottom:1px solid #1a1a2e;display:flex;
            align-items:center;justify-content:space-between;gap:8px;">
  <div style="min-width:0;">
    <div style="font-size:12px;color:#c8c8e0;font-weight:500;
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:140px;">{name}</div>
    <div style="font-size:10px;color:#44445a;margin-top:1px;">${arr2/1000:.0f}K</div>
  </div>
  <span style="font-size:10px;font-weight:700;color:{tm2['color']};
               flex-shrink:0;">{sc2}</span>
</div>"""
        if not rows_html:
            rows_html = '<div style="font-size:12px;color:#2a2a4a;font-style:italic;padding:10px 0;">None</div>'

        col.markdown(f"""
<div style="background:{bg};border:1px solid {bd};border-radius:12px;overflow:hidden;">
  <div style="padding:14px 16px;border-bottom:1px solid {bd};">
    <div style="font-size:10px;font-weight:700;color:{c};text-transform:uppercase;letter-spacing:.7px;">{lbl}</div>
    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:6px;">
      <span style="font-size:26px;font-weight:700;color:{c};">{len(items)}</span>
      <span style="font-size:11px;color:{c};opacity:.6;">${total_bucket_arr/1000:.0f}K ARR</span>
    </div>
  </div>
  <div style="padding:0 16px;max-height:200px;overflow-y:auto;">{rows_html}</div>
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════ CHANGELOG RISK ══════════════════
with t3:
    st.markdown("""
<div style="background:#13131f;border:1px solid #1a1a2e;border-radius:14px;
            padding:16px 20px;margin-bottom:20px;
            display:flex;gap:14px;align-items:center;">
  <span style="font-size:20px;flex-shrink:0;">📋</span>
  <div style="font-size:13px;color:#6b6b8a;line-height:1.6;">
    Accounts still on <strong style="color:#fbbf24;">deprecated SDK versions or sunset APIs</strong>
    face forced migrations and security exposure at renewal.
    Each event below shows affected accounts and the ARR at risk before the deadline.
  </div>
</div>""", unsafe_allow_html=True)

    # Parse changelog events
    CHANGELOG_EVENTS = [
        {
            "version": "v4.3.2 — Mar 2026",
            "type": "🔴 Security",
            "title": "Critical privilege escalation vulnerability (CVE-2026-1102)",
            "detail": "All customers must update to v4.3.2 immediately. Accounts on older SDK versions have an unpatched security hole.",
            "affected_check": lambda row: not str(row.get("sdk_version_latest","")).lower().startswith("v4.3"),
            "affected_label": "On SDK older than v4.3.2",
            "color": "#f87171", "bg": "#2d0a0a", "border": "#5c1a1a",
        },
        {
            "version": "v4.3.2 — Apr 30 2026",
            "type": "🔴 Sunset",
            "title": "REST Content Delivery API v2 — FINAL sunset April 30, 2026",
            "detail": "No further extensions. Accounts using REST API v2 will break after this date. SDK v3.x customers are most exposed.",
            "affected_check": lambda row: str(row.get("sdk_version_latest","")).lower().startswith("v3"),
            "affected_label": "Still on SDK v3.x (most exposed)",
            "color": "#f87171", "bg": "#2d0a0a", "border": "#5c1a1a",
        },
        {
            "version": "v4.3.2 — Apr 30 2026",
            "type": "🟡 Deprecation",
            "title": "SDK v3.x stops receiving security patches",
            "detail": "After April 30 2026, SDK v3.x will not receive security patches. Accounts on v3.x are running unsupported software.",
            "affected_check": lambda row: str(row.get("sdk_version_latest","")).lower().startswith("v3"),
            "affected_label": "Still on SDK v3.x",
            "color": "#fbbf24", "bg": "#2d1f00", "border": "#5c3d00",
        },
        {
            "version": "v4.4.0 — May 2026",
            "type": "🟡 Breaking",
            "title": "Legacy editor fully removed in v4.4.0 (expected May 2026)",
            "detail": "All customers must migrate to the new editor. Accounts that haven't migrated will lose editing capability entirely.",
            "affected_check": lambda row: str(row.get("sdk_version_latest","")).lower().startswith(("v3","v4.0","v4.1")),
            "affected_label": "On SDK v3.x, v4.0.x, or v4.1.x (pre-new-editor era)",
            "color": "#fbbf24", "bg": "#2d1f00", "border": "#5c3d00",
        },
        {
            "version": "v4.2.0 — Oct 2025",
            "type": "🟡 Breaking",
            "title": "API response envelope changed: `response.entry` → `response.data`",
            "detail": "Applications built on SDK below v4.2.0 will silently break if they reference `response.entry`. No error thrown — just wrong data.",
            "affected_check": lambda row: str(row.get("sdk_version_latest","")).lower().startswith(("v3","v4.0","v4.1")),
            "affected_label": "On SDK v3.x, v4.0.x, or v4.1.x",
            "color": "#fbbf24", "bg": "#2d1f00", "border": "#5c3d00",
        },
    ]

    for event in CHANGELOG_EVENTS:
        c = event["color"]; bg = event["bg"]; bd = event["border"]

        # Find affected accounts renewing in 90 days
        try:
            exposed = df[df.apply(event["affected_check"], axis=1)]
        except Exception:
            exposed = df.head(0)

        exposed_arr = int(exposed["arr"].sum())
        exposed_n   = len(exposed)

        # account pills
        pills = "".join(
            f'<span style="display:inline-block;background:#0f0f1e;border:1px solid #1a1a2e;'
            f'border-radius:6px;padding:3px 10px;font-size:11px;color:#8888a8;'
            f'margin:2px 3px 2px 0;">'
            f'{row["account_name"]} <span style="color:{TIER_META.get(row["risk_tier"],TIER_META["Low"])["color"]};">'
            f'({row["risk_tier"]})</span></span>'
            for _, row in exposed.head(12).iterrows()
        )
        more = f'<span style="font-size:11px;color:#44445a;"> +{exposed_n-12} more</span>' if exposed_n > 12 else ""

        st.markdown(f"""
<div style="background:{bg};border:1px solid {bd};border-radius:12px;
            padding:18px 22px;margin-bottom:12px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;
              flex-wrap:wrap;gap:10px;margin-bottom:12px;">
    <div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">
        <span style="font-size:11px;font-weight:700;color:{c};background:{bg};
                     border:1px solid {bd};border-radius:6px;padding:2px 9px;">{event['type']}</span>
        <span style="font-size:11px;color:#44445a;">{event['version']}</span>
      </div>
      <div style="font-size:14px;font-weight:600;color:#e0e0f4;">{event['title']}</div>
      <div style="font-size:12px;color:#6b6b8a;margin-top:4px;line-height:1.55;">{event['detail']}</div>
    </div>
    <div style="text-align:right;flex-shrink:0;">
      <div style="font-size:22px;font-weight:700;color:{c};">{exposed_n}</div>
      <div style="font-size:10px;color:#44445a;">accounts exposed</div>
      <div style="font-size:11px;color:{c};margin-top:2px;">${exposed_arr/1000:.0f}K ARR</div>
    </div>
  </div>
  <div style="font-size:10px;font-weight:600;color:#44445a;text-transform:uppercase;
              letter-spacing:.6px;margin-bottom:6px;">{event['affected_label']}</div>
  <div>{pills}{more}</div>
</div>""", unsafe_allow_html=True)

    # Download markdown report
    report_path = DATA_DIR / "output" / "renewal_risk_report.md"
    if report_path.exists():
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            "⬇️  Download Markdown Report",
            data=report_path.read_bytes(),
            file_name="renewal_risk_report.md",
            mime="text/markdown",
        )


# ═══════════════════════════════════════════ DATA ════════════════════════════
with t4:
    show_cols = [c for c in [
        "account_name","arr","days_to_renewal","risk_score","risk_tier",
        "avg_api_decline_ratio","active_users_last_month",
        "nps_score","p1_tickets","open_tickets","sdk_version_latest",
        "risk_explanation",
    ] if c in df.columns]

    st.dataframe(
        df[show_cols].sort_values("risk_score", ascending=False).reset_index(drop=True),
        width="stretch", height=580,
    )
    st.download_button(
        "⬇️  Download CSV", data=df.to_csv(index=False).encode(),
        file_name="renewal_risk.csv", mime="text/csv",
    )

# ═══════════════════════════════════════════ ASK AI (CHAT) ═══════════════════
with t5:

    CHAT_STARTERS = [
        "Which High risk accounts have a competitor mention?",
        "Which accounts are hitting dead endpoints right now?",
        "What's the total ARR at risk from the SDK v3 sunset?",
        "Which accounts should I call this week and why?",
        "Which CSMs have the most at-risk accounts?",
        "Which accounts have unpatched CVE-2026-1102?",
    ]

    def _build_chat_system_prompt(data_df: pd.DataFrame | None) -> str:
        changelog_intel = (
            "CRITICAL: REST API v2 sunset date was April 30 2026 — ALREADY PASSED. "
            "Any account on SDK v3.x is hitting dead endpoints in production right now. "
            "CVE-2026-1102 (privilege escalation) is fixed only in v4.3.2+. "
            "SDK v3.x stopped receiving security patches after April 30 2026."
        )
        if data_df is None or len(data_df) == 0:
            return (
                "You are a RiskPulse assistant for Contentstack's BizOps team. "
                "No pipeline output is loaded yet — tell the user to click ▶ Run Analysis in the sidebar first. "
                f"\n\nChangelog intel: {changelog_intel}"
            )

        high = data_df[data_df["risk_tier"] == "High"]
        medium = data_df[data_df["risk_tier"] == "Medium"]

        high_lines = "\n".join(
            f"- {r['account_name']} | ARR ${int(r['arr']):,} | score {r['risk_score']} "
            f"| SDK {r.get('sdk_version_latest','?')} | NPS {r.get('nps_score','?')}"
            for _, r in high.iterrows()
        )
        medium_lines = "\n".join(
            f"- {r['account_name']} | ARR ${int(r['arr']):,} | score {r['risk_score']}"
            for _, r in medium.iterrows()
        )
        sdk3 = data_df[data_df.get("sdk_version_latest", pd.Series(dtype=str)).str.lower().str.startswith("v3", na=False)] if "sdk_version_latest" in data_df.columns else data_df.head(0)
        sdk3_names = ", ".join(sdk3["account_name"].tolist()[:12]) or "none detected"

        full_context = "\n".join(
            f"{r['account_name']} | {r['risk_tier']} | score {r['risk_score']} "
            f"| ARR ${int(r['arr']):,} | renews in {int(r.get('days_to_renewal', 0))}d "
            f"| SDK {r.get('sdk_version_latest','?')} | NPS {r.get('nps_score','?')} "
            f"| signals: {r.get('heuristic_reasons','')}"
            for _, r in data_df.iterrows()
        )

        return f"""You are a RiskPulse assistant for Contentstack's BizOps team.
You have full access to risk scores for all {len(data_df)} accounts renewing in the next 90 days.

=== CHANGELOG INTEL ===
{changelog_intel}

=== HIGH RISK ({len(high)} accounts) ===
{high_lines if not high.empty else "None"}

=== MEDIUM RISK ({len(medium)} accounts) ===
{medium_lines if not medium.empty else "None"}

=== PRODUCTION EMERGENCY: SDK v3.x ACCOUNTS ===
Hitting dead REST v2 endpoints right now: {sdk3_names}

=== FULL ACCOUNT CONTEXT ===
{full_context}

Answer with specific account names, ARR figures, and concrete next actions.
Prioritise production-impacting issues (SDK sunset, CVE) over softer signals.
Keep answers focused and structured for a BizOps audience."""

    def _stream_chat(messages: list, system: str, api_key: str, model: str):
        client = _anthropic.Anthropic(api_key=api_key)
        with client.messages.stream(
            model=model,
            max_tokens=1024,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    # ── session state ──
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # ── header ──
    st.markdown("""
<div style="display:flex;align-items:flex-start;gap:14px;margin-bottom:24px;">
  <div style="width:40px;height:40px;border-radius:50%;background:#4f46e5;
              display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;">✦</div>
  <div>
    <div style="font-size:16px;font-weight:700;color:#c7d2fe;">RiskPulse Chat</div>
    <div style="font-size:13px;color:#44445a;margin-top:2px;">
      Full portfolio context loaded · Ask anything about your renewal accounts
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    if not _ANTHROPIC_OK:
        st.error("anthropic package not installed. Run: pip install anthropic>=0.49.0")
        st.stop()

    chat_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    chat_model   = os.getenv("LLM_MODEL", "claude-haiku-4-5")

    if not chat_api_key or chat_api_key.startswith("sk-ant-..."):
        st.warning("Set ANTHROPIC_API_KEY in .env to enable chat. The sidebar API key field also works.")
        chat_api_key = api_key  # fall back to sidebar input

    system_prompt = _build_chat_system_prompt(df)

    # ── starter questions ──
    if not st.session_state.chat_history:
        st.markdown("""
<div style="font-size:10px;font-weight:600;color:#44445a;text-transform:uppercase;
            letter-spacing:.8px;margin-bottom:10px;">Suggested questions</div>""",
            unsafe_allow_html=True)
        cols = st.columns(3)
        for i, q in enumerate(CHAT_STARTERS):
            if cols[i % 3].button(q, key=f"starter_{i}", use_container_width=True):
                st.session_state.chat_history.append({"role": "user", "content": q})
                st.rerun()

    # ── conversation history ──
    for msg in st.session_state.chat_history:
        is_user = msg["role"] == "user"
        align   = "flex-end" if is_user else "flex-start"
        bg      = "#1e1e3a" if is_user else "#13131f"
        border  = "#2a2a50" if is_user else "#1a1a2e"
        color   = "#c7d2fe" if is_user else "#c8c8e0"
        prefix  = "" if is_user else "✦ &nbsp;"
        st.markdown(f"""
<div style="display:flex;justify-content:{align};margin-bottom:10px;">
  <div style="max-width:82%;background:{bg};border:1px solid {border};border-radius:12px;
              padding:12px 16px;font-size:14px;color:{color};line-height:1.65;">
    {prefix}{msg['content']}
  </div>
</div>""", unsafe_allow_html=True)

    # ── input ──
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.container():
        col_inp, col_btn = st.columns([6, 1])
        with col_inp:
            user_input = st.text_input(
                "Message",
                placeholder="Ask about accounts, risk signals, SDK issues…",
                label_visibility="collapsed",
                key="chat_input",
            )
        with col_btn:
            send = st.button("Send →", type="primary", use_container_width=True)

    if (send or user_input) and user_input.strip():
        if not chat_api_key:
            st.error("No API key found. Paste it in the sidebar or set ANTHROPIC_API_KEY in .env.")
        else:
            st.session_state.chat_history.append({"role": "user", "content": user_input.strip()})
            with st.spinner("Thinking…"):
                messages_for_api = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.chat_history
                ]
                try:
                    response_text = ""
                    response_box = st.empty()
                    for chunk in _stream_chat(messages_for_api, system_prompt, chat_api_key, chat_model):
                        response_text += chunk
                        response_box.markdown(f"""
<div style="background:#13131f;border:1px solid #1a1a2e;border-radius:12px;
            padding:14px 18px;font-size:14px;color:#c8c8e0;line-height:1.7;margin-top:8px;">
✦ &nbsp;{response_text}▌
</div>""", unsafe_allow_html=True)
                    response_box.markdown(f"""
<div style="background:#13131f;border:1px solid #1a1a2e;border-radius:12px;
            padding:14px 18px;font-size:14px;color:#c8c8e0;line-height:1.7;margin-top:8px;">
✦ &nbsp;{response_text}
</div>""", unsafe_allow_html=True)
                    st.session_state.chat_history.append({"role": "assistant", "content": response_text})
                except Exception as e:
                    st.error(f"Chat error: {e}")

    # ── clear button ──
    if st.session_state.chat_history:
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        if st.button("Clear conversation", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()

    st.markdown("""
<div style="font-size:11px;color:#2a2a44;margin-top:16px;text-align:center;">
  Powered by Claude · Full portfolio context loaded as system prompt
</div>""", unsafe_allow_html=True)


# ── footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;padding:28px 0 4px;">
  <span style="font-size:11px;color:#1e1e30;">
    RiskPulse &nbsp;·&nbsp; Contentstack BizOps
  </span>
</div>""", unsafe_allow_html=True)
