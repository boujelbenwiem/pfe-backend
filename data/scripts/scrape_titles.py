"""
scrape_titles.py — Récupère le <title> de chaque SKU depuis bureau-vallee.fr.

Pour chaque SKU dans missing_skus.csv :
  → construit l'URL  https://www.bureau-vallee.fr/product-{sku}.html
  → suit la redirection vers la vraie page produit
  → extrait le contenu de <title>
  → exporte SKU + titre dans un fichier Excel

Modifie les paramètres ci-dessous puis lance :
    python scrape_titles.py
"""

import re
import time

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# ✏️  PARAMÈTRES
# ---------------------------------------------------------------------------
INPUT_CSV    = "missing_skus.csv"      # colonne : missing_sku
INPUT_COL    = "missing_sku"           # nom de la colonne SKU dans le CSV
OUTPUT_EXCEL = "skus_titles.xlsx"      # fichier de sortie

DELAY        = 0.5     # secondes entre chaque requête (politesse)
TIMEOUT      = 10      # timeout HTTP en secondes
MAX_SKUS     = None    # None = tous ; mettre ex. 50 pour tester
# ---------------------------------------------------------------------------

BASE_URL = "https://www.bureau-vallee.fr/product-{sku}.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def fetch_title(sku: str) -> tuple[str, str]:
    """Retourne (final_url, title) pour un SKU donné."""
    url = BASE_URL.format(sku=sku)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        match = TITLE_RE.search(resp.text)
        title = match.group(1).strip() if match else ""
        # Nettoyer les entités HTML basiques
        title = title.replace("&amp;", "&").replace("&#039;", "'").replace("&quot;", '"')
        # Supprimer le suffixe "| Bureau Vallée" en fin de titre
        for suffix in [" | Bureau Vallée", "| Bureau Vallée", " - Bureau Vallée", "- Bureau Vallée"]:
            if title.endswith(suffix):
                title = title[: -len(suffix)].rstrip()
                break
        return resp.url, title
    except requests.RequestException as e:
        return url, f"[ERREUR] {e}"


def main():
    df_in = pd.read_csv(INPUT_CSV, dtype=str)

    if INPUT_COL not in df_in.columns:
        print(f"[ERREUR] Colonne '{INPUT_COL}' introuvable. Colonnes : {list(df_in.columns)}")
        return

    skus = df_in[INPUT_COL].dropna().str.strip().tolist()
    if MAX_SKUS:
        skus = skus[:MAX_SKUS]

    total = len(skus)
    print(f"🔍 {total} SKUs à traiter...\n")

    results = []
    for i, sku in enumerate(skus, 1):
        final_url, title = fetch_title(sku)
        status = "✅" if not title.startswith("[ERREUR]") else "❌"
        print(f"  [{i:>5}/{total}] {status} SKU {sku} → {title[:80]}")
        results.append({"sku": sku, "name": title, "url": final_url})
        time.sleep(DELAY)

    df_out = pd.DataFrame(results)[["sku", "name", "url"]]
    df_out.to_excel(OUTPUT_EXCEL, index=False, engine="openpyxl")

    ok  = df_out[~df_out["name"].str.startswith("[ERREUR]", na=False)]
    err = df_out[df_out["name"].str.startswith("[ERREUR]", na=False)]
    print(f"\n✅ Succès : {len(ok)} | ❌ Erreurs : {len(err)}")
    print(f"💾 Résultats exportés → {OUTPUT_EXCEL}")


if __name__ == "__main__":
    main()
