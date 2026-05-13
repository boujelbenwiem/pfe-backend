import duckdb
import os

# ── Parameters ──────────────────────────────────────────────────────────────
DB_PATH    = "../bv-auth-backend/bv_datawarehouse.duckdb"
CSV_FILE   = "../data/commandes.csv"   # path to the CSV file to load
TABLE_NAME = "orders_items"                     # target table in the database
CSV_SEP    = ";"                            # column separator in the CSV
# ────────────────────────────────────────────────────────────────────────────


def main():
    db_path  = os.path.abspath(DB_PATH)
    csv_path = os.path.abspath(CSV_FILE)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    con = duckdb.connect(db_path)

    # Count rows before
    before = con.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]

    csv_path_fwd = csv_path.replace(chr(92), "/")

    # If table has a PRIMARY KEY, skip duplicates; otherwise plain insert
    has_pk = con.execute(f"""
        SELECT COUNT(*) FROM information_schema.table_constraints
        WHERE table_name = '{TABLE_NAME}'
        AND constraint_type = 'PRIMARY KEY'
    """).fetchone()[0] > 0

    if has_pk:
        sql = f"""
            INSERT OR IGNORE INTO {TABLE_NAME}
            SELECT * FROM read_csv_auto('{csv_path_fwd}', delim='{CSV_SEP}', header=true, all_varchar=true, ignore_errors=true)
        """
    else:
        sql = f"""
            INSERT INTO {TABLE_NAME}
            SELECT * FROM read_csv_auto('{csv_path_fwd}', delim='{CSV_SEP}', header=true, all_varchar=true, ignore_errors=true)
        """
    con.execute(sql)

    after = con.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    con.close()

    print(f"Inserted {after - before} new rows into '{TABLE_NAME}' ({after} total).")


if __name__ == "__main__":
    main()
