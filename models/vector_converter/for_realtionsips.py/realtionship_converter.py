from neo4j import GraphDatabase
from langchain_huggingface import HuggingFaceEmbeddings
import numpy as np
import logging
from langchain_ollama.llms import OllamaLLM
from langchain_ollama.llms import OllamaLLM

class Neo4jRelationshipUpdater:
    def __init__(self, neo4j_url, username, password, llm_model):
        # Neo4j connection details
        self.neo4j_url = neo4j_url
        self.username = username
        self.password = password

        # Initialize Neo4j driver
        self.driver = GraphDatabase.driver(self.neo4j_url, auth=(self.username, self.password))

        # Initialize LLM and embeddings
        self.llm_model = OllamaLLM(model="mistral:7b")  
        self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )# Replace with your embedding model if needed

        # Initialize logging
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

    def fetch_relationships_with_labels(self):
        """
        Fetch all relationship types in the Neo4j database with their connected node labels.
        """
        query = """
        MATCH (a)-[r]->(b)
        RETURN DISTINCT type(r) AS relationship, labels(a) AS start_labels, labels(b) AS end_labels
        """
        with self.driver.session() as session:
            result = session.run(query)
            relationships = [
                {
                    "relationship": record["relationship"],
                    "start_labels": record["start_labels"],
                    "end_labels": record["end_labels"]
                }
                for record in result
            ]
        self.logger.info(f"Fetched relationships with labels: {relationships}")
        return relationships

    def generate_description(self, relationship_type, start_labels, end_labels):
        """
        Generate a description for a relationship using the LLM, including node label context.
        """
        start_labels_str = ", ".join(start_labels)
        end_labels_str = ", ".join(end_labels)

        prompt = (
            f"Describe the '{relationship_type}' relationship. "
            f"It connects nodes with labels '{start_labels_str}' to '{end_labels_str}'. "
            "Explain its purpose and how it can help find related information in an AI context."
        )
        
        # Call the LLM with the prompt
        response = self.llm_model(prompt=prompt)
        
        # Extract the text from the response (OllamaLLM returns a string response directly)
        description = response.strip()
        
        self.logger.info(f"Generated description for '{relationship_type}': {description}")
        return description
    def generate_embedding(self, description):
        """
        Generate an embedding vector for the given description.
        """
        embedding = self.embeddings.embed_query(description)
        self.logger.info(f"Generated embedding for description: {description}")
        return embedding

    def update_relationship_properties(self, relationship_type, start_labels, end_labels, description, embedding):
        """
        Update the Neo4j relationship with the description and embedding properties.
        """
        start_labels_str = ", ".join(start_labels)
        end_labels_str = ", ".join(end_labels)

        query = f"""
        MATCH (a)-[r:`{relationship_type}`]->(b)
        WHERE labels(a) = $start_labels AND labels(b) = $end_labels
        SET r.description = $description,
            r.embedding = $embedding
        """
        with self.driver.session() as session:
            session.run(
                query,
                start_labels=start_labels,
                end_labels=end_labels,
                description=description,
                embedding=embedding
            )
        self.logger.info(f"Updated properties for relationship '{relationship_type}' with labels '{start_labels_str}' -> '{end_labels_str}'.")

    def process(self):
        """
        Execute the full pipeline: Fetch relationships, generate descriptions, and update properties.
        """
        # Step 1: Fetch relationships with node labels
        relationships = self.fetch_relationships_with_labels()

        # Step 2: For each relationship, generate a description and embedding, then update the database
        for rel in relationships:
            relationship_type = rel["relationship"]
            start_labels = rel["start_labels"]
            end_labels = rel["end_labels"]

            description = self.generate_description(relationship_type, start_labels, end_labels)
            embedding = self.generate_embedding(description)
            self.update_relationship_properties(relationship_type, start_labels, end_labels, description, np.array(embedding).tolist())

# Example usage
if __name__ == "__main__":
    # Define Neo4j and LLM credentials
    NEO4J_URL = "bolt://localhost:7687"
    NEO4J_USERNAME = "neo4j"
    NEO4J_PASSWORD = "Mento@2152"
    LLM_MODEL = "mistral"  # Replace with your local Mistral LLM integration

    # Initialize and process
    updater = Neo4jRelationshipUpdater(
        neo4j_url=NEO4J_URL,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        llm_model=LLM_MODEL
    )
    updater.process()