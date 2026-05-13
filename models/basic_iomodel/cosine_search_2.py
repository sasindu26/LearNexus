import os
import numpy as np
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Tuple
import nltk
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import requests

# Download required NLTK data
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')

class XAI:
    def __init__(self):
        self.api_key = os.environ.get("XAI_API_KEY", "")
        self.api_url = "https://api.x.ai/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def invoke(self, prompt: str) -> str:
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": "You are MENTO, an educational advisor."},
                    {"role": "user", "content": prompt}
                ],
                "model": "grok-2-latest",
                "stream": False,
                "temperature": 0
            }
            
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"Error calling X.AI API: {e}")
            return "Sorry, I encountered an error while processing your request."

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
        
        # Replace OllamaLLM with XAI
        self.llm = XAI()
        
        # Initialize sentiment analyzer
        self.sentiment_analyzer = SentimentIntensityAnalyzer()

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

    def semantic_search_courses(self, user_query: str, threshold: float = 0.2) -> List[Dict[str, Any]]:
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
        LIMIT 5
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
        :return: List of related modules with descriptions
        """
        cypher_query = """
        MATCH (c:Course {name: $course_name})-[:CONTAINS]->(m:Module)
        RETURN {
            name: m.name,
            description: m.description
        } AS module
        """
        
        try:
            with self.driver.session() as session:
                results = session.run(cypher_query, course_name=course_name)
                modules = [record["module"] for record in results]
                print("Retrieved modules:", modules)  # Debug print
                return modules
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

    def is_question(self, text: str) -> bool:
        """
        Detect if the input text is a question using NLP techniques
        """
        # Tokenize and POS tag the text
        tokens = word_tokenize(text.lower())
        pos_tags = pos_tag(tokens)
        
        # Question indicators
        question_words = {'what', 'why', 'how', 'when', 'where', 'which', 'who', 'whose', 'whom'}
        starts_with_question_word = tokens[0] in question_words
        ends_with_question_mark = text.strip().endswith('?')
        has_modal_verb_first = pos_tags[0][1] in ['MD', 'VBP', 'VBZ'] if pos_tags else False
        
        return starts_with_question_word or ends_with_question_mark or has_modal_verb_first

    def get_sentiment(self, text: str) -> float:
        """
        Analyze sentiment of the input text
        Returns compound sentiment score (-1 to 1)
        """
        sentiment_scores = self.sentiment_analyzer.polarity_scores(text)
        return sentiment_scores['compound']

    def chat(self, user_query: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Modified chat interface with question detection and sentiment analysis
        """
        # Analyze query characteristics
        is_question = self.is_question(user_query)
        sentiment_score = self.get_sentiment(user_query)
        
        # Direct to LLM if it's a question/greeting/negative sentiment
        if (is_question or sentiment_score < -0.1 or len(user_query.split()) <= 3):
            prompt = f"""
            Your name is MENTO. You are an educational advisor who helps students.
            Current query: "{user_query}"
            Context: {'This appears to be a question.' if is_question else 'This appears to be a statement.'}
            Sentiment: {'negative' if sentiment_score < -0.1 else 'neutral or positive'}
            
            Respond appropriately to the query. If it's a greeting, be friendly.
            If it's a question, provide helpful information.
            If there's frustration, show empathy and offer constructive guidance.
            """
            try:
                response = self.llm.invoke(prompt)
                return response, []
            except Exception as e:
                print(f"Error generating response: {e}")
                return "I'm sorry, I couldn't generate a response at the moment.", []

        # Search for matching courses
        courses = self.semantic_search_courses(user_query)
        
        if not courses:
            # If no courses match, use LLM for response
            prompt = f"""
            Your name is MENTO. You are an educational advisor who helps students.
            Based on the query: "{user_query}"
            Recommend suitable courses from:
            - Computer Science
            - Data Science
            - Software Engineering
            - Computer Networks
            - Information Management Systems
            
            Provide a friendly and informative response with course suggestions.
            """
            try:
                response = self.llm.invoke(prompt)
                return response, []
            except Exception as e:
                print(f"Error generating response: {e}")
                return "I'm sorry, I couldn't generate a response at the moment.", []

        # Get modules for the best matching course
        best_course = courses[0]['name']
        modules = self.retrieve_related_modules(best_course)  # Removed description parameter
        
        # Generate response with course and module information
        response = self.generate_learning_path_response(courses, modules, user_query)
        return response, modules  # Return modules instead of courses

def main():
    neo4j_config = {
        "url": "bolt://localhost:7691",
        "username": "neo4j",
        "password": "Mento@2152",
        "database": "neo4j"
    }
    
    chatbot = EducationalChatbot(neo4j_config)
    
    if not chatbot.connect():
        return
    
    try:
        while True:
            user_query = input("You: ")
            response, modules = chatbot.chat(user_query)
            print("Chatbot:", response)
    
    except KeyboardInterrupt:
        print("\nChat ended by user.")
    
    finally:
        # Ensure database connection is closed
        chatbot.close()

if __name__ == "__main__":
    main()