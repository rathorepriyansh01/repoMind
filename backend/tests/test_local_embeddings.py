from app.services.local_embeddings import (
    embed_documents,
    embed_query,
)


texts = [
    "FastAPI backend provides REST API endpoints.",
    "React frontend communicates with the backend.",
]

print("Loading embedding model...")

vectors = embed_documents(texts)

print("Number of document vectors:", len(vectors))
print("Embedding dimension:", len(vectors[0]))

query_vector = embed_query(
    "Where are the API endpoints implemented?"
)

print("Query embedding dimension:", len(query_vector))

print("\nLocal embeddings working successfully!")