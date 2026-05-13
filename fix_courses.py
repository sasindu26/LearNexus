import json
import os
import sys
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Ensure we can import from models
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from models.services.gemini_service import GeminiService

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
dotenv_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path)

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
gemini = GeminiService()

def fix_courses_and_embeddings():
    with driver.session() as session:
        # 1. Find courses without descriptions or embeddings
        result = session.run("MATCH (c:Course) WHERE c.description IS NULL OR c.embedding IS NULL RETURN id(c) AS node_id, c.name AS name, c.description AS desc, c.university AS uni")
        
        for record in result:
            node_id = record["node_id"]
            name = record["name"]
            uni = record["uni"] or "Unknown University"
            desc = record["desc"]
            
            print(f"Fixing course: {name} at {uni}")
            
            if not desc:
                # Generate description
                prompt = f"Write a 2-sentence description for a university degree called '{name}' at '{uni}'. Be professional and concise. Don't use asterisks or markdown formatting."
                desc = gemini.generate_content(prompt)
                if not desc:
                    desc = f"A comprehensive {name} degree program offering advanced knowledge and practical skills."
                
                print(f"Generated description: {desc}")
                session.run("MATCH (c:Course) WHERE id(c) = $node_id SET c.description = $desc", node_id=node_id, desc=desc)
            
            # Generate embedding for the name + description
            text_to_embed = f"{name}. {desc}"
            embedding = embedding_model.encode(text_to_embed).tolist()
            
            session.run("MATCH (c:Course) WHERE id(c) = $node_id SET c.embedding = $embedding", node_id=node_id, embedding=embedding)
            print(f"Generated and saved embedding for {name}")

def generate_modules_for_course(course_name: str, university: str):
    print(f"\nChecking modules for {course_name}...")
    with driver.session() as session:
        # Check if it already has modules
        result = session.run("MATCH (c:Course {name: $course_name})-[:CONTAINS]->(m:Module) RETURN count(m) AS c", course_name=course_name)
        count = result.single()["c"]
        if count > 0:
            print(f"{course_name} already has {count} modules. Skipping module generation.")
            return

        print(f"Generating modules and resources for {course_name}...")
        prompt = f"""
        Generate a JSON array of 4 core modules for a university degree called '{course_name}' at '{university}'.
        For each module, assign it to a 'level' (1, 2, 3, 4 representing the academic year).
        For each module, provide a list of 2 key topics.
        For each topic, provide 1 resource (a realistic name and an example URL like 'https://example.com/topic-guide').
        Format STRICTLY as valid JSON.
        Example:
        [
          {{
            "name": "Module Name",
            "description": "Module description",
            "level": 1,
            "topics": [
              {{
                "name": "Topic Name",
                "description": "Topic Description",
                "resources": [
                  {{"name": "Resource Book", "type": "article", "url": "https://example.com/book"}}
                ]
              }}
            ]
          }}
        ]
        """
        
        response_text = gemini.generate_content(prompt)
        
        try:
            # Clean up markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                
            modules_data = json.loads(response_text)
            
            for mod in modules_data:
                # Create Module
                session.run("""
                MATCH (c:Course {name: $course_name})
                MERGE (m:Module {name: $mod_name})
                SET m.description = $mod_desc, m.level = $mod_level
                MERGE (c)-[:CONTAINS]->(m)
                """, course_name=course_name, mod_name=mod['name'], mod_desc=mod['description'], mod_level=mod['level'])
                
                for topic in mod.get('topics', []):
                    # Create Topic
                    session.run("""
                    MATCH (m:Module {name: $mod_name})
                    MERGE (t:Topic {name: $topic_name})
                    SET t.description = $topic_desc
                    MERGE (m)-[:HAS_TOPIC]->(t)
                    """, mod_name=mod['name'], topic_name=topic['name'], topic_desc=topic['description'])
                    
                    for res in topic.get('resources', []):
                        # Create Resource
                        session.run("""
                        MATCH (t:Topic {name: $topic_name})
                        MATCH (m:Module {name: $mod_name})
                        MERGE (r:Resource {name: $res_name})
                        SET r.type = $res_type, r.url = $res_url
                        MERGE (m)-[:HAS_RESOURCE]->(r)
                        """, topic_name=topic['name'], mod_name=mod['name'], res_name=res['name'], res_type=res.get('type', 'article'), res_url=res['url'])
            
            print(f"Successfully generated and inserted modules for {course_name}")
            
        except Exception as e:
            print(f"Failed to parse or insert modules for {course_name}: {e}")
            print(f"Raw response: {response_text}")


if __name__ == '__main__':
    fix_courses_and_embeddings()
    generate_modules_for_course("Computer Security", "NSBM Green University")
    generate_modules_for_course("Artificial Intelligence (Plymouth)", "Plymouth University")
    print("\nAll database fixes complete.")
