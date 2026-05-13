#!/usr/bin/env python3
"""
Utility script to test module content extraction directly
"""
import os
import sys
import json
import argparse

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.append(project_root)

# Import the ModuleContentExtractor class
from models.module_content.module_content import ModuleContentExtractor
from config.logging_config import setup_logger

# Setup logger
logger = setup_logger('test_script', 'test_module_content.log')

def test_module_content(module_name):
    """
    Test extracting module content for a given module name
    """
    print(f"\nTesting module content extraction for: '{module_name}'")
    print("-" * 50)
    
    content_extractor = ModuleContentExtractor()
    try:
        print("Connecting to Neo4j database...")
        print("Extracting topics...")
        
        topics = content_extractor.get_module_content(module_name)
        
        print(f"\nFound {len(topics)} topics for module '{module_name}':")
        if topics:
            for idx, topic in enumerate(topics, 1):
                print(f"\n{idx}. {topic.get('topic', 'Unnamed Topic')}")
                print(f"   {topic.get('description', 'No description available')[:100]}...")
            
            print("\nComplete JSON output:")
            print(json.dumps(topics, indent=2))
        else:
            print("No topics found.")
            
        return topics
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        content_extractor.close()

def main():
    parser = argparse.ArgumentParser(description='Test module content extraction')
    parser.add_argument('module_name', nargs='?', default=None, help='Module name to test')
    args = parser.parse_args()
    
    if args.module_name:
        test_module_content(args.module_name)
    else:
        # Test multiple known module names
        test_modules = [
            "Human Computer Interaction",
 ]
        
        print("\nTesting multiple module names:\n")
        for module in test_modules:
            result = test_module_content(module)
            if result:
                print(f"\n✅ Successfully retrieved {len(result)} topics for '{module}'")
            else:
                print(f"\n❌ Failed to retrieve topics for '{module}'")
            print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
