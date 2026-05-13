import json
from langchain.embeddings import HuggingFaceEmbeddings
from py2neo import Graph, Node, Relationship
from description_preprocessing import DescriptionPreprocessor

# Connect to Neo4j
graph = Graph("bolt://localhost:7691", auth=("neo4j", "Mento@2152"))

# Load embeddings model
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Initialize preprocessor
preprocessor = DescriptionPreprocessor()

print("🔍 Fetching articles without preprocessed embeddings...")

# Query to find articles that don't have preprocessed_embedding (fixed syntax)
query = """
MATCH (a:Article) 
WHERE a.preprocessed_embedding IS NULL
RETURN a.title as title, a.description as description, a.url as url, id(a) as node_id
"""

articles_to_process = graph.run(query).data()
total_articles = len(articles_to_process)

print(f"📊 Found {total_articles} articles missing preprocessed embeddings")

if total_articles == 0:
    print("✅ All articles already have preprocessed embeddings!")
    exit()

# Process articles missing preprocessed embeddings
for i, article_data in enumerate(articles_to_process, 1):
    title = article_data.get("title", "Unknown Title")
    description = article_data.get("description", "No Description Available")
    url = article_data.get("url", "No URL")
    node_id = article_data.get("node_id")
    
    print(f"🔄 Processing article {i}/{total_articles}: {title[:50]}...")
    
    try:
        # Preprocess the description
        preprocessing_result = preprocessor.preprocess_description(description)
        preprocessed_description = preprocessing_result['preprocessed_text']
        
        # Generate embedding for preprocessed description
        preprocessed_embedding = embedding_model.embed_query(preprocessed_description)
        
        # Update the existing article node with preprocessed data
        update_query = """
        MATCH (a:Article) 
        WHERE id(a) = $node_id
        SET a.preprocessed_description = $preprocessed_description,
            a.preprocessed_embedding = $preprocessed_embedding
        RETURN a.title as title
        """
        
        result = graph.run(update_query, 
                          node_id=node_id,
                          preprocessed_description=preprocessed_description,
                          preprocessed_embedding=preprocessed_embedding)
        
        print(f"✅ Updated: {title[:50]}...")
        
    except Exception as e:
        print(f"❌ Error processing article '{title[:50]}...': {str(e)}")
        continue

print(f"\n🎉 Successfully updated {total_articles} articles with preprocessed descriptions and embeddings!")

# Verify the update
verification_query = """
MATCH (a:Article)
RETURN 
    count(a) as total_articles,
    count(CASE WHEN a.embedding IS NOT NULL THEN 1 END) as with_regular_embeddings,
    count(CASE WHEN a.preprocessed_embedding IS NOT NULL THEN 1 END) as with_preprocessed_embeddings,
    count(CASE WHEN a.embedding IS NOT NULL AND a.preprocessed_embedding IS NOT NULL THEN 1 END) as with_both_embeddings
"""

stats = graph.run(verification_query).data()[0]
print("\n📈 Final Statistics:")
print(f"   Total articles: {stats['total_articles']}")
print(f"   Regular embeddings: {stats['with_regular_embeddings']}")
print(f"   Preprocessed embeddings: {stats['with_preprocessed_embeddings']}")
print(f"   Both embeddings: {stats['with_both_embeddings']}")