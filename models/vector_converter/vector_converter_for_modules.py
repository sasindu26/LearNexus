from langchain.embeddings import OpenAIEmbeddings  # Replace with your embedding model
from langchain.vectorstores import Neo4jVector
from neo4j import GraphDatabase
from langchain.embeddings import HuggingFaceEmbeddings


class ModuleEmbeddingUpdater:
    def __init__(self, neo4j_url, neo4j_username, neo4j_password, embedding_model="sentence-transformers/all-MiniLM-L6-v2"):
        # Initialize Neo4j
        self.graph = GraphDatabase.driver(neo4j_url, auth=(neo4j_username, neo4j_password))
        
        # Initialize embeddings model
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            self.logger.info("Embeddings model initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize embeddings: {e}", exc_info=True)
            raise
        # Neo4j configuration for Neo4jVector
        self.neo4j_config = {
            "uri": neo4j_url,
            "auth": (neo4j_username, neo4j_password)
        }

    def generate_embeddings_for_modules(self):
        """
        Generate and store embeddings for all Module nodes using their descriptions.
        """
        # Create vector store for the Module nodes
        vector_store = Neo4jVector.from_existing_graph(
            embedding=self.embeddings,
            **self.neo4j_config,
            index_name="module_embeddings",  # Name of the vector index
            node_label="Module",  # Target only Module nodes
            text_node_properties=["description"],  # Use the 'description' property for embeddings
            embedding_node_property="embeddings"  # Where to store the embeddings
        )
        print("Embeddings generated and stored for all modules.")

if __name__ == "__main__":
    updater = ModuleEmbeddingUpdater(
        neo4j_url="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="Mento@2152"
    )
    
    updater.generate_embeddings_for_modules()
