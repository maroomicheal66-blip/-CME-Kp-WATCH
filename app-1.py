import streamlit as st
import pandas as pd
import json
import io
from datetime import datetime, timezone

st.set_page_config(
    page_title="CME–Kp WATCH | Data Intake",
    page_icon="🛰️",
    layout="wide"
)

st.markdown("""
<style>
.stApp { background: #071426; color: #EAF1FA; }
[data-testid="stHeader"] { background: rgba(7,20,38,0.95); }
[data-testid="stMetric"] {
    background: #10243D; border: 1px solid #294664;
    padding: 14px; border-radius: 12px;
}
div[data-testid="stFileUploader"] {
    background: #10243D; border: 1px dashed #52749A;
    border-radius: 12px; padding: 14px;
}
.small-note { color: #AFC2D8; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

st.title("🛰️ CME–Kp WATCH")
st.subheader("Uncertainty-Aware Space-Weather Monitoring & Decision-Support Prototype")
st.caption("Prototype 0.1 — Data intake and validation only")

st.info(
    "This version receives and audits uploaded CSV/JSON files. "
    "It does not forecast geomagnetic storms, calculate satellite risk, or establish causation."
)

EXPECTED_FILES = {
    "cme": ["CMEAnalysis_2026.csv", "CMEAnalysis_2026.json"],
    "enlil": ["WSAEnlilSimulations_2026.csv", "WSAEnlilSimulations_2026.json"],
    "kp": ["GFZ_Kp_cleaned.csv", "GFZ_Kp_2026.json"],
    "comparison": ["ENLIL_vs_observed_Kp_comparison.csv"],
    "sensitivity": ["Kp_ENLIL_deduplicated_sensitivity.csv"],
}

def classify_file(filename):
    name = filename.lower()
    # Check specific derived datasets before broad ENLIL/Kp filename matches.
    if "sensitivity" in name:
        return "Sensitivity"
    if "comparison" in name:
        return "Comparison"
    if "cmeanalysis" in name or ("cme" in name and "enlil" not in name):
        return "CME"
    if "enlil" in name or "wsa" in name:
        return "ENLIL"
    if "gfz" in name or "kp" in name:
        return "Kp"
    return "Unclassified"

def load_uploaded_file(uploaded):
    raw = uploaded.getvalue()
    filename = uploaded.name
    if filename.lower().endswith(".csv"):
        # Keep original values as text where possible; pandas infers types for useful audit.
        df = pd.read_csv(io.BytesIO(raw), low_memory=False)
        return df, raw, "CSV"
    if filename.lower().endswith(".json"):
        obj = json.loads(raw.decode("utf-8-sig"))
        # Support common JSON layouts without discarding the original object.
        if isinstance(obj, list):
            df = pd.json_normalize(obj)
        elif isinstance(obj, dict):
            candidate = None
            for key in ("data", "results", "records", "Kp", "events", "simulations"):
                if key in obj and isinstance(obj[key], list):
                    candidate = obj[key]
                    break
            if candidate is not None:
                df = pd.json_normalize(candidate)
            else:
                df = pd.json_normalize(obj)
        else:
            df = pd.DataFrame({"value": [obj]})
        return df, raw, "JSON"
    raise ValueError("Unsupported file type. Upload CSV or JSON.")

def audit_dataframe(df, filename, file_type):
    rows, cols = df.shape
    missing_by_col = df.isna().sum()
    missing_total = int(missing_by_col.sum())
    duplicate_rows = int(df.duplicated().sum()) if rows else 0
    memory_bytes = int(df.memory_usage(deep=True).sum())

    date_candidates = [
        c for c in df.columns
        if any(token in str(c).lower() for token in
               ["date", "time", "timestamp", "arrival", "epoch", "datetime"])
    ]
    numeric_candidates = [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c])
    ]

    kp_candidates = [c for c in df.columns if "kp" in str(c).lower()]
    kp_checks = {}
    for col in kp_candidates:
        numeric = pd.to_numeric(df[col], errors="coerce")
        nonnumeric = int((df[col].notna() & numeric.isna()).sum())
        # Kp commonly uses 0–9; preserve values outside this range as flagged, not corrected.
        out_of_range = int(((numeric < 0) | (numeric > 9)).sum())
        kp_checks[col] = {
            "non_numeric_non_missing": nonnumeric,
            "outside_0_to_9": out_of_range
        }

    date_parse = {}
    for col in date_candidates:
        parsed = pd.to_datetime(df[col], errors="coerce", utc=True)
        nonmissing_original = int(df[col].notna().sum())
        parse_failures = int((df[col].notna() & parsed.isna()).sum())
        date_parse[str(col)] = {
            "non_missing_values": nonmissing_original,
            "unparseable_values": parse_failures
        }

    return {
        "filename": filename,
        "classification": classify_file(filename),
        "file_type": file_type,
        "rows": int(rows),
        "columns_count": int(cols),
        "columns": [str(c) for c in df.columns],
        "missing_cells": missing_total,
        "duplicate_rows": duplicate_rows,
        "memory_bytes": memory_bytes,
        "date_candidates": [str(c) for c in date_candidates],
        "numeric_candidates": [str(c) for c in numeric_candidates],
        "date_parse_checks": date_parse,
        "kp_checks": kp_checks,
        "missing_by_column": {str(k): int(v) for k, v in missing_by_col.items()},
        "dtypes": {str(k): str(v) for k, v in df.dtypes.items()},
    }

st.header("01 · Upload research datasets")
uploaded_files = st.file_uploader(
    "Choose your original or cleaned research files",
    type=["csv", "json"],
    accept_multiple_files=True,
    help="You can upload multiple CSV and JSON files in one session."
)

if uploaded_files:
    audits = []
    loaded = {}
    errors = []

    for uploaded in uploaded_files:
        try:
            df, raw, file_type = load_uploaded_file(uploaded)
            audit = audit_dataframe(df, uploaded.name, file_type)
            audits.append(audit)
            loaded[uploaded.name] = df
        except Exception as exc:
            errors.append({"filename": uploaded.name, "error": str(exc)})

    st.header("02 · Dataset inventory")
    if audits:
        inventory = pd.DataFrame([{
            "File": a["filename"],
            "Detected type": a["classification"],
            "Format": a["file_type"],
            "Rows": a["rows"],
            "Columns": a["columns_count"],
            "Missing cells": a["missing_cells"],
            "Duplicate rows": a["duplicate_rows"],
        } for a in audits])
        st.dataframe(inventory, use_container_width=True, hide_index=True)

        total_rows = sum(a["rows"] for a in audits)
        total_missing = sum(a["missing_cells"] for a in audits)
        total_duplicates = sum(a["duplicate_rows"] for a in audits)
        c1, c2, c3 = st.columns(3)
        c1.metric("Files read successfully", len(audits))
        c2.metric("Total rows across files", f"{total_rows:,}")
        c3.metric("Missing cells", f"{total_missing:,}")

        st.header("03 · Quality audit")
        for audit in audits:
            with st.expander(f'{audit["filename"]} · {audit["classification"]}', expanded=False):
                left, right = st.columns(2)
                left.write("**Columns and data types**")
                left.dataframe(
                    pd.DataFrame({
                        "Column": list(audit["dtypes"].keys()),
                        "Data type": list(audit["dtypes"].values())
                    }),
                    use_container_width=True,
                    hide_index=True
                )
                right.write("**Missing values by column**")
                missing_df = pd.DataFrame(
                    list(audit["missing_by_column"].items()),
                    columns=["Column", "Missing cells"]
                )
                right.dataframe(missing_df, use_container_width=True, hide_index=True)

                st.write("**Date/time parsing checks (interpreted as UTC for audit only)**")
                if audit["date_parse_checks"]:
                    st.json(audit["date_parse_checks"])
                else:
                    st.caption("No obvious date/time column names detected.")

                st.write("**Kp value checks**")
                if audit["kp_checks"]:
                    st.json(audit["kp_checks"])
                else:
                    st.caption("No column with 'Kp' in its name detected.")

                st.write("**Detected columns**")
                st.write(", ".join(audit["columns"]) if audit["columns"] else "No columns detected.")

        st.header("04 · Preview")
        selected = st.selectbox("Choose a dataset to preview", list(loaded.keys()))
        st.dataframe(loaded[selected].head(20), use_container_width=True)

        report = {
            "project": "CME-Kp WATCH",
            "prototype": "0.1",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "Data intake and validation only; no forecasting or causal inference.",
            "files": audits,
            "errors": errors
        }
        report_bytes = json.dumps(report, indent=2, ensure_ascii=False, default=str).encode("utf-8")
        st.download_button(
            "⬇️ Download data audit report (JSON)",
            data=report_bytes,
            file_name="CME_Kp_WATCH_data_audit_report.json",
            mime="application/json"
        )

    if errors:
        st.error("Some files could not be read.")
        st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)

else:
    st.markdown("""
    ### Expected research files
    Upload any available subset of these files:
    - `CMEAnalysis_2026.csv` or `.json`
    - `WSAEnlilSimulations_2026.csv` or `.json`
    - `GFZ_Kp_cleaned.csv`
    - `ENLIL_vs_observed_Kp_comparison.csv`
    - `Kp_ENLIL_deduplicated_sensitivity.csv`

    **No file is modified or overwritten.** The report records the audit findings only.
    """)

st.divider()
st.caption("CME–Kp WATCH · Prototype 0.1 · Data intake only · Research integrity: preserve originals, flag anomalies, never silently replace missing or invalid values.")
