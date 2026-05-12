# 🔷 QueryMind — NL-to-SQL AI Data Pipeline

> **Converts natural language business questions into validated, executable SQL queries — with automated data validation and full pipeline observability.**

Built as a demonstration of AI-driven data engineering principles: LLM-powered automation, data integrity enforcement, structured audit logging, and a clean self-service UI.

---

## 🎯 What It Does

| Pipeline Stage | What Happens |
|---|---|
| **1. NL → SQL Generation** | Google Gemini LLM interprets plain-English questions and generates syntactically correct SQL, given the database schema as context |
| **2. Automated Data Validation** | A rule-based validation layer sanitizes LLM output — blocks destructive keywords (DROP, DELETE, etc.), enforces SELECT-only access, and verifies table references |
| **3. Query Execution** | Validated SQL is executed against a local SQLite database (500 orders, 100 customers, 10 products across 4 regions) |
| **4. Observability Logging** | Every pipeline run is logged to a structured CSV audit trail with timestamp, latency, validation status, row count, and errors |

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/YOUR_USERNAME/querymind.git
cd querymind
pip install -r requirements.txt
```

### 2. Get a Free Gemini API Key
1. Visit [aistudio.google.com](https://aistudio.google.com)
2. Sign in → **Get API Key** → Create API key
3. Copy the key

### 3. Set Up the Database
```bash
python setup_db.py
```

### 4. Launch the App
```bash
streamlit run app.py
```
Paste your Gemini API key in the sidebar and start querying!

---

## 💡 Example Questions You Can Ask

- *"What are the top 5 products by total revenue?"*
- *"How many orders were completed in 2024?"*
- *"Which region has the most customers?"*
- *"Show monthly revenue trend for 2023"*
- *"What is the average order value by product category?"*
- *"List customers who placed more than 5 orders"*

---

## 🗂️ Project Structure

```
querymind/
│
├── app.py              # Streamlit UI — 4-stage pipeline visualization
├── pipeline.py         # Core engine: LLM generation → validation → execution → logging
├── setup_db.py         # One-time DB seed: 4 tables, 500 orders, 100 customers
│
├── data/
│   └── sales.db        # SQLite database (auto-created by setup_db.py)
│
├── logs/
│   └── pipeline_log.csv  # Auto-generated audit trail of all pipeline runs
│
└── requirements.txt
```

---

## 🏗️ Architecture

```
User Question (Natural Language)
         │
         ▼
┌─────────────────────┐
│  Gemini 1.5 Flash   │  ← Schema injected as context (prompt engineering)
│  LLM SQL Generator  │
└────────┬────────────┘
         │  generated SQL
         ▼
┌─────────────────────┐
│  Validation Layer   │  ← Blocks: DROP/DELETE/INSERT/UPDATE/ALTER
│  (Data Integrity)   │  ← Enforces: SELECT-only, known tables only
└────────┬────────────┘
         │  validated SQL
         ▼
┌─────────────────────┐
│  SQLite Execution   │  ← Parameterized, read-only connection
└────────┬────────────┘
         │  results
         ▼
┌─────────────────────┐
│  Observability Log  │  ← CSV audit: timestamp, latency, errors, row count
└─────────────────────┘
         │
         ▼
    Streamlit UI
  (Table + Bar Chart)
```

---

## 🛡️ Data Validation Rules

The automated validation gate (`pipeline.py → validate_sql`) enforces:

1. **Destructive keyword blocking** — `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `TRUNCATE`, `CREATE`, `REPLACE`
2. **Read-only enforcement** — Only `SELECT` statements are executed
3. **Schema verification** — Query must reference at least one known table
4. **All violations are logged** with reason — full auditability

---

## 📊 Observability Log Schema

```
timestamp | question | generated_sql | validation_passed | validation_reason | row_count | columns | exec_error | latency_ms
```

Enables:
- Monitoring query failure rates
- Tracking average pipeline latency
- Debugging LLM-generated SQL errors
- Full audit trail for compliance

---

## 🔧 Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini 1.5 Flash (via `google-generativeai`) |
| Prompt Engineering | Schema-injected system prompts |
| Validation | Custom Python rule engine |
| Database | SQLite (easily swappable with Snowflake, PostgreSQL) |
| Observability | Structured CSV logging |
| UI | Streamlit |
| Language | Python 3.10+ |

---

## 🔮 Extending to Snowflake

This project is architected to swap SQLite for Snowflake with minimal changes:

```python
# In pipeline.py, replace sqlite3 with:
import snowflake.connector
conn = snowflake.connector.connect(
    user=os.getenv("SF_USER"),
    password=os.getenv("SF_PASSWORD"),
    account=os.getenv("SF_ACCOUNT"),
    warehouse="COMPUTE_WH",
    database="SALES_DB",
    schema="PUBLIC"
)
```

---

## 👩‍💻 Author

**Nishtha Verma** — B.Tech CSE, Graphic Era University  
[GitHub](https://github.com/nishthaverma101) · [LinkedIn](https://www.linkedin.com/in/nishtha-verma-68a6332b7)
