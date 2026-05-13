import numpy as np
import hdbscan
from py2neo import Graph
from sklearn.metrics.pairwise import cosine_similarity

# Connect to Neo4j
graph = Graph("bolt://localhost:7691", auth=("neo4j", "Mento@2152"))

# Step 1: Fetch article embeddings from Neo4j
article_query = """
MATCH (a:Article) 
RETURN a.url AS url, a.embedding AS embedding
"""
articles = graph.run(article_query).data()

# Extract URLs and embeddings
article_urls = [article["url"] for article in articles]
article_embeddings = np.array([article["embedding"] for article in articles])

 
# Step 2: Fetch module embeddings from Neo4j
module_query = """
MATCH (m:Module)
RETURN m.name AS name, m.embeddings AS embedding
"""
modules = graph.run(module_query).data()

# Extract module names and embeddings
module_names = [module["name"] for module in modules]
module_embeddings = np.array([module["embedding"] for module in modules])

# Step 3: Cluster Articles using HDBSCAN
clusterer = hdbscan.HDBSCAN(min_cluster_size=3, metric='euclidean', cluster_selection_method='eom')
cluster_labels = clusterer.fit_predict(article_embeddings)

# Step 4: Store Cluster Labels in Neo4j
for i, url in enumerate(article_urls):
    graph.run("""
        MATCH (a:Article {url: $url})
        SET a.cluster = $cluster
    """, url=url, cluster=int(cluster_labels[i]) if cluster_labels[i] != -1 else None)

print("✅ Clusters successfully stored in Neo4j!")

# Step 5: Compute Cosine Similarity for Module-Article Matching
article_module_sim = cosine_similarity(article_embeddings, module_embeddings)

# Step 6: Store Module-Article Relationships in Neo4j
for i, url in enumerate(article_urls):
    best_module_index = np.argmax(article_module_sim[i])  # Get the most relevant module
    best_module_name = module_names[best_module_index]
    
    graph.run("""
        MATCH (a:Article {url: $url}), (m:Module {name: $module})
        MERGE (a)-[:RELATED_TO]->(m)
    """, url=url, module=best_module_name)

print("✅ Articles linked to the most relevant modules in Neo4j!")

# Step 7: Compute Cosine Similarity for Article Recommendations
cosine_sim = cosine_similarity(article_embeddings)

# Step 8: Store Similar Article Relationships in Neo4j
for i, url in enumerate(article_urls):
    similarities = list(enumerate(cosine_sim[i]))
    similarities.sort(key=lambda x: x[1], reverse=True)  # Sort by similarity score
    top_similar_articles = similarities[1:6]  # Get top 5 most similar articles

    for index, score in top_similar_articles:
        similar_url = article_urls[index]
        graph.run("""
            MATCH (a1:Article {url: $url1}), (a2:Article {url: $url2})
            MERGE (a1)-[:SIMILAR_TO {score: $score}]->(a2)
        """, url1=url, url2=similar_url, score=score)

print("✅ Articles linked to similar articles in Neo4j!")
