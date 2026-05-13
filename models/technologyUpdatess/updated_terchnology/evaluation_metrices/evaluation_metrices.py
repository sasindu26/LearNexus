import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from py2neo import Graph
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter
import json
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class RelationshipQualityEvaluator:
    """
    Comprehensive evaluation system for Article-Module and Article-Article relationships
    created by the intelligent threshold selection system
    """
    
    def __init__(self, neo4j_uri: str = "bolt://localhost:7691", auth: tuple = ("neo4j", "Mento@2152")):
        """Initialize the evaluator with Neo4j connection"""
        self.graph = Graph(neo4j_uri, auth=auth)
        self.evaluation_results = {}
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    def get_database_stats(self) -> Dict[str, Any]:
        """Get basic statistics about the database"""
        print("📊 Collecting database statistics...")
        
        stats_query = """
        MATCH (a:Article) WHERE a.embedding IS NOT NULL
        WITH count(a) as article_count
        MATCH (m:Module) WHERE m.embedding IS NOT NULL
        WITH article_count, count(m) as module_count
        MATCH (a:Article)-[r1:RELATED_TO]->(m:Module)
        WITH article_count, module_count, count(r1) as article_module_relationships
        MATCH (a1:Article)-[r2:SIMILAR_TO]->(a2:Article)
        WITH article_count, module_count, article_module_relationships, count(r2) as article_article_relationships
        RETURN article_count, module_count, article_module_relationships, article_article_relationships
        """
        
        result = self.graph.run(stats_query).data()[0]
        
        stats = {
            'articles_with_embeddings': int(result['article_count']) if result['article_count'] else 0,
            'modules_with_embeddings': int(result['module_count']) if result['module_count'] else 0,
            'article_module_relationships': int(result['article_module_relationships']) if result['article_module_relationships'] else 0,
            'article_article_relationships': int(result['article_article_relationships']) if result['article_article_relationships'] else 0,
            'total_relationships': (int(result['article_module_relationships']) if result['article_module_relationships'] else 0) + (int(result['article_article_relationships']) if result['article_article_relationships'] else 0)
        }
        
        print(f"   📄 Articles with embeddings: {stats['articles_with_embeddings']}")
        print(f"   📚 Modules with embeddings: {stats['modules_with_embeddings']}")
        print(f"   🔗 Article-Module relationships: {stats['article_module_relationships']}")
        print(f"   🔗 Article-Article relationships: {stats['article_article_relationships']}")
        
        return stats
    
    def evaluate_similarity_accuracy(self) -> Dict[str, float]:
        """Evaluate how accurate the stored similarity scores are"""
        print("\n🎯 Evaluating similarity accuracy...")
        
        # Get Article-Module relationships with stored similarities
        am_query = """
        MATCH (a:Article)-[r:RELATED_TO]->(m:Module)
        WHERE r.similarity_score IS NOT NULL
        RETURN a.embedding as article_embedding, 
               m.embedding as module_embedding,
               r.similarity_score as stored_similarity
        LIMIT 100
        """
        
        am_results = self.graph.run(am_query).data()
        
        # Get Article-Article relationships with stored similarities
        aa_query = """
        MATCH (a1:Article)-[r:SIMILAR_TO]->(a2:Article)
        WHERE r.similarity_score IS NOT NULL
        RETURN a1.embedding as article1_embedding,
               a2.embedding as article2_embedding,
               r.similarity_score as stored_similarity
        LIMIT 100
        """
        
        aa_results = self.graph.run(aa_query).data()
        
        accuracy_metrics = {}
        
        # Evaluate Article-Module similarities
        if am_results:
            am_errors = []
            for result in am_results:
                try:
                    emb1 = np.array(result['article_embedding'])
                    emb2 = np.array(result['module_embedding'])
                    
                    calculated_sim = cosine_similarity(
                        emb1.reshape(1, -1), 
                        emb2.reshape(1, -1)
                    )[0][0]
                    
                    stored_sim = result['stored_similarity']
                    error = abs(float(calculated_sim) - float(stored_sim))
                    am_errors.append(error)
                    
                except Exception as e:
                    continue
            
            if am_errors:
                accuracy_metrics['article_module_mae'] = float(np.mean(am_errors))
                accuracy_metrics['article_module_max_error'] = float(np.max(am_errors))
                accuracy_metrics['article_module_accuracy_percentage'] = float((1 - np.mean(am_errors)) * 100)
        
        # Evaluate Article-Article similarities
        if aa_results:
            aa_errors = []
            for result in aa_results:
                try:
                    emb1 = np.array(result['article1_embedding'])
                    emb2 = np.array(result['article2_embedding'])
                    
                    calculated_sim = cosine_similarity(
                        emb1.reshape(1, -1), 
                        emb2.reshape(1, -1)
                    )[0][0]
                    
                    stored_sim = result['stored_similarity']
                    error = abs(float(calculated_sim) - float(stored_sim))
                    aa_errors.append(error)
                    
                except Exception as e:
                    continue
            
            if aa_errors:
                accuracy_metrics['article_article_mae'] = float(np.mean(aa_errors))
                accuracy_metrics['article_article_max_error'] = float(np.max(aa_errors))
                accuracy_metrics['article_article_accuracy_percentage'] = float((1 - np.mean(aa_errors)) * 100)
        
        print(f"   📊 Article-Module accuracy: {accuracy_metrics.get('article_module_accuracy_percentage', 0):.2f}%")
        print(f"   📊 Article-Article accuracy: {accuracy_metrics.get('article_article_accuracy_percentage', 0):.2f}%")
        
        return accuracy_metrics
    
    def evaluate_threshold_effectiveness(self) -> Dict[str, Any]:
        """Evaluate how well the threshold selection worked"""
        print("\n⚖️ Evaluating threshold effectiveness...")
        
        # Get similarity distribution for Article-Module relationships
        am_sim_query = """
        MATCH (a:Article)-[r:RELATED_TO]->(m:Module)
        WHERE r.similarity_score IS NOT NULL
        RETURN r.similarity_score as similarity
        """
        
        am_similarities_list = [float(r['similarity']) for r in self.graph.run(am_sim_query).data()]
        
        # Get similarity distribution for Article-Article relationships
        aa_sim_query = """
        MATCH (a1:Article)-[r:SIMILAR_TO]->(a2:Article)
        WHERE r.similarity_score IS NOT NULL
        RETURN r.similarity_score as similarity
        """
        
        aa_similarities_list = [float(r['similarity']) for r in self.graph.run(aa_sim_query).data()]
        
        threshold_metrics = {}
        
        if len(am_similarities_list) > 0:
            am_similarities = np.array(am_similarities_list)
            threshold_metrics['am_similarity_mean'] = float(np.mean(am_similarities))
            threshold_metrics['am_similarity_std'] = float(np.std(am_similarities))
            threshold_metrics['am_similarity_min'] = float(np.min(am_similarities))
            threshold_metrics['am_similarity_max'] = float(np.max(am_similarities))
            threshold_metrics['am_quality_score'] = float(self._calculate_quality_score(am_similarities))
            threshold_metrics['am_relationships_count'] = len(am_similarities_list)
        else:
            threshold_metrics['am_quality_score'] = 0.0
            threshold_metrics['am_relationships_count'] = 0
        
        if len(aa_similarities_list) > 0:
            aa_similarities = np.array(aa_similarities_list)
            threshold_metrics['aa_similarity_mean'] = float(np.mean(aa_similarities))
            threshold_metrics['aa_similarity_std'] = float(np.std(aa_similarities))
            threshold_metrics['aa_similarity_min'] = float(np.min(aa_similarities))
            threshold_metrics['aa_similarity_max'] = float(np.max(aa_similarities))
            threshold_metrics['aa_quality_score'] = float(self._calculate_quality_score(aa_similarities))
            threshold_metrics['aa_relationships_count'] = len(aa_similarities_list)
        else:
            threshold_metrics['aa_quality_score'] = 0.0
            threshold_metrics['aa_relationships_count'] = 0
        
        # Calculate overall threshold effectiveness
        if len(am_similarities_list) > 0 and len(aa_similarities_list) > 0:
            combined_similarities = np.concatenate([np.array(am_similarities_list), np.array(aa_similarities_list)])
            threshold_metrics['overall_quality_score'] = float(self._calculate_quality_score(combined_similarities))
            threshold_metrics['relationship_balance'] = float(len(am_similarities_list) / len(aa_similarities_list))
        elif len(am_similarities_list) > 0:
            threshold_metrics['overall_quality_score'] = float(threshold_metrics.get('am_quality_score', 0.0))
            threshold_metrics['relationship_balance'] = 1.0
        elif len(aa_similarities_list) > 0:
            threshold_metrics['overall_quality_score'] = float(threshold_metrics.get('aa_quality_score', 0.0))
            threshold_metrics['relationship_balance'] = 1.0
        else:
            threshold_metrics['overall_quality_score'] = 0.0
            threshold_metrics['relationship_balance'] = 0.0
        
        print(f"   📈 Article-Module relationships: {threshold_metrics.get('am_relationships_count', 0)}")
        print(f"   📈 Article-Module quality score: {threshold_metrics.get('am_quality_score', 0):.3f}")
        print(f"   📈 Article-Article relationships: {threshold_metrics.get('aa_relationships_count', 0)}")
        print(f"   📈 Article-Article quality score: {threshold_metrics.get('aa_quality_score', 0):.3f}")
        print(f"   📈 Overall quality score: {threshold_metrics.get('overall_quality_score', 0):.3f}")
        
        return threshold_metrics
    
    def _calculate_quality_score(self, similarities: np.ndarray) -> float:
        """Calculate a quality score for similarity distribution"""
        if len(similarities) == 0:
            return 0.0
        
        similarities = np.array(similarities)
        
        mean_score = float(np.mean(similarities))
        std_dev = float(np.std(similarities))
        consistency_score = 1.0 / (1.0 + std_dev)
        spread_score = (float(np.max(similarities)) - float(np.min(similarities))) / 2.0
        
        quality_score = (mean_score * 0.5) + (consistency_score * 0.3) + (spread_score * 0.2)
        return float(min(quality_score, 1.0))
    
    def evaluate_clustering_quality(self) -> Dict[str, float]:
        """Evaluate the quality of embeddings clustering"""
        print("\n🎯 Evaluating clustering quality...")
        
        articles_query = """
        MATCH (a:Article)
        WHERE a.embedding IS NOT NULL
        RETURN id(a) as node_id, a.embedding as embedding
        LIMIT 500
        """
        
        articles = self.graph.run(articles_query).data()
        
        if len(articles) < 10:
            print("   ⚠️ Not enough articles for clustering evaluation")
            return {}
        
        embeddings = []
        for article in articles:
            try:
                embedding = np.array(article['embedding'])
                embeddings.append(embedding)
            except:
                continue
        
        if len(embeddings) < 10:
            print("   ⚠️ Not enough valid embeddings for clustering evaluation")
            return {}
        
        embeddings = np.array(embeddings)
        clustering_metrics = {}
        
        try:
            best_silhouette = -1
            best_k = 2
            
            for k in range(2, min(11, len(embeddings)//2)):
                try:
                    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                    cluster_labels = kmeans.fit_predict(embeddings)
                    silhouette = silhouette_score(embeddings, cluster_labels)
                    
                    if silhouette > best_silhouette:
                        best_silhouette = silhouette
                        best_k = k
                except:
                    continue
            
            kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(embeddings)
            
            clustering_metrics['silhouette_score'] = float(silhouette_score(embeddings, cluster_labels))
            clustering_metrics['calinski_harabasz_score'] = float(calinski_harabasz_score(embeddings, cluster_labels))
            clustering_metrics['davies_bouldin_score'] = float(davies_bouldin_score(embeddings, cluster_labels))
            clustering_metrics['optimal_clusters'] = int(best_k)
            clustering_metrics['total_articles_analyzed'] = int(len(embeddings))
            
        except Exception as e:
            print(f"   ❌ Error in clustering evaluation: {e}")
            return {}
        
        print(f"   📊 Silhouette Score: {clustering_metrics['silhouette_score']:.3f}")
        print(f"   📊 Calinski-Harabasz Score: {clustering_metrics['calinski_harabasz_score']:.1f}")
        print(f"   📊 Davies-Bouldin Score: {clustering_metrics['davies_bouldin_score']:.3f}")
        print(f"   📊 Optimal clusters: {clustering_metrics['optimal_clusters']}")
        
        return clustering_metrics
    
    def evaluate_relationship_diversity(self) -> Dict[str, Any]:
        """Evaluate the diversity of created relationships"""
        print("\n🌈 Evaluating relationship diversity...")
        
        diversity_metrics = {}
        
        am_diversity_query = """
        MATCH (a:Article)-[r:RELATED_TO]->(m:Module)
        WITH a, count(m) as module_connections
        RETURN avg(module_connections) as avg_modules_per_article,
               max(module_connections) as max_modules_per_article,
               min(module_connections) as min_modules_per_article,
               stDev(module_connections) as std_modules_per_article
        """
        
        am_diversity = self.graph.run(am_diversity_query).data()[0]
        
        if am_diversity and am_diversity['avg_modules_per_article']:
            diversity_metrics['avg_modules_per_article'] = float(am_diversity['avg_modules_per_article'])
            diversity_metrics['max_modules_per_article'] = float(am_diversity['max_modules_per_article'])
            diversity_metrics['min_modules_per_article'] = float(am_diversity['min_modules_per_article'])
            diversity_metrics['std_modules_per_article'] = float(am_diversity['std_modules_per_article'] or 0)
        
        module_coverage_query = """
        MATCH (m:Module)
        WITH count(m) as total_modules
        MATCH (m:Module)<-[:RELATED_TO]-(a:Article)
        WITH total_modules, count(DISTINCT m) as connected_modules
        RETURN toFloat(connected_modules) / total_modules as module_coverage_ratio,
               connected_modules, total_modules
        """
        
        module_coverage = self.graph.run(module_coverage_query).data()[0]
        
        if module_coverage:
            diversity_metrics['module_coverage_ratio'] = float(module_coverage['module_coverage_ratio'])
            diversity_metrics['connected_modules'] = int(module_coverage['connected_modules'])
            diversity_metrics['total_modules'] = int(module_coverage['total_modules'])
        
        aa_diversity_query = """
        MATCH (a1:Article)-[r:SIMILAR_TO]->(a2:Article)
        WITH a1, count(a2) as similar_articles
        RETURN avg(similar_articles) as avg_similar_per_article,
               max(similar_articles) as max_similar_per_article,
               min(similar_articles) as min_similar_per_article,
               stDev(similar_articles) as std_similar_per_article
        """
        
        aa_diversity = self.graph.run(aa_diversity_query).data()[0]
        
        if aa_diversity and aa_diversity['avg_similar_per_article']:
            diversity_metrics['avg_similar_per_article'] = float(aa_diversity['avg_similar_per_article'])
            diversity_metrics['max_similar_per_article'] = float(aa_diversity['max_similar_per_article'])
            diversity_metrics['min_similar_per_article'] = float(aa_diversity['min_similar_per_article'])
            diversity_metrics['std_similar_per_article'] = float(aa_diversity['std_similar_per_article'] or 0)
        
        print(f"   📊 Avg modules per article: {diversity_metrics.get('avg_modules_per_article', 0):.2f}")
        print(f"   📊 Module coverage: {diversity_metrics.get('module_coverage_ratio', 0)*100:.1f}%")
        print(f"   📊 Avg similar articles per article: {diversity_metrics.get('avg_similar_per_article', 0):.2f}")
        
        return diversity_metrics
    
    def generate_recommendations(self, results: Dict) -> List[str]:
        """Generate actionable recommendations based on evaluation results"""
        recommendations = []
        
        # Threshold effectiveness recommendations
        if 'threshold_effectiveness' in results:
            threshold = results['threshold_effectiveness']
            
            if threshold.get('overall_quality_score', 0) < 0.6:
                recommendations.append("🔧 Consider adjusting the similarity threshold - current relationships show low quality scores")
            
            if threshold.get('relationship_balance', 1) > 3:
                recommendations.append("⚖️ Article-Article relationships significantly outnumber Article-Module relationships - consider lowering Article-Module threshold")
            elif threshold.get('relationship_balance', 1) < 0.3:
                recommendations.append("⚖️ Article-Module relationships significantly outnumber Article-Article relationships - consider lowering Article-Article threshold")
        
        # Accuracy recommendations
        if 'similarity_accuracy' in results:
            accuracy = results['similarity_accuracy']
            
            if accuracy.get('article_module_accuracy_percentage', 100) < 95:
                recommendations.append("🎯 Article-Module similarity calculations show some inaccuracy - verify embedding preprocessing")
            
            if accuracy.get('article_article_accuracy_percentage', 100) < 95:
                recommendations.append("🎯 Article-Article similarity calculations show some inaccuracy - verify embedding consistency")
        
        # Clustering recommendations
        if 'clustering_quality' in results:
            clustering = results['clustering_quality']
            
            if clustering.get('silhouette_score', 0) < 0.3:
                recommendations.append("🎯 Low clustering quality detected - consider different embedding models or preprocessing")
            
            if clustering.get('davies_bouldin_score', 1) > 1.5:
                recommendations.append("🔍 High Davies-Bouldin score indicates overlapping clusters - consider higher similarity thresholds")
        
        # Diversity recommendations
        if 'relationship_diversity' in results:
            diversity = results['relationship_diversity']
            
            if diversity.get('module_coverage_ratio', 0) < 0.5:
                recommendations.append("📚 Low module coverage - many modules are not connected to articles")
            
            if diversity.get('avg_modules_per_article', 0) < 1:
                recommendations.append("🔗 Articles have very few module connections - consider lowering thresholds")
        
        # Domain coverage recommendations
        if 'technology_domain_coverage' in results:
            domain = results['technology_domain_coverage']
            
            if domain.get('total_domain_coverage', 0) < 2:
                recommendations.append("💻 Low technology domain coverage - dataset may be too narrow or specialized")
            
            if domain.get('overall_diversity', 0) > 0.3:
                recommendations.append("🌈 Uneven technology domain distribution - consider balancing dataset or adjusting thresholds per domain")
        
        if not recommendations:
            recommendations.append("✅ System is performing well! No major issues detected.")
        
        return recommendations
    
    def create_visualization_plots(self, results: Dict, output_dir: str = "evaluation_plots"):
        """Create visualization plots for the evaluation results"""
        print(f"\n📊 Creating visualization plots in '{output_dir}' directory...")
        
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        plt.style.use('default')
        
        # 1. Similarity Distribution Plot
        if 'threshold_effectiveness' in results:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            # Get similarity data from database
            am_sim_query = "MATCH (a:Article)-[r:RELATED_TO]->(m:Module) WHERE r.similarity_score IS NOT NULL RETURN r.similarity_score as similarity"
            aa_sim_query = "MATCH (a1:Article)-[r:SIMILAR_TO]->(a2:Article) WHERE r.similarity_score IS NOT NULL RETURN r.similarity_score as similarity"
            
            am_sims = [r['similarity'] for r in self.graph.run(am_sim_query).data()]
            aa_sims = [r['similarity'] for r in self.graph.run(aa_sim_query).data()]
            
            if am_sims:
                ax1.hist(am_sims, bins=30, alpha=0.7, color='blue', edgecolor='black')
                ax1.set_title('Article-Module Similarity Distribution')
                ax1.set_xlabel('Similarity Score')
                ax1.set_ylabel('Frequency')
                ax1.axvline(np.mean(am_sims), color='red', linestyle='--', label=f'Mean: {np.mean(am_sims):.3f}')
                ax1.legend()
            
            if aa_sims:
                ax2.hist(aa_sims, bins=30, alpha=0.7, color='green', edgecolor='black')
                ax2.set_title('Article-Article Similarity Distribution')
                ax2.set_xlabel('Similarity Score')
                ax2.set_ylabel('Frequency')
                ax2.axvline(np.mean(aa_sims), color='red', linestyle='--', label=f'Mean: {np.mean(aa_sims):.3f}')
                ax2.legend()
            
            plt.tight_layout()
            plt.savefig(f"{output_dir}/similarity_distributions.png", dpi=300, bbox_inches='tight')
            plt.close()
        
        # 2. Quality Metrics Overview
        if any(key in results for key in ['clustering_quality', 'similarity_accuracy', 'threshold_effectiveness']):
            fig, ax = plt.subplots(figsize=(12, 8))
            
            metrics = []
            values = []
            
            # Collect metrics
            if 'clustering_quality' in results and 'silhouette_score' in results['clustering_quality']:
                metrics.append('Silhouette Score')
                values.append(results['clustering_quality']['silhouette_score'])
            
            if 'similarity_accuracy' in results and 'article_module_accuracy_percentage' in results['similarity_accuracy']:
                metrics.append('AM Accuracy %')
                values.append(results['similarity_accuracy']['article_module_accuracy_percentage'] / 100)
            
            if 'similarity_accuracy' in results and 'article_article_accuracy_percentage' in results['similarity_accuracy']:
                metrics.append('AA Accuracy %')
                values.append(results['similarity_accuracy']['article_article_accuracy_percentage'] / 100)
            
            if 'threshold_effectiveness' in results and 'overall_quality_score' in results['threshold_effectiveness']:
                metrics.append('Overall Quality')
                values.append(results['threshold_effectiveness']['overall_quality_score'])
            
            if metrics:
                colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'][:len(metrics)]
                bars = ax.bar(metrics, values, color=colors, alpha=0.8, edgecolor='black')
                
                # Add value labels on bars
                for bar, value in zip(bars, values):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                           f'{value:.3f}', ha='center', va='bottom', fontweight='bold')
                
                ax.set_title('Relationship Quality Metrics Overview', fontsize=16, fontweight='bold')
                ax.set_ylabel('Score', fontsize=12)
                ax.set_ylim(0, 1.1)
                ax.grid(True, alpha=0.3)
                
                plt.xticks(rotation=45)
                plt.tight_layout()
                plt.savefig(f"{output_dir}/quality_metrics_overview.png", dpi=300, bbox_inches='tight')
                plt.close()
        
        # 3. Technology Domain Coverage
        if 'technology_domain_coverage' in results:
            fig, ax = plt.subplots(figsize=(14, 8))
            
            domains = []
            coverages = []
            
            for domain, data in results['technology_domain_coverage'].items():
                if domain not in ['overall_diversity', 'total_domain_coverage'] and isinstance(data, dict):
                    domains.append(domain.replace('_', ' ').title())
                    coverages.append(data['coverage_ratio'] * 100)
            
            if domains:
                colors = plt.cm.Set3(np.linspace(0, 1, len(domains)))
                bars = ax.bar(domains, coverages, color=colors, alpha=0.8, edgecolor='black')
                
                # Add value labels
                for bar, coverage in zip(bars, coverages):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                           f'{coverage:.1f}%', ha='center', va='bottom', fontweight='bold')
                
                ax.set_title('Technology Domain Coverage', fontsize=16, fontweight='bold')
                ax.set_ylabel('Coverage Percentage (%)', fontsize=12)
                ax.grid(True, alpha=0.3)
                
                plt.xticks(rotation=45)
                plt.tight_layout()
                plt.savefig(f"{output_dir}/technology_domain_coverage.png", dpi=300, bbox_inches='tight')
                plt.close()
        
        print(f"   ✅ Plots saved to '{output_dir}' directory")
    
    def run_comprehensive_evaluation(self) -> Dict[str, Any]:
        """Run all evaluation metrics and return comprehensive results"""
        print("🚀 Starting Comprehensive Relationship Quality Evaluation")
        print("=" * 80)
        print(f"⏰ Timestamp: {self.timestamp}")
        print("=" * 80)
        
        results = {
            'timestamp': self.timestamp,
            'database_stats': {},
            'similarity_accuracy': {},
            'threshold_effectiveness': {},
            'clustering_quality': {},
            'relationship_diversity': {},
            'technology_domain_coverage': {},
            'recommendations': []
        }
        
        try:
            # Run all evaluations
            results['database_stats'] = self.get_database_stats()
            results['similarity_accuracy'] = self.evaluate_similarity_accuracy()
            results['threshold_effectiveness'] = self.evaluate_threshold_effectiveness()
            results['clustering_quality'] = self.evaluate_clustering_quality()
            results['relationship_diversity'] = self.evaluate_relationship_diversity()
            results['technology_domain_coverage'] = self.evaluate_technology_domain_coverage()
            
            # Generate recommendations
            results['recommendations'] = self.generate_recommendations(results)
            
            # Create visualizations
            self.create_visualization_plots(results)
            
            # Print summary
            self.print_evaluation_summary(results)
            
        except Exception as e:
            print(f"❌ Error during evaluation: {e}")
            results['error'] = str(e)
        
        return results
    
    def print_evaluation_summary(self, results: Dict):
        """Print a comprehensive summary of evaluation results"""
        print("\n" + "="*80)
        print("📋 EVALUATION SUMMARY")
        print("="*80)
        
        # Database overview
        if 'database_stats' in results and results['database_stats']:
            stats = results['database_stats']
            print(f"\n📊 DATABASE OVERVIEW:")
            print(f"   📄 Articles: {stats.get('articles_with_embeddings', 0)}")
            print(f"   📚 Modules: {stats.get('modules_with_embeddings', 0)}")
            print(f"   🔗 Total Relationships: {stats.get('total_relationships', 0)}")
        
        # Performance scores
        print(f"\n🎯 PERFORMANCE SCORES:")
        
        if 'similarity_accuracy' in results and results['similarity_accuracy']:
            acc = results['similarity_accuracy']
            am_acc = acc.get('article_module_accuracy_percentage', 0)
            aa_acc = acc.get('article_article_accuracy_percentage', 0)
            print(f"   📊 Article-Module Accuracy: {am_acc:.1f}%")
            print(f"   📊 Article-Article Accuracy: {aa_acc:.1f}%")
        
        if 'threshold_effectiveness' in results and results['threshold_effectiveness']:
            thresh = results['threshold_effectiveness']
            quality = thresh.get('overall_quality_score', 0)
            print(f"   📊 Overall Quality Score: {quality:.3f}")
        
        if 'clustering_quality' in results and results['clustering_quality']:
            cluster = results['clustering_quality']
            silhouette = cluster.get('silhouette_score', 0)
            print(f"   📊 Clustering Quality (Silhouette): {silhouette:.3f}")
        
        # Recommendations
        if 'recommendations' in results and results['recommendations']:
            print(f"\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(results['recommendations'], 1):
                print(f"   {i}. {rec}")
        
        # Technology coverage
        if 'technology_domain_coverage' in results and results['technology_domain_coverage']:
            domain = results['technology_domain_coverage']
            total_coverage = domain.get('total_domain_coverage', 0)
            print(f"\n💻 TECHNOLOGY COVERAGE:")
            print(f"   📊 Total Domain Coverage: {total_coverage:.2f}")
        
        print("\n" + "="*80)
        print("✅ EVALUATION COMPLETED SUCCESSFULLY!")
        print("="*80)

def main():
    """Main function to run the evaluation"""
    evaluator = RelationshipQualityEvaluator()
    
    # Run comprehensive evaluation
    results = evaluator.run_comprehensive_evaluation()
    
    # Save results to JSON
    output_file = f"relationship_evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Convert numpy types to Python types for JSON serialization
    def convert_numpy_types(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy_types(item) for item in obj]
        return obj
    
    results = convert_numpy_types(results)
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Detailed report saved to: {output_file}")
    except Exception as e:
        print(f"❌ Error saving report: {e}")
    
    return results

if __name__ == "__main__":
    main()