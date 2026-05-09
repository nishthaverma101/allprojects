"""
setup_db.py  –  Run this ONCE to create the sample SQLite database.
Usage: python setup_db.py
"""
import sqlite3, random, os
from datetime import datetime, timedelta

DB_PATH = "data/sales.db"
os.makedirs("data", exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

# ── Tables ───────────────────────────────────────────────────────────────────
cur.executescript("""
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS regions;

CREATE TABLE regions (
    region_id   INTEGER PRIMARY KEY,
    region_name TEXT NOT NULL
);

CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT UNIQUE,
    region_id     INTEGER REFERENCES regions(region_id),
    signup_date   TEXT
);

CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    product_name  TEXT NOT NULL,
    category      TEXT,
    unit_price    REAL
);

CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY,
    customer_id   INTEGER REFERENCES customers(customer_id),
    product_id    INTEGER REFERENCES products(product_id),
    quantity      INTEGER,
    order_date    TEXT,
    status        TEXT
);
""")

# ── Seed data ─────────────────────────────────────────────────────────────────
regions = ["North", "South", "East", "West", "Central"]
cur.executemany("INSERT INTO regions VALUES (?,?)", enumerate(regions, 1))

first = ["Alice","Bob","Carol","David","Eva","Frank","Grace","Henry","Iris","James",
         "Kavya","Leo","Mia","Nikhil","Olivia","Paul","Quincy","Riya","Sam","Tara"]
last  = ["Sharma","Verma","Singh","Kumar","Patel","Gupta","Mehta","Joshi","Nair","Reddy"]

random.seed(42)
customers = []
for i in range(1, 101):
    name  = f"{random.choice(first)} {random.choice(last)}"
    email = f"user{i}@example.com"
    region= random.randint(1, 5)
    date  = (datetime(2022,1,1) + timedelta(days=random.randint(0,730))).strftime("%Y-%m-%d")
    customers.append((i, name, email, region, date))
cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)

products = [
    (1,"Snowboard Pro","Sports",4999.0),(2,"Ski Jacket","Apparel",2499.0),
    (3,"Trail Boots","Footwear",1799.0),(4,"Helmet Elite","Safety",1299.0),
    (5,"Goggles HD","Accessories",799.0),(6,"Gloves Warm","Accessories",399.0),
    (7,"Poles Carbon","Sports",999.0),(8,"Avalanche Kit","Safety",3499.0),
    (9,"Base Layer","Apparel",599.0),(10,"Backpack 40L","Gear",1599.0),
]
cur.executemany("INSERT INTO products VALUES (?,?,?,?)", products)

statuses = ["completed","completed","completed","pending","cancelled"]
orders = []
for i in range(1, 501):
    cust    = random.randint(1,100)
    prod    = random.randint(1,10)
    qty     = random.randint(1,5)
    date    = (datetime(2023,1,1) + timedelta(days=random.randint(0,730))).strftime("%Y-%m-%d")
    status  = random.choice(statuses)
    orders.append((i, cust, prod, qty, date, status))
cur.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", orders)

conn.commit()
conn.close()
print(f"✅  Database created at {DB_PATH}  (4 tables, 500 orders, 100 customers, 10 products)")
