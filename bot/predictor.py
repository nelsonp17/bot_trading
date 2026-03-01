import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class GeminiPredictor:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model_id = "gemini-2.0-flash" # Modelo rápido y eficiente para trading

    def get_prediction(self, df):
        """
        Envía los últimos datos OHLCV a Gemini y obtiene una predicción.
        """
        # Preparar los últimos 20 registros para el contexto
        recent_data = df.tail(20).to_string(index=False)
        
        prompt = f"""
        Actúa como un experto Analista de Criptomonedas y Trader Algorítmico.
        Analiza los siguientes datos históricos de {os.getenv('SYMBOL', 'BTC/USDT')} (OHLCV):
        
        {recent_data}
        
        Basado en la acción del precio y el volumen, responde EXCLUSIVAMENTE en formato JSON con la siguiente estructura:
        {{
            "signal": "BUY" | "SELL" | "HOLD",
            "confidence": 0.0 a 1.0,
            "reasoning": "Breve explicación técnica de 1 frase"
        }}
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            # El SDK de google-genai devuelve el objeto parsed si usamos JSON mode
            return response.parsed
            
        except Exception as e:
            print(f"[!] Error consultando a Gemini: {e}")
            return {"signal": "HOLD", "confidence": 0, "reasoning": "Error en API"}
