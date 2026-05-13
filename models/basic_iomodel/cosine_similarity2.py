import os
import numpy as np
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from langchain_ollama.llms import OllamaLLM
from typing import List, Dict, Any

class EducationalChatbot:
    def __init__(self, neo4j_config: Dict[str, str]):
        """
        Initialize the Educational Chatbot with Neo4j configuration
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
        # LLM for Response Generation
        self.llm = OllamaLLM(model="mistral:7b")

    def semantic_search_courses(self, user_query: str, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Perform semantic search for courses using vector similarity
        """
        # Generate embedding for user query
        query_embedding = self.embedding_model.encode(user_query).tolist()
        
        # Cypher query for semantic search using vector similarity
        cypher_query = """
        MATCH (c:Course)
        WITH c, 
             gds.similarity.cosine(c.embedding, $query_embedding) AS similarity
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

    def generate_response(self, user_query: str, courses: List[Dict]) -> str:
        """
        Generate a detailed response using LLM with multiple fallback methods
        """
        # Prepare course details
        course_details = "\n".join([
            f"- {course['name']}: {course.get('description', 'No description available')}"
            for course in courses
        ])
        
        # Construct prompt
        prompt = f"""
        User Query: {user_query}

        Matched Courses:
        {course_details}

        Provide a comprehensive and engaging response that:
        1. Explains the relevance of these courses to the user's interests
        2. Outlines potential learning paths in data science
        3. Offers insights into how these courses can support the user's goals
        4. Recommend next steps for learning

        Write in a friendly, motivational tone that encourages learning.
        """
        
        try:
            # Multiple methods to generate and extract response
            try:
                # Method 1: Using invoke() with explicit content extraction
                response = self.llm.invoke(prompt)
                
                # Check different possible response formats


                if hasattr(response, 'content'):
                    generated_text = response.content
                elif hasattr(response, 'text'):
                    generated_text = response.text
                else:
                    generated_text = str(response)
                
                if not generated_text:
                    raise ValueError("Empty response generated")
                
                return generated_text
            
            except Exception as e1:
                print(f"First method failed: {e1}")
                
                try:
                    # Method 2: Direct string conversion
                    response = str(self.llm.invoke(prompt))
                    if response:
                        return response
                    raise ValueError("Empty response")
                
                except Exception as e2:
                    print(f"Second method failed: {e2}")
                    
                    # Fallback response
                    return f"""
                    I'm having trouble generating a detailed response, but here's what I found:

                    Matched Courses for '{user_query}':
                    {course_details}

                    Recommendations:
                    1. These courses seem relevant to your interests in data science
                    2. I suggest exploring each course description in more detail
                    3. Consider reaching out to the course providers for more information
                    """
        
        except Exception as e:
            print(f"Comprehensive error in response generation: {e}")
            return f"I encountered an error generating a personalized response. Matched courses: {course_details}"

    def chat(self, user_query: str) -> str:
        """
        Main chat interface method
        """
        # Step 1: Semantic Course Search
        courses = self.semantic_search_courses(user_query)
        
        # If no courses found
        if not courses:
            return "I couldn't find any courses matching your interests. Could you provide more specific details about what you'd like to learn in data science?"
        
        # Step 2: Generate Response
        response = self.generate_response(user_query, courses)
        
        return response

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
    
    try:
        # Interactive Chat Loop
        while True:
            user_query = input("You: ")
            if user_query.lower() in ['exit', 'quit', 'bye']:
                break
            
            response = chatbot.chat(user_query)
            print("Chatbot:", response)
    
    except KeyboardInterrupt:
        print("\nChat ended by user.")

if __name__ == "__main__":
    main()