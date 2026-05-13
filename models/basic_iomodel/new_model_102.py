from langchain_ollama.llms import OllamaLLM
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.schema import StrOutputParser
from langchain_community.chat_message_histories import Neo4jChatMessageHistory
from langchain_community.graphs import Neo4jGraph
from langchain_community.vectorstores import Neo4jVector
from langchain_huggingface import HuggingFaceEmbeddings
from uuid import uuid4
from typing import Dict, Any
import logging

class AcademicGraphRAG:
    def __init__(self):
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.SESSION_ID = str(uuid4())
        self.logger.info(f"Initializing session: {self.SESSION_ID}")
        
        # Initialize LLM
        self.llm = OllamaLLM(model="codellama")
        
        # Neo4j configuration
        self.neo4j_config = {
            "url": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "Mento@2152",
        }
        
        # Initialize components
        self._init_graph()
        self._init_embeddings()
        self._init_vector_store()
        self._init_chat_components()

    def _init_graph(self):
        """Initialize Neo4j graph connection"""
        try:
            self.graph = Neo4jGraph(**self.neo4j_config)
            self.graph.refresh_schema()
            self.logger.info("Neo4j graph connection established")
        except Exception as e:
            self.logger.error(f"Failed to initialize Neo4j graph: {e}")
            raise

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
                text_node_properties=["name", "description"],  # Update to match Neo4j schema
                embedding_node_property="embeddings",
            )
            self.logger.info("Vector store initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize vector store: {e}")
            self.vector_store = None

    def _init_chat_components(self):
        """Initialize chat components including prompt and tools"""
        # Enhanced system prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are an intelligent academic advisor with access to a knowledge graph and vector embeddings.
            Use the following tools to provide comprehensive answers:
            1. Graph database queries for course and program information
            2. Semantic vector search for related content
            
            Combine information from both sources to provide detailed, accurate responses.
            Always explain your reasoning and cite the source of information.
            """),
            ("human", "{input}")
        ])

        # Enhanced Neo4j query tool
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

        # Initialize agent
        agent_prompt = hub.pull("hwchase17/react-chat")
        agent = create_react_agent(self.llm, self.tools, agent_prompt)
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )

    def _enhanced_graph_query(self, query: str) -> str:
        """Enhanced graph query with relationship traversal"""
        try:
            # Complex Cypher query that explores relationships
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
            LIMIT 5
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
                k=3
            )
            
            if not results:
                return "No semantically similar content found."
                
            response = ["🔍 Semantic Search Results:"]
            for doc, score in results:
                relevance = (1 - score) * 100  # Convert distance to similarity percentage
                response.append(
                    f"Relevance: {relevance:.1f}%\n"
                    f"Content: {doc.page_content}\n"
                )
                
            return "\n".join(response)
            
        except Exception as e:
            self.logger.error(f"Semantic search error: {e}")
            return f"Error performing semantic search: {str(e)}"

    def process_query(self, user_input: str) -> Dict[str, Any]:
        """Process a user query and return structured response"""
        try:
            # Combine graph and semantic search results
            graph_results = self._enhanced_graph_query(user_input)
            semantic_results = self._semantic_search(user_input)
            
            # Use the agent to synthesize information
            agent_response = self.agent_executor.invoke({
                "input": user_input,
                "context": f"Graph Results:\n{graph_results}\n\nSemantic Results:\n{semantic_results}"
            })
            
            return {
                "success": True,
                "response": agent_response["output"],
                "graph_results": graph_results,
                "semantic_results": semantic_results
            }
            
        except Exception as e:
            self.logger.error(f"Query processing error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    

    def invoke(self, input_data: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, str]:
        """
        API-compatible invoke method for processing queries
        
        Args:
            input_data (Dict[str, Any]): Dictionary containing 'input' key with user query
            config (Dict[str, Any], optional): Additional configuration options
            
        Returns:
            Dict[str, str]: Dictionary containing 'output' key with response
        """
        try:
            user_input = input_data.get("input", "")
            self.logger.info(f"Processing input: {user_input}")
            
            # Use process_query to get comprehensive results
            results = self.process_query(user_input)
            
            if results["success"]:
                # Combine all results into a formatted response
                formatted_response = (
                    f"Combined Response:\n{results['response']}\n\n"
                    f"Knowledge Graph Results:\n{results['graph_results']}\n\n"
                    f"Semantic Search Results:\n{results['semantic_results']}"
                )
                
                return {"output": formatted_response}
            else:
                return {"output": f"Error processing query: {results['error']}"}
                
        except Exception as e:
            self.logger.error(f"Error in invoke method: {e}")
            return {"output": f"An error occurred: {str(e)}"}

    def chat(self):
        """Interactive chat interface"""
        print("🎓 Welcome to the Academic Advisor! Ask me about courses and programs.")
        print("Type 'exit' to end the conversation.\n")
        
        while True:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                print("\nThank you for using the Academic Advisor. Goodbye! 👋")
                break
                
            # Use invoke method for consistency
            result = self.invoke({"input": user_input})
            print("\n🤖 Advisor:", result["output"], "\n")

# Example usage
if __name__ == "__main__":
    advisor = AcademicGraphRAG()
    
    # Example of using invoke method
    # result = advisor.invoke({"input": "Tell me about computer science courses"})
    # print(result["output"])
    
    # Or use interactive chat
    advisor.chat()