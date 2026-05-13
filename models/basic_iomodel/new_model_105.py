import os
from mistralai import Mistral
from neo4j import GraphDatabase
from langchain.agents import initialize_agent, Tool
from langchain.memory import ConversationBufferMemory

# Wrapper for Mistral API
class MistralLLMWrapper:
    def __init__(self, client, model):
        self.client = client
        self.model = model

    def __call__(self, prompt):
        response = self.client.chat.complete(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

# Academic Advisor Class
class AcademicGraphRAG:
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.neo4j_driver = self._init_neo4j()
        self.llm = self._init_llm()
        self.agent_executor = self._init_agent()
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

    def _init_neo4j(self):
        """
        Initialize the Neo4j database connection.
        """
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        username = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        return GraphDatabase.driver(uri, auth=(username, password))

    def _init_llm(self):
        """
        Initialize the Mistral API client and wrapper.
        """
        api_key = os.getenv("MISTRAL_API_KEY")
        mistral_client = Mistral(api_key=api_key)
        return MistralLLMWrapper(client=mistral_client, model="mistral-large-latest")

    def _neo4j_query(self, query):
        """
        Execute a query on the Neo4j database.
        """
        try:
            with self.neo4j_driver.session() as session:
                results = session.run(query)
                return [record.data() for record in results]
        except Exception as e:
            return f"Database error: {str(e)}"

    def _search_tool_function(self, query):
        """
        Simulate a search tool for retrieving external information.
        Replace this with actual logic if integrating with external sources.
        """
        return f"Simulated search results for query: {query}"

    def _database_query_tool_function(self, query):
        """
        Execute a query against the Neo4j database and return the results.
        """
        return self._neo4j_query(query)

    def _init_agent(self):
        """
        Initialize the LangChain agent with tools and memory.
        """
        tools = [
            Tool(
                name="DatabaseQuery",
                func=self._database_query_tool_function,
                description="Query the Neo4j database for course/module data."
            ),
            Tool(
                name="Search",
                func=self._search_tool_function,
                description="Retrieve external search results."
            ),
        ]

        return initialize_agent(
            tools=tools,
            llm=self.llm,
            agent="react",
            verbose=self.debug_mode,
        )

    def process_input(self, user_input):
        """
        Process user input through the agent executor.
        """
        try:
            if self.debug_mode:
                print(f"INFO: Processing input: {user_input}")
            response = self.agent_executor.run(user_input)
            return response
        except Exception as e:
            return f"An error occurred: {str(e)}"
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


# Main Execution
if __name__ == "__main__":
    # Enable debug mode for detailed logs
    advisor = AcademicGraphRAG(debug_mode=True)

    print("🤖 Academic Advisor ready!")
    while True:
        user_input = input("You: ")
        if user_input.lower() in {"exit", "quit"}:
            print("Exiting. Goodbye!")
            break
        response = advisor.process_input(user_input)
        print(f"🤖 Advisor: {response}")
