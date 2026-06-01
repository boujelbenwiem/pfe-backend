from datetime import datetime, timezone

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.core.config import settings


llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=settings.GROQ_API_KEY,
    temperature=0.1,
)


def classify_query(state: AgentState) -> AgentState:
    """Détecte l'intention de la question."""
    question = state["question"]
    prompt = f"""Analyse cette question et détermine son INTENTION.

QUESTION: {question}

Choisis UNE SEULE intention parmi:

- "analytique": besoin de DONNÉES SPÉCIFIQUES dans la base
  * stock, prix, commandes, CA, statistiques, top produits
  * catalogue, catégories, produits
  * informations magasin (contact, mail, adresse, région, services, horaires)
  * informations produit (nom, marque, prix, stock, avis)
  * questions contenant: "quels sont", "liste", "combien", "quel est le prix"
  * questions avec FILTRE: marque , catégorie, type
  * ID spécifique: BV000, SKU, produit X

- "metier": définition, concept, règle métier
  * ex: "c'est quoi BOGO ?", "comment fonctionne le click & collect ?"

- "generale": information générale sur l'entreprise
  * uniquement sans données spécifiques

Rappel: "Quels sont les produits de la marque X" → ANALYTIQUE

Réponds UNIQUEMENT par: analytique, metier, generale"""

    try:
        response = llm.invoke([
            SystemMessage(content="Tu es un expert en classification. Réponds uniquement par le nom de l'intention."),
            HumanMessage(content=prompt),
        ])
        intention = response.content.strip().lower()
        if intention not in ["analytique", "metier", "generale"]:
            intention = "erreur"

        return {**state, "intention": intention, "error": None}
    except Exception as e:
        return {**state, "intention": "erreur", "error": f"Classification failed: {str(e)}"}


def answer_directly(state: AgentState) -> AgentState:
    """Répond directement à la question sans passer par le RAG/SQL (générale ou métier)."""
    question = state["question"]
    intention = state.get("intention", "generale")

    system = (
        "Tu es un assistant expert Bureau Vallée. Réponds en français de façon claire et concise.si question en englais repond en anglais. "
        + (
            "Explique les concepts, règles et processus métier du retail/distribution."
            if intention == "metier"
            else "Réponds naturellement à la question de l'utilisateur."
        )
    )

    try:
        response = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=question),
        ])
        content = response.content.strip()
    except Exception as e:
        content = "Je n'ai pas pu traiter votre question. Veuillez réessayer."

    return {
        **state,
        "formatted_response": {"type": "text", "content": content},
    }


if __name__ == "__main__":
    test_questions = [
        # Analytique
        "Quel est le stock du produit 1282 ?",
        "Combien coûte le produit 79364646 ?",
        "Quel est le chiffre d'affaires du magasin BV551 ?",
        "Quels sont les produits les plus vendus ?",
        # Métier
        "C'est quoi une promotion BOGO ?",
        "Comment fonctionne le click and collect ?",
        "Quelle est la différence entre livraison standard et express ?",
        # Générale
        "salut cava",
    ]

    print("\n" + "=" * 70)
    print("🧪 TEST DE L'AGENT 1 - CLASSIFICATEUR D'INTENTION")
    print("=" * 70)

    for question in test_questions:
        result = classify_query({"question": question})
        emoji = {"analytique": "📊", "metier": "📖", "generale": "ℹ️", "erreur": "❌"}.get(result["intention"], "❓")
        print(f"{emoji} {result['intention']:10} | {question}")

    print("\n" + "=" * 70)
    print("✅ Test terminé")
    print("=" * 70)


