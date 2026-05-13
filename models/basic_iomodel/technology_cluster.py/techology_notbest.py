import numpy as np
import hdbscan
from py2neo import Graph
from sklearn.metrics.pairwise import cosine_similarity
import json

# Connect to Neo4j
graph = Graph("bolt://localhost:7691", auth=("neo4j", "Mento@2152"))

# Step 1: Fetch embeddings from Neo4j
query = """
MATCH (a:Article) 
RETURN a.url AS url, a.embedding AS embedding
"""
articles = graph.run(query).data()

# Extract URLs and embeddings
article_urls = [article["url"] for article in articles]
article_embeddings = np.array([article["embedding"] for article in articles])

# Step 2: Clustering using HDBSCAN (automatic number of clusters)
clusterer = hdbscan.HDBSCAN(min_cluster_size=3, metric='euclidean', cluster_selection_method='eom')
cluster_labels = clusterer.fit_predict(article_embeddings)

# Step 3: Store cluster labels in Neo4j
for i, url in enumerate(article_urls):
    graph.run("""
        MATCH (a:Article {url: $url})
        SET a.cluster = $cluster
    """, url=url, cluster=int(cluster_labels[i]) if cluster_labels[i] != -1 else None)

print("✅ Clusters successfully stored in Neo4j!")

# Step 4: Build Cosine Similarity for recommendations
cosine_sim = cosine_similarity(article_embeddings)

# Step 5: Store Similar Articles in Neo4j (Only Top 5 similar)
for i, url in enumerate(article_urls):
    similarities = list(enumerate(cosine_sim[i]))
    similarities.sort(key=lambda x: x[1], reverse=True)  # Sort by similarity score
    top_similar_articles = similarities[1:6]  # Get top 5 most similar articles

    for index, score in top_similar_articles:
        similar_url = article_urls[index]
        graph.run("""
            MATCH (a1:Article {url: $url1}), (a2:Article {url: $url2})
            MERGE (a1)-[:SIMILAR_TO {score: $score}]->(a2)
        """, url1=url, url2=similar_url, score=float(score))

print("✅ Similarity relationships stored in Neo4j!")
