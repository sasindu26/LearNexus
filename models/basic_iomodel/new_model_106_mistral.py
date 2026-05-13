from mistralai import Mistral
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain import hub
from langchain.memory import ConversationBufferMemory
from langchain_community.graphs import Neo4jGraph
from langchain_community.vectorstores import Neo4jVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.schema import LLMResult
from typing import Dict, Any, List, Optional, Union, Mapping
from pydantic import BaseModel, Field
from uuid import uuid4
import logging
import os
from dotenv import load_dotenv



class MistralLLM(LLM, BaseModel):
    """Custom LLM class to integrate Mistral AI with LangChain"""
    client: Mistral = Field(exclude=True)
    model_name: str = "mistral-large-latest"
    
    def __init__(self, api_key: str, model: str = "mistral-large-latest"):
        super().__init__(model_name=model)
        self.client = Mistral(api_key=api_key)

    def _call(
        self, 
        prompt: str, 
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Execute the chat completion"""
        messages = [{"role": "user", "content": prompt}]
        response = self.client.chat(
            model=self.model_name,
            messages=messages,
        )
        return response.choices[0].message.content

    @property
    def _llm_type(self) -> str:
        return "mistral"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        return {"model_name": self.model_name}

class AcademicGraphRAG:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Load environment variables from .env file
        load_dotenv()
        
        self.SESSION_ID = str(uuid4())
        self.logger.info(f"Initializing session: {self.SESSION_ID}")
        
        # Initialize components
        self._init_base_components()
        self._init_graph()
        self._init_embeddings()
        self._init_vector_store()
        self._init_chat_components()

    def _init_base_components(self):
        """Initialize base components like LLM and config"""
        api_key = "Ojl3y0iNWuvtvFwifyHUEkr88IJUzR84"
        
        self.llm = MistralLLM(api_key=api_key)
        self.neo4j_config = {
            "url": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "Mento@2152",
        }
        
        # Initialize conversation memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

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
                **self.neo4j_config,
                index_name="task_embeddings",
                node_label="Task",
                text_node_properties=["name", "description"],
                embedding_node_property="embedding",
            )
            self.logger.info("Vector store initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize vector store: {e}")
            self.vector_store = None

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

if __name__ == "__main__":
    advisor = AcademicGraphRAG()
    advisor.chat()