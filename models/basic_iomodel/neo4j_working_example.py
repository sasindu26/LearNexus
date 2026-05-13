from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.schema import StrOutputParser
from langchain_community.chat_message_histories import Neo4jChatMessageHistory
from langchain_community.graphs import Neo4jGraph
from uuid import uuid4
from langchain_ollama.llms import OllamaLLM

# Session setup
SESSION_ID = str(uuid4())
print(f"Session ID: {SESSION_ID}")

llm = OllamaLLM(model="codellama")
# Connect to the Neo4j graph database
graph = Neo4jGraph(
    url="bolt://localhost:7687",
    username="neo4j",
    password="Mento@2152"
)

# Define the prompt for course guidance
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an educational guide specializing in IT and computer science courses. "
            "Provide recommendations based on the student's interests and skills, using the database for accurate suggestions.",
        ),
        ("human", "{input}"),
    ]
)

# Define the chat functionality for course queries
course_chat = prompt | llm | StrOutputParser()

# Memory management for chat history in Neo4j
def get_memory(session_id):
    return Neo4jChatMessageHistory(session_id=session_id, graph=graph)

# Define a function to query the Neo4j graph for course information
def query_course(input):
    query = f"""
    MATCH (course:Course)
    WHERE course.name CONTAINS '{input}'
    RETURN course.name AS name, course.description AS description
    """
    results = graph.run(query).data()
    if not results:
        return "No courses found matching your input."
    return "\n".join(f"{res['name']}: {res['description']}" for res in results)

# Define the tools
tools = [
    Tool.from_function(
        name="Course Chat",
        description="Chat about courses and degrees based on student input. Return a string.",
        func=course_chat.invoke,
    ),
    Tool.from_function(
        name="Course Database Query",
        description="Query the database to find courses matching the input. Return a string with course details.",
        func=query_course,
    ),
]

# Define the REACT agent with the updated tools
agent_prompt = hub.pull("hwchase17/react-chat")
agent = create_react_agent(llm, tools, agent_prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools)

# Combine the agent with a message history handler
chat_agent = RunnableWithMessageHistory(
    agent_executor,
    get_memory,
    input_messages_key="input",
    history_messages_key="chat_history",
)

# Main interaction loop
while True:
    q = input("> ")

    response = chat_agent.invoke(
        {
            "input": q
        },
        {"configurable": {"session_id": SESSION_ID}},
    )
    
    print(response["output"])
