import os
import numpy as np
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from langchain_ollama.llms import OllamaLLM
from typing import List, Dict, Any, Tuple

class EducationalChatbot:
    def __init__(self, neo4j_config: Dict[str, str]):

        """
        Initialize the Educational Chatbot with Neo4j configuration
        
        :param neo4j_config: Dictionary containing Neo4j connection parameters
        """
        # Neo4j Connection
        try:
            self.driver = GraphDatabase.driver(
                neo4j_config["url"],
                auth=(neo4j_config["username"], neo4j_config["password"]),
                database=neo4j_config.get("database", "neo4j")
            )
        except Exception as e:
            print(f"Error connecting to Neo4j: {e}")
            raise

        # Embedding Model for Semantic Search
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # LLM for Response Generation
        self.llm = OllamaLLM(model="mistral:7b")
    def connect(self) -> bool:
        """
        Verify database connectivity
        
        :return: Boolean indicating connection status
        """
        try:
            with self.driver.session() as session:
                session.run("MATCH (n) RETURN 1 LIMIT 1")
            print("Successfully connected to Neo4j database!")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def semantic_search_courses(self, user_query: str, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Perform semantic search for courses based on user query
        
        :param user_query: User's input query
        :param threshold: Similarity threshold for course matching
        :return: List of matching courses
        """
        # Generate embedding for user query
        query_embedding = self.embedding_model.encode(user_query).tolist()
        
        # Cypher query for semantic search
        cypher_query = """
        MATCH (c:Course)
        WITH c, gds.similarity.cosine(c.embedding, $query_embedding) AS similarity
        WHERE similarity > $threshold
        RETURN c.name AS name, 
               c.description AS description, 
               c.level AS level,
               similarity
        ORDER BY similarity DESC
        LIMIT 3
        """
        
        try:
            with self.driver.session() as session:
                results = session.run(
                    cypher_query, 
                    query_embedding=query_embedding, 
                    threshold=threshold
                )
                return [dict(record) for record in results]
        except Exception as e:
            print(f"Error in semantic course search: {e}")
            return []

    def retrieve_related_modules(self, course_name: str) -> List[Dict[str, Any]]:
        """
        Retrieve modules related to a specific course
        
        :param course_name: Name of the course
        :return: List of related modules
        """
        cypher_query = """
        MATCH (c:Course {name: $course_name})-[:CONTAINS]->(m:Module)
        RETURN m.name AS name
        """
        
        try:
            with self.driver.session() as session:
                results = session.run(cypher_query, course_name=course_name)
                return [dict(record) for record in results]
            print([dict(record) for record in results])
        except Exception as e:
            print(f"Error retrieving modules: {e}")
            return []

    def retrieve_topics_and_resources(self, module_name: str) -> List[Dict[str, Any]]:
        """
        Retrieve topics and resources for a specific module
        
        :param module_name: Name of the module
        :return: List of topics and associated resources
        """
        cypher_query = """
        MATCH (m:Module {name: $module_name})
        OPTIONAL MATCH (m)-[:HAS_TOPIC]->(t:Topic)
        OPTIONAL MATCH (m)-[:HAS_RESOURCE]->(r:Resource)
        RETURN 
            COLLECT(DISTINCT {
                name: t.name, 
                description: t.description
            }) AS topics,
            COLLECT(DISTINCT {
                name: r.name, 
                type: r.type, 
                url: r.url
            }) AS resources
        """
        
        try:
            with self.driver.session() as session:
                results = session.run(cypher_query, module_name=module_name)
                return [dict(record) for record in results][0]
        except Exception as e:
            print(f"Error retrieving topics and resources: {e}")
            return {"topics": [], "resources": []}
        print([dict(record) for record in results][0])

    def generate_learning_path_response(self, courses: List[Dict], 
                                        modules: List[Dict], 
                                        user_query: str) -> str:
        """
        Generate a comprehensive learning path response
        
        :param courses: List of matched courses
        :param modules: List of related modules
        :param user_query: Original user query
        :return: Detailed learning recommendation
        """
        # Prepare context for LLM
        context = f"""
        User Query: {user_query}

        Matched Courses:
        {', '.join([course['name'] for course in courses])}

        Related Modules:
        {', '.join([module['name'] for module in modules])}
        """
        
        # Prompt for generating learning path
        prompt = f"""
        Based on the following context and user's educational interests: Consider that user don't have any prior knowledge about the courses and modules.:

        {context}

        Please provide:
        welcome message to the course. maximum 50 words. with course summary

        Ensure the response is engaging, informative, and tailored to the user's needs.
        """
        
        try:
            response = self.llm.invoke(prompt)
            return response
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I'm sorry, but I couldn't generate a personalized learning recommendation at the moment."

    def chat(self, user_query: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Main chat interface method
        
        :param user_query: User's input query
        :return: Comprehensive learning recommendation and related modules
        """
        # Step 1: Semantic Course Search
        courses = self.semantic_search_courses(user_query)
        
        if not courses:
            return "I couldn't find any courses matching your interests. Could you please be more specific?", []

        # Step 2: Retrieve Related Modules
        best_course = courses[0]['name']
        modules = self.retrieve_related_modules(best_course)
        
        # Optional Step: Retrieve Topics and Resources for the first module
        if modules:
            first_module = modules[0]['name']
            additional_info = self.retrieve_topics_and_resources(first_module)
        
        # Step 3: Generate Personalized Learning Path
        response = self.generate_learning_path_response(
            courses, modules, user_query
        )
        
        return response, modules

    def close(self):
        """
        Close the database connection
        """
        if self.driver:
            self.driver.close()

# Configuration
neo4j_config = {
    "url": "bolt://localhost:7691",
    "username": "neo4j",
    "password": "Mento@2152",
    "database": "neo4j"
}

# Main execution
def main():
    # Initialize Chatbot
    chatbot = EducationalChatbot(neo4j_config)
    
    # Verify Connection
    if not chatbot.connect():
        print("Failed to connect to the database. Exiting.")
        return
    
    try:
        # Interactive Chat Loop
        while True:
            user_query = input("You: ")
            if user_query.lower() in ['exit', 'quit', 'bye']:
                break
            
            response, modules = chatbot.chat(user_query)
            print("Chatbot:", response)
    
    except KeyboardInterrupt:
        print("\nChat ended by user.")
    
    finally:
        # Ensure database connection is closed
        chatbot.close()

if __name__ == "__main__":
    main()