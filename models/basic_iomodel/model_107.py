from llm import llm
from graph import graph  # Your Neo4j graph driver
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from langchain.tools import Tool
from langchain_community.chat_message_histories import Neo4jChatMessageHistory
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.runnables.history import RunnableWithMessageHistory
from utils import get_session_id  # Utility function for unique session management
from tools.vector import search_vector_store  # Replace with your vector search logic

# Define Chat Prompt
chat_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are an educational advisor with expertise in IT and Data Science."),
        ("human", "{input}"),
    ]
)

# Combine the Chat Prompt with the LLM and Output Parser
mento_chat = chat_prompt | llm | StrOutputParser()

# Define the Tools
tools = [
    Tool.from_function(
        name="General Chat",
        description="Answer general questions about IT education, courses, and career guidance.",
        func=mento_chat.invoke,
    ),
    Tool.from_function(
        name="Vector Search",
        description="Retrieve information from the database using semantic search.",
        func=search_vector_store,  # Your implementation for vector search
    )
]

# Define Memory for Neo4j-Powered Chat History
def get_memory(session_id):
    return Neo4jChatMessageHistory(session_id=session_id, graph=graph)

# Create the Agent's Prompt Template
agent_prompt = PromptTemplate.from_template("""
You are an educational advisor specializing in IT and Data Science.
Be as helpful as possible and return information specific to the user query.
You are connected to a database and tools to provide accurate responses.

TOOLS:
------

You have access to the following tools:

{tools}

To use a tool, please use the following format:

Thought: Do I need to use a tool? Yes Action: the action to take, should be one of [{tool_names}] Action Input: the input to the action Observation: the result of the action


When you have a response to say to the user, or if you do not need to use a tool, you MUST use the format:

Thought: Do I need to use a tool? No Final Answer: [your response here]


Begin!

Previous conversation history:
{chat_history}

New input: {input}
{agent_scratchpad}
""")

# Create the React Agent
agent = create_react_agent(llm, tools, agent_prompt)

# Define the Agent Executor
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True
)

# Integrate with Message History
chat_agent = RunnableWithMessageHistory(
    agent_executor,
    get_memory,
    input_messages_key="input",
    history_messages_key="chat_history",
)

# Generate Responses
def generate_response(user_input):
    """
    Process user input through the conversational agent
    and return the response.
    """
    response = chat_agent.invoke(
        {"input": user_input},
        {"configurable": {"session_id": get_session_id()}},
    )
    return response['output']

# Example Test
if __name__ == "__main__":
    print("MENTO Chatbot: Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Chatbot: Goodbye!")
            break
        try:
            output = generate_response(user_input)
            print(f"Chatbot: {output}")
        except Exception as e:
            print(f"Error: {e}")