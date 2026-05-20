import json
import pandas as pd


def flatten(obj, parent=""):
    """Aplatit récursivement tous les niveaux (dicts + listes imbriquées)."""
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{parent}_{k}" if parent else k
            items.update(flatten(v, key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            key = f"{parent}_{i}" if parent else str(i)
            items.update(flatten(v, key))
    else:
        items[parent] = obj
    return items


def json_to_excel(json_file, output_excel_file):
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support Elasticsearch hits wrapper ou liste brute
    if isinstance(data, dict):
        hits = data.get("hits", {})
        products = hits.get("hits", []) if isinstance(hits, dict) else list(data.values())[0]
    else:
        products = data

    rows = []
    for p in products:
        src = p.get("_source", p)
        row = {"_score": p.get("_score")}
        row.update(flatten(src))
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_excel(output_excel_file, index=False, engine="openpyxl")

    print(f"✅ {len(rows)} produits exportés → {output_excel_file}")
    print(f"   {len(df.columns)} colonnes générées")


json_to_excel("promotions2.json", "promotions2.xlsx")
