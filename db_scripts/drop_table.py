import duckdb
import os

# ── Parameters ──────────────────────────────────────────────────────────────
DB_PATH    = "../bv-auth-backend/bv_datawarehouse.duckdb"
TABLE_NAME = "promotions"   # table to drop
# ────────────────────────────────────────────────────────────────────────────


def main():
    db_path = os.path.abspath(DB_PATH)
    con = duckdb.connect(db_path)
    con.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
    con.close()
    print(f"Table '{TABLE_NAME}' dropped (or did not exist).")


if __name__ == "__main__":
    main()
