import pandas as pd
import ast
from tqdm import tqdm

# ── Load data ────────────────────────────────────────────────────────────────
offers   = pd.read_excel("offers_result.xlsx")
existing = pd.read_csv("product_delivery_stock.csv", sep=";")

print(f"Offers rows: {len(offers)}")
print(f"Existing product_delivery_stock rows: {len(existing)}")

# ── Parse and flatten ────────────────────────────────────────────────────────
new_rows = []

for _, row in tqdm(offers.iterrows(), total=len(offers), desc="Processing"):
    shop_id  = row["_shopId"]
    sku      = row["offer.sku"]

    raw_delivery = row.get("deliveryInformations")
    raw_avail    = row.get("offer.availabilities")

    # Skip rows with empty lists or NaN
    if pd.isna(raw_delivery) or pd.isna(raw_avail):
        continue
    if str(raw_delivery).strip() in ("", "[]", "nan"):
        continue
    if str(raw_avail).strip() in ("", "[]", "nan"):
        continue

    try:
        delivery_list = ast.literal_eval(str(raw_delivery))
        avail_list    = ast.literal_eval(str(raw_avail))
    except Exception:
        continue

    if not delivery_list or not avail_list:
        continue

    # Build lookup: mode -> deliveryInfo
    delivery_map = {d["mode"]: d for d in delivery_list}

    for avail in avail_list:
        mode     = avail.get("deliveryMode")
        dinfo    = delivery_map.get(mode, {})
        in_delay = dinfo.get("inStockDelay") or {}

        new_rows.append({
            "shop_id":           shop_id,
            "sku":               sku,
            "delivery_mode":     mode,
            "is_available":      str(avail.get("available", "")).lower(),
            "available_quantity": avail.get("quantity"),
            "origin_quantity":   avail.get("originQuantity"),
            "is_resuppliable":   str(avail.get("resuppliable", "")).lower(),
            "location_id":       avail.get("locationId"),
            "stock_type":        dinfo.get("stockLocationType"),
            "stock_name":        dinfo.get("stockLocationName"),
            "stock_location_id": dinfo.get("stockLocationId"),
            "delay_hours":       in_delay.get("delayInHour"),
            "date_from":         in_delay.get("dateFrom"),
            "has_malus":         str(dinfo.get("hasDeliveryMalus", "")).lower(),
        })

print(f"\nNew rows extracted: {len(new_rows)}")

if not new_rows:
    print("No data to add.")
else:
    new_df = pd.DataFrame(new_rows)

    # Append to existing and remove duplicates on (shop_id, sku, delivery_mode)
    combined = pd.concat([existing, new_df], ignore_index=True)
    before   = len(combined)
    combined = combined.drop_duplicates(subset=["shop_id", "sku", "delivery_mode"])
    print(f"Duplicates removed: {before - len(combined)}")
    print(f"Final rows: {len(combined)}")

    combined.to_csv("product_delivery_stock.csv", sep=";", index=False)
    print("Saved to product_delivery_stock.csv")

    # Also export only the new rows to Excel for review
    new_df.to_excel("new_delivery_stock_rows.xlsx", index=False)
    print("New rows saved to new_delivery_stock_rows.xlsx")
