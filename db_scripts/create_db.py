import duckdb
import os

# ── Parameters ──────────────────────────────────────────────────────────────
DB_PATH = "../bv-auth-backend/bv_datawarehouse.duckdb"
# ────────────────────────────────────────────────────────────────────────────


def main():
    db_path = os.path.abspath(DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    con = duckdb.connect(db_path)
    con.close()

    print(f"Database created (or already exists): {db_path}")


if __name__ == "__main__":
    main()
