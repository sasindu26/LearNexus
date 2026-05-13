from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory

chat_llm = OllamaLLM(model="codellama")

from langchain_community.chat_message_histories import ChatMessageHistory

memory = ChatMessageHistory()

def get_memory(session_id):
    return memory


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a surfer dude, having a conversation about the surf conditions on the beach. Respond using surfer slang.",
        ),
        ( "system", "{context}" ),
        ( "human", "{question}" ),
    ]
)

chat_chain = prompt | chat_llm | StrOutputParser()

chat_with_message_history = RunnableWithMessageHistory(
    chat_chain,
    get_memory,
    input_messages_key="question",
    history_messages_key="chat_history",
)


chat_chain = prompt | chat_llm | StrOutputParser()

current_weather = """
    {
        "surf": [
            {"beach": "Fistral", "conditions": "6ft waves and offshore winds"},
            {"beach": "Polzeath", "conditions": "Flat and calm"},
            {"beach": "Watergate Bay", "conditions": "3ft waves and onshore winds"}
        ]
    }"""


while True:
    question = input("You: ")
    if question.lower() in ["exit", "quit"]:
        break
    response = chat_chain.invoke(
        {
            "context": current_weather,
            "question": question,
        }
    )
    print(f"Surfer Dude: {response}")

response = chat_chain.invoke(
    {
        "context": current_weather,
        "question": question,
    },
    config={"configurable": {"session_id": "none"}}
)

print(response)