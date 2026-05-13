import duckdb
import os

# ── Parameters ──────────────────────────────────────────────────────────────
DB_PATH = "../bv-auth-backend/bv_datawarehouse.duckdb"

# Define your tables here.
# Each entry is a CREATE TABLE IF NOT EXISTS statement.
# Edit, add or remove tables as needed.
TABLES = [
  
    """
    CREATE TABLE IF NOT EXISTS orders_items (
    order_id INTEGER,
    order_number VARCHAR(50) ,
    created_at TIMESTAMP,
    customer_id INTEGER,
    item_id INTEGER,
    sku INTEGER,
    product_name VARCHAR(500),
    qty_ordered INTEGER,
    FOREIGN KEY (sku) REFERENCES products(sku)
);





    """,
    

   
]
# ────────────────────────────────────────────────────────────────────────────


def main():
    db_path = os.path.abspath(DB_PATH)
    con = duckdb.connect(db_path)

    for sql in TABLES:
        sql = sql.strip()
        if not sql:
            continue
        # Extract table name for logging
        name = sql.split("EXISTS", 1)[-1].strip().split()[0] if "EXISTS" in sql else "?"
        con.execute(sql)
        print(f"  OK  {name}")

    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
