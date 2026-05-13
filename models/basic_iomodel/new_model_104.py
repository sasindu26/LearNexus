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

class AcademicGraphRAG:
    def __init__(self, debug_mode: bool = True):
        self.debug_mode = debug_mode
        self.logger = DebugLogger(__name__).logger
        
        self.SESSION_ID = str(uuid4())
        self.logger.info(f"Initializing session: {self.SESSION_ID}")
        
        # Initialize components with error handling
        self._init_base_components()
        self._verify_neo4j_connection()
        self._init_graph()
        self._init_embeddings()
        self._init_vector_store()
        self._init_chat_components()

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
            self.logger.error(f"Neo4j connection test failed: {e}")
            raise ConnectionError(f"Cannot connect to Neo4j: {str(e)}")
        
    def _init_embeddings(self):
        """Initialize embedding model"""
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            self.logger.info("Embeddings model initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize embeddings: {e}")
            raise


    def _init_chat_components(self):
        """Initialize chat components including prompt and tools"""
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
            verbose=True,
            handle_parsing_errors=True
        )
    def _init_vector_store(self):
        """Initialize Neo4j vector store"""
        try:
            self.vector_store = Neo4jVector.from_existing_graph(
                embedding=self.embeddings,
                url=self.neo4j_url,
                username=self.username,
                password=self.password,
                index_name="course_embeddings",
                node_label="Course",  # Update this to your use case
                )
            self.logger.info("Vector store initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize vector store: {e}")
            self.vector_store = None


    def _init_graph(self):
        """Initialize Neo4j graph connection"""
        try:
            self.graph = Neo4jGraph(**self.neo4j_config)
            self.graph.refresh_schema()
            self.logger.info("Neo4j graph connection established")
        except Exception as e:
            self.logger.error(f"Failed to initialize Neo4j graph: {e}")
            raise

    def _init_base_components(self):
        """Initialize base components with enhanced error handling"""
        try:
            self.llm = OllamaLLM(
                model="mistral:7b",
                temperature=0.7,
                top_p=0.9,
            )
            
            self.neo4j_config = {
                "url": "bolt://localhost:7687",
                "username": "neo4j",
                "password": "Mento@2152",
                "database": "neo4j"  # Specify default database
            }
            
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key="output"
            )
            
            self.logger.info("Base components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize base components: {e}")
            raise

    def _create_callback_manager(self):
        """Create callback manager for LLM debugging"""
        from langchain.callbacks import CallbackManager
        from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
        
        class DebugCallback(StreamingStdOutCallbackHandler):
            def __init__(self, logger):
                super().__init__()
                self.logger = logger
                
            def on_llm_start(self, serialized, prompts, **kwargs):
                self.logger.debug(f"LLM Start - Prompts: {prompts}")
                
            def on_llm_end(self, response, **kwargs):
                self.logger.debug(f"LLM End - Response: {response}")
                
            def on_llm_error(self, error, **kwargs):
                self.logger.error(f"LLM Error: {error}")
        
        return CallbackManager([DebugCallback(self.logger)])

    def _enhanced_graph_query(self, query: str) -> str:
        """Enhanced graph query with better error handling and debugging"""
        self.logger.debug(f"Executing graph query: {query}")
        
        try:
            # First, try to extract specific course names or topics
            extract_query = """
            MATCH (c:Course)
            WHERE toLower(c.name) CONTAINS toLower($query) 
               OR toLower(c.description) CONTAINS toLower($query)
            WITH c
            OPTIONAL MATCH (prereq)-[:PREREQUISITE_FOR]->(c)
            OPTIONAL MATCH (c)-[:PREREQUISITE_FOR]->(next)
            OPTIONAL MATCH (c)-[:PART_OF]->(program)
            RETURN 
                c.name AS course_name,
                c.description AS description,
                collect(DISTINCT prereq.name) AS prerequisites,
                collect(DISTINCT next.name) AS next_courses,
                collect(DISTINCT program.name) AS programs
            LIMIT 5
            """
            
            result = self.graph.query(extract_query, {"query": query})
            self.logger.debug(f"Query result: {json.dumps(result, indent=2)}")
            
            if not result:
                self.logger.info("No direct matches found, trying semantic search")
                return self._semantic_search(query)
            
            response = []
            for record in result:
                course_info = [f"📚 Course: {record['course_name']}"]
                
                if record['description']:
                    course_info.append(f"Description: {record['description']}")
                
                if record['prerequisites']:
                    course_info.append("Prerequisites: " + ", ".join(record['prerequisites']))
                
                if record['next_courses']:
                    course_info.append("Leads to: " + ", ".join(record['next_courses']))
                
                if record['programs']:
                    course_info.append("Part of programs: " + ", ".join(record['programs']))
                
                response.append("\n".join(course_info))
            
            return "\n\n".join(response)
            
        except Exception as e:
            self.logger.error(f"Graph query error: {e}", exc_info=True)
            return f"Error querying the knowledge graph: {str(e)}"

    def _semantic_search(self, query: str) -> str:
        """Enhanced semantic search with better error handling"""
        self.logger.debug(f"Executing semantic search: {query}")
        
        if not self.vector_store:
            self.logger.warning("Vector store not initialized")
            return "Vector search is currently unavailable."
            
        try:
            results = self.vector_store.similarity_search_with_score(
                query,
                k=5,
                fetch_k=20  # Fetch more candidates for better results
            )
            
            if not results:
                return "No semantically similar content found."
                
            response = ["🔍 Most Relevant Results:"]
            for doc, score in results:
                relevance = (1 - score) * 100  # Convert distance to similarity
                if relevance < 50:  # Filter low-relevance results
                    continue
                    
                response.append(
                    f"Relevance: {relevance:.1f}%\n"
                    f"Content: {doc.page_content}\n"
                )
                
            return "\n".join(response) if len(response) > 1 else "No highly relevant results found."
            
        except Exception as e:
            self.logger.error(f"Semantic search error: {e}", exc_info=True)
            return f"Error performing semantic search: {str(e)}"

    def invoke(self, input_data: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, str]:
        """Process a query with enhanced debugging"""
        try:
            user_input = input_data.get("input", "")
            self.logger.info(f"Processing input: {user_input}")
            
            # Log conversation history
            if self.debug_mode:
                history = self.memory.load_memory_variables({})
                self.logger.debug(f"Current conversation history: {history}")
            
            # Use agent executor to process the query
            response = self.agent_executor.invoke(
                {
                    "input": user_input,
                    "chat_history": self.memory.chat_memory.messages
                }
            )
            
            self.logger.debug(f"Agent response: {response}")
            
            return {"output": response["output"]}
            
        except Exception as e:
            self.logger.error(f"Error in invoke method: {e}", exc_info=True)
            return {
                "output": "I encountered an error processing your request. "
                         "Please try rephrasing your question or contact support if the issue persists."
            }

    def chat(self):
        """Interactive chat interface with debug options"""
        print("🎓 Welcome to the Academic Advisor! Ask me about courses and programs.")
        print("Type 'exit' to end the conversation.")
        print("Type 'debug on/off' to toggle debug mode.\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print("\nThank you for using the Academic Advisor. Goodbye! 👋")
                    break
                    
                if user_input.lower() == 'debug on':
                    self.debug_mode = True
                    print("Debug mode enabled.")
                    continue
                    
                if user_input.lower() == 'debug off':
                    self.debug_mode = False
                    print("Debug mode disabled.")
                    continue
                
                result = self.invoke({"input": user_input})
                print("\n🤖 Advisor:", result["output"], "\n")
                
            except KeyboardInterrupt:
                print("\nExiting gracefully...")
                break
            except Exception as e:
                self.logger.error(f"Chat interface error: {e}", exc_info=True)
                print("\n❌ An error occurred. Please try again.")

if __name__ == "__main__":
    try:
        advisor = AcademicGraphRAG(debug_mode=True)
        advisor.chat()
    except Exception as e:
        print(f"Failed to start Academic Advisor: {e}")
        logging.error("Startup failed", exc_info=True)