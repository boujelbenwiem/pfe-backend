import json
import os
import time
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

#Configuration 
load_dotenv()
JINA_API_KEY = os.getenv("JINA_API_KEY")
JINA_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v5-text-small"
EMBEDDING_SIZE = 1024

COLLECTION_NAME = "table_schemas"
QDRANT_PATH = Path(__file__).resolve().parent.parent / "../qdrant_data"
KNOWLEDGE_BASE = Path(__file__).resolve().parent.parent / "knowledgeBase" / "table_schemas"

session = requests.Session()


#Helpers 

def schema_to_text(schema: dict) -> str:
    """
    Convert a schema dict into a rich text chunk optimized for embedding.
    Supports both single-category and merged multi-category schemas.
    """
    lines = []
    lines.append(f"Table: {schema['table_name']}")
    lines.append(f"Category: {schema['category']}")
    lines.append(f"Description: {schema['description']}")
    lines.append("Columns:")
    for col in schema["columns"]:
        pk = " [PRIMARY KEY]" if col.get("pk") else ""
        lines.append(f"  - {col['name']} ({col['type']}){pk}: {col['description']}")
    if schema.get("relations"):
        lines.append("Relations:")
        for rel in schema["relations"]:
            lines.append(f"  - {rel}")
    return "\n".join(lines)



def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Get embeddings for multiple texts in one API call (more efficient)."""
    t0 = time.perf_counter()
    resp = session.post(
        JINA_URL,
        headers={"Authorization": f"Bearer {JINA_API_KEY}"},
        json={"model": JINA_MODEL, "input": texts, "normalized": True},
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    embeddings = [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]
    print(f"  batch embedding ({len(texts)} texts) took {time.perf_counter() - t0:.3f}s")
    return embeddings


#Main ingestion pipeline 

def load_schemas(folder: Path) -> list[dict]:
    """Load all JSON schema files from the knowledge base folder."""
    schemas = []
    for file in sorted(folder.glob("*.json")):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            schemas.extend(data)
        else:
            schemas.append(data)
    print(f"Loaded {len(schemas)} schema chunks from {folder}")
    return schemas


def create_qdrant_collection(client: QdrantClient):
    """Create the collection if it doesn't exist."""
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in collections:
        print(f"Collection '{COLLECTION_NAME}' already exists — recreating.")
        client.delete_collection(COLLECTION_NAME)
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_SIZE, distance=Distance.COSINE),
    )
    print(f"Created collection '{COLLECTION_NAME}'")


def ingest_schemas():
    """Full pipeline: load schemas → embed → store in Qdrant on disk."""
    # 1. Initialize Qdrant on disk
    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(QDRANT_PATH))
    print(f"Qdrant storage: {QDRANT_PATH}")

    # 2. Create collection
    create_qdrant_collection(client)

    # 3. Load schemas
    schemas = load_schemas(KNOWLEDGE_BASE)

    # 4. Convert to text chunks
    texts = [schema_to_text(s) for s in schemas]
    for i, t in enumerate(texts):
        print(f"\n--- Chunk {i} ---\n{t}")

    # 5. Embed in batches (Jina supports up to 2048 inputs per call)
    BATCH_SIZE = 64
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        all_embeddings.extend(get_embeddings_batch(batch))

    # 6. Upsert into Qdrant with metadata
    points = []
    for i, (schema, embedding) in enumerate(zip(schemas, all_embeddings)):
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "table_name": schema["table_name"],
                    "category": schema["category"],
                    "description": schema["description"],
                    "text": texts[i],
                    "columns": [col["name"] for col in schema["columns"]],
                    "relations": schema.get("relations", []),
                },
            )
        )

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"\nInserted {len(points)} vectors into '{COLLECTION_NAME}'")
    client.close()
    print("Done!")


if __name__ == "__main__":
    ingest_schemas()

