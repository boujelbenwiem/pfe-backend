import re
import pandas as pd

INPUT_XLSX    = "products_categories.xlsx"
CATEGORIES_CSV = "categories.csv"
SKU_COL       = "sku"


def read_csv_auto(path):
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(path, sep=None, engine="python", dtype=str, encoding=enc)
            df.columns = [c.strip() for c in df.columns]
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {path}")


def extract_categories_from_xlsx(df):
    """Collect unique (category_id, name, path, level) from all category_x_* columns."""
    # Find all category indices
    indices = set()
    for col in df.columns:
        m = re.match(r"category_(\d+)_category_id", col)
        if m:
            indices.add(int(m.group(1)))

    records = {}
    for i in sorted(indices):
        id_col   = f"category_{i}_category_id"
        name_col = f"category_{i}_name"
        path_col = f"category_{i}_path"
        lvl_col  = f"category_{i}_level"

        if id_col not in df.columns:
            continue

        for _, row in df.iterrows():
            cat_id = str(row[id_col]).strip() if pd.notna(row[id_col]) else ""
            if not cat_id or cat_id in ("nan", ""):
                continue
            name  = str(row[name_col]).strip()  if name_col  in df.columns and pd.notna(row[name_col])  else ""
            path  = str(row[path_col]).strip()  if path_col  in df.columns and pd.notna(row[path_col])  else ""
            level = str(row[lvl_col]).strip()   if lvl_col   in df.columns and pd.notna(row[lvl_col])   else ""

            if cat_id not in records:
                records[cat_id] = {"category_id": cat_id, "category_name": name,
                                   "breadcrumb_path": path, "category_level": level}
            else:
                # Fill missing fields if we get better data later
                r = records[cat_id]
                if not r["category_name"]    and name:  r["category_name"]    = name
                if not r["breadcrumb_path"]  and path:  r["breadcrumb_path"]  = path
                if not r["category_level"]   and level: r["category_level"]   = level

    return records


def derive_parent_id(path, name_to_id):
    """Return parent_id from breadcrumb path using name->id mapping."""
    if not path:
        return ""
    parts = [p.strip() for p in path.split(">")]
    if len(parts) < 2:
        return ""  # root category
    parent_name = parts[-2]
    return name_to_id.get(parent_name, "")


def main():
    df = pd.read_excel(INPUT_XLSX, dtype=str)
    existing = read_csv_auto(CATEGORIES_CSV)

    existing["category_id"] = existing["category_id"].astype(str).str.strip()
    existing_ids = set(existing["category_id"].unique())

    # Build name -> id mapping from existing categories
    name_to_id = {}
    for _, row in existing.iterrows():
        name = str(row.get("category_name", "")).strip()
        if name:
            name_to_id[name] = str(row["category_id"]).strip()

    # Extract all categories from xlsx
    xlsx_records = extract_categories_from_xlsx(df)

    # Add xlsx categories to name->id map too (for deriving parents of new categories)
    for cat_id, rec in xlsx_records.items():
        if rec["category_name"] and rec["category_name"] not in name_to_id:
            name_to_id[rec["category_name"]] = cat_id

    # Find missing ones
    missing = [rec for cat_id, rec in xlsx_records.items() if cat_id not in existing_ids]

    if not missing:
        print("No missing categories found.")
        return

    # Derive parent_id for each missing category
    for rec in missing:
        rec["parent_id"] = derive_parent_id(rec["breadcrumb_path"], name_to_id)

    new_df = pd.DataFrame(missing, columns=["category_id", "category_name",
                                             "breadcrumb_path", "category_level", "parent_id"])

    combined = pd.concat([existing, new_df], ignore_index=True)
    combined.to_csv(CATEGORIES_CSV, index=False, encoding="utf-8-sig")

    print(f"Added {len(missing)} missing categories to {CATEGORIES_CSV}")
    for r in missing[:10]:
        print(f"  {r['category_id']} | {r['category_name']} | level={r['category_level']} | parent={r['parent_id']}")
    if len(missing) > 10:
        print(f"  ... and {len(missing)-10} more")


if __name__ == "__main__":
    main()
