import requests
import json
import os
import time
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load .env from the project root (two levels up from models/services/)
_env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=_env_path)

class GeminiService:
    def __init__(self, api_key: str = None):
        # Gemini setup
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        
        # Ollama setup (local LLM)
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api/generate")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        
        # Check if Ollama is running
        self.ollama_available = self._check_ollama()

    def _check_ollama(self) -> bool:
        """Check if local Ollama service is running"""
        try:
            # Short timeout just to check connection
            res = requests.get("http://localhost:11434/", timeout=2)
            if res.status_code == 200:
                print(f"[LLM] Ollama is available. Using local model: {self.ollama_model}")
                return True
        except requests.exceptions.RequestException:
            pass
        
        print("[LLM] Ollama not detected. Falling back to Gemini API.")
        return False

    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call local Ollama model"""
        try:
            payload = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False
            }
            # Set high timeout since local LLM inference can take time
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            return result.get("response")
        except Exception as e:
            print(f"[LLM] Ollama inference error: {e}")
            return None

    def _call_gemini(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Call Gemini API with retry logic for rate limits (429)"""
        url = f"{self.gemini_url}?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        headers = {'Content-Type': 'application/json'}
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                
                # If rate limited, wait and retry
                if response.status_code == 429:
                    wait_time = (2 ** attempt) + 2 # Exponential backoff
                    print(f"[LLM] Gemini Rate Limited (429). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                
                result = response.json()
                if 'candidates' in result:
                    return result['candidates'][0]['content']['parts'][0]['text']
                    
                print(f"[LLM] Gemini unexpected format: {json.dumps(result)[:200]}")
                return None
                
            except requests.exceptions.HTTPError as e:
                print(f"[LLM] Gemini HTTP error (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
            except Exception as e:
                print(f"[LLM] Gemini error (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
        
        return None

    def generate_content(self, prompt: str) -> Optional[str]:
        """
        Generate content - tries Ollama first (checks live each call), falls back to Gemini.
        """
        # Re-check Ollama on every call so Flask doesn't need a restart when Ollama starts
        if self._check_ollama():
            result = self._call_ollama(prompt)
            if result:
                return result
            print("[LLM] Ollama failed, falling back to Gemini...")

        # Fallback to Gemini
        return self._call_gemini(prompt)

    def generate_educational_response(self, 
                                   query: str, 
                                   context: Dict[str, Any] = None,
                                   available_courses: list = None) -> str:
        """
        Generate educational response using context
        """
        try:
            history = context.get('history', []) if context else []
            history_text = "\n".join([f"{'User' if m['role'] == 'user' else 'Mento'}: {m['content']}" for m in history[-4:]])
            courses_text = ', '.join(available_courses) if available_courses else 'Not available'
            
            prompt = f"""
            You are Mento AI, an expert university degree advisor for LearNexus. 
            Students come to you because they don't have a clear idea of what course or degree they should do.
            
            Recent Chat History:
            {history_text}
            
            User's latest message: {query}
            
            AVAILABLE DEGREES AT OUR UNIVERSITY (ONLY suggest from this list):
            {courses_text}
            
            Your goal is to:
            1. If they mention their abilities, skills, and likes, suggest the best matching degree from the AVAILABLE DEGREES list above.
            2. If you don't have enough information, politely ask them what they are good at, what they enjoy doing, and what their career goals are.
            3. You MUST ONLY suggest degrees from the AVAILABLE DEGREES list. Do NOT invent or hallucinate other degrees.
            4. Keep responses encouraging, structured, and easy to read.
            5. DO NOT start your response with an introduction like "Hi there, I'm Mento" if you have already introduced yourself in the history.
            
            Response should be in a conversational tone and under 150 words.
            """
            
            response = self.generate_content(prompt)
            return response if response else "I apologize, but I couldn't generate a response at the moment. Please try again."
            
        except Exception as e:
            print(f"[LLM] Error generating educational response: {e}")
            return "I'm sorry, I encountered an error while processing your request."

