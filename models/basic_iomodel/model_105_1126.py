import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from uuid import uuid4
import os
import sys
from langchain_ollama.llms import OllamaLLM

# Comprehensive library imports
try:
    from langchain_community.graphs import Neo4jGraph
    from langchain.tools import Tool
    from langchain.agents import initialize_agent, AgentType
    from langchain.prompts import PromptTemplate
    from langchain.chains import LLMChain
except ImportError as e:
    print(f"Missing library: {e}")
    print("Please install required libraries:")
    print("pip install langchain langchain-community ollama neo4j")
    sys.exit(1)

class AcademicRAGAssistant:
    def __init__(self, debug_mode=True):
        # 1. Logger Setup
        self.logger = self._setup_logger()
        
        # 2. Session ID initialization
        self.SESSION_ID = str(uuid4())
        self.logger.info(f"Initializing session: {self.SESSION_ID}")
        
        # 3. Configuration Management
        self.debug_mode = debug_mode
        
        # 4. Neo4j Configuration
        self.neo4j_config = {
            "url": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "Mento@2152",
        }
        
        # Initialize Components
        try:
            self._init_components()
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            raise

    def _setup_logger(self):
        """
        Set up comprehensive logging with console and file handlers
        """
        logger = logging.getLogger('AcademicRAG')
        logger.setLevel(logging.DEBUG)
        
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
        
        # Console Handler - Informative output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('🔹 %(levelname)s: %(message)s')
        console_handler.setFormatter(console_format)
        
        # File Handler - Detailed logging
        file_handler = RotatingFileHandler(
            f'logs/academic_rag_{datetime.now().strftime("%Y%m%d")}.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        
        # Add handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger

    def _init_components(self):
        """
        Initialize all necessary components with robust error handling
        """
        # Initialize Local LLM (Ollama)
        try:
            self.llm = OllamaLLM(model="mistral:7b")
            self.logger.info("🤖 Local Language Model initialized successfully")
        except Exception as e:
            self.logger.error(f"LLM initialization failed: {e}")
            raise

        # Initialize Neo4j Graph Database
        try:
            self.graph = Neo4jGraph(**self.neo4j_config)
            self.graph.refresh_schema()
            self.logger.info("🗂️ Neo4j graph connection established")
        except Exception as e:
            self.logger.error(f"Neo4j connection failed: {e}")
            raise

        # Initialize a simple conversational chain
        try:
            # Create a basic prompt template for general conversation
            prompt_template = PromptTemplate(
                input_variables=["input"],
                template="You are an academic assistant. Provide a helpful and informative response to the following: {input}"
            )

            # Create an LLM chain
            self.chat_agent = LLMChain(
                llm=self.llm,
                prompt=prompt_template
            )
            self.logger.info("💬 Conversational agent initialized")
        except Exception as e:
            self.logger.error(f"Chat agent initialization failed: {e}")
            raise

    def invoke(self, message_dict, config_dict=None):
        """
        Handle chat invocations from the API endpoint.
        """
        try:
            user_input = message_dict.get("input", "")
            
            if not user_input:
                return {"output": "Please provide a valid input."}
            
            # Use the chat_agent to generate a response
            response = self.chat_agent.run(user_input)
            
            return {"output": response}
        
        except Exception as e:
            self.logger.error(f"Error processing chat input: {e}")
            return {"output": f"Error: {str(e)}"}
    def advanced_knowledge_graph_query(self, query):
        """
        Enhanced semantic search across courses, modules, and topics
        """
        try:
            comprehensive_query = """
            MATCH (c:Course)
            WHERE 
                toLower(c.name) CONTAINS toLower($query) OR 
                toLower(c.description) CONTAINS toLower($query) OR
                ANY(keyword IN split(toLower($query), ' ') 
                    WHERE toLower(c.name) CONTAINS keyword OR 
                          toLower(c.description) CONTAINS keyword)
            
            OPTIONAL MATCH (c)-[:CONTAINS]->(m:Module)
            WHERE 
                toLower(m.name) CONTAINS toLower($query) OR 
                toLower(m.description) CONTAINS toLower($query)
            
            RETURN 
                DISTINCT c.name AS course_name,
                c.description AS course_description,
                COLLECT(DISTINCT {
                    module_name: m.name,
                    module_description: m.description
                }) AS modules
            LIMIT 3
            """
            
            results = self.graph.query(comprehensive_query, {"query": query})
            
            if not results:
                return f"🔍 Sorry, I couldn't find any courses related to '{query}'. Would you like to explore something different?"
            
            # Conversational response formatting
            responses = []
            for record in results:
                response = f"🚀 Exciting Discovery in '{record['course_name']}'!\n\n"
                response += f"📖 Course Overview: {record['course_description']}\n\n"
                
                if record['modules']:
                    response += "🔍 Relevant Modules:\n"
                    for module in record['modules'][:2]:  # Limit to 2 modules
                        response += f"• {module['module_name']}\n"
                        response += f"  {module['module_description']}\n\n"
                
                response += f"Would you like to know more about {record['course_name']}?"
                responses.append(response)
            
            return "\n\n".join(responses)
        
        except Exception as e:
            self.logger.error(f"Advanced graph query error: {e}")
            return f"🤖 Oops! I encountered an issue while searching. Let's try again."

    def contextual_search(self, query):
        """
        Enhanced contextual search with semantic understanding
        """
        try:
            contextual_query = """
            MATCH (n)
            WHERE 
                toLower(n.name) CONTAINS toLower($query) OR 
                toLower(n.description) CONTAINS toLower($query) OR
                ANY(keyword IN split(toLower($query), ' ') 
                    WHERE toLower(n.name) CONTAINS keyword OR 
                          toLower(n.description) CONTAINS keyword)
            RETURN 
                labels(n) AS node_types,
                n.name AS name,
                n.description AS description
            LIMIT 3
            """
            
            results = self.graph.query(contextual_query, {"query": query})
            
            if not results:
                return f"🔍 No results found for '{query}'. Want to try a different search?"
            
            response = "🌟 Related Insights:\n\n"
            for result in results:
                response += f"🏷️ Type: {', '.join(result['node_types'])}\n"
                response += f"📘 Name: {result.get('name', 'N/A')}\n"
                response += f"💡 Description: {result.get('description', 'No description available')}\n\n"
            
            return response
        
        except Exception as e:
            self.logger.error(f"Contextual search error: {e}")
            return f"🤖 Search encountered an issue: {str(e)}"

    def generate_learning_path(self, subject):
        """
        Generate a potential learning path based on the subject
        """
        try:
            path_query = """
            MATCH (c:Course)-[:CONTAINS]->(m:Module)
            WHERE 
                toLower(c.name) CONTAINS toLower($subject) OR 
                toLower(m.name) CONTAINS toLower($subject)
            RETURN 
                c.name AS course_name,
                COLLECT(DISTINCT m.name) AS modules
            ORDER BY SIZE(modules) DESC
            LIMIT 1
            """
            
            results = self.graph.query(path_query, {"subject": subject})
            
            if not results:
                return f"🤔 I couldn't find a comprehensive learning path for '{subject}'."
            
            result = results[0]
            learning_path = f"🌈 Learning Path for {subject}:\n\n"
            learning_path += f"📚 Recommended Course: {result['course_name']}\n\n"
            learning_path += "🔍 Suggested Learning Modules:\n"
            
            for idx, module in enumerate(result['modules'][:5], 1):
                learning_path += f"{idx}. {module}\n"
            
            learning_path += "\n💡 Tip: Start with the first module and progressively move forward!"
            
            return learning_path
        
        except Exception as e:
            self.logger.error(f"Learning path generation error: {e}")
            return f"🤖 Couldn't generate learning path: {str(e)}"

    def interactive_chat(self):
        """
        Enhanced interactive chat with multiple interaction modes
        """
        print("🎓 Academic Knowledge Explorer")
        print("I'm your AI guide to learning. How can I help you today?")
        print("Commands: 'search', 'path', 'exit'\n")
        
        while True:
            command = input("\n🔍 Choose a mode (search/path/exit): ").strip().lower()
            
            if command == 'exit':
                print("Thank you for exploring with me. Keep learning and growing! 🚀")
                break
            
            if command not in ['search', 'path']:
                print("🤔 Invalid command. Please choose 'search', 'path', or 'exit'.")
                continue
            
            query = input("Enter your query: ").strip()
            
            if len(query.split()) < 2:
                print("🤔 Could you be a bit more specific? Try a more detailed query.")
                continue
            
            if command == 'search':
                graph_result = self.advanced_knowledge_graph_query(query)
                contextual_result = self.contextual_search(query)
                
                print("\n🤖 Search Results:")
                print(graph_result)
                print("\n🌐 Contextual Insights:")
                print(contextual_result)
            
            elif command == 'path':
                learning_path = self.generate_learning_path(query)
                print("\n🚀 Learning Pathway:")
                print(learning_path)
            
            follow_up = input("\nWould you like to continue? (yes/no) ").strip().lower()
            if follow_up not in ['yes', 'y']:
                break
    def invoke(self, message_dict, config_dict=None):
            """
            Handle chat invocations from the API endpoint.
            """
            try:
                user_input = message_dict.get("input", "")
                
                # Process commands if present
                if user_input.startswith('/'):
                    command, query = self._parse_command(user_input[1:])
                    
                    if command == 'search':
                        graph_result = self.advanced_knowledge_graph_query(query)
                        contextual_result = self.contextual_search(query)
                        return {"output": f"Search Results:\n{graph_result}\n\nContextual Insights:\n{contextual_result}"}
                    
                    elif command == 'path':
                        learning_path = self.generate_learning_path(query)
                        return {"output": f"Learning Pathway:\n{learning_path}"}
                
                # Default chat response
                response = self.chat_agent.invoke(
                    {"input": user_input},
                    {"configurable": {"session_id": self.SESSION_ID}}
                )
                return {"output": response["output"]}
            
            except Exception as e:
                self.logger.error(f"Error processing chat input: {e}")
                return {"output": f"Error: {str(e)}"}
        
def main():
    try:
        assistant = AcademicRAGAssistant(debug_mode=True)
        assistant.interactive_chat()
    except Exception as e:
        print(f"❌ Failed to start Academic Assistant: {e}")

if __name__ == "__main__":
    main()