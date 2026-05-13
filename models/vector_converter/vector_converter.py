from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase

# Set up your Neo4j connection
neo4j_url = "bolt://localhost:7687"
neo4j_user = "neo4j"
neo4j_password = "Mento@2152"

# Initialize the sentence transformer model for generating embeddings
model = SentenceTransformer('all-MiniLM-L6-v2')

# Connect to the Neo4j database
driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))

def generate_and_store_embeddings():
    with driver.session() as session:
        # Fetch all courses from Neo4j
        courses = session.run("MATCH (c:Course) RETURN c.name AS name, c.description AS description")

        for course in courses:
            course_name = course["name"]
            course_description = course["description"]

            # Generate embeddings for the course name and description
            course_text = f"{course_name} {course_description}"  # Combining both for better embedding
            embedding = model.encode(course_text).tolist()  # Convert numpy array to list for Neo4j storage

            # Store the embedding in the Course node
            session.run(
                "MATCH (c:Course {name: $name}) "
                "SET c.embedding = $embedding",
                name=course_name,
                embedding=embedding
            )
            print(f"Embedding added to course: {course_name}")

# Run the function to generate and store embeddings
generate_and_store_embeddings()

# Close the Neo4j connection after use
driver.close()
