from neo4j import GraphDatabase
from transformers import pipeline
from langchain_ollama.llms import OllamaLLM
class Neo4jHandler:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def find_modules_by_course(self, course_name):
        query = """
        MATCH (c:Course)-[:CONTAINS]->(m:Module)
        WHERE toLower(c.name) CONTAINS toLower($course_name)
        RETURN c.name AS course, collect(m.name) AS modules
        """
        with self.driver.session() as session:
            result = session.run(query, course_name=course_name)
            return result.single()

# Initialize Neo4j and LLM
db = Neo4jHandler(uri="bolt://localhost:7687", user="neo4j", password="Mento@2152")
llm = OllamaLLM(
                model="mistral:7b",
                temperature=0.7,)

def preprocess_query(query):
    irrelevant_words = {"i", "love", "to", "learn", "the"}
    return " ".join(word for word in query.lower().split() if word not in irrelevant_words)


MAX_MODULES = 10

def create_llm_prompt(course, modules):
    if len(modules) > MAX_MODULES:
        modules_to_display = modules[:MAX_MODULES]
        remaining = len(modules) - MAX_MODULES
        prompt = (
            f"The course '{course}' includes several modules. Here are some examples: "
            f"{', '.join(modules_to_display)}. "
            f"There are {remaining} more modules in this course. "
            "Could you provide an overview for a beginner?"
        )
    else:
        prompt = (
            f"The course '{course}' includes the following modules: {', '.join(modules)}. "
            "Could you provide an overview for a beginner?"
        )
    return prompt


def main():
    print("Welcome to the Course Assistant!")
    while True:
        prompt = input("Enter your query (or type 'exit' to quit): ")
        if prompt.lower() == "exit":
            print("Goodbye!")
            break
        
        processed_prompt = preprocess_query(prompt)
        print(f"Processed Query: {processed_prompt}")  # Debugging
        search_result = db.find_modules_by_course(processed_prompt)
        
        if not search_result:
            print("No matching courses found. Try a different query.")
            continue
        
        course = search_result["course"]
        modules = search_result["modules"]
        print(f"Search Result: {course}, Modules: {modules}")  # Debugging
        
        llm_prompt = create_llm_prompt(course, modules)
        print(f"LLM Prompt: {llm_prompt}")  # Debugging
        
        response = llm.invoke(llm_prompt,num_return_sequences=1)
        print(f"Raw LLM Response: {response}")  # Debugging

        # Adjust response handling based on format
        if isinstance(response, list):
            print("AI Assistant Response:")
            print(response[0])  # Use the first item if it's a list
        elif isinstance(response, str):
            print("AI Assistant Response:")
            print(response)  # Directly print if it's a string
        else:
            print("Unexpected response format. Please check the LLM output.")

if __name__ == "__main__":
    main()
