import pandas as pd

INPUT_XLSX  = "products_categories.xlsx"
TARGET_CSV  = "product_category.csv"
SKU_COL     = "sku"          # column name in xlsx
SEP         = ","            # separator in product_category.csv


def main():
    # Read source (wide format)
    df = pd.read_excel(INPUT_XLSX, dtype=str)

    cat_cols = [c for c in df.columns if c.lower().startswith("category") and "category_id" in c.lower()]

    # Melt to long format: sku -> product_sku, values -> category_id
    long = df[[SKU_COL] + cat_cols].melt(
        id_vars=SKU_COL, value_vars=cat_cols, value_name="category_id"
    ).drop(columns="variable")
    long = long.rename(columns={SKU_COL: "product_sku"})
    long = long.dropna(subset=["category_id"])
    long = long[long["category_id"].str.strip() != ""]
    long["product_sku"] = long["product_sku"].str.strip()
    long["category_id"] = long["category_id"].str.strip()

    # Read existing CSV — auto-detect separator
    try:
        existing = pd.read_csv(TARGET_CSV, sep=None, engine="python", dtype=str)
        # Normalise column names (strip whitespace)
        existing.columns = [c.strip() for c in existing.columns]
        # If file has no header (just two numeric columns), name them
        if "product_sku" not in existing.columns:
            existing.columns = ["product_sku", "category_id"]
        existing["product_sku"] = existing["product_sku"].astype(str).str.strip()
        existing["category_id"] = existing["category_id"].astype(str).str.strip()
    except FileNotFoundError:
        existing = pd.DataFrame(columns=["product_sku", "category_id"])

    existing_skus = set(existing["product_sku"].unique())

    # Keep only rows whose SKU is not already in the CSV
    new_rows = long[~long["product_sku"].isin(existing_skus)]

    if new_rows.empty:
        print("No new SKUs to add — product_category.csv is already up to date.")
        return

    combined = pd.concat([existing, new_rows], ignore_index=True)
    combined.to_csv(TARGET_CSV, sep=SEP, index=False, encoding="utf-8-sig")

    print(f"Added {len(new_rows['product_sku'].unique())} new SKU(s) ({len(new_rows)} rows) to {TARGET_CSV}")


if __name__ == "__main__":
    main()
