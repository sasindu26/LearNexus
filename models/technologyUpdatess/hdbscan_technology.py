import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from py2neo import Graph
from tqdm import tqdm

# Connect to Neo4j
graph = Graph("bolt://localhost:7691", auth=("neo4j", "Mento@2152"))

# Configuration
SIMILARITY_THRESHOLD = 0.3  # This will be auto-adjusted
AUTO_THRESHOLD = True  # Set to False to use manual threshold

def fetch_modules_with_embeddings():
    """Fetch all modules that have embeddings"""
    print("🔍 Fetching modules with embeddings...")
    
    query = """
    MATCH (m:Module) 
    WHERE m.embedding IS NOT NULL
    RETURN id(m) as node_id, m.name as name, m.embedding as embedding
    """
    
    modules = graph.run(query).data()
    print(f"📊 Found {len(modules)} modules with embeddings")
    
    return modules

def fetch_articles_with_embeddings():
    """Fetch all articles that have preprocessed embeddings"""
    print("🔍 Fetching articles with preprocessed embeddings...")
    
    query = """
    MATCH (a:Article) 
    WHERE a.embedding IS NOT NULL
    RETURN id(a) as node_id, a.title as title, a.embedding as embedding
    """
    
    articles = graph.run(query).data()
    print(f"📊 Found {len(articles)} articles with embeddings")
    
    return articles

def calculate_similarity_and_create_relationships(articles, modules):
    """Calculate cosine similarity between articles and modules, create RELATED_TO relationships"""
    print(f"🔗 Comparing {len(articles)} articles with {len(modules)} modules...")
    print(f"📊 Using similarity threshold: {SIMILARITY_THRESHOLD}")
    
    relationships_created = 0
    total_comparisons = 0
    similarities = []
    
    for article in tqdm(articles, desc="Processing articles"):
        try:
            # Convert article embedding to numpy array
            article_embedding = np.array(article['embedding'])
            article_id = article['node_id']
            article_title = article['title']
            
            for module in modules:
                try:
                    # Convert module embedding to numpy array
                    module_embedding = np.array(module['embedding'])
                    module_id = module['node_id']
                    module_name = module['name']
                    
                    # Calculate cosine similarity
                    similarity = cosine_similarity(
                        article_embedding.reshape(1, -1),
                        module_embedding.reshape(1, -1)
                    )[0][0]
                    
                    total_comparisons += 1
                    similarities.append(similarity)
                    
                    # Create RELATED_TO relationship if similarity is above threshold
                    if similarity >= SIMILARITY_THRESHOLD:
                        create_relationship_query = """
                        MATCH (a:Article), (m:Module)
                        WHERE id(a) = $article_id AND id(m) = $module_id
                        MERGE (a)-[r:RELATED_TO]->(m)
                        SET r.similarity_score = $similarity
                        RETURN r
                        """
                        
                        graph.run(create_relationship_query,
                                 article_id=article_id,
                                 module_id=module_id,
                                 similarity=float(similarity))
                        
                        relationships_created += 1
                        print(f"✅ Connected: '{article_title[:40]}...' -> '{module_name}' (similarity: {similarity:.3f})")
                
                except Exception as e:
                    print(f"❌ Error processing module '{module.get('name', 'Unknown')}': {e}")
        
        except Exception as e:
            print(f"❌ Error processing article '{article.get('title', 'Unknown')}': {e}")
    
    # Print statistics
    print(f"\n📊 Similarity Analysis Results:")
    print(f"   Total comparisons: {total_comparisons}")
    print(f"   Relationships created: {relationships_created}")
    
    if similarities:
        print(f"   Highest similarity: {max(similarities):.4f}")
        print(f"   Lowest similarity: {min(similarities):.4f}")
        print(f"   Average similarity: {np.mean(similarities):.4f}")
        print(f"   Similarities above threshold: {sum(1 for s in similarities if s >= SIMILARITY_THRESHOLD)}")
    
    return relationships_created

def verify_relationships():
    """Verify the created relationships in the database"""
    print("🔍 Verifying created relationships...")
    
    query = """
    MATCH (a:Article)-[r:RELATED_TO]->(m:Module)
    RETURN count(r) as total_relationships,
           avg(r.similarity_score) as avg_similarity,
           max(r.similarity_score) as max_similarity,
           min(r.similarity_score) as min_similarity
    """
    
    result = graph.run(query).data()[0]
    
    print(f"✅ Database Verification:")
    print(f"   Total RELATED_TO relationships: {result['total_relationships']}")
    
    if result['total_relationships'] > 0:
        print(f"   Average similarity score: {result['avg_similarity']:.4f}")
        print(f"   Highest similarity score: {result['max_similarity']:.4f}")
        print(f"   Lowest similarity score: {result['min_similarity']:.4f}")
    else:
        print("   No RELATED_TO relationships found in database")

def clean_existing_relationships():
    """Clean existing RELATED_TO relationships"""
    print("🧹 Cleaning existing RELATED_TO relationships...")
    
    # Count existing relationships first
    count_query = "MATCH (a:Article)-[r:RELATED_TO]->(m:Module) RETURN count(r) as count"
    existing_count = graph.run(count_query).data()[0]['count']
    
    if existing_count > 0:
        print(f"   Found {existing_count} existing RELATED_TO relationships")
        
        # Delete existing relationships
        delete_query = "MATCH (a:Article)-[r:RELATED_TO]->(m:Module) DELETE r"
        graph.run(delete_query)
        
        print(f"   Deleted {existing_count} RELATED_TO relationships")
    else:
        print("   No existing RELATED_TO relationships found")

def analyze_similarity_distribution(articles, modules, sample_size=1000):
    """Analyze the distribution of similarities to determine optimal threshold"""
    print("🔍 Analyzing similarity distribution for intelligent threshold detection...")
    
    similarities = []
    sampled_comparisons = 0
    
    # Sample a subset for analysis (to avoid processing all combinations)
    article_sample = articles[:min(len(articles), int(np.sqrt(sample_size)))]
    module_sample = modules[:min(len(modules), int(np.sqrt(sample_size)))]
    
    print(f"   Sampling {len(article_sample)} articles × {len(module_sample)} modules = {len(article_sample) * len(module_sample)} comparisons")
    
    for article in tqdm(article_sample, desc="Sampling similarities"):
        try:
            article_embedding = np.array(article['embedding'])
            
            for module in module_sample:
                try:
                    module_embedding = np.array(module['embedding'])
                    
                    similarity = cosine_similarity(
                        article_embedding.reshape(1, -1),
                        module_embedding.reshape(1, -1)
                    )[0][0]
                    
                    similarities.append(similarity)
                    sampled_comparisons += 1
                    
                except Exception as e:
                    continue
        except Exception as e:
            continue
    
    return np.array(similarities)

def find_optimal_threshold_methods(similarities):
    """Apply multiple methods to find optimal threshold"""
    print("\n🤖 Applying intelligent threshold detection methods...")
    
    methods = {}
    
    # Method 1: Statistical approach (Mean + N * Standard Deviations)
    mean_sim = np.mean(similarities)
    std_sim = np.std(similarities)
    methods['statistical'] = mean_sim + (2 * std_sim)  # 2 standard deviations above mean
    
    # Method 2: Percentile-based approach
    methods['percentile_90'] = np.percentile(similarities, 90)
    methods['percentile_95'] = np.percentile(similarities, 95)
    methods['percentile_85'] = np.percentile(similarities, 85)
    
    # Method 3: K-means clustering to find natural breakpoints
    try:
        similarities_reshaped = similarities.reshape(-1, 1)
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(similarities_reshaped)
        cluster_centers = kmeans.cluster_centers_.flatten()
        
        # Use the boundary between highest and middle cluster
        sorted_centers = np.sort(cluster_centers)
        methods['kmeans'] = (sorted_centers[1] + sorted_centers[2]) / 2
    except:
        methods['kmeans'] = methods['percentile_90']
    
    # Method 4: Gaussian Mixture Model to find natural distribution breaks
    try:
        similarities_reshaped = similarities.reshape(-1, 1)
        gmm = GaussianMixture(n_components=2, random_state=42)
        gmm.fit(similarities_reshaped)
        
        # Find the intersection point of two gaussians
        means = gmm.means_.flatten()
        methods['gmm'] = np.mean(means)
    except:
        methods['gmm'] = methods['percentile_90']
    
    # Method 5: Elbow method - find point of diminishing returns
    sorted_sims = np.sort(similarities)[::-1]  # Sort descending
    # Find the "elbow" - point where slope changes most dramatically
    diffs = np.diff(sorted_sims)
    second_diffs = np.diff(diffs)
    if len(second_diffs) > 0:
        elbow_idx = np.argmax(np.abs(second_diffs)) + 1
        methods['elbow'] = sorted_sims[elbow_idx] if elbow_idx < len(sorted_sims) else methods['percentile_90']
    else:
        methods['elbow'] = methods['percentile_90']
    
    return methods

def display_threshold_analysis(similarities, methods):
    """Display analysis results and let user choose"""
    print(f"\n📊 Similarity Distribution Analysis:")
    print(f"   Total similarities analyzed: {len(similarities)}")
    print(f"   Mean: {np.mean(similarities):.4f}")
    print(f"   Std Dev: {np.std(similarities):.4f}")
    print(f"   Min: {np.min(similarities):.4f}")
    print(f"   Max: {np.max(similarities):.4f}")
    
    print(f"\n🎯 Recommended Thresholds:")
    for i, (method, threshold) in enumerate(methods.items(), 1):
        # Estimate relationships for each threshold
        estimated_relationships = np.sum(similarities >= threshold)
        percentage = (estimated_relationships / len(similarities)) * 100
        
        print(f"   {i}. {method:15}: {threshold:.4f} (~{estimated_relationships:,} relationships, {percentage:.1f}%)")
    
    # Recommend the best method
    recommended = methods['percentile_90']  # Default recommendation
    
    # Smart recommendation based on distribution
    if np.std(similarities) > 0.1:  # High variance
        recommended = methods['kmeans']
        rec_method = 'kmeans'
    elif np.mean(similarities) > 0.7:  # High overall similarity
        recommended = methods['percentile_95']
        rec_method = 'percentile_95'
    else:
        recommended = methods['percentile_90']
        rec_method = 'percentile_90'
    
    print(f"\n💡 Smart Recommendation: {rec_method} = {recommended:.4f}")
    
    return methods, recommended

def choose_threshold_interactively(methods, recommended):
    """Let user choose threshold interactively"""
    print(f"\n🤔 Choose your threshold strategy:")
    print(f"   0. Use smart recommendation ({recommended:.4f})")
    
    method_list = list(methods.items())
    for i, (method, threshold) in enumerate(method_list, 1):
        print(f"   {i}. Use {method}: {threshold:.4f}")
    
    print(f"   {len(method_list) + 1}. Enter custom threshold")
    
    while True:
        try:
            choice = input(f"\nEnter your choice (0-{len(method_list) + 1}): ").strip()
            
            if choice == '0':
                return recommended
            elif choice.isdigit():
                choice_idx = int(choice)
                if 1 <= choice_idx <= len(method_list):
                    return method_list[choice_idx - 1][1]
                elif choice_idx == len(method_list) + 1:
                    custom = float(input("Enter custom threshold (0.0-1.0): "))
                    if 0.0 <= custom <= 1.0:
                        return custom
                    else:
                        print("❌ Threshold must be between 0.0 and 1.0")
                else:
                    print(f"❌ Please enter a number between 0 and {len(method_list) + 1}")
            else:
                print(f"❌ Please enter a valid number")
        except ValueError:
            print("❌ Please enter a valid number")

def intelligent_threshold_selection(articles, modules):
    """Main function for intelligent threshold selection"""
    print("\n🤖 Starting Intelligent Threshold Selection...")
    
    # Analyze similarity distribution
    similarities = analyze_similarity_distribution(articles, modules)
    
    if len(similarities) == 0:
        print("❌ No similarities could be calculated. Using default threshold.")
        return SIMILARITY_THRESHOLD
    
    # Find optimal thresholds using multiple methods
    methods = find_optimal_threshold_methods(similarities)
    
    # Display analysis and get recommendation
    methods, recommended = display_threshold_analysis(similarities, methods)
    
    # Let user choose interactively
    chosen_threshold = choose_threshold_interactively(methods, recommended)
    
    print(f"\n✅ Selected threshold: {chosen_threshold:.4f}")
    return chosen_threshold

def main():
    """Main application function"""
    print("🚀 Starting Intelligent Article-Module Similarity Analysis")
    print("=" * 60)
    
    # Check for existing relationships and ask user
    existing_count_query = "MATCH (a:Article)-[r:RELATED_TO]->(m:Module) RETURN count(r) as count"
    existing_count = graph.run(existing_count_query).data()[0]['count']
    
    if existing_count > 0:
        print(f"⚠️  Found {existing_count} existing RELATED_TO relationships in the database")
        user_choice = input("🗑️  Do you want to delete existing relationships and start over? (y/n): ").lower().strip()
        
        if user_choice in ['y', 'yes']:
            clean_existing_relationships()
            print("✅ Ready to create new relationships!")
        else:
            print("⚠️  Continuing with existing relationships (may create duplicates)")
    else:
        print("✅ No existing RELATED_TO relationships found. Starting fresh!")
    
    print()
    
    # Step 1: Fetch modules with embeddings
    modules = fetch_modules_with_embeddings()
    if not modules:
        print("❌ No modules with embeddings found!")
        return
    
    # Step 2: Fetch articles with embeddings
    articles = fetch_articles_with_embeddings()
    if not articles:
        print("❌ No articles with preprocessed embeddings found!")
        return
    
    # Step 3: Intelligent threshold selection
    global SIMILARITY_THRESHOLD
    if AUTO_THRESHOLD:
        SIMILARITY_THRESHOLD = intelligent_threshold_selection(articles, modules)
    else:
        print(f"📊 Using manual threshold: {SIMILARITY_THRESHOLD}")
    
    # Step 4: Calculate similarities and create relationships
    relationships_created = calculate_similarity_and_create_relationships(articles, modules)
    
    # Step 5: Verify results
    verify_relationships()
    
    print(f"\n🎉 Application completed successfully!")
    print(f"   Used threshold: {SIMILARITY_THRESHOLD:.4f}")
    print(f"   Created {relationships_created} RELATED_TO relationships")

if __name__ == "__main__":
    main()