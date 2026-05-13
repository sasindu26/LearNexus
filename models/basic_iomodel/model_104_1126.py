import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from uuid import uuid4
import os

# Simplified imports - ensure you have these libraries installed
try:
    from langchain_community.llms import Ollama
    from langchain_community.graphs import Neo4jGraph
    from langchain.tools import Tool
    from langchain.agents import initialize_agent, AgentType
    from langchain.prompts import PromptTemplate
    from langchain.chains import LLMChain
except ImportError as e:
    print(f"Missing library: {e}")
    print("Please install required libraries:")
    print("pip install langchain langchain-community ollama neo4j")
    exit(1)

class AcademicRAGAssistant:
    def __init__(self, debug_mode=True):
        # Logging Setup
        self.logger = self._setup_logger()
        
        # Neo4j Configuration - REPLACE WITH YOUR ACTUAL CREDENTIALS
        self.neo4j_config = {
            "url": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "Mento@2152",
            "database": "neo4j"
        }
        
        # Initialize Components
        try:
            self._init_components()
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            raise

    def _setup_logger(self):
        """Set up logging with console and file handlers"""
        logger = logging.getLogger('AcademicRAG')
        logger.setLevel(logging.DEBUG)
        
        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_format)
        
        # File Handler
        os.makedirs('logs', exist_ok=True)
        file_handler = RotatingFileHandler(
            f'logs/academic_rag_{datetime.now().strftime("%Y%m%d")}.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger

    def _init_components(self):
        """Initialize all necessary components"""
        # Initialize LLM (Local Ollama model)
        try:
            self.llm = Ollama(model="mistral:7b")
        except Exception as e:
            self.logger.error(f"LLM initialization failed: {e}")
            raise

        # Initialize Neo4j Graph
        try:
            self.graph = Neo4jGraph(**self.neo4j_config)
            self.graph.refresh_schema()
            self.logger.info("Neo4j graph connection established")
        except Exception as e:
            self.logger.error(f"Neo4j connection failed: {e}")
            raise

    def advanced_knowledge_graph_query(self, query):
        """
        Perform a comprehensive query across different node types
        Supporting Course, Module, Topic, and Resources
        """
        try:
            # Comprehensive Cypher query to fetch related information
            comprehensive_query = """
            MATCH (c:Course)
            WHERE toLower(c.name) CONTAINS toLower($query) 
               OR toLower(c.description) CONTAINS toLower($query)
            
            OPTIONAL MATCH (c)-[:CONTAINS]->(m:Module)
            OPTIONAL MATCH (m)-[:HAS]->(t:Topic)
            OPTIONAL MATCH (t)-[:LINKS_TO]->(r:Resources)
            
            RETURN 
                c.name AS course_name,
                c.description AS course_description,
                COLLECT(DISTINCT {
                    module_name: m.name,
                    module_description: m.description,
                    topics: COLLECT(DISTINCT {
                        topic_name: t.name,
                        topic_description: t.description,
                        resources: COLLECT(DISTINCT r.url)
                    })
                }) AS module_details
            LIMIT 3
            """
            
            results = self.graph.query(comprehensive_query, {"query": query})
            
            if not results:
                return "🔍 I couldn't find any courses matching your query. Would you like to try a different search?"
            
            response = []
            for record in results:
                course_info = f"🎓 Course: {record['course_name']}\n"
                course_info += f"Description: {record.get('course_description', 'No description available')}\n\n"
                
                course_info += "Course Structure:\n"
                for module in record['module_details']:
                    course_info += f"📘 Module: {module.get('module_name', 'Unnamed Module')}\n"
                    course_info += f"   Description: {module.get('module_description', 'No module description')}\n\n"
                    
                    course_info += "   🔍 Key Topics:\n"
                    for topic in module.get('topics', []):
                        course_info += f"   - {topic.get('topic_name', 'Unnamed Topic')}\n"
                        course_info += f"     Description: {topic.get('topic_description', 'No topic description')}\n"
                        
                        resources = topic.get('resources', [])
                        if resources:
                            course_info += "     Learning Resources:\n"
                            for res in resources[:3]:  # Limit to 3 resources
                                course_info += f"     • {res}\n"
                        
                        course_info += "\n"
                
                response.append(course_info)
            
            return "\n".join(response)
        
        except Exception as e:
            self.logger.error(f"Advanced graph query error: {e}")
            return f"🤖 Oops! I encountered an issue while searching. Error: {str(e)}"

    def contextual_search(self, query):
        """
        Perform a contextual search across different node types
        Supporting semantic-like search without vector store
        """
        try:
            contextual_query = """
            MATCH (n)
            WHERE 
                toLower(n.name) CONTAINS toLower($query) OR 
                toLower(n.description) CONTAINS toLower($query)
            RETURN 
                labels(n) AS node_types,
                n.name AS name,
                n.description AS description
            LIMIT 5
            """
            
            results = self.graph.query(contextual_query, {"query": query})
            
            if not results:
                return "🔍 No relevant information found in the knowledge base."
            
            response = "🧠 Contextual Search Results:\n"
            for result in results:
                response += f"Type: {result['node_types']}\n"
                response += f"Name: {result.get('name', 'N/A')}\n"
                response += f"Description: {result.get('description', 'No description')}\n\n"
            
            return response
        
        except Exception as e:
            self.logger.error(f"Contextual search error: {e}")
            return f"🤖 Search encountered an issue: {str(e)}"

    def interactive_chat(self):
        """Simple interactive chat interface"""
        print("🎓 Academic Knowledge Assistant")
        print("Type 'exit' to quit")
        
        while True:
            query = input("\nYou: ").strip()
            
            if query.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
            
            # Combine advanced graph query and contextual search
            graph_result = self.advanced_knowledge_graph_query(query)
            contextual_result = self.contextual_search(query)
            
            print("\n🤖 Assistant:")
            print("Detailed Course Information:")
            print(graph_result)
            print("\nContextual Search Results:")
            print(contextual_result)

def main():
    try:
        assistant = AcademicRAGAssistant(debug_mode=True)
        assistant.interactive_chat()
    except Exception as e:
        print(f"Failed to start Academic Assistant: {e}")

if __name__ == "__main__":
    main()