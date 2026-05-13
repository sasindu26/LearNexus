import json
from langchain.embeddings import HuggingFaceEmbeddings
from py2neo import Graph, Node, Relationship

# Connect to Neo4j
graph = Graph("bolt://localhost:7691", auth=("neo4j", "Mento@2152"))

# Load embeddings model
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Load JSON file
with open("devto_articles_4.json", "r", encoding="utf-8") as file:
    articles = json.load(file)

# Process and store articles in Neo4j
for article in articles:
    title = article.get("title", "Unknown Title")
    description = article.get("full_description", "No Description Available")
    url = article.get("url", "No URL")
    tags = article.get("tags", [])
    
    # Generate embedding for full description
    embedding = embedding_model.embed_query(description)
    embedding_list = embedding  # Embedding is already a list

    # Create Article node
    article_node = Node("Article", title=title, description=description, url=url, embedding=embedding_list)
    graph.merge(article_node, "Article", "url")  # Merge prevents duplicate articles

    # Create Tag nodes and relationships
    for tag in tags:
        tag_node = Node("Tag", name=tag.lower())  # Tags are lowercase to avoid duplication
        graph.merge(tag_node, "Tag", "name")
        graph.merge(Relationship(article_node, "HAS_TAG", tag_node))

print("✅ Articles and tags successfully stored in Neo4j!")
