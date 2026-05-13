import pandas as pd

INPUT_FILE  = "raw_products.xlsx"
OUTPUT_FILE = "products_categories.xlsx"
KEY_COL     = "sku"


def main():
    df = pd.read_excel(INPUT_FILE, dtype=str)

    category_cols = [c for c in df.columns if c.lower().startswith("category")]

    if not category_cols:
        print("No columns starting with 'category' found.")
        return

    result = df[[KEY_COL] + category_cols]
    result.to_excel(OUTPUT_FILE, index=False)

    print(f"Extracted {len(category_cols)} category column(s): {category_cols}")
    print(f"Saved {len(result)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
