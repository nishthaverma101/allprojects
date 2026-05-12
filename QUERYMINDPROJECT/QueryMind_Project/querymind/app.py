"""
app.py  –  QueryMind Streamlit UI
Run: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import os, json
from pipeline import init_gemini, run_pipeline

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="QueryMind – NL-to-SQL Pipeline",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Sora:wght@300;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Sora', sans-serif; }
    code, .stCodeBlock { font-family: 'DM Mono', monospace !important; }

    .main { background: #0d1117; }
    .block-container { padding-top: 2rem; }

    .qm-header {
        background: linear-gradient(135deg, #1a6faf 0%, #0d3b6e 100%);
        border-radius: 12px;
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        color: white;
    }
    .qm-header h1 { margin:0; font-size:2rem; font-weight:700; letter-spacing:-0.5px; }
    .qm-header p  { margin:0.4rem 0 0; opacity:0.8; font-size:0.95rem; font-weight:300; }

    .pipeline-stage {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }
    .stage-label {
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: #58a6ff;
        margin-bottom: 0.4rem;
    }
    .metric-pill {
        display: inline-block;
        background: #1f2937;
        border: 1px solid #374151;
        border-radius: 20px;
        padding: 2px 12px;
        font-size: 0.8rem;
        color: #9ca3af;
        margin-right: 6px;
    }
    .success-badge { color: #3fb950; font-weight:600; }
    .fail-badge    { color: #f85149; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="qm-header">
  <h1>🔷 QueryMind</h1>
  <p>AI-Powered Natural Language → SQL Data Pipeline &nbsp;|&nbsp; Automated Validation &amp; Observability</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    api_key = st.text_input("Gemini API Key", type="password",
                            placeholder="Paste your key from aistudio.google.com")
    st.markdown("---")
    st.markdown("### 📐 Database Schema")
    st.markdown("""
**`orders`** order_id, customer_id, product_id, quantity, order_date, status

**`customers`** customer_id, name, email, region_id, signup_date

**`products`** product_id, product_name, category, unit_price

**`regions`** region_id, region_name
    """)
    st.markdown("---")
    st.markdown("### 💡 Example Questions")
    examples = [
        "What are the top 5 products by total revenue?",
        "How many orders were completed in 2024?",
        "Which region has the most customers?",
        "Show monthly revenue trend for 2023",
        "What is the average order value by product category?",
        "List customers who placed more than 5 orders",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True, key=ex):
            st.session_state["question_input"] = ex

# ── Main Input ────────────────────────────────────────────────────────────────
col1, col2 = st.columns([5, 1])
with col1:
    question = st.text_input(
        "Ask a business question in plain English",
        value=st.session_state.get("question_input", ""),
        placeholder="e.g. What are the top 5 products by total revenue?",
        label_visibility="collapsed",
        key="question_input"
    )
with col2:
    run_btn = st.button("▶ Run Pipeline", use_container_width=True, type="primary")

# ── Pipeline Execution ────────────────────────────────────────────────────────
if run_btn:
    if not api_key:
        st.error("⚠️ Please enter your Gemini API key in the sidebar.")
        st.stop()
    if not question.strip():
        st.warning("Please enter a question first.")
        st.stop()

    # Check DB exists
    if not os.path.exists("data/sales.db"):
        st.error("Database not found. Run `python setup_db.py` first.")
        st.stop()

    with st.spinner("Running pipeline…"):
        model  = init_gemini(api_key)
        result = run_pipeline(model, question)

    st.markdown("---")

    # ── Stage 1: Generated SQL ─────────────────────────────────────────────
    st.markdown('<div class="pipeline-stage"><div class="stage-label">Stage 1 · LLM SQL Generation</div>', unsafe_allow_html=True)
    if result["sql"]:
        st.code(result["sql"], language="sql")
    else:
        st.error("SQL generation failed.")
    st.markdown(f'<span class="metric-pill">⏱ {result["latency_ms"]:.0f} ms total</span>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Stage 2: Validation ────────────────────────────────────────────────
    st.markdown('<div class="pipeline-stage"><div class="stage-label">Stage 2 · Automated Data Validation</div>', unsafe_allow_html=True)
    if result["valid"]:
        st.markdown(f'<span class="success-badge">{result["valid_reason"]}</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="fail-badge">{result["valid_reason"]}</span>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Stage 3: Results ───────────────────────────────────────────────────
    st.markdown('<div class="pipeline-stage"><div class="stage-label">Stage 3 · Query Results</div>', unsafe_allow_html=True)
    if result["exec_error"]:
        st.error(f"Execution error: {result['exec_error']}")
    elif result["rows"]:
        df = pd.DataFrame(result["rows"], columns=result["columns"])
        st.dataframe(df, use_container_width=True)
        st.markdown(f'<span class="metric-pill">📊 {len(df)} rows returned</span>', unsafe_allow_html=True)

        # Auto chart for numeric results
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        text_cols    = df.select_dtypes(exclude="number").columns.tolist()
        if numeric_cols and text_cols:
            st.bar_chart(df.set_index(text_cols[0])[numeric_cols[0]])
    elif result["valid"]:
        st.info("Query returned no rows.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Stage 4: Observability ─────────────────────────────────────────────
    st.markdown('<div class="pipeline-stage"><div class="stage-label">Stage 4 · Pipeline Observability Log</div>', unsafe_allow_html=True)
    st.success("✅ Run logged to `logs/pipeline_log.csv`")
    st.markdown('</div>', unsafe_allow_html=True)

# ── Log Viewer Tab ────────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("📋 View Full Pipeline Audit Log"):
    log_path = "logs/pipeline_log.csv"
    if os.path.exists(log_path):
        log_df = pd.read_csv(log_path)
        st.dataframe(log_df, use_container_width=True)
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total Runs",        len(log_df))
        col_b.metric("Validation Pass %", f"{log_df['validation_passed'].mean()*100:.0f}%")
        col_c.metric("Avg Latency",       f"{log_df['latency_ms'].mean():.0f} ms")
    else:
        st.info("No runs logged yet. Run a query above.")
