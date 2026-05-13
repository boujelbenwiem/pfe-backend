import pandas as pd

# Parameters — edit these as needed
FILE1       = "products_fixed.csv"   # file to fill
FILE2       = "Feuil1.csv"            # source file
OUTPUT_FILE = "products_fixed_filled.csv"
KEY_COL     = "sku"
SEP         = ";"                     # separator used in both CSV files

# Mapping: col name in FILE1 -> col name in FILE2 (only for columns with different names)
COLUMN_MAP = {
    "product_sales":  "productsales",
    "rating_summary": "review_summary",
}


def is_empty(val):
    if val is None:
        return True
    if pd.isna(val):
        return True
    return str(val).strip() in ("", "nan", "NaN", "None")


def read_csv(path):
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return pd.read_csv(path, sep=SEP, dtype=str, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {path} with any known encoding")


def main():
    df1 = read_csv(FILE1)
    df2 = read_csv(FILE2)

    df1[KEY_COL] = df1[KEY_COL].str.strip()
    df2[KEY_COL] = df2[KEY_COL].str.strip()

    # Use first occurrence of each SKU in sheet 2 as lookup
    df2_lookup = df2.drop_duplicates(subset=KEY_COL).set_index(KEY_COL)

    filled_cells = 0
    filled_rows = 0

    for idx, row in df1.iterrows():
        sku = row[KEY_COL]
        if sku not in df2_lookup.index:
            continue
        row2 = df2_lookup.loc[sku]
        row_filled = False
        for col in df1.columns:
            if col == KEY_COL:
                continue
            col2 = COLUMN_MAP.get(col, col)  # mapped name in file2
            if is_empty(row[col]) and col2 in row2.index and not is_empty(row2[col2]):
                df1.at[idx, col] = row2[col2]
                filled_cells += 1
                row_filled = True
        if row_filled:
            filled_rows += 1

    df1.to_csv(OUTPUT_FILE, sep=SEP, index=False, encoding="utf-8-sig")

    print(f"Done — {filled_cells} cells filled across {filled_rows} rows")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
