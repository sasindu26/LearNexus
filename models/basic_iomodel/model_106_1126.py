from neo4j import GraphDatabase
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
import numpy as np
import pickle
from langchain_ollama.llms import OllamaLLM

# Configuration
neo4j_url = "bolt://localhost:7687"
neo4j_user = "neo4j"
neo4j_password = "Mento@2152"

# Initialize Neo4j Driver
driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))

# Function to Fetch Embeddings and Data
def fetch_embeddings_from_neo4j():
    query = """
    MATCH (n)
    RETURN n.id AS id, n.text AS text, n.embedding AS embedding
    """
    with driver.session() as session:
        result = session.run(query)
        data = []
        for record in result:
            data.append({
                "id": record["id"],
                "text": record["text"],
                "embedding": np.array(record["embedding"], dtype=np.float32)
            })
        return data

# Load Data from Neo4j
data = fetch_embeddings_from_neo4j()

# Build FAISS Vector Store
from langchain.vectorstores.faiss import FAISS
from langchain.docstore import InMemoryDocstore

# Prepare Data for Vector Store
texts = [item["text"] for item in data]
embeddings = np.vstack([item["embedding"] for item in data])
docstore = InMemoryDocstore({item["id"]: {"text": item["text"]} for item in data})

# Create FAISS Index
vector_store = FAISS(embedding_function=None, docstore=docstore)
vector_store.index.add(embeddings)

# Save FAISS Index for Reuse
with open("faiss_index.pkl", "wb") as f:
    pickle.dump(vector_store, f)

# Load FAISS Index (if already saved)
# with open("faiss_index.pkl", "rb") as f:
#     vector_store = pickle.load(f)

# Connect to OpenAI (or Your Preferred LLM)
llm = OllamaLLM(model="mistral:7b") # Replace with your LLM integration

# Build RetrievalQA
retriever = vector_store.as_retriever()
qa_chain = RetrievalQA(llm=llm, retriever=retriever)

# Chatbot Interface
def chatbot(query):
    response = qa_chain.run(query)
    return response

# Example Usage
while True:
    user_query = input("You: ")
    if user_query.lower() in ["exit", "quit"]:
        print("Chatbot: Goodbye!")
        break
    bot_response = chatbot(user_query)
    print(f"Chatbot: {bot_response}")
