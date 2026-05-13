import pandas as pd
import requests
import time
import json
from tqdm import tqdm

# ── Config ──────────────────────────────────────────────────────────────────
BASE_URL   = "https://bva-integ-offer.decade.fr/api/v2/offers"
BATCH_SIZE = 50          # SKUs per request
DELAY      = 0.2         # seconds between requests (be polite to the API)
OUTPUT     = "offers_result.xlsx"
# ────────────────────────────────────────────────────────────────────────────

# Load inputs
shops    = pd.read_excel("shop_id.xlsx")["shop_id"].dropna().astype(str).tolist()
skus_df  = pd.read_excel("all_missing_skus.xlsx")
skus     = skus_df["missing_sku"].dropna().astype(str).tolist()

# Build SKU batches
sku_batches = [skus[i:i + BATCH_SIZE] for i in range(0, len(skus), BATCH_SIZE)]

print(f"Shops: {len(shops)} | SKUs: {len(skus)} | Batches/shop: {len(sku_batches)}")
print(f"Total requests: {len(shops) * len(sku_batches)}")

all_rows = []
errors   = []

total = len(shops) * len(sku_batches)

with tqdm(total=total, desc="Fetching offers") as pbar:
    for shop_id in shops:
        for batch in sku_batches:
            params = {
                "shopId": shop_id,
                "skus":   ",".join(batch)
            }
            try:
                resp = requests.get(BASE_URL, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                # Normalize: data may be a list or a dict with a key
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    # Try common wrapper keys
                    items = (
                        data.get("offers")
                        or data.get("data")
                        or data.get("results")
                        or data.get("items")
                        or [data]
                    )
                else:
                    items = []

                if items:
                    flat = pd.json_normalize(items)
                    flat.insert(0, "_shopId", shop_id)
                    all_rows.append(flat)

            except requests.exceptions.RequestException as e:
                errors.append({"shopId": shop_id, "skus": ",".join(batch), "error": str(e)})

            pbar.update(1)
            time.sleep(DELAY)

# ── Save results ─────────────────────────────────────────────────────────────
if all_rows:
    result = pd.concat(all_rows, ignore_index=True)
    print(f"\nTotal rows collected: {len(result)}")
    print(f"Columns: {result.columns.tolist()}")
    result.to_excel(OUTPUT, index=False)
    print(f"Saved to {OUTPUT}")
else:
    print("\nNo data collected.")

if errors:
    err_df = pd.DataFrame(errors)
    err_df.to_excel("offers_errors.xlsx", index=False)
    print(f"{len(errors)} errors saved to offers_errors.xlsx")
