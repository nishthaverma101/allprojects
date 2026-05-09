"""
pipeline.py  –  Core QueryMind engine.
Handles: LLM prompt → SQL generation → validation → execution → observability logging.
"""
import sqlite3, csv, os, re, time, json
from datetime import datetime
import google.generativeai as genai

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH   = "data/sales.db"
LOG_PATH  = "logs/pipeline_log.csv"
os.makedirs("logs", exist_ok=True)

# Database schema (injected into every LLM prompt for context)
SCHEMA = """
You have access to a SQLite database with the following schema:

TABLE regions    (region_id INTEGER PK, region_name TEXT)
TABLE customers  (customer_id INTEGER PK, name TEXT, email TEXT, region_id FK→regions, signup_date TEXT 'YYYY-MM-DD')
TABLE products   (product_id INTEGER PK, product_name TEXT, category TEXT, unit_price REAL)
TABLE orders     (order_id INTEGER PK, customer_id FK→customers, product_id FK→products,
                  quantity INTEGER, order_date TEXT 'YYYY-MM-DD', status TEXT ['completed','pending','cancelled'])

Rules:
- Revenue = quantity * unit_price
- Always alias computed columns (e.g. SUM(...) AS total_revenue)
- Use STRFTIME('%Y', order_date) for year-based grouping
- Limit results to 20 rows max unless the user asks for all
- Return ONLY the raw SQL query. No explanation, no markdown, no backticks.
"""

BLOCKED_KEYWORDS = ["DROP","DELETE","INSERT","UPDATE","ALTER","TRUNCATE","CREATE","REPLACE"]

# ── Initialise Gemini ─────────────────────────────────────────────────────────
def init_gemini(api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")

# ── 1. SQL Generation ─────────────────────────────────────────────────────────
def generate_sql(model, question: str) -> str:
    prompt = f"{SCHEMA}\n\nUser question: {question}\n\nSQL query:"
    response = model.generate_content(prompt)
    sql = response.text.strip()
    # strip accidental markdown fences
    sql = re.sub(r"```sql|```", "", sql).strip()
    return sql

# ── 2. Data Validation Layer ───────────────────────────────────────────────────
def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Automated data-validation gate.
    Ensures LLM output is a safe, read-only SELECT query.
    Returns (is_valid: bool, reason: str)
    """
    sql_upper = sql.upper()

    # Block destructive operations
    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", sql_upper):
            return False, f"❌ Blocked: query contains forbidden keyword '{kw}'"

    # Must be a SELECT
    if not sql_upper.strip().startswith("SELECT"):
        return False, "❌ Blocked: only SELECT queries are permitted"

    # Basic syntax check – must reference at least one known table
    known_tables = ["orders","customers","products","regions"]
    if not any(t in sql.lower() for t in known_tables):
        return False, "❌ Validation failed: query does not reference any known table"

    return True, "✅ Validation passed"

# ── 3. Execution ──────────────────────────────────────────────────────────────
def execute_sql(sql: str) -> tuple[list, list, str]:
    """
    Execute validated SQL against SQLite.
    Returns (columns, rows, error_message)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        cur.execute(sql)
        rows    = cur.fetchall()
        columns = [d[0] for d in cur.description] if cur.description else []
        conn.close()
        return columns, [list(r) for r in rows], ""
    except Exception as e:
        return [], [], str(e)

# ── 4. Observability Logger ───────────────────────────────────────────────────
def log_pipeline(question, sql, valid, valid_reason, columns, rows, exec_error, latency_ms):
    """
    Structured CSV audit trail – every pipeline run is logged.
    Enables monitoring, debugging, and performance tracking.
    """
    file_exists = os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp","question","generated_sql","validation_passed",
                "validation_reason","row_count","columns","exec_error","latency_ms"
            ])
        writer.writerow([
            datetime.now().isoformat(),
            question,
            sql,
            valid,
            valid_reason,
            len(rows),
            json.dumps(columns),
            exec_error,
            round(latency_ms, 2),
        ])

# ── 5. Master Pipeline Function ───────────────────────────────────────────────
def run_pipeline(model, question: str) -> dict:
    """
    Full NL → SQL → Validate → Execute → Log pipeline.
    Returns a result dict consumed by the Streamlit UI.
    """
    t0 = time.time()

    # Stage 1: Generate
    try:
        sql = generate_sql(model, question)
        gen_error = ""
    except Exception as e:
        sql, gen_error = "", str(e)

    # Stage 2: Validate
    if sql:
        valid, valid_reason = validate_sql(sql)
    else:
        valid, valid_reason = False, f"❌ LLM generation failed: {gen_error}"

    # Stage 3: Execute
    columns, rows, exec_error = [], [], ""
    if valid:
        columns, rows, exec_error = execute_sql(sql)

    latency_ms = (time.time() - t0) * 1000

    # Stage 4: Log
    log_pipeline(question, sql, valid, valid_reason, columns, rows, exec_error, latency_ms)

    return {
        "question":     question,
        "sql":          sql,
        "valid":        valid,
        "valid_reason": valid_reason,
        "columns":      columns,
        "rows":         rows,
        "exec_error":   exec_error,
        "latency_ms":   latency_ms,
    }
