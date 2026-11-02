import streamlit as st
import pandas as pd
import json
import io
from datetime import datetime, timezone

st.set_page_config(page_title="CME–Kp WATCH", page_icon="🛰️", layout="wide")

st.markdown("""
<style>
.stApp{background:#071426;color:#EAF1FA}
[data-testid="stSidebar"]{background:#091B30;border-right:1px solid #294664}
[data-testid="stMetric"]{background:#10243D;border:1px solid #294664;padding:14px;border-radius:12px}
[data-testid="stFileUploader"]{background:#10243D;border:1px dashed #6685A7;border-radius:12px;padding:12px}
.hero{background:linear-gradient(120deg,#10243D,#0B1B30);border:1px solid #294664;border-radius:18px;padding:22px}
.kicker{color:#E9C875;letter-spacing:.12em;font-size:.8rem;font-weight:700}
h1,h2,h3{color:#EAF1FA!important}
</style>
""", unsafe_allow_html=True)

for k,v in {"datasets":{},"audits":[],"pdfs":{}}.items():
    if k not in st.session_state: st.session_state[k]=v

def classify(name):
    n=name.lower()
    if "sensitivity" in n:return "Sensitivity"
    if "comparison" in n:return "Comparison"
    if "cmeanalysis" in n:return "CME"
    if "enlil" in n or "wsa" in n:return "ENLIL"
    if "gfz" in n or "kp" in n:return "Kp"
    return "Unclassified"

def read_file(f):
    raw=f.getvalue()
    if f.name.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(raw),low_memory=False),"CSV"
    obj=json.loads(raw.decode("utf-8-sig"))
    if isinstance(obj,list): df=pd.json_normalize(obj)
    elif isinstance(obj,dict):
        val=next((obj[x] for x in ("data","results","records","Kp","events","simulations") if isinstance(obj.get(x),list)),obj)
        df=pd.json_normalize(val)
    else: df=pd.DataFrame({"value":[obj]})
    return df,"JSON"

def audit(df,f,fmt):
    miss=df.isna().sum()
    dates=[c for c in df.columns if any(t in str(c).lower() for t in ("date","time","timestamp","arrival","epoch"))]
    kp=[c for c in df.columns if "kp" in str(c).lower()]
    return {
      "filename":f,"classification":classify(f),"format":fmt,
      "rows":len(df),"columns":len(df.columns),"column_names":[str(c) for c in df.columns],
      "missing_cells":int(miss.sum()),"duplicates":int(df.duplicated().sum()) if len(df) else 0,
      "dtypes":{str(c):str(t) for c,t in df.dtypes.items()},
      "missing_by_column":{str(c):int(v) for c,v in miss.items()},
      "date_checks":{str(c):{"non_missing":int(df[c].notna().sum()),
       "unparseable":int((df[c].notna() & pd.to_datetime(df[c],errors="coerce",utc=True).isna()).sum())} for c in dates},
      "kp_checks":{str(c):{"nonnumeric":int((df[c].notna() & pd.to_numeric(df[c],errors="coerce").isna()).sum()),
       "outside_0_to_9":int(((pd.to_numeric(df[c],errors="coerce")<0)|(pd.to_numeric(df[c],errors="coerce")>9)).sum())} for c in kp}
    }

with st.sidebar:
    st.markdown("## 🛰️ CME–Kp WATCH")
    st.markdown('<div class="kicker">SPACE WEATHER PLATFORM</div>',unsafe_allow_html=True)
    page=st.radio("NAVIGATION",["Overview","Data Center","Quality Audit","Research Documents","Admin Center","Research Scope"])
    st.divider()
    st.caption(f'{len(st.session_state.audits)} dataset(s) · {len(st.session_state.pdfs)} PDF(s) in this session')

st.markdown("""
<div class="hero">
<div class="kicker">SPACE WEATHER MONITORING & RESEARCH</div>
<h1>🛰️ CME–Kp WATCH</h1>
Uncertainty-Aware Space-Weather Monitoring & Decision-Support Prototype
<p><span class="kicker">PROTOTYPE 0.2 · DATA & DOCUMENT INTAKE</span></p>
</div>
""",unsafe_allow_html=True)
st.info("This prototype audits CSV/JSON datasets and accepts PDF research documents. It does not forecast storms, calculate satellite risk, or establish causation.")

if page=="Overview":
    st.header("Mission Control")
    a,b,c,d=st.columns(4)
    a.metric("Datasets",len(st.session_state.audits))
    b.metric("Records",f'{sum(x["rows"] for x in st.session_state.audits):,}')
    c.metric("Missing cells",f'{sum(x["missing_cells"] for x in st.session_state.audits):,}')
    d.metric("PDF documents",len(st.session_state.pdfs))
    st.subheader("Platform modules")
    x,y=st.columns(2)
    x.info("01 · Data Center\n\nUpload research datasets.")
    y.info("02 · Quality Audit\n\nInspect missing values, duplicates and data types.")
    x.info("03 · Research Documents\n\nManage PDF papers and reports.")
    y.info("04 · Analysis Engine\n\nPlanned; not active in this version.")
    st.warning("Statistics describe only files uploaded during the current session.")

elif page=="Data Center":
    st.header("01 · Upload Research Datasets")
    st.caption("Accepted formats: CSV and JSON. Upload PDFs in Research Documents.")
    files=st.file_uploader("Choose original or cleaned research files",type=["csv","json"],accept_multiple_files=True,key="datasets")
    if files:
        loaded,checks={},[]
        for f in files:
            try:
                df,fmt=read_file(f); loaded[f.name]=df; checks.append(audit(df,f.name,fmt))
            except Exception as e: st.error(f"{f.name}: {e}")
        st.session_state.datasets=loaded
        st.session_state.audits=checks
        if checks:
            st.success(f"{len(checks)} dataset(s) read successfully.")
            st.dataframe(pd.DataFrame([{"File":z["filename"],"Type":z["classification"],"Rows":z["rows"],"Columns":z["columns"],"Missing":z["missing_cells"],"Duplicates":z["duplicates"]} for z in checks]),use_container_width=True,hide_index=True)
    st.markdown("**Expected files**")
    st.markdown("- CMEAnalysis_2026.csv / JSON\n- WSAEnlilSimulations_2026.csv / JSON\n- GFZ_Kp_cleaned.csv\n- ENLIL_vs_observed_Kp_comparison.csv\n- Kp_ENLIL_deduplicated_sensitivity.csv")
    st.warning("Uploads are session-only in this prototype. Keep original files backed up separately.")

elif page=="Quality Audit":
    st.header("02 · Quality Audit")
    if not st.session_state.audits: st.info("Upload datasets first in Data Center.")
    else:
        for z in st.session_state.audits:
            with st.expander(f'{z["filename"]} · {z["classification"]}'):
                st.write("**Data types**"); st.json(z["dtypes"])
                st.write("**Missing values by column**"); st.json(z["missing_by_column"])
                st.write("**Date/time parsing (UTC interpretation for audit only)**"); st.json(z["date_checks"])
                st.write("**Kp checks**"); st.json(z["kp_checks"])
        choice=st.selectbox("Preview dataset",list(st.session_state.datasets))
        st.dataframe(st.session_state.datasets[choice].head(25),use_container_width=True)
        report={"project":"CME-Kp WATCH","prototype":"0.2","generated_utc":datetime.now(timezone.utc).isoformat(),"files":st.session_state.audits}
        st.download_button("Download audit report (JSON)",json.dumps(report,indent=2,ensure_ascii=False).encode(), "CME_Kp_WATCH_audit_0_2.json","application/json")

elif page=="Research Documents":
    st.header("03 · Research Documents")
    st.write("Upload research papers, references, protocols and reports as PDF.")
    pdfs=st.file_uploader("Choose PDF documents",type=["pdf"],accept_multiple_files=True,key="pdfs")
    if pdfs:
        for f in pdfs:
            data=f.getvalue()
            if data.startswith(b"%PDF"): st.session_state.pdfs[f.name]=data
            else: st.error(f"{f.name} is not recognized as a valid PDF file.")
    if st.session_state.pdfs:
        for name,data in st.session_state.pdfs.items():
            st.download_button(f"Download {name}",data,name,"application/pdf",key="pdf_"+name)
    else: st.info("No PDF documents uploaded in this session.")
    st.warning("PDF files are session-only. Permanent storage and PDF text extraction are not implemented yet.")

elif page=="Admin Center":
    st.header("04 · Admin Center")
    st.warning("Prototype limitation: this page is not protected by administrator authentication. Do not upload confidential documents. Secure login and permanent storage must be added before public/team administration.")
    st.write(f"Datasets in session: **{len(st.session_state.audits)}**")
    st.write(f"PDFs in session: **{len(st.session_state.pdfs)}**")
    manifest={"datasets":st.session_state.audits,"pdfs":[{"filename":n,"bytes":len(v)} for n,v in st.session_state.pdfs.items()],"storage":"session-only"}
    st.download_button("Export session inventory (JSON)",json.dumps(manifest,indent=2,ensure_ascii=False).encode(),"CME_Kp_WATCH_manifest.json","application/json")
    if st.button("Clear current session uploads"):
        st.session_state.datasets={}; st.session_state.audits=[]; st.session_state.pdfs={}
        st.success("Current session uploads cleared. Original files on your device are unchanged.")

elif page=="Research Scope":
    st.header("05 · Research Scope & Integrity")
    st.markdown("""
**Research objective:** assess the association between predicted CME arrival times and observed geomagnetic activity represented by Kp.

**Implemented:** CSV/JSON intake, filename classification, row/column and data-type audit, missing/duplicate checks, basic timestamp parsing, basic Kp range checks, and separate PDF intake.

**Not implemented:** CME forecasting, geomagnetic storm prediction, satellite-risk estimation, causal inference, permanent storage, secure admin authentication, PDF text extraction, or operational recommendations.

**Integrity rules:** preserve originals; never silently replace missing/invalid values; distinguish observations from model predictions; document limitations and uncertainty.
""")

st.divider()
st.caption("CME–Kp WATCH · Prototype 0.2 · Data and document intake only · Preserve originals and report anomalies transparently.")
