"""Cluster Tool — K-means clustering on chunk embeddings."""

import numpy as np
from sklearn.cluster import KMeans

from app.services.ingestion import get_collection
from app.services.embeddings import embed_texts
from app.tools.registry import BaseTool, ToolResult


class ClusterTool(BaseTool):
    @property
    def name(self) -> str:
        return "cluster"

    @property
    def description(self) -> str:
        return (
            "Cluster interview content into thematic groups. Best for discovering "
            "patterns, identifying themes, or exploring what topics exist in the data."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "n_clusters": {"type": "integer", "default": 5, "description": "Number of clusters"},
                "query": {"type": "string", "description": "Optional: focus clustering on a topic"},
            },
        }

    async def execute(self, params: dict) -> ToolResult:
        n_clusters = params.get("n_clusters", 5)

        try:
            collection = get_collection()
            total = collection.count()

            if total < n_clusters:
                return ToolResult(
                    data={"message": f"Not enough documents ({total}) for {n_clusters} clusters"},
                    success=True,
                )

            # Get all embeddings from ChromaDB
            all_data = collection.get(
                include=["embeddings", "documents", "metadatas"],
                limit=min(total, 1000),
            )

            if not all_data["embeddings"]:
                return ToolResult(
                    data={"message": "No embeddings found"},
                    success=True,
                )

            embeddings = np.array(all_data["embeddings"])
            documents = all_data["documents"]
            ids = all_data["ids"]

            # K-means clustering
            kmeans = KMeans(n_clusters=min(n_clusters, len(embeddings)), random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)

            # Build cluster summaries
            clusters = {}
            for i, (label, doc, doc_id) in enumerate(zip(labels, documents, ids)):
                label = int(label)
                if label not in clusters:
                    clusters[label] = {
                        "cluster_id": label,
                        "documents": [],
                        "size": 0,
                    }
                clusters[label]["documents"].append({
                    "id": doc_id,
                    "content": doc[:200] + "..." if len(doc) > 200 else doc,
                })
                clusters[label]["size"] += 1

            # Find representative document (closest to centroid)
            for label, cluster in clusters.items():
                mask = labels == label
                cluster_embeddings = embeddings[mask]
                centroid = kmeans.cluster_centers_[label]
                distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
                representative_idx = np.argmin(distances)
                cluster_docs = [documents[i] for i, l in enumerate(labels) if l == label]
                cluster["representative"] = cluster_docs[representative_idx][:300]

            return ToolResult(
                data={
                    "clusters": list(clusters.values()),
                    "total_documents": total,
                    "n_clusters": len(clusters),
                },
                metadata={"method": "kmeans"},
            )

        except Exception as e:
            return ToolResult(data=None, errors=[str(e)], success=False)
