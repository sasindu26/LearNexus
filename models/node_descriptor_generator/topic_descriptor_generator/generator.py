from neo4j import GraphDatabase
from langchain.llms import Ollama
from langchain.prompts import PromptTemplate
import time
import logging

# Update logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('topic_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Neo4j configuration
neo4j_config = {
    "url": "bolt://localhost:7691",
    "username": "neo4j",
    "password": "Mento@2152",
    "database": "neo4j"
}

class TopicDescriptionGenerator:
    def __init__(self, neo4j_config):
        """Initialize the generator with Neo4j connection and Ollama LLM."""
        logger.debug(f"Initializing TopicDescriptionGenerator with config: {neo4j_config}")
        self.driver = GraphDatabase.driver(
            neo4j_config["url"], 
            auth=(neo4j_config["username"], neo4j_config["password"])
        )
        
        # Initialize Ollama with Mistral-7B model
        self.llm = Ollama(model="mistral:7b")
        
        # Define the prompt template for topic descriptions
        self.prompt_template = PromptTemplate(
            input_variables=["topic_name", "topic_properties"],
            template="""
            Generate a comprehensive academic description of approximately 250 words for the topic "{topic_name}".
            
            If available, use these additional details about the topic: {topic_properties}
            
            The description should be informative, well-structured, and suitable for educational purposes.
            Like how to start to get into it . Include key concepts, applications, and significance of this topic in its field.
            """
        )
        logger.debug("LLM and Neo4j connection initialized successfully")

    def fetch_topics(self):
        """Fetch all Topic nodes from Neo4j."""
        logger.debug("Starting to fetch topics from Neo4j")
        with self.driver.session(database=neo4j_config["database"]) as session:
            result = session.run("MATCH (t:Topic) RETURN t")
            topics = [record["t"] for record in result]
            logger.debug(f"Query executed, found {len(topics)} topics")
            logger.info(f"Fetched {len(topics)} topics from Neo4j")
            return topics

    def generate_description(self, topic_name, topic_properties=None):
        """Generate a description for a given topic using the LLM."""
        logger.debug(f"Generating description for topic: {topic_name}")
        logger.debug(f"Topic properties: {topic_properties}")
        
        if topic_properties is None:
            topic_properties = "No additional information available"
        
        # Format the prompt with topic information
        prompt = self.prompt_template.format(
            topic_name=topic_name,
            topic_properties=topic_properties
        )
        
        # Generate description with the LLM
        try:
            logger.debug("Sending prompt to LLM")
            description = self.llm.predict(prompt)
            logger.debug(f"Generated description length: {len(description)}")
            return description.strip()
        except Exception as e:
            logger.error(f"LLM error for {topic_name}: {str(e)}", exc_info=True)
            return f"Description generation failed: {str(e)}"

    def update_topic_with_description(self, topic_id, description):
        """Update the Topic node in Neo4j with the generated description."""
        logger.debug(f"Updating topic {topic_id} with new description")
        with self.driver.session(database=neo4j_config["database"]) as session:
            result = session.run(
                "MATCH (t:Topic) WHERE ID(t) = $topic_id "
                "SET t.description = $description "
                "RETURN t",
                topic_id=topic_id,
                description=description
            )
            logger.debug(f"Topic {topic_id} updated successfully")
            return result.single()

    def process_all_topics(self, batch_size=5, delay_seconds=2):
        """Process all topics, generate descriptions, and update Neo4j."""
        logger.debug(f"Starting batch processing with size={batch_size}, delay={delay_seconds}s")
        topics = self.fetch_topics()
        logger.info(f"Starting to process {len(topics)} topics")
        
        for i, topic in enumerate(topics):
            topic_id = topic.id
            topic_name = topic.get("name", f"Unknown Topic {topic_id}")
            
            # Extract all properties to provide context to the LLM
            properties_dict = dict(topic)
            # Remove any existing description to avoid influencing the new generation
            properties_dict.pop("description", None)
            
            logger.info(f"Generating description for topic: {topic_name} ({i+1}/{len(topics)})")
            description = self.generate_description(topic_name, str(properties_dict))
            
            # Update the topic in Neo4j
            self.update_topic_with_description(topic_id, description)
            logger.info(f"Updated description for topic: {topic_name}")
            
            # Introduce delay after each batch to avoid overloading Ollama
            if (i + 1) % batch_size == 0:
                logger.info(f"Processed {i+1} topics. Pausing for {delay_seconds} seconds.")
                time.sleep(delay_seconds)

    def close(self):
        """Close the Neo4j connection."""
        self.driver.close()


def main():
    """Main function to run the topic description generator."""
    generator = TopicDescriptionGenerator(neo4j_config)
    try:
        generator.process_all_topics()
        logger.info("Successfully generated descriptions for all topics")
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
    finally:
        generator.close()


if __name__ == "__main__":
    main()