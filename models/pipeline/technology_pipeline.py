import numpy as np
import hdbscan
import umap
from py2neo import Graph
import schedule
import time
from sklearn.metrics.pairwise import cosine_similarity
import json
from datetime import datetime
import logging
from sentence_transformers import SentenceTransformer
from time import perf_counter
import sys
import os

# Ensure the pipeline directory is on sys.path so `deepseel2` can be imported
_pipeline_dir = os.path.abspath(os.path.dirname(__file__))
if _pipeline_dir not in sys.path:
    sys.path.insert(0, _pipeline_dir)

# Enhanced logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TechnologyPipeline:
    def __init__(self):
        self.graph = Graph("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.last_processed_time = None
        self.statistics = {
            'articles_processed': 0,
            'clusters_formed': 0,
            'processing_time': 0,
            'articles_by_source': {},
            'total_sources': 0
        }

    def log_statistics(self):
        """Enhanced statistics logging"""
        logger.info("Pipeline Statistics:")
        for key, value in self.statistics.items():
            if key == 'articles_by_source':
                logger.info("  Articles by source:")
                for source, count in value.items():
                    logger.info(f"    {source}: {count}")
            else:
                logger.info(f"  {key}: {value}")

    def get_article_embedding(self, article):
        """Generate embedding from plain text (strip HTML if present)."""
        import re
        def strip_html(text):
            return re.sub(r'<[^>]+>', ' ', text or '')
        content = f"{article.get('title','')} {strip_html(article.get('description',''))} {strip_html(article.get('full_description',''))}"
        return self.model.encode(content)

    def process_new_articles(self):
        start_time = perf_counter()
        logger.info("Starting new article processing cycle")
        
        try:
            from deepseel2 import fetch_all_tech_news, process_articles_to_neo4j, check_existing_articles  # type: ignore
            
            # Define tags for technology articles
            tech_tags = ["AI" , "python " , "networking" , "secuirty" , "docker" , "cloud" , "LLMs"]
            
            logger.info("Fetching articles from multiple sources...")
            all_articles = fetch_all_tech_news(
                tags=tech_tags, 
                max_articles_per_source=10,
                graph=self.graph,
                use_time_filter=True
            )
            
            logger.info(f"Total articles fetched: {len(all_articles)}")
            
            # Filter out existing articles BEFORE processing
            new_articles, duplicate_articles = check_existing_articles(all_articles, self.graph)
            
            logger.info(f"New articles to process: {len(new_articles)}")
            logger.info(f"Duplicate articles filtered out: {len(duplicate_articles)}")
            
            # Track source distribution for NEW articles only
            source_counts = {}
            for article in new_articles:
                source = article.get('source', 'unknown')
                source_counts[source] = source_counts.get(source, 0) + 1
            
            logger.info("New article counts by source:")
            for source, count in source_counts.items():
                logger.info(f"  {source}: {count}")
            
            if not new_articles:
                logger.info("No new articles to process - all were duplicates")
                # Still run clustering and relationships on existing data
                self.update_clusters()
                self.update_relationships()
                
                end_time = perf_counter()
                processing_time = end_time - start_time
                self.statistics['processing_time'] = processing_time
                logger.info(f"Pipeline cycle completed in {processing_time:.2f} seconds (no new articles)")
                self.log_statistics()
                return
            
            # Check current article count in Neo4j before processing
            current_count = self.graph.run("""
                MATCH (a:Article) 
                RETURN count(a) as total
            """).data()[0]['total']
            logger.info(f"Articles currently in Neo4j: {current_count}")
            
            # Process only NEW articles directly to Neo4j
            processed_count = process_articles_to_neo4j(
                articles=new_articles,
                graph=self.graph,
                embedding_model=self.model
            )
            
            # Check final article count in Neo4j after processing
            final_count = self.graph.run("""
                MATCH (a:Article) 
                RETURN count(a) as total
            """).data()[0]['total']
            logger.info(f"Articles in Neo4j after processing: {final_count}")
            logger.info(f"New articles added: {final_count - current_count}")
            
            # Update statistics with ACTUAL processed articles
            self.statistics['articles_processed'] += processed_count
            self.statistics['articles_by_source'].update(source_counts)
            self.statistics['total_sources'] = len(source_counts)
            
            logger.info(f"Processed {processed_count} new articles")

            # Check if modules exist before updating relationships
            module_count = self.graph.run("""
                MATCH (m:Module) 
                RETURN count(m) as total
            """).data()[0]['total']
            logger.info(f"Modules in database: {module_count}")
            
            if module_count == 0:
                logger.warning("No modules found in database. Creating sample modules...")
                self.create_sample_modules()

            # Update clusters and relationships
            self.update_clusters()
            self.update_relationships()
            
            # Log completion time
            end_time = perf_counter()
            processing_time = end_time - start_time
            self.statistics['processing_time'] = processing_time
            
            logger.info(f"Pipeline cycle completed in {processing_time:.2f} seconds")
            self.log_statistics()
            
        except Exception as e:
            logger.error(f"Pipeline error: {str(e)}")
            raise

    def update_clusters(self):
        """Update article clusters with detailed monitoring and UMAP dimensionality reduction"""
        logger.info("Starting cluster update process")
        start_time = perf_counter()
        
        try:
            # Fetch all articles and their embeddings
            articles = self.graph.run("""
                MATCH (a:Article) 
                RETURN a.url AS url, a.embedding AS embedding
            """).data()

            if not articles:
                logger.warning("No articles found for clustering")
                return

            logger.info(f"Clustering {len(articles)} articles")
            # Prepare data for clustering
            embeddings = np.array([article["embedding"] for article in articles])
            
            # Apply UMAP for dimensionality reduction
            logger.info("Applying UMAP dimensionality reduction...")
            umap_reducer = umap.UMAP(
                n_components=50, 
                random_state=42, 
                metric='cosine',
                min_dist=0.1,
                n_neighbors=15
            )
            reduced_embeddings = umap_reducer.fit_transform(embeddings)
            logger.info(f"Reduced embeddings from {embeddings.shape[1]} to {reduced_embeddings.shape[1]} dimensions")
            
            # Clustering with HDBSCAN on reduced embeddings
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=3,
                metric='euclidean',
                prediction_data=True
            )
            cluster_labels = clusterer.fit_predict(reduced_embeddings)
            
            # Analyze clustering results
            n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
            n_noise = list(cluster_labels).count(-1)
            self.statistics['clusters_formed'] = n_clusters
            
            logger.info(f"Formed {n_clusters} clusters")
            logger.info(f"Found {n_noise} noise points")
            
            # Log cluster sizes
            for cluster_id in set(cluster_labels):
                if cluster_id != -1:
                    cluster_size = list(cluster_labels).count(cluster_id)
                    logger.info(f"Cluster {cluster_id}: {cluster_size} articles")

            # Update clusters in Neo4j with transaction
            tx = self.graph.begin()
            try:
                for i, article in enumerate(articles):
                    tx.run("""
                        MATCH (a:Article {url: $url})
                        SET a.cluster = $cluster
                    """, url=article["url"], 
                        cluster=int(cluster_labels[i]) if cluster_labels[i] != -1 else None)
                tx.commit()
                logger.info(f"Successfully committed cluster updates for {len(articles)} articles")
            except Exception as tx_error:
                tx.rollback()
                logger.error(f"Transaction failed, rolling back: {str(tx_error)}")
                raise
            
            clustering_time = perf_counter() - start_time
            logger.info(f"Clustering completed in {clustering_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Clustering error: {str(e)}")
            raise

    def update_relationships(self):
        """Update relationships with source-aware similarity monitoring"""
        logger.info("Starting relationship update process")
        start_time = perf_counter()
        
        try:
            # Fetch articles with source information
            articles = self.graph.run("""
                MATCH (a:Article)-[:FROM_SOURCE]->(s:Source)
                RETURN a.url AS url, a.embedding AS embedding, s.name AS source
            """).data()

            modules = self.graph.run("""
                MATCH (m:Module)
                RETURN m.name AS name, m.embeddings AS embedding
            """).data()

            if not articles or not modules:
                logger.warning("No articles or modules found for relationship update")
                return

            logger.info(f"Updating relationships for {len(articles)} articles and {len(modules)} modules")
            
            # Prepare data
            article_embeddings = np.array([article["embedding"] for article in articles])
            module_embeddings = np.array([module["embedding"] for module in modules])
            
            # Calculate and log similarity statistics
            article_module_sim = cosine_similarity(article_embeddings, module_embeddings)
            cosine_sim = cosine_similarity(article_embeddings)
            
            avg_module_sim = np.mean(article_module_sim)
            avg_article_sim = np.mean(cosine_sim)
            
            logger.info(f"Average article-module similarity: {avg_module_sim:.3f}")
            logger.info(f"Average article-article similarity: {avg_article_sim:.3f}")

            # Update module relationships and similar articles with transaction
            tx = self.graph.begin()
            try:
                for i, article in enumerate(articles):
                    # Update module relationships
                    best_module_index = np.argmax(article_module_sim[i])
                    tx.run("""
                        MATCH (a:Article {url: $url}), (m:Module {name: $module})
                        MERGE (a)-[:RELATED_TO]->(m)
                    """, url=article["url"], module=modules[best_module_index]["name"])

                    # Update similar articles
                    similarities = list(enumerate(cosine_sim[i]))
                    similarities.sort(key=lambda x: x[1], reverse=True)
                    for idx, score in similarities[1:6]:  # Top 5 similar articles
                        tx.run("""
                            MATCH (a1:Article {url: $url1}), (a2:Article {url: $url2})
                            MERGE (a1)-[:SIMILAR_TO {score: $score}]->(a2)
                        """, url1=article["url"], url2=articles[idx]["url"], score=float(score))
                
                tx.commit()
                logger.info(f"Successfully committed relationship updates for {len(articles)} articles")
            except Exception as tx_error:
                tx.rollback()
                logger.error(f"Relationship transaction failed, rolling back: {str(tx_error)}")
                raise
                
            # Add source-based similarity logging
            sources = set(article['source'] for article in articles)
            for source in sources:
                source_articles = [a for a in articles if a['source'] == source]
                if len(source_articles) > 1:
                    source_embeddings = np.array([a['embedding'] for a in source_articles])
                    source_sim = cosine_similarity(source_embeddings)
                    avg_sim = np.mean(source_sim)
                    logger.info(f"Average similarity for {source} articles: {avg_sim:.3f}")

            update_time = perf_counter() - start_time
            logger.info(f"Relationship update completed in {update_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Relationship update error: {str(e)}")
            raise

    def create_sample_modules(self):
        """Create sample technology modules for relationship building"""
        logger.info("Creating sample technology modules...")
        
        modules = [
            {"name": "Artificial Intelligence", "description": "Machine learning, deep learning, AI applications"},
            {"name": "Python Programming", "description": "Python development, frameworks, libraries"},
            {"name": "Network Security", "description": "Cybersecurity, network protection, security protocols"},
            {"name": "Docker & Containers", "description": "Containerization, Docker, Kubernetes"},
            {"name": "Cloud Computing", "description": "AWS, Azure, GCP, cloud services"},
            {"name": "Large Language Models", "description": "LLMs, GPT, transformer models, NLP"}
        ]
        
        tx = self.graph.begin()
        try:
            for module in modules:
                # Generate embedding for module
                content = f"{module['name']} {module['description']}"
                embedding = self.model.encode(content).tolist()
                
                tx.run("""
                    MERGE (m:Module {name: $name})
                    SET m.description = $description,
                        m.embeddings = $embedding,
                        m.created_date = datetime()
                """, name=module['name'], description=module['description'], embedding=embedding)
            
            tx.commit()
            logger.info(f"Created {len(modules)} technology modules")
            
        except Exception as e:
            tx.rollback()
            logger.error(f"Failed to create modules: {e}")
            raise

def run_pipeline():
    pipeline = TechnologyPipeline()
    pipeline.process_new_articles()

if __name__ == "__main__":
    # Schedule the pipeline to run every 6 hours
    schedule.every(6).hours.do(run_pipeline)
    
    # Run immediately on start
    run_pipeline()
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)
