import os
from abc import ABC, abstractmethod
from google import genai
from google.genai import types
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class BasePredictor(ABC):
    @abstractmethod
    def get_prediction(self, df):
        pass

class GeminiPredictor(BasePredictor):
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model_id = "gemini-2.0-flash"

    def get_prediction(self, df):
        recent_data = df.tail(20).to_string(index=False)
        prompt = self._get_prompt(recent_data)
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return response.parsed
        except Exception as e:
            print(f"[!] Error Gemini: {e}")
            return {"signal": "HOLD", "confidence": 0, "reasoning": str(e)}

    def _get_prompt(self, data):
        return f"Analiza estos datos de trading y responde en JSON {{'signal': 'BUY'|'SELL'|'HOLD', 'confidence': 0-1, 'reasoning': 'string'}}: {data}"

class DeepSeekPredictor(BasePredictor):
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model_id = "deepseek-chat"

    def get_prediction(self, df):
        recent_data = df.tail(20).to_string(index=False)
        prompt = f"Actúa como un trader experto. Analiza estos datos OHLCV y responde únicamente en formato JSON con 'signal', 'confidence' y 'reasoning':\n{recent_data}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            import json
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"[!] Error DeepSeek: {e}")
            return {"signal": "HOLD", "confidence": 0, "reasoning": str(e)}

def get_predictor(provider="gemini"):
    """Factory para obtener el predictor seleccionado."""
    if provider.lower() == "deepseek":
        print("[*] Usando DeepSeek como motor de IA")
        return DeepSeekPredictor()
    else:
        print("[*] Usando Google Gemini como motor de IA")
        return GeminiPredictor()
