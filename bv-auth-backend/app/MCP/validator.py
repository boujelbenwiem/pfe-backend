# Etape 1 : Validation syntaxique et sécurité de la requête SQL

import re # regex pour validation basique
from dataclasses import dataclass

# Mots-clés interdits (écriture / destruction)

_FORBIDDEN = re.compile(
    r"\b(DROP|DELETE|TRUNCATE|INSERT|UPDATE|ALTER|CREATE|REPLACE|MERGE"
    r"|ATTACH|DETACH|COPY|EXPORT|IMPORT|INSTALL|LOAD)\b",
    re.IGNORECASE,
)

# Patterns dangereux supplémentaires
_DANGEROUS = re.compile(
    r"(--|\bxp_|\bexec\b|\bexecute\b|;.+;)",
    re.IGNORECASE,
)


@dataclass
class ValidationResult:
    valid: bool
    error: str = ""


def validate_sql(sql: str) -> ValidationResult:
    """
    Valide la requête SQL :
    - Doit être non vide
    - Doit commencer par SELECT
    - Ne doit pas contenir de mots-clés de modification/destruction
    - Ne doit pas contenir de patterns dangereux (injection)
    """
    if not sql or not sql.strip():
        return ValidationResult(valid=False, error="La requête SQL est vide.")

    sql_stripped = sql.strip()

    if not sql_stripped.upper().startswith("SELECT"):
        return ValidationResult(
            valid=False,
            error="Seules les requêtes SELECT sont autorisées."
        )

    forbidden_match = _FORBIDDEN.search(sql_stripped)
    if forbidden_match:
        return ValidationResult(
            valid=False,
            error=f"Mot-clé interdit détecté : '{forbidden_match.group()}'."
        )

    dangerous_match = _DANGEROUS.search(sql_stripped)
    if dangerous_match:
        return ValidationResult(
            valid=False,
            error="Pattern dangereux détecté dans la requête."
        )

    return ValidationResult(valid=True)
