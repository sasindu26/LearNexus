import os
import numpy as np
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from models.services.gemini_service import GeminiService
from typing import List, Dict, Any, Tuple
import nltk
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Download required NLTK data
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('averaged_perceptron_tagger_eng', quiet=True)

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
        
        # Initialize Gemini Service
        self.gemini = GeminiService()
        
        # Initialize sentiment analyzer
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        
        # Cache available courses to restrict LLM hallucinations
        self.available_courses = self._fetch_available_courses()

    def _fetch_available_courses(self) -> List[str]:
        """Fetch all course names from the database to guide the LLM."""
        try:
            with self.driver.session() as session:
                result = session.run("MATCH (c:Course) RETURN c.name AS name")
                return [record["name"] for record in result]
        except Exception as e:
            print(f"Error fetching available courses: {e}")
            return []

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

    def semantic_search_courses(self, user_query: str, threshold: float = 0.3) -> List[Dict[str, Any]]:
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
        WHERE c.embedding IS NOT NULL
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
            description: m.description,
            level: m.level
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
        Generate a comprehensive learning path response using Gemini
        """
        context = {
            "user_query": user_query,
            "matched_courses": [course['name'] for course in courses],
            "related_modules": [module['name'] for module in modules]
        }
        
        return self.gemini.generate_educational_response(
            user_query,
            context=context
        )

    def is_question(self, text: str) -> bool:
        """
        Detect if the input text is a question using NLP techniques
        """
        try:
            # Tokenize and POS tag the text
            tokens = word_tokenize(text.lower())
            pos_tags = pos_tag(tokens)
            
            # Question indicators
            question_words = {'what', 'why', 'how', 'when', 'where', 'which', 'who', 'whose', 'whom'}
            starts_with_question_word = tokens[0] in question_words if tokens else False
            ends_with_question_mark = text.strip().endswith('?')
            has_modal_verb_first = pos_tags[0][1] in ['MD', 'VBP', 'VBZ'] if pos_tags else False
            
            return starts_with_question_word or ends_with_question_mark or has_modal_verb_first
        except Exception as e:
            print(f"is_question NLP error (falling back to simple check): {e}")
            # Fallback: simple check without NLTK
            question_words = ['what', 'why', 'how', 'when', 'where', 'which', 'who', 'whose', 'whom', 'is', 'are', 'can', 'could', 'will', 'would']
            lower = text.lower().strip()
            return lower.endswith('?') or any(lower.startswith(w + ' ') for w in question_words)

    def get_sentiment(self, text: str) -> float:
        """
        Analyze sentiment of the input text
        Returns compound sentiment score (-1 to 1)
        """
        sentiment_scores = self.sentiment_analyzer.polarity_scores(text)
        return sentiment_scores['compound']

    def chat(self, user_query: str, history: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Chat interface with conversation memory.
        Logic:
        1. Pure greetings (hello, hi) with no prior history -> welcome message via LLM
        2. Once user has shared interests/skills -> always attempt semantic search
        3. If semantic search finds a match -> return course with modules (triggers popup)
        4. If no match -> LLM gives guidance using ONLY available courses
        """
        history = history or []
        
        # Aggregate ALL user messages for a rich search query
        user_messages = [m['content'] for m in history if m['role'] == 'user']
        combined_query = " ".join(user_messages + [user_query]).strip()
        
        # Count how many times the user has spoken (including this message)
        user_turn_count = len(user_messages) + 1
        
        # Build history text for LLM context
        history_text = "\n".join([f"{'User' if m['role'] == 'user' else 'Mento'}: {m['content']}" for m in history[-6:]])
        courses_list = ', '.join(self.available_courses)
        
        # --- STEP 1: Pure greeting on first message ---
        greeting_words = ['hello', 'hi', 'hey', 'good morning', 'good evening', 'good afternoon', 'sup', 'yo']
        is_greeting = user_query.lower().strip().rstrip('!.') in greeting_words
        
        if is_greeting and user_turn_count <= 1:
            # First message is just a greeting - welcome them
            prompt = f"""
            You are Mento AI, a friendly university degree advisor at LearNexus.
            A new student just said: "{user_query}"
            
            Give them a warm welcome. Introduce yourself briefly and ask them:
            - What subjects or activities they enjoy
            - What skills they are naturally good at
            - What career they dream about
            
            Keep it warm, encouraging, and under 100 words. Start with "Hi there! I'm Mento AI"
            """
            response = self.gemini.generate_content(prompt)
            return (response or "Hi there! I'm Mento AI, your degree advisor. Tell me about your interests and skills!"), []
        
        # --- STEP 2: Always try semantic search if user has shared anything ---
        if user_turn_count >= 2 or not is_greeting:
            print(f"[SEARCH] Searching with combined query: {combined_query[:100]}...")
            courses = self.semantic_search_courses(combined_query)
            
            if courses:
                # Found a matching course! Return it with modules.
                best_course = courses[0]
                print(f"[SEARCH] Found match: {best_course['name']} (similarity: {best_course.get('similarity', 'N/A')})")
                modules = self.retrieve_related_modules(best_course['name'])
                best_course['modules'] = modules
                
                response = self.generate_learning_path_response(courses, modules, user_query)
                return response, [best_course]
        
        # --- STEP 3: No match found - use LLM with available courses list ---
        prompt = f"""
        You are Mento AI, a university career advisor for LearNexus.
        
        Recent Chat History:
        {history_text}
        
        User's latest message: "{user_query}"
        
        AVAILABLE DEGREES AT OUR UNIVERSITY (ONLY suggest from this list):
        {courses_list}
        
        RULES:
        1. You MUST ONLY suggest or discuss degrees from the AVAILABLE DEGREES list above.
        2. Do NOT invent, hallucinate, or mention any degree that is not in that list.
        3. If the user's interests match one of the available degrees, confidently recommend it by its exact name.
        4. If you need more info, ask focused questions about their skills and interests.
        5. DO NOT re-introduce yourself if you already did in the chat history.
        6. Keep it friendly, structured, and under 120 words.
        """
        try:
            response = self.gemini.generate_content(prompt)
            return (response if response else "I'm sorry, I couldn't generate a response at the moment."), []
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I'm sorry, I couldn't generate a response at the moment.", []

def main():
    neo4j_config = {
        "url": "bolt://localhost:7687",
        "username": "neo4j",
        "password": "LearNexus1212",
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