#!/usr/bin/env python3
"""
🔍 Verification Script - Checks if the evaluation system is working correctly
Run this after fixing issues to ensure everything is ready
"""

import sys
import json
from datetime import datetime

def verify_evaluation_system():
    """Verify all components of the evaluation system"""
    print("🔍 EVALUATION SYSTEM VERIFICATION")
    print("=" * 80)
    print(f"⏰ Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    checks_passed = 0
    checks_total = 0
    
    # Check 1: Import modules
    print("\n✓ Checking imports...")
    checks_total += 1
    try:
        from evaluation_metrices import RelationshipQualityEvaluator
        import numpy as np
        from py2neo import Graph
        print("  ✅ All imports successful")
        checks_passed += 1
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
    
    # Check 2: Database connection
    print("\n✓ Checking database connection...")
    checks_total += 1
    try:
        from py2neo import Graph
        graph = Graph("bolt://localhost:7691", auth=("neo4j", "Mento@2152"))
        result = graph.run("RETURN 1 as test").data()
        print("  ✅ Database connection successful")
        checks_passed += 1
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
    
    # Check 3: Article data
    print("\n✓ Checking article data...")
    checks_total += 1
    try:
        article_count = graph.run("MATCH (a:Article) RETURN count(a) as count").data()[0]['count']
        articles_with_embeddings = graph.run(
            "MATCH (a:Article) WHERE a.embedding IS NOT NULL RETURN count(a) as count"
        ).data()[0]['count']
        print(f"  ✅ Found {article_count} articles ({articles_with_embeddings} with embeddings)")
        checks_passed += 1 if articles_with_embeddings > 0 else 0
    except Exception as e:
        print(f"  ❌ Failed to get article data: {e}")
    
    # Check 4: Module data
    print("\n✓ Checking module data...")
    checks_total += 1
    try:
        module_count = graph.run("MATCH (m:Module) RETURN count(m) as count").data()[0]['count']
        modules_with_embeddings = graph.run(
            "MATCH (m:Module) WHERE m.embedding IS NOT NULL RETURN count(m) as count"
        ).data()[0]['count']
        print(f"  ✅ Found {module_count} modules ({modules_with_embeddings} with embeddings)")
        checks_passed += 1 if modules_with_embeddings > 0 else 0
    except Exception as e:
        print(f"  ❌ Failed to get module data: {e}")
    
    # Check 5: Article-Module relationships
    print("\n✓ Checking Article-Module relationships...")
    checks_total += 1
    try:
        am_count = graph.run(
            "MATCH (a:Article)-[r:RELATED_TO]->(m:Module) RETURN count(r) as count"
        ).data()[0]['count']
        print(f"  ✅ Found {am_count} RELATED_TO relationships")
        checks_passed += 1 if am_count > 0 else 0
    except Exception as e:
        print(f"  ❌ Failed to get AM relationships: {e}")
    
    # Check 6: Article-Article relationships
    print("\n✓ Checking Article-Article relationships...")
    checks_total += 1
    try:
        aa_count = graph.run(
            "MATCH (a1:Article)-[r:SIMILAR_TO]->(a2:Article) RETURN count(r) as count"
        ).data()[0]['count']
        print(f"  ✅ Found {aa_count} SIMILAR_TO relationships")
        checks_passed += 1 if aa_count > 0 else 0
    except Exception as e:
        print(f"  ❌ Failed to get AA relationships: {e}")
    
    # Check 7: Evaluator instantiation
    print("\n✓ Checking evaluator instantiation...")
    checks_total += 1
    try:
        from evaluation_metrices import RelationshipQualityEvaluator
        evaluator = RelationshipQualityEvaluator()
        print("  ✅ Evaluator instantiated successfully")
        checks_passed += 1
    except Exception as e:
        print(f"  ❌ Failed to instantiate evaluator: {e}")
    
    # Check 8: Database stats method
    print("\n✓ Checking database stats method...")
    checks_total += 1
    try:
        stats = evaluator.get_database_stats()
        if stats and 'articles_with_embeddings' in stats:
            print(f"  ✅ Database stats retrieved: {stats}")
            checks_passed += 1
        else:
            print("  ❌ Database stats incomplete")
    except Exception as e:
        print(f"  ❌ Failed to get database stats: {e}")
    
    # Check 9: Similarity accuracy method
    print("\n✓ Checking similarity accuracy method...")
    checks_total += 1
    try:
        accuracy = evaluator.evaluate_similarity_accuracy()
        if accuracy:
            print(f"  ✅ Similarity accuracy evaluated")
            if 'article_module_accuracy_percentage' in accuracy:
                am_acc = accuracy['article_module_accuracy_percentage']
                print(f"     → Article-Module: {am_acc:.2f}%")
            if 'article_article_accuracy_percentage' in accuracy:
                aa_acc = accuracy['article_article_accuracy_percentage']
                print(f"     → Article-Article: {aa_acc:.2f}%")
            checks_passed += 1
        else:
            print("  ⚠️ No accuracy data returned (may be normal if few relationships)")
    except Exception as e:
        print(f"  ❌ Failed to evaluate similarity accuracy: {e}")
    
    # Check 10: Threshold effectiveness method
    print("\n✓ Checking threshold effectiveness method...")
    checks_total += 1
    try:
        threshold = evaluator.evaluate_threshold_effectiveness()
        if threshold and 'overall_quality_score' in threshold:
            quality = threshold['overall_quality_score']
            print(f"  ✅ Threshold effectiveness evaluated")
            print(f"     → Overall quality score: {quality:.3f}")
            checks_passed += 1
        else:
            print("  ⚠️ No threshold data returned")
    except Exception as e:
        print(f"  ❌ Failed to evaluate threshold effectiveness: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 80)
    
    score = (checks_passed / checks_total) * 100
    print(f"\nTests Passed: {checks_passed}/{checks_total} ({score:.1f}%)")
    
    if checks_passed == checks_total:
        print("\n✅ ALL CHECKS PASSED!")
        print("   The evaluation system is ready to use.")
        print("\n   Run: python evaluation_metrices.py")
        return True
    elif checks_passed >= checks_total * 0.8:
        print("\n⚠️ MOST CHECKS PASSED")
        print("   Some components may need attention.")
        print("   See failures above for details.")
        return True
    else:
        print("\n❌ CRITICAL ISSUES DETECTED")
        print("   Please resolve the failed checks above.")
        return False

if __name__ == "__main__":
    success = verify_evaluation_system()
    
    print("\n" + "=" * 80)
    if success:
        print("🚀 Status: READY FOR EVALUATION")
        sys.exit(0)
    else:
        print("🔧 Status: NEEDS ATTENTION")
        sys.exit(1)
