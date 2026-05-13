from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Neo4jVector
from neo4j import GraphDatabase
import logging


class ModuleEmbeddingUpdater:
    def __init__(self, neo4j_url, neo4j_username, neo4j_password):
        # Initialize Neo4j
        self.graph = GraphDatabase.driver(neo4j_url, auth=(neo4j_username, neo4j_password))
        
        # Initialize logger
        self.logger = logging.getLogger("ModuleEmbeddingUpdater")
        logging.basicConfig(level=logging.INFO)

        # Initialize embeddings model
        self.embeddings = self._init_embeddings()

    def _init_embeddings(self):
        """Initialize the embedding model."""
        try:
            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            self.logger.info("Embeddings model initialized successfully")
            return embeddings
        except Exception as e:
            self.logger.error(f"Failed to initialize embeddings: {e}", exc_info=True)
            raise

    def generate_embeddings_for_modules(self):
        """
        Generate and store embeddings for all Module nodes using their descriptions.
        """
        try:
            # Create vector store for the Module nodes
            vector_store = Neo4jVector.from_existing_graph(
                graph=self.graph,
                embedding=self.embeddings,
                index_name="module_embeddings",  # Name of the vector index
                node_label="Module",  # Target only Module nodes
                text_node_properties=["description"],  # Use the 'description' property for embeddings
                embedding_node_property="embeddings"  # Where to store the embeddings
            )
            self.logger.info("Embeddings generated and stored for all modules.")
        except Exception as e:
            self.logger.error(f"Failed to generate embeddings for modules: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    updater = ModuleEmbeddingUpdater(
        neo4j_url="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="Mento@2152"
    )
    
    updater.generate_embeddings_for_modules()
