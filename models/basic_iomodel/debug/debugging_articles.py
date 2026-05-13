import numpy as np
import hdbscan
from py2neo import Graph, ServiceUnavailable
from sklearn.metrics.pairwise import cosine_similarity

try:
    # Create Graph connection with authentication
    graph = Graph("bolt://localhost:7691", auth=("neo4j", "Mento@2152"))

    article_query = """
    MATCH (a:Article) 
    RETURN a.url AS url, a.embedding AS embedding
    """
    articles = graph.run(article_query).data()

    print("✅ Retrieved Articles:", articles[:3])  # Check the first 3 articles

    # Convert to NumPy array (ensure embeddings are correctly formatted)
    article_embeddings = np.array([article["embedding"] for article in articles if article["embedding"] is not None])

    # Check for NaNs
    print("🚨 Any NaNs in article embeddings?", np.isnan(article_embeddings).any())

except ServiceUnavailable:
    print("❌ Could not connect to Neo4j database. Please check if the database is running.")
except Exception as e:
    print(f"❌ An error occurred: {str(e)}")
