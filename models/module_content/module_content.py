import sys
import os
import time
from neo4j import GraphDatabase
import json 
# Add project root to path for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.append(project_root)

# Use absolute import
from config.logging_config import setup_logger

# Setup logger for module content
logger = setup_logger('module_content', 'topic_extractor.log')

class ModuleContentExtractor:
    def __init__(self, uri="bolt://localhost:7687", username="neo4j", password="LearNexus1212"):
        logger.info("Initializing ModuleContentExtractor")
        try:
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
            # Test the connection
            with self.driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) as count LIMIT 1")
                count = result.single()["count"]
                logger.info(f"Connected to Neo4j database. Node count: {count}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    # Add this method to handle the API call
    def get_module_content(self, module_name):
        """
        Wrapper method that calls get_topics_for_module - this matches the API call
        
        Args:
            module_name (str): The name of the module
            
        Returns:
            list: A list of dictionaries containing topic information
        """
        logger.info(f"get_module_content called for: {module_name}")
        try:
            return self.get_topics_for_module(module_name)
        except Exception as e:
            logger.error(f"Error in get_module_content for '{module_name}': {str(e)}", exc_info=True)
            # Return empty list instead of raising to avoid 500 errors
            return []

    def get_topics_for_module(self, module_name):
        """
        Retrieves all topics associated with a specific module
        
        Args:
            module_name (str): The name of the module
            
        Returns:
            list: A list of dictionaries containing topic information
        """
        logger.info(f"Fetching topics for module: {module_name}")
        
        try:
            with self.driver.session() as session:
                # Use exact match to avoid pulling topics from different-cased module variants
                query = """
                    MATCH (m:Module {name: $module_name})-[:HAS_TOPIC]->(t:Topic)
                    RETURN t.name AS topic_name, t.description AS topic_description
                    ORDER BY t.name
                """
                logger.info(f"Executing Neo4j query with module_name={module_name}")
                result = session.run(query, module_name=module_name)

                topics = []
                for record in result:
                    topics.append({
                        "topic": record["topic_name"],
                        "description": record.get("topic_description", "No description available")
                    })

                logger.info(f"Query returned {len(topics)} topics for module '{module_name}'")

                # Fallback: case-insensitive, but only from ONE module (first alphabetically)
                if len(topics) == 0:
                    logger.info("Exact match returned no topics, trying case-insensitive fallback")
                    fallback_query = """
                        MATCH (m:Module)-[:HAS_TOPIC]->(t:Topic)
                        WHERE toLower(m.name) = toLower($module_name)
                        WITH m.name AS matched_name, collect({topic: t.name, description: t.description}) AS topics
                        ORDER BY matched_name ASC
                        LIMIT 1
                        UNWIND topics AS tp
                        RETURN tp.topic AS topic_name, tp.description AS topic_description
                        ORDER BY topic_name
                    """
                    fallback_result = session.run(fallback_query, module_name=module_name)
                    for record in fallback_result:
                        topics.append({
                            "topic": record["topic_name"],
                            "description": record.get("topic_description", "No description available")
                        })
                    if topics:
                        logger.info(f"Fallback returned {len(topics)} topics for '{module_name}'")

                return topics
                
        except Exception as e:
            logger.error(f"Error fetching topics for module '{module_name}': {e}", exc_info=True)
            # Re-raise the exception to be caught by the wrapper
            raise

    def close(self):
        """Close the Neo4j driver connection"""
        if hasattr(self, 'driver'):
            self.driver.close()
            logger.info("Neo4j connection closed")


def main():
    try:
        logger.info("Starting ModuleContentExtractor")
        extractor = ModuleContentExtractor()
        logger.debug("ModuleContentExtractor initialized")
        
        module_name = input("Enter module name: ")
        logger.info(f"Requesting topics for module: '{module_name}'")
        
        topics = extractor.get_module_content(module_name)
        
        # Prepare results as a dictionary
        result = {
            "module_name": module_name,
            "status": "success",
            "topics": topics if topics else []
        }
        
        if topics:
            logger.info(f"Found {len(topics)} topics for module '{module_name}'")
        else:
            logger.warning(f"No topics found for module '{module_name}'")
            result["status"] = "warning"
            result["message"] = f"No topics found for module '{module_name}'"
        
        # Output as formatted JSON
        print(json.dumps(result, indent=2))
    
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}", exc_info=True)
        error_result = {
            "status": "error",
            "message": str(e),
            "module_name": module_name if 'module_name' in locals() else None,
            "topics": []
        }
        print(json.dumps(error_result, indent=2))
    finally:
        logger.debug("Cleaning up resources")
        if 'extractor' in locals():
            extractor.close()
        logger.info("ModuleContentExtractor finished")

if __name__ == "__main__":
    main()