
import numpy as np
import hdbscan
from py2neo import Graph, ServiceUnavailable
from sklearn.metrics.pairwise import cosine_similarity

graph = Graph("bolt://localhost:7691", auth=("neo4j", "Mento@2152"))

module_query = """
MATCH (m:Module)
RETURN m.name AS name, m.embeddings AS embedding
"""
modules = graph.run(module_query).data()

print("✅ Retrieved Modules:", modules[:3])  # Check the first 3 modules

# Convert to NumPy array (ensure embeddings are correctly formatted)
module_embeddings = np.array([module["embedding"] for module in modules if module["embedding"] is not None])

# Check for NaNs
print("🚨 Any NaNs in module embeddings?", np.isnan(module_embeddings).any())

###########
