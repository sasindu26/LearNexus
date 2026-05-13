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
from langchain.embeddings import OpenAIEmbeddings
from uuid import uuid4
from langchain_huggingface import HuggingFaceEmbeddings

class AcademicChatBot:
    def __init__(self):
        # Unique session ID for user interactions
        self.SESSION_ID = str(uuid4())
        print(f"Session ID: {self.SESSION_ID}")
        
        # Initialize LLM
        self.llm = OllamaLLM(model="mistral")
        
        # Initialize Neo4j database
        self.neo4j_url = "bolt://localhost:7687"
        self.username = "neo4j"
        self.password = "Mento@2152"
        self.graph = Neo4jGraph(
            url=self.neo4j_url,
            username=self.username,
            password=self.password,
        )
        
        # Initialize HuggingFace Embeddings
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

        
        # Create or load Neo4j vector index
        try:
            self.vector_index = Neo4jVector.from_existing_graph(
                embedding=self.embeddings,
                url=self.neo4j_url,
                username=self.username,
                password=self.password,
                index_name="course_embeddings",
                node_label="Course",  # Update this to your use case
                text_node_properties=["name", "description"],  # Update to match Neo4j schema
                embedding_node_property="embeddings",
            )
            print("Neo4j vector index successfully loaded.")
        except Exception as e:
            print(f"Error loading Neo4j vector index: {e}")
            self.vector_index = None
        
        # Refresh Neo4j schema for querying
        self.graph.refresh_schema()
        
        # Setup prompt
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an academic advisor. Use structured knowledge from Neo4j, embeddings, and contextual knowledge to answer queries.",
                ),
                ("human", "{input}"),
            ]
        )
        
        # Tools for Neo4j and embeddings
        self.tools = [
            Tool.from_function(
                name="Academic Database Tool",
                description="Retrieves course details and relationships from the Neo4j database.",
                func=self.query_neo4j,
            ),
            Tool.from_function(
                name="Semantic Vector Search",
                description="Retrieves insights from Neo4j vector embeddings.",
                func=self.semantic_vector_search,
            ),
        ]
        
        # Agent setup
        agent_prompt = hub.pull("hwchase17/react-chat")
        agent = create_react_agent(self.llm, self.tools, agent_prompt)
        self.agent_executor = AgentExecutor(agent=agent, tools=self.tools)
        
        # Chat agent with memory
        self.chat_agent = RunnableWithMessageHistory(
            self.agent_executor,
            self.get_memory,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

    def get_memory(self, session_id):
        """
        Retrieves session-specific chat history.
        """
        return Neo4jChatMessageHistory(session_id=session_id, graph=self.graph)
    
    def query_neo4j(self, user_input):
        """
        Query the Neo4j database and return relevant course details.
        """
        query = f"""
        MATCH (course:Course)
        WHERE course.name CONTAINS '{user_input}'
        RETURN course.name AS course_name, coalesce(course.description, "Description not available") AS course_description
        LIMIT 3
        """
        
        try:
            result = self.graph.query(query)
            if result:
                response = "Here are some courses I found that might interest you:\n"
                for idx, course_info in enumerate(result, start=1):
                    response += f"{idx}. {course_info['course_name']}: {course_info['course_description']}\n"
                return response
            else:
                return "I couldn't find any relevant courses in the database. Could you clarify your query?"
        except Exception as e:
            print(f"Database Query Error: {e}")
            return "An error occurred while querying the database. Please try again later."

    def semantic_vector_search(self, user_input):
        """
        Perform semantic search using Neo4j vector embeddings.
        """
        if not self.vector_index:
            return "Vector embeddings are unavailable."
        
        try:
            # Perform similarity search
            docs = self.vector_index.query(
                user_input,
            )
            if docs:
                response = "Here are some insights I found using vector embeddings:\n"
                for idx, doc in enumerate(docs, start=1):
                    response += f"{idx}. {doc['text']} (Score: {doc['score']:.2f})\n"
                return response
            else:
                return "No relevant insights found using embeddings. Could you rephrase?"
        except Exception as e:
            print(f"Semantic Search Error: {e}")
            return "An error occurred during semantic search. Please try again later."

    def invoke(self, input_data, config=None):
        """
        API-ready method to process user input.
        """
        try:
            user_input = input_data.get("input", "")
            print(f"User input: {user_input}")
            
            # Get responses from Neo4j and vector embeddings
            db_response = self.query_neo4j(user_input)
            vector_response = self.semantic_vector_search(user_input)
            
            # Combine responses
            final_response = (
                f"Database Response:\n{db_response}\n\n"
                f"Vector Embeddings Insights:\n{vector_response}"
            )
            
            print(f"Response: {final_response}")
            return {"output": final_response}
        except Exception as e:
            print(f"Error: {e}")
            return {"output": f"Error: {e}"}

    def console_mode(self):
        """
        Console-based chatbot interaction.
        """
        print("Welcome to the Academic Chatbot! Ask me about degrees, courses, or guidance!")
        while True:
            user_input = input("> ")
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye! Feel free to come back anytime.")
                break
            output = self.invoke({"input": user_input})
            print(output["output"])


# Main entry point
if __name__ == "__main__":
    chatbot = AcademicChatBot()
    
    import sys
