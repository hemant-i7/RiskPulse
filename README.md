# RiskPulse

> Identify which accounts are most likely to churn before renewal — and exactly why — using multi-source signal fusion and an LLM explanation layer.

---

## What it does

Given six data sources (account master, usage telemetry, support tickets, CSM call notes, NPS responses, product changelog), this tool:

1. **Reconciles** all sources into a single account-level feature set, handling messy name mismatches in CSM notes via fuzzy matching
2. **Scores** every account renewing in the next 90 days across 14 weighted risk signals (0–100)
3. **Tiers** accounts as High / Medium / Low and generates a ranked renewal risk list
4. **Explains** each at-risk account in plain English using Claude (or GPT-4o) — what signals fired, what the team should do next
5. **Surfaces non-obvious insights** a pure rules engine would miss (e.g. silent churn: high NPS + falling usage)
6. **Flags changelog exposure** — which accounts are on deprecated SDK versions or sunset APIs, and the ARR at stake

---

## Architecture

```
accounts.csv ──────┐
usage_metrics.csv ─┤
support_tickets.csv┼── build_features() ── score_row() ── build_explanations() ── output/
nps_responses.csv ─┤        │                                   (LLM / heuristic fallback)
csm_notes.txt ─────┤   fuzzy match
changelog.md ──────┘   deprecation flags
```

**Pipeline** (`renewal_intelligence.py`) — runs standalone via CLI or triggered from the UI  
**Dashboard** (`app.py`) — Streamlit frontend with account cards, portfolio dashboard, changelog risk view, and raw data export

---

## Scoring model

14 signals, each calibrated to its relative churn impact:

| Signal | Weight |
|--------|--------|
| API call decline (6-month trend) | 18 |
| Active user decline | 15 |
| Competitor mentioned in CSM notes | 14 |
| NPS detractor (≤ 6) | 14 |
| SDK v3.x in use (deprecation deadline) | 12 |
| Silent churn pattern in notes | 12 |
| P1 ticket burden | 12 |
| Security / compliance blocker | 11 |
| Budget pressure in notes | 10 |
| Open tickets near renewal | 9 |
| Slow ticket resolution (≥ 72h) | 8 |
| Executive escalation in notes | 8 |
| NPS passive (7–8) | 6 |

Score capped at 100. Thresholds: **High ≥ 65 · Medium ≥ 35 · Low < 35**

---

## Non-obvious insight: Silent Churn

A rules engine flags detractors and usage decline independently. What it misses: accounts with **NPS 8–10 (promoter range) while API calls and active users drop 25%+ quarter-over-quarter**. These accounts aren't unhappy — they've quietly stopped using the product. They won't escalate. They'll just not renew.

`derive_non_obvious_insight()` detects this pattern explicitly and surfaces it in the dashboard and report.

---

## Changelog risk

`changelog.md` contains breaking changes and deprecation deadlines that directly expose certain accounts at renewal time:

- SDK v3.x security patches ended Apr 30 2026 → accounts still on v3 are running unpatched software
- REST API v2 sunset Apr 30 2026 → SDK v3 customers face breaking changes
- Response envelope changed in v4.2.0 (`response.entry` → `response.data`) → silent breakage risk
- Legacy editor removed in v4.4.0 → customers on old SDK can't use the editor

The **Changelog Risk tab** shows which accounts are exposed, how many, and the ARR at stake per event.

---

## Quick start

### 1. Install

```bash
pip install -r requirements.txt
```

Requires Python 3.9+.

### 2. Configure API key

```bash
cp .env.example .env
# then edit .env and add your key
```

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-haiku-4-5
```

> **No API key?** The pipeline still runs — risk scores and tiers are fully rule-based. LLM explanations fall back to heuristic text automatically.

### 3a. Streamlit app (recommended)

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Click **▶ Run Analysis** in the sidebar.

### 3b. CLI

```bash
python renewal_intelligence.py \
  --data-dir . \
  --as-of-date 2026-05-06 \
  --output-dir output \
  --top-k 15
```

Writes:
- `output/renewal_risk_ranked.csv` — all renewing accounts sorted by risk score
- `output/renewal_risk_report.md` — markdown report with explanations and the non-obvious insight

### CLI options

| Argument | Default | Description |
|----------|---------|-------------|
| `--data-dir` | `.` | Folder containing the input data files |
| `--as-of-date` | today | Reference date for 90-day window (`YYYY-MM-DD`) |
| `--output-dir` | `output` | Where to write results |
| `--top-k` | `15` | Accounts in the markdown report |

---

## Deploy to Streamlit Cloud

1. Push this repo to GitHub (`.env` and `output/` are already git-ignored)
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → connect repo → entry point `app.py`
3. In **App settings → Secrets**, paste:

```toml
LLM_PROVIDER      = "anthropic"
ANTHROPIC_API_KEY = "sk-ant-..."
LLM_MODEL         = "claude-haiku-4-5"
```

No `.env` file needed in production — secrets are injected automatically as environment variables.

---

## Repository structure

```
RiskPulse/
├── renewal_intelligence.py    # Pipeline — data ingestion, scoring, LLM calls (CLI entry point)
├── app.py                     # Streamlit dashboard
├── requirements.txt           # Python dependencies
├── .env.example               # API key template (copy to .env)
├── .gitignore
├── accounts.csv               # 120 accounts — firmographic + contract data
├── usage_metrics.csv          # 6-month usage telemetry
├── support_tickets.csv        # Support ticket history
├── nps_responses.csv          # NPS scores + verbatims
├── csm_notes.txt              # Unstructured CSM call notes
├── changelog.md               # Product changelog (Q4 2025–Q1 2026)
└── output/                    # Generated by the pipeline (git-ignored)
    ├── renewal_risk_ranked.csv
    └── renewal_risk_report.md
```

---

## Tradeoffs

**Weighted scoring vs ML model**  
A gradient-boosted model would handle feature interactions better. Not used here because: no labeled historical churn data was provided, weights are fully interpretable and auditable, and every score can be explained without a black box.

**LLM for explanation, not scoring**  
Running scoring through an LLM per account is expensive, non-deterministic, and hard to audit. The LLM is used where it uniquely adds value: synthesizing messy prose (CSM notes, NPS verbatims) into a concise, actionable sentence.

**Fuzzy match threshold (0.58)**  
Too low → false matches between similar account names. Too high → orphaned CSM notes. 0.58 balances coverage and precision on this 120-account dataset.

**Non-English CSM notes**  
Passed through as-is — the LLM handles multilingual input natively. Regex-based signal flags may miss patterns in non-English notes (known gap, see below).

---

## What I'd do with more time

- **Labeled churn data** — train a classifier on historical renewal outcomes; use the weighted score as a feature, not the final output
- **Live data sources** — replace CSV reads with Salesforce API + product database queries via Snowflake
- **Scheduled pipeline** — nightly Airflow run → S3/Snowflake write → Slack digest for the BizOps team
- **Confidence scores** — surface a data-completeness flag alongside each risk score (accounts with no NPS, no CSM notes get a "low confidence" warning)
- **Foreign-language note handling** — add a translation pass before regex extraction, or use a structured LLM extraction schema to catch signals in any language
- **Cohort benchmarking** — compare each account's usage decline against peers in the same plan tier and industry
- **Feedback loop** — CSMs mark outcomes post-renewal; feeds back into weight calibration over time
- **LLM audit log** — store raw prompts and responses so outputs can be reviewed and the model can be swapped without losing history

---

## What I'd change for production

- Replace CSV inputs with live CRM and product-database reads
- Async + batched LLM calls with rate limiting (120 accounts is fine; 10,000 is not)
- Role-based access — CSMs see only their accounts; team leads see the full portfolio
- A/B test the scoring weights against actual renewal outcomes quarterly
