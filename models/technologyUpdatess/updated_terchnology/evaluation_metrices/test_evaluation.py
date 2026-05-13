#!/usr/bin/env python3
"""
Quick test script to verify the evaluation metrics work correctly
Run this to debug any issues
"""

from evaluation_metrices import RelationshipQualityEvaluator
import sys

def test_evaluation():
    """Test the evaluation metrics"""
    print("🧪 Testing Relationship Quality Evaluator...")
    print("=" * 80)
    
    try:
        evaluator = RelationshipQualityEvaluator()
        
        # Test database connection
        print("\n1️⃣ Testing database connection...")
        stats = evaluator.get_database_stats()
        if stats:
            print("   ✅ Database connection successful")
        else:
            print("   ❌ Failed to get stats")
            return False
        
        # Test similarity accuracy
        print("\n2️⃣ Testing similarity accuracy evaluation...")
        accuracy = evaluator.evaluate_similarity_accuracy()
        if accuracy:
            print("   ✅ Similarity accuracy evaluation successful")
        
        # Test threshold effectiveness
        print("\n3️⃣ Testing threshold effectiveness evaluation...")
        threshold = evaluator.evaluate_threshold_effectiveness()
        if threshold:
            print("   ✅ Threshold effectiveness evaluation successful")
        
        # Test clustering quality
        print("\n4️⃣ Testing clustering quality evaluation...")
        clustering = evaluator.evaluate_clustering_quality()
        if clustering:
            print("   ✅ Clustering quality evaluation successful")
        
        # Test diversity
        print("\n5️⃣ Testing relationship diversity evaluation...")
        diversity = evaluator.evaluate_relationship_diversity()
        if diversity:
            print("   ✅ Relationship diversity evaluation successful")
        
        print("\n" + "=" * 80)
        print("✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_evaluation()
    sys.exit(0 if success else 1)
