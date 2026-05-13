"""
Script de correction CSV générique.
Usage: modifier la config ci-dessous puis lancer le script.
"""
import pandas as pd
import sys

# ============================================================
# CONFIGURATION - Modifier ici
# ============================================================

FILE = "../commandes.csv"              # Nom du fichier CSV (dans le dossier csv/)
SEP = ";"                        # Séparateur
ENCODING_IN = "utf-8"             # Encodage lecture
ENCODING_OUT = "utf-8"          # Encodage sortie (utf-8-sig = avec BOM pour Excel)

# Colonnes booléennes: VRAI/FAUX et/ou 0/1 -> true/false
BOOL_COLS = [
    
]

# Colonnes numériques: virgule -> point
NUMERIC_COMMA = [
]

# Colonnes entières: après conversion numérique, arrondir et convertir en entier
# (ex: 3,70E+17 -> 370000000000000000) pour compatibilité DuckDB BIGINT
INTEGER_COLS = [
   
]

# Colonnes datetime: convertir vers format ISO (YYYY-MM-DD HH:MM:SS) pour DuckDB
# Format source ex: "01/05/2026 10:00" -> mettre le strptime format correspondant
DATETIME_COLS = {
    # "nom_colonne": "format_source"
    
    "created_at": "%d/%m/%Y %H:%M",
}

# =================================================
# ============================================================

def fix_csv():
    print(f"📂 Lecture: {FILE}")
    df = pd.read_csv(FILE, sep=SEP, encoding=ENCODING_IN)
    print(f"   {len(df)} lignes × {len(df.columns)} colonnes\n")

    # Fix booleans: VRAI/FAUX and/or 0/1 -> true/false
    if BOOL_COLS:
        print("🔧 Booléens -> true/false:")
        bool_map = {
            'VRAI': 'true', 'FAUX': 'false',
            'True': 'true', 'False': 'false',
            'TRUE': 'true', 'FALSE': 'false',
            1: 'true', 0: 'false',
            1.0: 'true', 0.0: 'false',
            '1': 'true', '0': 'false',
            '1.0': 'true', '0.0': 'false',
        }
        for col in BOOL_COLS:
            if col in df.columns:
                df[col] = df[col].map(bool_map)
                print(f"   ✅ {col}: {df[col].value_counts(dropna=False).to_dict()}")
            else:
                print(f"   ⚠ {col} non trouvée")

    # Fix virgule -> point
    if NUMERIC_COMMA:
        print("🔧 virgule -> point:")
        for col in NUMERIC_COMMA:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce')
                print(f"   ✅ {col}")
            else:
                print(f"   ⚠ {col} non trouvée")

    # Convert integer columns (removes decimal point for BIGINT compatibility)
    if INTEGER_COLS:
        print("🔧 Conversion entière (BIGINT):")
        for col in INTEGER_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').round(0).astype('Int64')
                print(f"   ✅ {col}")
            else:
                print(f"   ⚠ {col} non trouvée")

    # Fix datetime columns -> ISO format for DuckDB
    if DATETIME_COLS:
        print("🔧 Datetime -> ISO (YYYY-MM-DD HH:MM:SS):")
        for col, fmt in DATETIME_COLS.items():
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], format=fmt, errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
                print(f"   ✅ {col} (format source: {fmt})")
            else:
                print(f"   ⚠ {col} non trouvée")

    # Save
    out_file = FILE.replace(".csv", "_fixed.csv") if FILE.endswith(".csv") else FILE + "_fixed"
    try:
        df.to_csv(FILE, index=False, sep=SEP, encoding=ENCODING_OUT)
        print(f"\n💾 Sauvegardé: {FILE} (encodage: {ENCODING_OUT})")
    except PermissionError:
        df.to_csv(out_file, index=False, sep=SEP, encoding=ENCODING_OUT)
        print(f"\n⚠ Fichier source ouvert. Sauvegardé sous: {out_file} (encodage: {ENCODING_OUT})")


if __name__ == "__main__":
    fix_csv()
