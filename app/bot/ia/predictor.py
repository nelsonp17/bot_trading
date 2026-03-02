import os
from abc import ABC, abstractmethod
from google import genai
from google.genai import types
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class BasePredictor(ABC):
    @abstractmethod
    def get_prediction(self, df, balance=None, history=None):
        pass

    @abstractmethod
    def get_market_rank(self, market_data, capital, quote):
        pass


class GeminiPredictor(BasePredictor):
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model_id = "gemini-2.0-flash"

    def get_prediction(self, df, balance=None, history=None):
        recent_data = df.tail(20).to_string(index=False)
        prompt = self._get_prompt(recent_data, balance, history)
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            data = response.parsed
            if "min_price" not in data: data["min_price"] = 0
            if "max_price" not in data: data["max_price"] = float('inf')
            return data
        except Exception as e:
            print(f"[!] Error Gemini: {e}")
            return {"signal": "MANTENER", "confidence": 0, "reasoning": str(e), "min_price": 0,
                    "max_price": float('inf')}

    def get_market_rank(self, market_data, capital, quote):
        prompt = f"""Actúa como un Analista de Inteligencia de Mercado Cripto. 
        Tu tarea es evaluar una lista de criptomonedas y determinar cuáles son las más rentables para invertir {capital} {quote}.

        DATOS DE MERCADO:
        {market_data}

        Para cada moneda, analiza:
        1. **Rentabilidad Esperada:** % de ganancia estimada.
        2. **Riesgo:** % de pérdida potencial (Stop Loss sugerido).
        3. **Volatilidad:** Clasifícala (Baja, Media, Alta, Extrema).
        4. **Estrategia:** (ej. Breakout, Swing, Scalping).
        5. **Timeframe Recomendado:** (15m, 1h, 4h, 1d).
        6. **Gas/Fees:** Estimación de comisiones de red.

        Responde en una LISTA de objetos JSON ordenada por RANK (el más rentable primero):
        {{
            "rankings": [
                {{
                    "symbol": "BTC/USDT",
                    "rank": 1,
                    "expected_profit_pct": float,
                    "expected_loss_pct": float,
                    "volatility": "Alta",
                    "recommended_strategy": "string",
                    "recommended_timeframe": "1h",
                    "gas_fee_estimate": float,
                    "reasoning": "Resumen de por qué es rentable en español"
                }},
                ...
            ]
        }}
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return response.parsed.get("rankings", [])
        except Exception as e:
            print(f"[!] Error Gemini Scanner: {e}")
            return []

    def _get_prompt(self, data, balance, history):
        balance_info = f"BALANCE ACTUAL: {balance}" if balance else "Balance no disponible"
        history_info = f"HISTORIAL RECIENTE: {history}" if history else "Sin historial previo"

        return f"""Actúa como un gestor de fondos (Fund Manager) y trader de crecimiento.
        Tu objetivo es gestionar un presupuesto asignado para maximizar ganancias minimizando el drawdown.

        CONTEXTO:
        - {balance_info}
        - {history_info}
        
        REGLAS DE GESTIÓN DE CAPITAL:
        1. **Monto Dinámico (trade_amount):** Debes decidir cuántos USDT invertir en esta operación específica. 
           - Si la confianza es alta (>80%) y la tendencia es clara, puedes arriesgar una parte mayor del presupuesto (ej. 20-30%).
           - Si la confianza es baja o hay mucha volatilidad, usa un monto pequeño (ej. 5-10%) o MANTENER.
           - NUNCA sugieras un monto mayor al USDT disponible en el presupuesto.
        2. **Consciencia de Cartera:** Si ya tienes el activo (SOL), evalúa si vale la pena comprar más (promediar) o simplemente MANTENER/VENTA.
        3. **Umbral Dinámico:** Define 'required_threshold' (float entre 0.0 y 1.0). Es el nivel de confianza mínimo que exiges para ejecutar esta señal.

        Responde ESTRICTAMENTE en JSON:
        {{
            'signal': 'COMPRA'|'VENTA'|'MANTENER',
            'confidence': 0.0 a 1.0,
            'trade_amount': float (USDT a invertir si es COMPRA),
            'required_threshold': float (Confianza mínima entre 0.0 y 1.0),
            'reasoning': 'Justificación técnica y financiera en español.',
            'min_price': float,
            'max_price': float
        }}
        
        DATOS DE MERCADO (OHLCV):
        {data}"""


class DeepSeekPredictor(BasePredictor):
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model_id = "deepseek-chat"

    def get_prediction(self, df, balance=None, history=None):
        recent_data = df.tail(20).to_string(index=False)
        balance_info = f"BALANCE ACTUAL: {balance}" if balance else "Balance no disponible"

        prompt = f"""Actúa como un gestor de fondos (Fund Manager) y trader de crecimiento.
        Tu objetivo es gestionar un presupuesto asignado para maximizar ganancias.

        CONTEXTO:
        - {balance_info}
        - Mercado OHLCV reciente.

        TAREAS:
        1. **Monto Dinámico (trade_amount):** Decide cuántos USDT invertir de tu presupuesto disponible.
        2. **Umbral Dinámico:** Define 'required_threshold' (float entre 0.0 y 1.0). Es la confianza mínima para ejecutar la señal.
        3. **Colchón:** Define min_price y max_price seguros.

        Responde ESTRICTAMENTE en JSON:
        {{
            "signal": "COMPRA"|"VENTA"|"MANTENER",
            "confidence": 0.0 a 1.0,
            "trade_amount": float,
            "required_threshold": float (0.0 a 1.0),
            "reasoning": "Explicación técnica en español justificando el monto y la señal",
            "min_price": float,
            "max_price": float
        }}
        
        Datos:\n{recent_data}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            import json
            data = json.loads(response.choices[0].message.content)
            if "min_price" not in data: data["min_price"] = 0
            if "max_price" not in data: data["max_price"] = float('inf')
            if "required_threshold" not in data: data["required_threshold"] = 0.60
            if "trade_amount" not in data: data["trade_amount"] = 0
            return data
        except Exception as e:
            print(f"[!] Error DeepSeek: {e}")
            return {"signal": "MANTENER", "confidence": 0, "required_threshold": 1.0, "reasoning": str(e),
                    "min_price": 0, "max_price": float('inf')}

    def get_market_rank(self, market_data, capital, quote):
        prompt = f"""Actúa como un Analista de Inteligencia de Mercado Cripto. 
        Tu tarea es evaluar una lista de criptomonedas y determinar cuáles son las más rentables para invertir {capital} {quote}.

        DATOS DE MERCADO:
        {market_data}

        Para cada moneda, analiza:
        1. **Rentabilidad Esperada:** % de ganancia estimada.
        2. **Riesgo:** % de pérdida potencial (Stop Loss sugerido).
        3. **Volatilidad:** Clasifícala (Baja, Media, Alta, Extrema).
        4. **Estrategia:** (ej. Breakout, Swing, Scalping).
        5. **Timeframe Recomendado:** (15m, 1h, 4h, 1d).
        6. **Gas/Fees:** Estimación de comisiones de red.

        Responde ESTRICTAMENTE en JSON con una LISTA de objetos ordenada por RANK (el más rentable primero):
        {{
            "rankings": [
                {{
                    "symbol": "BTC/USDT",
                    "rank": 1,
                    "expected_profit_pct": float,
                    "expected_loss_pct": float,
                    "volatility": "Alta",
                    "recommended_strategy": "string",
                    "recommended_timeframe": "1h",
                    "gas_fee_estimate": float,
                    "reasoning": "Resumen de por qué es rentable en español"
                }},
                ...
            ]
        }}
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            import json
            data = json.loads(response.choices[0].message.content)
            return data.get("rankings", [])
        except Exception as e:
            print(f"[!] Error DeepSeek Scanner: {e}")
            return []


def get_predictor(provider="gemini"):
    """Factory para obtener el predictor seleccionado."""
    if provider.lower() == "deepseek":
        print("[*] Usando DeepSeek como motor de IA")
        return DeepSeekPredictor()
    else:
        print("[*] Usando Google Gemini como motor de IA")
        return GeminiPredictor()
