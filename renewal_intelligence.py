import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib import error, request

import ssl
try:
    import certifi
    _SSL_CTX: ssl.SSLContext = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

# Load .env if present (local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pandas as pd


RISK_WEIGHTS = {
    "usage_decline": 18,
    "very_low_adoption": 15,
    "ticket_volume": 10,
    "p1_ticket_burden": 12,
    "slow_resolution": 8,
    "open_ticket_penalty": 9,
    "nps_detractor": 14,
    "nps_passive": 6,
    "note_competitor_mention": 14,
    "note_budget_pressure": 10,
    "note_executive_escalation": 8,
    "note_silent_churn": 12,
    "sdk_deprecation_risk": 12,
    "security_or_compliance_blocker": 11,
}


@dataclass
class LLMConfig:
    provider: str
    api_key: Optional[str]
    model: str
    endpoint: str = "https://api.openai.com/v1/chat/completions"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RiskPulse pipeline")
    parser.add_argument("--data-dir", default=".", help="Path containing assignment data files")
    parser.add_argument(
        "--as-of-date",
        default=datetime.now(timezone.utc).date().isoformat(),
        help="Reference date in YYYY-MM-DD for 90-day renewal window",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to write ranked risk outputs",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=15,
        help="Number of high-priority rows to include in markdown report",
    )
    return parser.parse_args()


def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    clean = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    clean = re.sub(r"\s+", " ", clean).strip()
    replacements = {
        "corp": "corporation",
        "co": "company",
        "tech": "technology",
        "moters": "motors",
        "britepath": "brightpath",
        "pinacle": "pinnacle",
        "renewl": "renewal",
    }
    tokens = [replacements.get(t, t) for t in clean.split()]
    return " ".join(tokens)


def parse_csm_notes(notes_text: str) -> List[Dict[str, str]]:
    chunks = [c.strip() for c in notes_text.split("---") if c.strip()]
    parsed = []
    for chunk in chunks:
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        header = lines[0]
        body = " ".join(lines[1:]) if len(lines) > 1 else lines[0]
        full = " ".join(lines)
        acct_match = re.search(r"(?:acct|account|#)\s*([0-9]{4})", full, re.IGNORECASE)
        parsed.append(
            {
                "raw_header": header,
                "note_text": full,
                "account_id_hint": int(acct_match.group(1)) if acct_match else None,
                "header_body_text": f"{header} {body}".strip(),
            }
        )
    return parsed


def match_note_to_account(note: Dict[str, str], accounts_df: pd.DataFrame) -> Optional[int]:
    if note.get("account_id_hint") in set(accounts_df["account_id"].tolist()):
        return int(note["account_id_hint"])

    text = normalize_name(note["header_body_text"])
    account_names = accounts_df["account_name"].tolist()
    normalized = {name: normalize_name(name) for name in account_names}

    best_score = 0.0
    best_account = None
    for name, norm in normalized.items():
        if not norm:
            continue
        score = SequenceMatcher(None, text, norm).ratio()
        if norm in text:
            score += 0.3
        if score > best_score:
            best_score = score
            best_account = name

    close = get_close_matches(text, normalized.values(), n=1, cutoff=0.55)
    if close and best_score < 0.58:
        reverse = {v: k for k, v in normalized.items()}
        best_account = reverse[close[0]]
        best_score = 0.58

    if best_account and best_score >= 0.58:
        row = accounts_df.loc[accounts_df["account_name"] == best_account].iloc[0]
        return int(row["account_id"])
    return None


def add_note_flags(text: str) -> Dict[str, int]:
    lower = text.lower()
    competitor = int(bool(re.search(r"hygraph|strapi|sanity|contentful|kontent|builder\.io|wordpress", lower)))
    budget = int(bool(re.search(r"budget|discount|price increase|procurement|downgrade|contraction", lower)))
    exec_escalation = int(bool(re.search(r"\bcto\b|\bciso\b|\bvp\b|\bcro\b|leadership", lower)))
    silent_churn = int(bool(re.search(r"silent churn|usage has cratered|shelfware|lost faith|stopped using", lower)))
    security = int(bool(re.search(r"soc 2|security questionnaire|gdpr|compliance|regulated|vulnerability", lower)))
    return {
        "note_competitor_mention": competitor,
        "note_budget_pressure": budget,
        "note_executive_escalation": exec_escalation,
        "note_silent_churn": silent_churn,
        "security_or_compliance_blocker": security,
    }


def build_features(data_dir: Path, as_of_date: datetime) -> pd.DataFrame:
    accounts = pd.read_csv(data_dir / "accounts.csv")
    usage = pd.read_csv(data_dir / "usage_metrics.csv")
    tickets = pd.read_csv(data_dir / "support_tickets.csv")
    nps = pd.read_csv(data_dir / "nps_responses.csv")
    notes_text = (data_dir / "csm_notes.txt").read_text(encoding="utf-8")

    accounts["contract_end_date"] = pd.to_datetime(accounts["contract_end_date"])
    usage["month"] = pd.to_datetime(usage["month"])
    tickets["created_date"] = pd.to_datetime(tickets["created_date"])

    cutoff = as_of_date + pd.Timedelta(days=90)
    renewals = accounts[
        (accounts["contract_end_date"] >= as_of_date) & (accounts["contract_end_date"] <= cutoff)
    ].copy()

    usage_agg = []
    for account_id, group in usage.groupby("account_id"):
        g = group.sort_values("month")
        first3 = g.head(3)
        last3 = g.tail(3)
        api_decline = 0.0
        if first3["api_calls"].mean() > 0:
            api_decline = (first3["api_calls"].mean() - last3["api_calls"].mean()) / first3["api_calls"].mean()
        users_decline = 0.0
        if first3["active_users"].mean() > 0:
            users_decline = (first3["active_users"].mean() - last3["active_users"].mean()) / first3["active_users"].mean()
        usage_agg.append(
            {
                "account_id": account_id,
                "api_calls_last_month": int(g.iloc[-1]["api_calls"]),
                "active_users_last_month": int(g.iloc[-1]["active_users"]),
                "workflows_last_month": int(g.iloc[-1]["workflows_triggered"]),
                "avg_api_decline_ratio": round(max(api_decline, 0), 4),
                "avg_users_decline_ratio": round(max(users_decline, 0), 4),
                "sdk_version_latest": str(g.iloc[-1]["sdk_version"]),
            }
        )
    usage_features = pd.DataFrame(usage_agg)

    ticket_features = (
        tickets.groupby("account_id")
        .agg(
            tickets_total=("ticket_id", "count"),
            p1_tickets=("priority", lambda s: int((s == "P1").sum())),
            open_tickets=("status", lambda s: int((s.str.lower() == "open").sum())),
            avg_resolution_hours=("resolution_time_hours", "mean"),
        )
        .reset_index()
    )
    ticket_features["avg_resolution_hours"] = ticket_features["avg_resolution_hours"].fillna(0)

    nps_features = nps.groupby("account_id").agg(nps_score=("score", "mean"), nps_comment=("verbatim_comment", "last")).reset_index()

    parsed_notes = parse_csm_notes(notes_text)
    note_rows = []
    for note in parsed_notes:
        matched = match_note_to_account(note, accounts)
        if matched is None:
            continue
        flags = add_note_flags(note["note_text"])
        row = {"account_id": matched, "csm_note_text": note["note_text"]}
        row.update(flags)
        note_rows.append(row)

    if note_rows:
        notes_df = pd.DataFrame(note_rows)
        notes_df = (
            notes_df.groupby("account_id")
            .agg(
                csm_note_text=("csm_note_text", lambda s: " || ".join(s)),
                note_competitor_mention=("note_competitor_mention", "max"),
                note_budget_pressure=("note_budget_pressure", "max"),
                note_executive_escalation=("note_executive_escalation", "max"),
                note_silent_churn=("note_silent_churn", "max"),
                security_or_compliance_blocker=("security_or_compliance_blocker", "max"),
            )
            .reset_index()
        )
    else:
        notes_df = pd.DataFrame(columns=["account_id", "csm_note_text"])

    df = renewals.merge(usage_features, on="account_id", how="left")
    df = df.merge(ticket_features, on="account_id", how="left")
    df = df.merge(nps_features, on="account_id", how="left")
    df = df.merge(notes_df, on="account_id", how="left")

    for col in [
        "tickets_total",
        "p1_tickets",
        "open_tickets",
        "avg_resolution_hours",
        "nps_score",
        "note_competitor_mention",
        "note_budget_pressure",
        "note_executive_escalation",
        "note_silent_churn",
        "security_or_compliance_blocker",
    ]:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    df["csm_note_text"] = df.get("csm_note_text", "").fillna("")
    df["nps_comment"] = df.get("nps_comment", "").fillna("")
    return df


def score_row(row: pd.Series) -> Tuple[int, List[str], Dict[str, float]]:
    contributions: Dict[str, float] = {}
    reasons: List[str] = []

    if row["avg_api_decline_ratio"] >= 0.3 or row["avg_users_decline_ratio"] >= 0.25:
        contributions["usage_decline"] = RISK_WEIGHTS["usage_decline"]
        reasons.append("Usage is declining materially over the last 6 months.")
    if row["active_users_last_month"] <= 3 or row["workflows_last_month"] == 0:
        contributions["very_low_adoption"] = RISK_WEIGHTS["very_low_adoption"]
        reasons.append("Adoption is weak (few active users/workflows).")
    if row["tickets_total"] >= 4:
        contributions["ticket_volume"] = RISK_WEIGHTS["ticket_volume"]
        reasons.append("Support ticket volume is elevated.")
    if row["p1_tickets"] >= 2:
        contributions["p1_ticket_burden"] = RISK_WEIGHTS["p1_ticket_burden"]
        reasons.append("Multiple P1 incidents indicate severe product pain.")
    if row["avg_resolution_hours"] >= 72:
        contributions["slow_resolution"] = RISK_WEIGHTS["slow_resolution"]
        reasons.append("Ticket resolution time is slow, increasing dissatisfaction.")
    if row["open_tickets"] >= 1:
        contributions["open_ticket_penalty"] = RISK_WEIGHTS["open_ticket_penalty"]
        reasons.append("Open support issues remain unresolved near renewal.")
    if row["nps_score"] <= 6 and row["nps_score"] > 0:
        contributions["nps_detractor"] = RISK_WEIGHTS["nps_detractor"]
        reasons.append("NPS indicates detractor sentiment.")
    elif 6 < row["nps_score"] < 8:
        contributions["nps_passive"] = RISK_WEIGHTS["nps_passive"]
        reasons.append("NPS is passive, not strongly positive.")

    for k in [
        "note_competitor_mention",
        "note_budget_pressure",
        "note_executive_escalation",
        "note_silent_churn",
        "security_or_compliance_blocker",
    ]:
        if row.get(k, 0) >= 1:
            contributions[k] = RISK_WEIGHTS[k]
            reasons.append(k.replace("_", " ").capitalize() + " detected in CSM notes.")

    sdk = str(row.get("sdk_version_latest", "")).lower()
    if sdk.startswith("v3"):
        contributions["sdk_deprecation_risk"] = RISK_WEIGHTS["sdk_deprecation_risk"]
        reasons.append("Account is still on SDK v3.x near security/deprecation deadlines.")

    risk_score = int(min(100, round(sum(contributions.values()))))
    return risk_score, reasons, contributions


def assign_tier(score: int) -> str:
    if score >= 65:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def llm_generate(config: LLMConfig, system_prompt: str, user_prompt: str) -> Optional[str]:
    if not config.api_key:
        return None
    if config.provider == "anthropic":
        payload = {
            "model": config.model,
            "max_tokens": 250,
            "temperature": 0.2,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        req = request.Request(
            config.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": config.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
    else:
        payload = {
            "model": config.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        req = request.Request(
            config.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}",
            },
            method="POST",
        )
    try:
        with request.urlopen(req, timeout=45, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if config.provider == "anthropic":
                return data["content"][0]["text"].strip()
            return data["choices"][0]["message"]["content"].strip()
    except (error.URLError, error.HTTPError, KeyError, TimeoutError, json.JSONDecodeError):
        return None


def build_explanations(df: pd.DataFrame, llm_cfg: LLMConfig) -> pd.DataFrame:
    explanations = []
    actions = []
    for _, row in df.iterrows():
        fallback_explanation = "; ".join(row["heuristic_reasons"][:4]) if row["heuristic_reasons"] else "No strong risk signals detected."
        fallback_action = (
            "Schedule executive QBR + remediation plan in 7 days."
            if row["risk_tier"] == "High"
            else "Review product adoption blockers and open support issues."
        )

        prompt = f"""
Account: {row['account_name']} (ID {row['account_id']})
Tier: {row['risk_tier']}
Risk score: {row['risk_score']}
ARR: {row['arr']}
Signals:
- Usage decline ratio: {row['avg_api_decline_ratio']}
- Active users last month: {row['active_users_last_month']}
- Workflows last month: {row['workflows_last_month']}
- Tickets total/P1/Open: {row['tickets_total']}/{row['p1_tickets']}/{row['open_tickets']}
- Avg resolution hrs: {round(float(row['avg_resolution_hours']),1)}
- NPS: {row['nps_score']}
- SDK version: {row['sdk_version_latest']}
- NPS comment: {row['nps_comment']}
- CSM notes: {row['csm_note_text'][:900]}

Return strict JSON with keys:
explanation: plain-English 2 sentences max
recommended_action: one concrete next action sentence
"""
        response = llm_generate(
            llm_cfg,
            system_prompt="You are a BizOps renewal-risk analyst. Be concise and factual.",
            user_prompt=prompt,
        )
        if response:
            try:
                # Strip markdown code fences (Claude often wraps JSON in ```json ... ```)
                clean = re.sub(r"^```(?:json)?\s*", "", response.strip(), flags=re.IGNORECASE)
                clean = re.sub(r"\s*```$", "", clean.strip())
                parsed = json.loads(clean)
                explanations.append(parsed.get("explanation", fallback_explanation))
                actions.append(parsed.get("recommended_action", fallback_action))
                continue
            except (json.JSONDecodeError, AttributeError):
                pass

        explanations.append(fallback_explanation)
        actions.append(fallback_action)

    df["risk_explanation"] = explanations
    df["recommended_action"] = actions
    return df


def derive_non_obvious_insight(df: pd.DataFrame, llm_cfg: LLMConfig) -> str:
    silent = df[
        (df["risk_tier"].isin(["High", "Medium"]))
        & (df["nps_score"] >= 8)
        & (df["avg_api_decline_ratio"] >= 0.25)
    ]
    heuristic = (
        f"Accounts with positive NPS but falling usage suggest silent churn risk: {len(silent)} account(s) in current renewal window."
    )
    table = df[
        [
            "account_name",
            "risk_tier",
            "nps_score",
            "avg_api_decline_ratio",
            "active_users_last_month",
            "note_silent_churn",
            "note_budget_pressure",
        ]
    ].head(35)
    llm_prompt = (
        "Find one non-obvious insight for renewal forecasting that rules-only systems miss. "
        "Use this data sample and respond with one sentence only.\n\n"
        + table.to_csv(index=False)
    )
    response = llm_generate(
        llm_cfg,
        system_prompt="You identify subtle behavioral churn signals from mixed customer telemetry.",
        user_prompt=llm_prompt,
    )
    return response if response else heuristic


def run_pipeline(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    as_of_date = pd.to_datetime(args.as_of_date)

    df = build_features(data_dir, as_of_date)
    scored = df.copy()
    risk_scores = []
    tiers = []
    reasons_col = []
    contribs = []
    for _, row in scored.iterrows():
        score, reasons, contributions = score_row(row)
        risk_scores.append(score)
        tiers.append(assign_tier(score))
        reasons_col.append(reasons)
        contribs.append(contributions)

    scored["risk_score"] = risk_scores
    scored["risk_tier"] = tiers
    scored["heuristic_reasons"] = reasons_col
    scored["risk_contributions"] = contribs

    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if provider == "anthropic":
        llm_cfg = LLMConfig(
            provider="anthropic",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model=os.getenv("LLM_MODEL", "claude-sonnet-4-6"),
            endpoint="https://api.anthropic.com/v1/messages",
        )
    else:
        llm_cfg = LLMConfig(
            provider="openai",
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("LLM_MODEL", "claude-sonnet-4-6"),
            endpoint="https://api.openai.com/v1/chat/completions",
        )
    scored = build_explanations(scored, llm_cfg)
    insight = derive_non_obvious_insight(scored.sort_values("risk_score", ascending=False), llm_cfg)

    out = scored.sort_values(["risk_score", "arr"], ascending=[False, False]).copy()
    out["days_to_renewal"] = (pd.to_datetime(out["contract_end_date"]) - as_of_date).dt.days

    columns = [
        "account_id",
        "account_name",
        "arr",
        "contract_end_date",
        "days_to_renewal",
        "risk_score",
        "risk_tier",
        "risk_explanation",
        "recommended_action",
        "heuristic_reasons",
        "risk_contributions",
        "nps_score",
        "tickets_total",
        "p1_tickets",
        "open_tickets",
        "avg_api_decline_ratio",
        "avg_users_decline_ratio",
        "active_users_last_month",
        "workflows_last_month",
        "sdk_version_latest",
    ]
    out.to_csv(output_dir / "renewal_risk_ranked.csv", index=False, columns=columns)

    top = out.head(args.top_k)
    lines = [
        "# RiskPulse Report",
        "",
        f"- As of date: `{args.as_of_date}`",
        f"- Accounts renewing in 90 days: `{len(out)}`",
        f"- High risk accounts: `{int((out['risk_tier'] == 'High').sum())}`",
        f"- Medium risk accounts: `{int((out['risk_tier'] == 'Medium').sum())}`",
        "",
        "## Non-obvious insight",
        insight,
        "",
        "## Top at-risk accounts",
        "",
    ]
    for _, row in top.iterrows():
        lines.append(
            f"- **{row['account_name']}** (`{row['risk_tier']}`, score `{row['risk_score']}`, ARR `${int(row['arr']):,}`): "
            f"{row['risk_explanation']} Action: {row['recommended_action']}"
        )

    (output_dir / "renewal_risk_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {output_dir / 'renewal_risk_ranked.csv'}")
    print(f"Wrote {output_dir / 'renewal_risk_report.md'}")


if __name__ == "__main__":
    run_pipeline(parse_args())
