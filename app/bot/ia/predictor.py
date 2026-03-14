import os
import json
from abc import ABC, abstractmethod
from google import genai
from google.genai import types
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

try:
    from app.bot.indicators import add_all_indicators, get_indicators_summary
except ImportError:
    add_all_indicators = None
    get_indicators_summary = None


def validate_execution_plan(plan, current_price, min_notional=10.0):
    """
    Valida que el plan de ejecución sea seguro y válido.
    Retorna (is_valid, error_message)
    """
    if not plan:
        return False, "Plan vacío o None"

    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except json.JSONDecodeError:
            return False, "JSON inválido"

    execution_plan = plan.get("execution_plan", plan)
    if not execution_plan:
        return False, "No existe execution_plan"

    entry = execution_plan.get("entry_config", {})
    exit_cfg = execution_plan.get("exit_config", {})
    safety = execution_plan.get("safety_cushion", {})

    trigger_price = entry.get("trigger_price")
    allocated = entry.get("allocated_capital_usdt", 0)
    tp = exit_cfg.get("take_profit")
    sl = exit_cfg.get("stop_loss")
    min_alert = safety.get("min_price_alert")
    max_alert = safety.get("max_price_alert")

    if (
        not trigger_price
        or not isinstance(trigger_price, (int, float))
        or trigger_price <= 0
    ):
        return False, "trigger_price inválido o no especificado"

    if not allocated or allocated <= 0:
        return False, "allocated_capital_usdt inválido"

    if allocated < min_notional:
        return False, f"Monto menor al mínimo ({min_notional} USDT)"

    if not tp or not isinstance(tp, (int, float)) or tp <= 0:
        return False, "take_profit inválido"

    if not sl or not isinstance(sl, (int, float)) or sl <= 0:
        return False, "stop_loss inválido"

    if tp <= trigger_price:
        return False, "TP debe ser mayor al precio de entrada"

    if sl >= trigger_price:
        return False, "SL debe ser menor al precio de entrada"

    if sl >= tp:
        return False, "SL debe ser menor que TP"

    if current_price:
        if trigger_price > current_price * 1.05:
            return (
                False,
                f"Precio de entrada {trigger_price} muy lejos del actual {current_price} (>5%)",
            )

        if sl < current_price * 0.90:
            return False, f"SL {sl} representa más del 10% de pérdida"

        if safety:
            if min_alert and max_alert:
                if current_price < min_alert or current_price > max_alert:
                    return (
                        False,
                        f"Precio actual fuera del rango seguro [{min_alert}-{max_alert}]",
                    )

    return True, "OK"


def validate_market_rank(rankings):
    """
    Valida que el ranking de mercado sea válido.
    """
    if not rankings:
        return False, "Ranking vacío"

    if isinstance(rankings, str):
        try:
            rankings = json.loads(rankings)
        except json.JSONDecodeError:
            return False, "JSON inválido"

    if isinstance(rankings, dict):
        rankings = rankings.get("rankings", [])

    if not rankings or not isinstance(rankings, list):
        return False, "Formato de ranking inválido"

    for item in rankings:
        if not isinstance(item, dict):
            return False, "Item del ranking no es un objeto"

        required = ["symbol", "rank", "expected_profit_pct", "expected_loss_pct"]
        for field in required:
            if field not in item:
                return False, f"Campo requerido ausente: {field}"

    return True, rankings


class BasePredictor(ABC):
    @abstractmethod
    def get_prediction(self, df, balance=None, history=None):
        pass

    @abstractmethod
    def get_market_rank(self, market_data, capital, quote, market_type="spot"):
        pass

    @abstractmethod
    def get_execution_plan(
        self, symbol, df, balance, recommendation, market_type="spot", timeframe="1h"
    ):
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
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            data = response.parsed
            if "min_price" not in data:
                data["min_price"] = 0
            if "max_price" not in data:
                data["max_price"] = float("inf")
            return data
        except Exception as e:
            print(f"[!] Error Gemini: {e}")
            return {
                "signal": "MANTENER",
                "confidence": 0,
                "reasoning": str(e),
                "min_price": 0,
                "max_price": float("inf"),
            }

    def get_market_rank(self, market_data, capital, quote, market_type="spot"):
        num_assets = len(market_data) if isinstance(market_data, list) else "todos los"
        prompt = f"""Actúa como un Analista de Inteligencia de Mercado Cripto experto en {market_type.upper()}. 
        Tu tarea es evaluar una lista de criptomonedas y determinar el ranking de rentabilidad para invertir {capital} {quote}.

        MERCADO: {market_type.upper()}
        (Nota: Evalúa los riesgos específicos. En FUTUROS, sé estricto con el riesgo pero clasifica los activos del mejor al peor).

        DATOS DE MERCADO:
        {market_data}

        Debes incluir en el ranking los {num_assets} activos proporcionados, ordenados de mayor a menor oportunidad.
        Para cada moneda, analiza:
        1. **Rentabilidad Esperada:** % de ganancia estimada.
        2. **Riesgo:** % de pérdida potencial (Stop Loss sugerido).
        3. **Volatilidad:** Clasifícala (Baja, Media, Alta, Extrema).
        4. **Estrategia:** (ej. Breakout, Swing, Scalping).
        5. **Timeframe Recomendado:** (15m, 1h, 4h, 1d).
        6. **Gas/Fees:** Estimación de comisiones.

        Responde en una LISTA de objetos JSON:
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
                    "reasoning": "Justificación técnica detallada en español para el mercado {market_type}"
                }},
                ...
            ]
        }}
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            return response.parsed.get("rankings", [])
        except Exception as e:
            print(f"[!] Error Gemini Scanner: {e}")
            return []

    def get_execution_plan(
        self, symbol, df, balance, recommendation, market_type="spot", timeframe="1h"
    ):
        recent_data = df.tail(30).to_string(index=False)

        # Agregar indicadores técnicos si están disponibles
        indicators_info = ""
        if add_all_indicators and get_indicators_summary:
            try:
                df_with_indicators = add_all_indicators(df)
                indicators_info = get_indicators_summary(df_with_indicators)
            except Exception as e:
                print(f"[!] Error calculando indicadores: {e}")

        prompt = f"""Actúa como un Ingeniero de Software Senior y Trader experto en {market_type.upper()}.
        Tu tarea es generar un "Plan de Ejecución Blindado" (Contrato) para el activo {symbol}.

        CONTEXTO TÉCNICO:
        - MERCADO: {market_type.upper()} (Si es FUTURE, considera apalancamiento implícito y riesgos de liquidación. Si es SPOT, gestión de holdings).
        - TIMEFRAME ANALIZADO: {timeframe}
        - RECOMENDACIÓN INICIAL: {recommendation}
        - LÍMITE DE PRESUPUESTO ASIGNADO: {balance["total_budget_assigned"]} USDT (No sugieras invertir más de esto en total).
        - BALANCE REAL DISPONIBLE EN EXCHANGE: {balance["real_account_usdt_available"]} USDT.
        
        DATOS RECIENTES (OHLCV):
        {recent_data}
        
        {indicators_info}

        TAREAS DE RAZONAMIENTO:
        1. **Cojín de Seguridad IA:** Calcula el `min_price_alert` y `max_price_alert` basándote en soportes/resistencias y volatilidad actual. Si el precio sale de aquí, el bot pidió re-evaluación.
        2. **Estrategia de Entrada:** Define el precio gatillo ideal usando los indicadores (RSI, MACD, BB).
        3. **Gestión de Salida:** Define Take Profit y Stop Loss lógicos para {market_type}. Usa ATR para volatilidad.

        INSTRUCCIONES:
        Genera un JSON imperativo siguiendo ESTRICTAMENTE esta estructura:
        {{
          "operation_id": "string_unico",
          "status": "WAITING_FOR_ENTRY",
          "pair": "{symbol}",
          "strategy_type": "string",
           "timeframe_ref": "{timeframe}",
          "expiration_date": "ISO_DATE_STRING (max 2 meses)",
          "execution_plan": {{
            "entry_config": {{
              "trigger_price": float,
              "order_type": "LIMIT_BUY",
              "allocated_capital_usdt": float (DENTRO DEL LÍMITE ASIGNADO),
              "smart_capital_mode": true
            }},
            "exit_config": {{
              "take_profit": float,
              "stop_loss": float,
              "trailing_stop_activation_price": float,
              "trailing_stop_distance_percent": float
            }},
            "safety_cushion": {{
              "min_price_alert": float (CALCULADO POR IA),
              "max_price_alert": float (CALCULADO POR IA),
              "emergency_reasoning_trigger": "OUT_OF_RANGE"
            }}
          }},
          "metadata": {{
            "reasoning_summary": "Justificación para {market_type}",
            "risk_score": 1-5
          }}
        }}
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            return response.parsed
        except Exception as e:
            print(f"[!] Error Gemini Plan: {e}")
            return None

    def _get_prompt(self, data, balance, history):
        balance_info = (
            f"BALANCE ACTUAL: {balance}" if balance else "Balance no disponible"
        )
        history_info = (
            f"HISTORIAL RECIENTE: {history}" if history else "Sin historial previo"
        )

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
        balance_info = (
            f"BALANCE ACTUAL: {balance}" if balance else "Balance no disponible"
        )

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
                response_format={"type": "json_object"},
            )
            import json

            data = json.loads(response.choices[0].message.content)
            if "min_price" not in data:
                data["min_price"] = 0
            if "max_price" not in data:
                data["max_price"] = float("inf")
            if "required_threshold" not in data:
                data["required_threshold"] = 0.60
            if "trade_amount" not in data:
                data["trade_amount"] = 0
            return data
        except Exception as e:
            print(f"[!] Error DeepSeek: {e}")
            return {
                "signal": "MANTENER",
                "confidence": 0,
                "required_threshold": 1.0,
                "reasoning": str(e),
                "min_price": 0,
                "max_price": float("inf"),
            }

    def get_market_rank(self, market_data, capital, quote, market_type="spot"):
        num_assets = len(market_data) if isinstance(market_data, list) else "todos los"
        prompt = f"""Actúa como un Analista de Inteligencia de Mercado Cripto experto en {market_type.upper()}. 
        Tu tarea es evaluar una lista de criptomonedas y determinar el ranking de rentabilidad para invertir {capital} {quote}.

        MERCADO: {market_type.upper()}
        (Nota: Evalúa los riesgos específicos de {market_type.upper()}. En FUTUROS, sé estricto con el riesgo pero clasifica los activos del mejor al peor).

        DATOS DE MERCADO:
        {market_data}

        Debes incluir en el ranking los {num_assets} activos proporcionados, ordenados de mayor a menor oportunidad.
        Para cada moneda, analiza:
        1. **Rentabilidad Esperada:** % de ganancia estimada.
        2. **Riesgo:** % de pérdida potencial (Stop Loss sugerido).
        3. **Volatilidad:** Clasifícala (Baja, Media, Alta, Extrema).
        4. **Estrategia:** (ej. Breakout, Swing, Scalping). Adapta la estrategia al mercado {market_type}.
        5. **Timeframe Recomendado:** (15m, 1h, 4h, 1d).
        6. **Gas/Fees:** Estimación de comisiones.

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
                    "reasoning": "Justificación técnica detallada en español considerando que es mercado {market_type}"
                }},
                ...
            ]
        }}
        """
        import json
        import re

        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )

            response_text = response.choices[0].message.content

            try:
                data = json.loads(response_text)
                return data.get("rankings", [])
            except json.JSONDecodeError as e:
                print(f"[!] Error DeepSeek: JSON inválido, intentando reparar...")
                match = re.search(r"\{[\s\S]*\}", response_text)
                if match:
                    try:
                        data = json.loads(match.group(0))
                        return data.get("rankings", [])
                    except:
                        pass
                rankings = self._extract_rankings_fallback(response_text)
                if rankings:
                    return rankings
                print(f"[!] Error DeepSeek Scanner: No se pudo parsear JSON")
                return []
        except Exception as e:
            print(f"[!] Error DeepSeek Scanner: {e}")
            return []

    def _extract_rankings_fallback(self, text):
        """Intenta extraer rankings de texto no estructurado."""
        import re
        import json

        rankings = []
        pattern = r'\{[^{}]*"symbol"[^{}]*\}'
        matches = re.findall(pattern, text)
        for i, match in enumerate(matches):
            try:
                item = json.loads(match)
                if "symbol" in item and "rank" not in item:
                    item["rank"] = i + 1
                rankings.append(item)
            except:
                continue
        return rankings

    def get_execution_plan(
        self, symbol, df, balance, recommendation, market_type="spot", timeframe="1h"
    ):
        recent_data = df.tail(30).to_string(index=False)

        indicators_info = ""
        if add_all_indicators and get_indicators_summary:
            try:
                df_with_indicators = add_all_indicators(df)
                indicators_info = get_indicators_summary(df_with_indicators)
            except Exception as e:
                print(f"[!] Error calculando indicadores: {e}")

        prompt = f"""Actúa como un Ingeniero Senior y Trader de {market_type.upper()}.
        Genera un "Plan de Ejecución Blindado" JSON para {symbol}.

        MERCADO: {market_type.upper()}
        TIMEFRAME ANALIZADO: {timeframe}
        PRESUPUESTO ASIGNADO: {balance["total_budget_assigned"]} USDT
        BALANCE REAL: {balance["real_account_usdt_available"]} USDT
        DATOS: {recent_data}
        
        {indicators_info}

        Define un Cojín de Seguridad IA (min/max price alert) y parámetros de entrada/salida.
        Responde ESTRICTAMENTE en JSON:
        {{
          "operation_id": "string",
          "status": "WAITING_FOR_ENTRY",
          "pair": "{symbol}",
          "strategy_type": "string",
           "timeframe_ref": "{timeframe}",
          "expiration_date": "ISO_DATE",
          "execution_plan": {{
            "entry_config": {{ "trigger_price": float, "order_type": "LIMIT_BUY", "allocated_capital_usdt": float, "smart_capital_mode": true }},
            "exit_config": {{ "take_profit": float, "stop_loss": float, "trailing_stop_activation_price": float, "trailing_stop_distance_percent": float }},
            "safety_cushion": {{ "min_price_alert": float, "max_price_alert": float, "emergency_reasoning_trigger": "OUT_OF_RANGE" }}
          }},
          "metadata": {{ "reasoning_summary": "string", "risk_score": int }}
        }}"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            import json

            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"[!] Error DeepSeek Plan: {e}")
            return None


def get_predictor(provider="gemini"):
    if provider.lower() == "deepseek":
        return DeepSeekPredictor()
    else:
        return GeminiPredictor()
