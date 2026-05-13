from langchain_core.runnables.history import RunnableWithMessageHistory

from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser

chat_llm = OllamaLLM(model="codellama")


chat_chain = prompt | chat_llm | StrOutputParser()

chat_with_message_history = RunnableWithMessageHistory(
    chat_chain,
    get_memory,
    input_messages_key="question",
    history_messages_key="chat_history",
)

response = chat_with_message_history.invoke(
    {
        "context": current_weather,
        "question": "Hi, I am at Watergate Bay. What is the surf like?"
    },
    config={"configurable": {"session_id": "none"}}
)
print(response)

response = chat_with_message_history.invoke(
    {
        "context": current_weather,
        "question": "Where I am?"
    },
    config={"configurable": {"session_id": "none"}}
)
print(response)