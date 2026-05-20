"""
check_sku.py — Script général de vérification de SKUs entre deux fichiers.

Usage :
    python check_sku.py \
        --source products_fixed.csv  --source-col sku \
        --target raw_products.xlsx   --target-col sku \
        --output missing_skus.csv

Arguments :
    --source       Fichier source (CSV ou Excel) — celui dont on vérifie les SKUs
    --source-col   Nom ou index (0-based) de la colonne SKU dans le fichier source
    --source-sep   Séparateur CSV source (défaut : auto-détecté  ; ou ,)
    --target       Fichier cible (CSV ou Excel) — celui où les SKUs doivent exister
    --target-col   Nom ou index (0-based) de la colonne SKU dans le fichier cible
    --target-sep   Séparateur CSV cible
    --output       Fichier de sortie pour les SKUs manquants (CSV, défaut : missing_skus.csv)
"""

import os
import sys

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_file(path, col, sep=None):
    """Lit n'importe quel CSV/Excel et retourne la colonne SKU en set de strings."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    else:
        # Auto-détection du séparateur si non fourni
        if sep is None:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                first_line = f.readline()
            sep = ";" if first_line.count(";") > first_line.count(",") else ","
        try:
            df = pd.read_csv(path, sep=sep, dtype=str, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(path, sep=sep, dtype=str, encoding="latin-1")

    # col peut être un nom ou un index entier
    if isinstance(col, int) or (isinstance(col, str) and col.isdigit()):
        series = df.iloc[:, int(col)]
    else:
        if col not in df.columns:
            print(f"[ERREUR] Colonne '{col}' introuvable dans {path}")
            print(f"  Colonnes disponibles : {list(df.columns)}")
            sys.exit(1)
        series = df[col]

    return set(series.dropna().str.strip()), df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # -----------------------------------------------------------------------
    # ✏️  PARAMÈTRES — modifie ici directement
    # -----------------------------------------------------------------------
    SOURCE      = "../promotion_by_product.csv"   # fichier source (CSV ou Excel)
    SOURCE_COL  = "product_sku"                 # colonne SKU dans le fichier source
    SOURCE_SEP  = None                  # séparateur CSV source (None = auto)

    TARGET      = "../products.csv"      # fichier cible  (CSV ou Excel)
    TARGET_COL  = "sku"                 # colonne SKU dans le fichier cible
    TARGET_SEP  = None                  # séparateur CSV cible  (None = auto)

    OUTPUT      = "missing_skus.csv"    # fichier de sortie pour les SKUs manquants
    # -----------------------------------------------------------------------

    print(f"\n📂 Source : {SOURCE}  (colonne : {SOURCE_COL})")
    print(f"📂 Cible  : {TARGET}  (colonne : {TARGET_COL})")

    source_skus, source_df = read_file(SOURCE, SOURCE_COL, SOURCE_SEP)
    target_skus, _         = read_file(TARGET, TARGET_COL, TARGET_SEP)

    missing = sorted(source_skus - target_skus)

    print(f"\n✅ SKUs dans source : {len(source_skus)}")
    print(f"✅ SKUs dans cible  : {len(target_skus)}")
    print(f"❌ SKUs manquants   : {len(missing)}")

    if missing:
        out_df = pd.DataFrame({"missing_sku": missing})
        out_df.to_csv(OUTPUT, index=False)
        print(f"\n💾 SKUs manquants exportés → {OUTPUT}")
    else:
        print("\n🎉 Tous les SKUs de la source existent dans la cible !")


if __name__ == "__main__":
    main()
