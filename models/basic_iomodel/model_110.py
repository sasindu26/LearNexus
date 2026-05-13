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
        self._init_graph()
        self._init_embeddings()
        self._init_vector_store()
        self._init_chat_components()

    def _create_callback_manager(self):
        """Create callback manager with debug callbacks"""
        callbacks = [DebugCallback(self.logger)] if self.debug_mode else []
        return CallbackManager(callbacks)

    def _init_base_components(self):
        """Initialize base components with enhanced error handling"""
        try:
            callback_manager = self._create_callback_manager()
            
            self.llm = OllamaLLM(
                model="mistral:7b",
                temperature=0.7,
                callbacks=callback_manager.handlers if self.debug_mode else None
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

    # [Previous methods remain the same]
    
    def _init_graph(self):
        """Initialize Neo4j graph connection"""
        try:
            self.graph = Neo4jGraph(**self.neo4j_config)
            self.graph.refresh_schema()
            self.logger.info("Neo4j graph connection established")
        except Exception as e:
            self.logger.error(f"Failed to initialize Neo4j graph: {e}", exc_info=True)
            raise

    def _init_embeddings(self):
        """Initialize embedding model"""
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            self.logger.info("Embeddings model initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize embeddings: {e}", exc_info=True)
            raise

    def _init_vector_store(self):
        """Initialize Neo4j vector store"""
        try:
            self.vector_store = Neo4jVector.from_existing_graph(
                embedding=self.embeddings,
                **self.neo4j_config,
                index_name="course_embeddings",
                node_label="Course",
                text_node_properties=["name", "description"],
                embedding_node_property="embeddings",
            )
            self.logger.info("Vector store initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize vector store: {e}", exc_info=True)
            self.vector_store = None

    def _enhanced_graph_query(self, query: str) -> str:
        """Enhanced graph query with relationship traversal"""
        try:
            cypher_query = """
            MATCH (c:Course)
            WHERE c.name CONTAINS $query OR c.description CONTAINS $query
            OPTIONAL MATCH (c)-[r]->(related)
            RETURN 
                c.name AS course_name,
                c.description AS description,
                COLLECT(DISTINCT {
                    type: type(r),
                    related_name: related.name
                }) AS relationships
            LIMIT 10
            """
            
            result = self.graph.query(cypher_query, {"query": query})
            
            if not result:
                return "No relevant information found in the knowledge graph."
                
            response = []
            for record in result:
                course_info = f"📚 {record['course_name']}\n"
                course_info += f"Description: {record.get('description', 'No description available')}\n"
                
                if record['relationships']:
                    course_info += "Related items:\n"
                    for rel in record['relationships']:
                        if rel['related_name']:
                            course_info += f"- {rel['type']}: {rel['related_name']}\n"
                            
                response.append(course_info)
                
            return "\n".join(response)
            
        except Exception as e:
            self.logger.error(f"Graph query error: {e}")
            return f"Error querying the knowledge graph: {str(e)}"
        
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

    def invoke(self, input_data: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, str]:
        """Process a query and return a response"""
        try:
            user_input = input_data.get("input", "")
            self.logger.info(f"Processing input: {user_input}")
            
            # Use agent executor to process the query
            response = self.agent_executor.invoke(
                {"input": user_input}
            )
            
            return {"output": response["output"]}
            
        except Exception as e:
            self.logger.error(f"Error in invoke method: {e}")
            return {"output": f"An error occurred: {str(e)}"}



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

    def chat(self):
        """Interactive chat interface"""
        print("🎓 Welcome to the Academic Advisor! Ask me about courses and programs.")
        print("Type 'exit' to end the conversation.\n")
        
        while True:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                print("\nThank you for using the Academic Advisor. Goodbye! 👋")
                break
                
            result = self.invoke({"input": user_input})
            print("\n🤖 Advisor:", result["output"], "\n")
 # [Rest of the methods remain the same]

if __name__ == "__main__":
    try:
        advisor = AcademicGraphRAG(debug_mode=True)
        advisor.chat()
    except Exception as e:
        print(f"Failed to start Academic Advisor: {e}")
        logging.error("Startup failed", exc_info=True)