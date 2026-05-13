
import asyncio
from app.rag.retriever import get_retriever
from app.rag.reranker import get_reranker

async def test_retrieval():
    retriever = get_retriever()
    reranker = get_reranker()
    query = "commandes?"

    # === AVANT RERANKING ===
    print("=" * 60)
    print(f"🔍 Query: '{query}'")
    print("=" * 60)

    results = retriever.retrieve(query, limit=5)

    print("\n📋 AVANT reranking (top 10 par similarité vectorielle):")
    print("-" * 60)
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['table_name']} ({r['category']})")
        print(f"     Score embedding: {r['score']:.4f}")
        print(f"     Description: {r['description'][:80]}...")
        print()

    # === APRÈS RERANKING ===
    reranked = reranker.rerank(query, results, top_n=3)

    print("\n✅ APRÈS reranking (top 3 par Jina Reranker v3):")
    print("-" * 60)
    for i, r in enumerate(reranked, 1):
        print(f"  {i}. {r['table_name']} ({r['category']})")
        print(f"     Score reranking: {r['rerank_score']:.4f} (était embedding: {r['score']:.4f})")
        print(f"     Description: {r['description'][:80]}...")
        print()

    retriever.close()
    reranker.close()

if __name__ == "__main__":
    asyncio.run(test_retrieval())