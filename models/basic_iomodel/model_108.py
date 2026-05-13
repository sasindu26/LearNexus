import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from langchain_ollama.llms import OllamaLLM
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain import hub
from langchain.memory import ConversationBufferMemory
from langchain_community.graphs import Neo4jGraph
from langchain_community.vectorstores import Neo4jVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks.manager import CallbackManager
from uuid import uuid4
from typing import Dict, Any, Optional, List
import json
import os

class DebugLogger:
    def __init__(self, name: str):
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Set up logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler with INFO level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_format)
        
        # File handler with DEBUG level and rotation
        file_handler = RotatingFileHandler(
            f'logs/academic_rag_{datetime.now().strftime("%Y%m%d")}.log',
            maxBytes=10485760,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        
        # Add handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

class DebugCallback(BaseCallbackHandler):
    """Custom callback handler for debugging"""
    def __init__(self, logger):
        self.logger = logger
        
    def on_llm_start(self, serialized, prompts, **kwargs):
        """Called when LLM starts running"""
        self.logger.debug(f"LLM Start - Prompts: {prompts}")
        
    def on_llm_end(self, response, **kwargs):
        """Called when LLM ends running"""
        self.logger.debug(f"LLM End - Response: {response}")
        
    def on_llm_error(self, error, **kwargs):
        """Called when LLM errors"""
        self.logger.error(f"LLM Error: {error}")
        
    def on_tool_start(self, serialized, input_str, **kwargs):
        """Called when tool starts running"""
        self.logger.debug(f"Tool Start - Input: {input_str}")
        
    def on_tool_end(self, output, **kwargs):
        """Called when tool ends running"""
        self.logger.debug(f"Tool End - Output: {output}")
        
    def on_chain_start(self, serialized, inputs, **kwargs):
        """Called when chain starts running"""
        self.logger.debug(f"Chain Start - Inputs: {inputs}")
        
    def on_chain_end(self, outputs, **kwargs):
        """Called when chain ends running"""
        self.logger.debug(f"Chain End - Outputs: {outputs}")


class AcademicGraphRAG:

    def __init__(self, debug_mode: bool = True):
        self.debug_mode = debug_mode
        self.logger = DebugLogger(__name__).logger
        
        self.SESSION_ID = str(uuid4())
        self.logger.info(f"Initializing session: {self.SESSION_ID}")
        
        # Initialize components with error handling
        self._init_base_components()
        self._verify_neo4j_connection()
        self._init_chat_components()
    

    def _semantic_search(self, query: str) -> str:
        """Enhanced semantic search with relevance scoring"""
        if not self.vector_store:
            return "Vector search is currently unavailable."
            
        try:
            results = self.vector_store.similarity_search_with_score(
                query,
                k=1
            )
            
            if not results:
                return "No semantically similar content found."
                
            response = ["🔍 Semantic Search Results:"]
            for doc, score in results:
                relevance = (1 - score) * 100
                response.append(
                    f"Relevance: {relevance:.1f}%\n"
                    f"Content: {doc.page_content}\n"
                )
                
            return "\n".join(response)
        
        except Exception as e:
            self.logger.error(f"Semantic search error: {e}")
            return f"Error performing semantic search: {str(e)}"

    def _init_chat_components(self):
        """Initialize chat components including prompt and tools"""
        try:
            # Initialize tools
            self.tools = [
                Tool(
                    name="graph_query",
                    description="Query the academic knowledge graph for courses, prerequisites, and relationships",
                    func=self._enhanced_graph_query
                ),
                Tool(
                    name="semantic_search",
                    description="Search for semantically similar content using vector embeddings",
                    func=self._semantic_search
                )
            ]

            # Get the react prompt from hub
            prompt = hub.pull("hwchase17/react")

            # Initialize agent with memory
            agent = create_react_agent(
                llm=self.llm,
                tools=self.tools,
                prompt=prompt
            )
            
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                memory=self.memory,
                verbose=self.debug_mode,
                handle_parsing_errors=True
            )
            
            self.logger.info("Chat components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize chat components: {e}", exc_info=True)
            raise

    def _init_base_components(self):
        """Initialize base components with enhanced error handling"""
        try:

            self.llm = OllamaLLM(
                model="mistral:7b",
                temperature=0.7,
           )
            
            self.neo4j_config = {
                "url": "bolt://localhost:7687",
                "username": "neo4j",
                "password": "Mento@2152",
                "database": "neo4j"
            }
            
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key="output"
            )
            
            self.logger.info("Base components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize base components: {e}", exc_info=True)
            raise
    def _verify_neo4j_connection(self):
        """Verify Neo4j connection and database state"""
        try:
            test_graph = Neo4jGraph(**self.neo4j_config)
            # Test basic query
            result = test_graph.query("MATCH (n) RETURN count(n) as count")
            node_count = result[0]['count']
            self.logger.info(f"Connected to Neo4j database. Total nodes: {node_count}")
            
            # Check for specific node types
            schema = test_graph.query("""
                CALL db.schema.visualization()
                YIELD nodes, relationships
                RETURN nodes, relationships
            """)
            self.logger.debug(f"Database schema: {json.dumps(schema, indent=2)}")
            
        except Exception as e:
            self.logger.error(f"Neo4j connection test failed: {e}", exc_info=True)
            raise ConnectionError(f"Cannot connect to Neo4j: {str(e)}")
    
    def invoke(self, input_data: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, str]:
        """Process a query and return a response"""
        try:
            user_input = input_data.get("input", "")
            self.logger.info(f"Processing input: {user_input}")
            
            # Check for interest-based queries
            interest_keywords = [
                "interested in", "want to learn", "love to do", 
                "passionate about", "curious about"
            ]
            
            is_interest_query = any(keyword in user_input.lower() for keyword in interest_keywords)
            
            # Determine which tool to use based on query type
            if is_interest_query:
                # Use interest-based guidance directly
                response_text = self._interest_based_guidance(user_input)
            else:
                # Use agent executor for other types of queries
                agent_response = self.agent_executor.invoke(
                    {"input": user_input}
                )
                response_text = agent_response.get("output", "I couldn't find a relevant response.")
            
            return {"output": response_text}
            
        except Exception as e:
            self.logger.error(f"Error in invoke method: {e}")
            return {"output": f"An error occurred: {str(e)}"}

    def chat(self):
        """Interactive chat interface with enhanced guidance"""
        print("🎓 Welcome to the Intelligent Academic Advisor!")
        print("I can help you explore courses, find learning paths, and provide personalized recommendations.")
        print("Type 'exit' to end the conversation.\n")
        
        while True:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                print("\nThank you for using the Intelligent Academic Advisor. Goodbye! 👋")
                break
            
            result = self.invoke({"input": user_input})
            print("\n🤖 Advisor:", result["output"], "\n")


    def _enhanced_graph_query(self, query: str) -> str:
        """
        Enhanced graph query with comprehensive knowledge traversal
        Supports multiple query types:
        1. Course exploration
        2. Interest-based guidance
        3. Module and topic discovery
        4. Resource recommendations
        """
        try:
            # Comprehensive query to explore multiple dimensions
            comprehensive_query = """
            // Detect user's intent using fuzzy matching and semantic search
            WITH $query AS input_query
            
            // Search across multiple node types
            CALL {
                // Course search
                MATCH (c:Course)
                WHERE 
                    toLower(c.name) CONTAINS toLower(input_query) OR 
                    toLower(c.description) CONTAINS toLower(input_query)
                RETURN 
                    'Course' AS type, 
                    c.name AS name, 
                    c.description AS description,
                    [] AS related_items
                
                UNION
                
                // Module search
                MATCH (m:Module)
                WHERE 
                    toLower(m.name) CONTAINS toLower(input_query) OR 
                    toLower(m.description) CONTAINS toLower(input_query)
                WITH m
                OPTIONAL MATCH (m)<-[:HAS_MODULE]-(c:Course)
                OPTIONAL MATCH (m)-[:HAS_TOPIC]->(t:Topic)
                OPTIONAL MATCH (m)-[:HAS_RESOURCE]->(r:Resource)
                RETURN 
                    'Module' AS type, 
                    m.name AS name, 
                    m.description AS description,
                    COLLECT(DISTINCT c.name) + 
                    COLLECT(DISTINCT t.name) + 
                    COLLECT(DISTINCT r.name) AS related_items
                
                UNION
                
                // Topic search
                MATCH (t:Topic)
                WHERE 
                    toLower(t.name) CONTAINS toLower(input_query) OR 
                    toLower(t.description) CONTAINS toLower(input_query)
                WITH t
                OPTIONAL MATCH (t)<-[:HAS_TOPIC]-(m:Module)
                OPTIONAL MATCH (t)-[:HAS_RESOURCE]->(r:Resource)
                RETURN 
                    'Topic' AS type, 
                    t.name AS name, 
                    t.description AS description,
                    COLLECT(DISTINCT m.name) + 
                    COLLECT(DISTINCT r.name) AS related_items
                
                UNION
                
                // Resource search
                MATCH (r:Resource)
                WHERE 
                    toLower(r.name) CONTAINS toLower(input_query) OR 
                    toLower(r.description) CONTAINS toLower(input_query)
                WITH r
                OPTIONAL MATCH (r)<-[:HAS_RESOURCE]-(m:Module)
                OPTIONAL MATCH (r)<-[:HAS_RESOURCE]-(t:Topic)
                RETURN 
                    'Resource' AS type, 
                    r.name AS name, 
                    r.description AS description,
                    COLLECT(DISTINCT m.name) + 
                    COLLECT(DISTINCT t.name) AS related_items
            }
            
            RETURN 
                type, 
                name, 
                description, 
                related_items
            LIMIT 5
            """
            
            # Execute the comprehensive query
            results = self.graph.query(comprehensive_query, {"query": query})
            
            if not results:
                return "No relevant information found in the knowledge graph."
            
            # Format response with rich context
            response = ["🔍 Knowledge Graph Insights:"]
            for record in results:
                entry = f"📚 {record['type']}: {record['name']}\n"
                
                # Add description if available
                if record['description']:
                    entry += f"Description: {record['description']}\n"
                
                # Add related items
                if record['related_items']:
                    entry += "Related Connections:\n"
                    for item in set(record['related_items']):
                        entry += f"- {item}\n"
                
                response.append(entry)
            
            return "\n".join(response)
        
        except Exception as e:
            self.logger.error(f"Comprehensive graph query error: {e}")
            return f"Error querying the knowledge graph: {str(e)}"

    def _interest_based_guidance(self, user_interests: str) -> str:
        """
        Provide personalized course and module recommendations 
        based on user's expressed interests
        """
        try:
            interest_query = """
            WITH $interests AS user_interests
            
            // Find relevant courses, modules, and topics
            MATCH (c:Course)-[:HAS_MODULE]->(m:Module)-[:HAS_TOPIC]->(t:Topic)
            WHERE 
                toLower(t.name) CONTAINS toLower(user_interests) OR
                toLower(m.name) CONTAINS toLower(user_interests) OR
                toLower(c.name) CONTAINS toLower(user_interests)
            
            WITH c, m, t, 
                 size([x IN SPLIT(user_interests, ' ') 
                       WHERE toLower(t.name) CONTAINS toLower(x)]) AS topic_match,
                 size([x IN SPLIT(user_interests, ' ') 
                       WHERE toLower(m.name) CONTAINS toLower(x)]) AS module_match
            
            // Order by relevance
            ORDER BY topic_match + module_match DESC
            
            RETURN DISTINCT
                c.name AS course_name,
                COLLECT(DISTINCT m.name) AS modules,
                COLLECT(DISTINCT t.name) AS topics
            LIMIT 3
            """
            
            results = self.graph.query(interest_query, {"interests": user_interests})
            
            if not results:
                return "🤔 I couldn't find courses matching your interests directly. Consider broadening your search."
            
            response = ["🌟 Personalized Learning Paths:"]
            for record in results:
                entry = f"📘 Course: {record['course_name']}\n"
                
                if record['modules']:
                    entry += "Relevant Modules:\n"
                    for module in record['modules']:
                        entry += f"- {module}\n"
                
                if record['topics']:
                    entry += "Covered Topics:\n"
                    for topic in record['topics']:
                        entry += f"- {topic}\n"
                
                response.append(entry)
            
            response.append("\n💡 Tip: These recommendations are based on your expressed interests.")
            return "\n".join(response)
        
        except Exception as e:
            self.logger.error(f"Interest-based guidance error: {e}")
            return f"Error generating personalized recommendations: {str(e)}"

    def _init_chat_components(self):
        """Initialize chat components with enhanced tools"""
        try:
            # Initialize tools with new methods
            self.tools = [
                Tool(
                    name="graph_query",
                    description="Comprehensive query of academic knowledge graph covering courses, modules, topics, and resources",
                    func=self._enhanced_graph_query
                ),
                Tool(
                    name="semantic_search",
                    description="Search for semantically similar content using vector embeddings",
                    func=self._semantic_search
                ),
                Tool(
                    name="interest_guidance",
                    description="Generate personalized learning recommendations based on user interests",
                    func=self._interest_based_guidance
                )
            ]

            # Rest of the initialization remains the same
            prompt = hub.pull("hwchase17/react")
            agent = create_react_agent(
                llm=self.llm,
                tools=self.tools,
                prompt=prompt
            )
            
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                memory=self.memory,
                verbose=self.debug_mode,
                handle_parsing_errors=True
            )
            
            self.logger.info("Enhanced chat components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize chat components: {e}", exc_info=True)
            raise

    def chat(self):
        """Interactive chat interface with enhanced guidance"""
        print("🎓 Welcome to the Intelligent Academic Advisor!")
        print("I can help you explore courses, find learning paths, and provide personalized recommendations.")
        print("Type 'exit' to end the conversation.\n")
        
        while True:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                print("\nThank you for using the Intelligent Academic Advisor. Goodbye! 👋")
                break
            
            # Check for interest-based queries
            interest_keywords = [
                "interested in", "want to learn", "love to do", 
                "passionate about", "curious about"
            ]
            
            is_interest_query = any(keyword in user_input.lower() for keyword in interest_keywords)
            
            if is_interest_query:
                # Use interest-based guidance
                result = self.invoke({"input": f"Find learning paths for {user_input}"})
            else:
                result = self.invoke({"input": user_input})
            
            print("\n🤖 Advisor:", result["output"], "\n")


if __name__ == "__main__":
    try:
        advisor = AcademicGraphRAG()
        advisor.chat()
    except Exception as e:
        print(f"Failed to start Academic Advisor: {e}")
        logging.error("Startup failed", exc_info=True)# Rest of the code remains the same