"""Unified AI Service provider supporting multiple fallback providers (OpenRouter, Groq, Cerebras, Gemini)."""
import os
import time
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from config.config import logger

class AIService:
    """Unified AI Service orchestrating fallback sequence and status monitoring."""
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AIService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.last_provider_used = "OpenRouter"
        self.last_model_used = "qwen/qwen-2.5-coder-32b-instruct"
        self.last_successful_request = "Never"
        self.average_response_time = 0.0
        self.response_times: List[float] = []
        self.rate_limit_status = "Green"
        self.fallback_status = "No Fallback"
        self.connection_status = "Connected"
        
        logger.info("AI Service initialized with multi-provider fallback sequence.")

    def translate_natural_rule(self, prompt: str) -> str:
        from config.config import (
            OPENROUTER_API_KEY, OPENROUTER_MODEL,
            GROQ_API_KEY, GROQ_MODEL,
            CEREBRAS_API_KEY, CEREBRAS_MODEL,
            GEMINI_API_KEY, GEMINI_MODEL,
            AI_PROVIDER
        )
        
        providers_priority = ["openrouter", "groq", "cerebras", "gemini"]
        preferred = AI_PROVIDER.lower() if AI_PROVIDER else "openrouter"
        if preferred in providers_priority:
            providers_priority.remove(preferred)
            providers_priority.insert(0, preferred)
            
        errors = []
        for provider in providers_priority:
            start_time = time.time()
            try:
                if provider == "openrouter" and OPENROUTER_API_KEY:
                    logger.info(f"Attempting rule translation via OpenRouter ({OPENROUTER_MODEL}).")
                    result = self._call_openrouter(OPENROUTER_MODEL, prompt)
                    self._update_stats("OpenRouter", OPENROUTER_MODEL, time.time() - start_time)
                    return result
                elif provider == "groq" and GROQ_API_KEY:
                    logger.info(f"Attempting rule translation via Groq ({GROQ_MODEL}).")
                    result = self._call_groq(GROQ_MODEL, prompt)
                    self._update_stats("Groq", GROQ_MODEL, time.time() - start_time)
                    return result
                elif provider == "cerebras" and CEREBRAS_API_KEY:
                    logger.info(f"Attempting rule translation via Cerebras ({CEREBRAS_MODEL}).")
                    result = self._call_cerebras(CEREBRAS_MODEL, prompt)
                    self._update_stats("Cerebras", CEREBRAS_MODEL, time.time() - start_time)
                    return result
                elif provider == "gemini" and GEMINI_API_KEY:
                    logger.info(f"Attempting rule translation via Gemini ({GEMINI_MODEL}).")
                    result = self._call_gemini(GEMINI_MODEL, prompt)
                    self._update_stats("Gemini", GEMINI_MODEL, time.time() - start_time)
                    return result
            except Exception as e:
                err_str = str(e)
                logger.warning(f"AI Provider {provider} failed: {err_str}")
                errors.append(f"{provider}: {err_str}")
                
        self.connection_status = "Offline"
        raise ValueError(f"All configured AI providers failed to translate the rule. Errors: {'; '.join(errors)}")

    def _update_stats(self, provider: str, model: str, elapsed: float):
        self.last_provider_used = provider
        self.last_model_used = model
        self.response_times.append(elapsed)
        if len(self.response_times) > 10:
            self.response_times.pop(0)
        self.average_response_time = sum(self.response_times) / len(self.response_times)
        self.last_successful_request = time.strftime("%Y-%m-%d %H:%M:%S")
        self.connection_status = "Connected"
        self.rate_limit_status = "Green"

    def _call_openrouter(self, model: str, prompt: str) -> str:
        from config.config import OPENROUTER_API_KEY
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://unisched.erp",
            "X-Title": "UniSched ERP"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["choices"][0]["message"]["content"]

    def _call_groq(self, model: str, prompt: str) -> str:
        from config.config import GROQ_API_KEY
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["choices"][0]["message"]["content"]

    def _call_cerebras(self, model: str, prompt: str) -> str:
        from config.config import CEREBRAS_API_KEY
        headers = {
            "Authorization": f"Bearer {CEREBRAS_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        req = urllib.request.Request(
            "https://api.cerebras.ai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["choices"][0]["message"]["content"]

    def _call_gemini(self, model: str, prompt: str) -> str:
        from config.config import GEMINI_API_KEY
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["candidates"][0]["content"]["parts"][0]["text"]

    def get_health_status(self) -> Dict[str, Any]:
        from config.config import (
            OPENROUTER_API_KEY, GROQ_API_KEY, CEREBRAS_API_KEY, GEMINI_API_KEY, AI_PROVIDER
        )
        
        providers_priority = ["openrouter", "groq", "cerebras", "gemini"]
        preferred = AI_PROVIDER.lower() if AI_PROVIDER else "openrouter"
        if preferred in providers_priority:
            providers_priority.remove(preferred)
            providers_priority.insert(0, preferred)
            
        fallback_prov = "None"
        for p in providers_priority:
            if p == "openrouter" and OPENROUTER_API_KEY and self.last_provider_used != "OpenRouter":
                fallback_prov = "OpenRouter"
                break
            elif p == "groq" and GROQ_API_KEY and self.last_provider_used != "Groq":
                fallback_prov = "Groq"
                break
            elif p == "cerebras" and CEREBRAS_API_KEY and self.last_provider_used != "Cerebras":
                fallback_prov = "Cerebras"
                break
            elif p == "gemini" and GEMINI_API_KEY and self.last_provider_used != "Gemini":
                fallback_prov = "Gemini"
                break

        return {
            "ai_provider": self.last_provider_used,
            "current_provider": self.last_provider_used,
            "current_model": self.last_model_used,
            "connection_status": self.connection_status,
            "last_successful_request": self.last_successful_request,
            "average_response_time": f"{self.average_response_time:.2f}s",
            "rate_limit_status": self.rate_limit_status,
            "fallback_status": f"Next Fallback: {fallback_prov.upper()}"
        }
