"""Google GenAI SDK abstraction layer for Gemini 3.5 Flash."""
import os
from google import genai
from config import GEMINI_MODEL, GEMINI_API_KEY, logger

class GeminiAIClient:
    """Handles prompt construction and rules translation using the new google-genai SDK."""
    
    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = GEMINI_MODEL):
        self.api_key = api_key
        self.model = model
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Google GenAI client initialized successfully.")
                # Verify connection with a simple test before using it
                try:
                    self.client.models.generate_content(
                        model=self.model,
                        contents="ping"
                    )
                    logger.info(f"Gemini connection verified successfully using model: {self.model}")
                except Exception as conn_err:
                    logger.error(f"Gemini connection verification failed for model {self.model}: {conn_err}")
            except Exception as e:
                logger.error(f"Failed to initialize GenAI client: {e}")
        else:
            logger.warning("GEMINI_API_KEY not found in environment. Mock fallbacks will be used.")

    def translate_natural_rule(self, prompt: str) -> str:
        """Sends natural language scheduling rule translation prompt to Gemini."""
        if not self.client:
            raise ValueError("Gemini AI Client is not configured. Add GEMINI_API_KEY to environment.")
        
        try:
            logger.debug(f"Calling Gemini with model={self.model} for rule parsing.")
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API generation content failed: {e}")
            raise e
