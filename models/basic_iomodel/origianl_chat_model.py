from langchain_ollama.llms import OllamaLLM
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.schema import StrOutputParser
from langchain_community.chat_message_histories import Neo4jChatMessageHistory
from langchain_community.graphs import Neo4jGraph
from uuid import uuid4
from langchain_huggingface import HuggingFaceEmbeddings



class AcademicChatBot:
    def __init__(self):
        # Unique session ID for user interactions
        self.SESSION_ID = str(uuid4())
        print(f"Session ID: {self.SESSION_ID}")
        
        # Initialize LLM
        self.llm = OllamaLLM(model="mistral:7b")
        
        # Initialize Neo4j
        self.graph = Neo4jGraph(
            url="bolt://localhost:7691",
            username="neo4j",
            password="Mento@2152"
        )
        
        # Setup prompt
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a friendly academic advisor. Engage in a conversation and provide suggestions from the database when needed.",
                ),
                ("human", "{input}"),
            ]
        )
        
        # Tool for querying Neo4j
        self.tools = [
            Tool.from_function(
                name="Academic Database Tool",
                description="For retrieving degree or course information and relationships from the database.",
                func=self.query_neo4j,  # Function defined below
            )
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
        Query the database and return user-friendly responses.
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
                response = "I found these courses that might interest you:\n"
                for idx, course_info in enumerate(result, start=1):
                    response += f"{idx}. {course_info['course_name']}: {course_info['course_description']}\n"
                return response + "Let me know if you'd like to hear more about any of these!"
            else:
                return "I couldn't find any relevant courses in the database. Could you clarify or ask about something else?"
        except Exception as e:
            print(f"Database Query Error: {e}")
            return "An error occurred while querying the database. Please try again later."

    def invoke(self, input_data, config=None):
        """
        API-ready method to process user input.
        """
        try:
            user_input = input_data.get("input", "")
            print(f"User input: {user_input}")
            
            # Get response from chat agent
            response = self.chat_agent.invoke(
                {"input": user_input},
                {"configurable": {"session_id": self.SESSION_ID}},
            )
            
            print(f"Response: {response['output']}")
            return {"output": response["output"]}
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
    if len(sys.argv) > 1 and sys.argv[1] == "api":
        print("Chatbot running in API mode. Ready to accept inputs.")
        # For integration with a REST API, keep this instance alive.
        # Use chatbot.invoke() within the API endpoints.
    else:
        chatbot.console_mode()
