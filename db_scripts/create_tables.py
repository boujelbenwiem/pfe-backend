import duckdb
import os

# ── Parameters ──────────────────────────────────────────────────────────────
DB_PATH = "../bv-auth-backend/bv_datawarehouse.duckdb"

# Define your tables here.
# Each entry is a CREATE TABLE IF NOT EXISTS statement.
# Edit, add or remove tables as needed.
TABLES = [
  
    """
    CREATE TABLE IF NOT EXISTS promotions (
    promo_id VARCHAR(100) PRIMARY KEY,
    promo_type VARCHAR(50),
    promo_value INTEGER,
    promo_renderingType VARCHAR(50),
    label VARCHAR(200),
    territoryId VARCHAR(10),
    version INTEGER,
    created_at TIMESTAMP,
    last_updated TIMESTAMP,
    is_active BOOLEAN,
    benefit_rule VARCHAR(100),
    X VARCHAR(50),
    Y VARCHAR(50),
    promo_name VARCHAR(200),
    promotion_role VARCHAR(50)
);
    """,
    """
    CREATE TABLE IF NOT EXISTS promotion_by_shop (
    promo_id VARCHAR(100),
    shop_id VARCHAR(50),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    PRIMARY KEY (promo_id, shop_id),
    FOREIGN KEY (promo_id) REFERENCES promotions(promo_id),   
);
    """,
    """
    CREATE TABLE IF NOT EXISTS promotion_by_product (
    promo_id VARCHAR(100),
    product_sku INTEGER,
    reference_price DECIMAL(10,2),
    discount_value DECIMAL(10,2),
    PRIMARY KEY (promo_id, product_sku),
    FOREIGN KEY (promo_id) REFERENCES promotions(promo_id),
    FOREIGN KEY (product_sku) REFERENCES products(sku)
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
