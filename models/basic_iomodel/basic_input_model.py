from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM
from langchain.schema import StrOutputParser

# Define the prompt template
template = """Question: {question}

You are a guider Named "Mento" using AI for guide the students for higher education."""

# Initialize OllamaLLM with the Code Llama model
model = OllamaLLM(model="codellama")
# Create a ChatPromptTemplate object from the template
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a surfer dude, having a conversation about the surf conditions on the beach. Respond using surfer slang.",
        ),
        (
            "human", 
            "{question}"
        ),
    ]
)

chat_chain = prompt | model | StrOutputParser()

response = chat_chain.invoke({"question": "What is the weather like?"})

print(response)