import pandas as pd
import re
from pathlib import Path

# Paths
input_file = Path(__file__).parent / "promotions1.xlsx"
output_file = Path(__file__).parent / "promotion_by_shop.xlsx"

print(f"📖 Reading {input_file}...")
df = pd.read_excel(input_file)

print(f"Columns found: {len(df.columns)}")
print(f"Rows: {len(df)}")

# Parse the nested structure
rows = []

for idx, row in df.iterrows():
    promo_id = row.get("_id")
    
    # Find all subscription columns (subscriptions_X_shopId pattern)
    for col in df.columns:
        match = re.match(r"subscriptions_(\d+)_shopId", col)
        if match:
            sub_index = match.group(1)
            shop_id = row.get(col)
            start_date_col = f"subscriptions_{sub_index}_period_start_$date"
            end_date_col = f"subscriptions_{sub_index}_period_end_$date"
            
            # Skip if shop_id is null/empty
            if pd.isna(shop_id) or shop_id == "":
                continue
            
            start_date = row.get(start_date_col)
            end_date = row.get(end_date_col)
            
            rows.append({
                "promo_id": promo_id,
                "shop_id": shop_id,
                "start_date": start_date,
                "end_date": end_date,
            })

# Create new DataFrame
result_df = pd.DataFrame(rows)

print(f"\n✅ Flattened {len(result_df)} subscription records")
print(f"Unique promos: {result_df['promo_id'].nunique()}")
print(f"Unique shops: {result_df['shop_id'].nunique()}")

# Save to new file
result_df.to_excel(output_file, index=False)
print(f"\n📝 Saved to {output_file}")

# Preview
print(f"\n Preview (first 10 rows):")
print(result_df.head(10))
