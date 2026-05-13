from langchain_ollama.llms import OllamaLLM
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import Neo4jChatMessageHistory
from langchain_community.graphs import Neo4jGraph
from uuid import uuid4


class AcademicChatBot:
    def __init__(self):
        # Unique session ID for user interactions
        self.SESSION_ID = str(uuid4())
        print(f"Session ID: {self.SESSION_ID}")

        # Initialize LLM (Mistral 7B)
        self.llm = OllamaLLM(model="mistral:7b")

        # Initialize Neo4j connection
        self.graph = Neo4jGraph(
            url="bolt://localhost:7691",  # Replace with your Neo4j URL
            username="neo4j",            # Replace with your Neo4j username
            password="Mento@2152"        # Replace with your Neo4j password
        )

        # Setup system prompt
        self.prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a friendly academic advisor. Use the CourseSearchTool to fetch information from the database. "
                "NEVER invent courses or details. If unsure, say 'I need to check the database.' "
                "Respond conversationally but factually."
            ),
            ("human", "{input}"),
        ])

        # Tool for querying Neo4j
        self.tools = [
            Tool.from_function(
                name="CourseSearchTool",
                description="Use this tool to search for courses, degrees, or academic requirements in the database.",
                func=self.query_neo4j,
            )
        ]

        # Agent setup
        agent_prompt = hub.pull("hwchase17/react-chat")
        agent = create_react_agent(self.llm, self.tools, agent_prompt)
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            handle_parsing_errors=True  # Handle LLM output parsing errors
        )

        # Chat agent with memory
        self.chat_agent = RunnableWithMessageHistory(
            self.agent_executor,
            self.get_memory,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

    def get_memory(self, session_id):
        """
        Retrieves session-specific chat history from Neo4j.
        """
        return Neo4jChatMessageHistory(session_id=session_id, graph=self.graph)

    def query_neo4j(self, user_input):
        """
        Query the Neo4j database for course information.
        """
        # Example query: Search for courses by name or description
        query = f"""
        MATCH (course:Course)
        WHERE toLower(course.name) CONTAINS toLower('{user_input}') OR
              toLower(course.description) CONTAINS toLower('{user_input}')
        RETURN course.name AS course_name, course.description AS course_description
        LIMIT 5
        """

        try:
            result = self.graph.query(query)
            if result:
                response = "Here are some courses that match your query:\n"
                for idx, course_info in enumerate(result, start=1):
                    response += f"{idx}. {course_info['course_name']}: {course_info['course_description']}\n"
                return response
            else:
                return "I couldn't find any courses matching your query. Please try again with different keywords."
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
        print("Welcome to the Academic Chatbot! Ask me about courses, degrees, or academic guidance!")
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