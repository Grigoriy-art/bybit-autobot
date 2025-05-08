from fastapi import FastAPI, Request
import os
import hmac
import hashlib
import time
import json
import requests
import uvicorn
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

@app.post("/")
async def webhook(request: Request):
    try:
        data = await request.json()
        print("📩 Получен сигнал:", data)

        symbol = data.get("symbol", "").upper()
        side = data.get("side", "").upper()  # BUY или SELL
        qty = float(data.get("qty", 10))
        leverage = int(data.get("leverage", 10))

        if not symbol or side not in ["BUY", "SELL"]:
            return {"error": "Неверный формат сигнала"}

        # Проверка и закрытие противоположной позиции
        current_position = get_position(symbol)
        if current_position == "Buy" and side == "SELL":
            print("🔁 Закрываем Buy → открываем Sell")
            close_position(symbol, "Sell")
        elif current_position == "Sell" and side == "BUY":
            print("🔁 Закрываем Sell → открываем Buy")
            close_position(symbol, "Buy")

        # Размещаем ордер
        result = place_market_order(symbol, side, qty)
        print("📤 Ордер отправлен:", result)
        return {"status": "success", "details": result}

    except Exception as e:
        print("❌ Ошибка:", e)
        return {"error": str(e)}

# Получение позиции
def get_position(symbol):
    url = "https://api.bybit.com/v5/position/list"
    params = {"category": "linear", "symbol": symbol}
    headers = signed_headers(params)
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    print("📥 Текущая позиция:", data)
    if "result" in data and "list" in data["result"] and len(data["result"]["list"]) > 0:
        pos = data["result"]["list"][0]
        if float(pos["size"]) > 0:
            return pos["side"]
    return None

# Закрытие позиции
def close_position(symbol, side):
    url = "https://api.bybit.com/v5/order/create"
    body = {
        "category": "linear",
        "symbol": symbol,
        "side": side,
        "orderType": "Market",
        "reduceOnly": True,
        "qty": 100,  # Можно заменить на get_position_size() при необходимости
        "timeInForce": "GoodTillCancel"
    }
    headers = signed_headers(body)
    response = requests.post(url, headers=headers, json=body)
    print("📤 Закрытие позиции:", response.json())
    return response.json()

# Размещение рыночного ордера
def place_market_order(symbol, side, qty):
    url = "https://api.bybit.com/v5/order/create"
    body = {
        "category": "linear",
        "symbol": symbol,
        "side": "Buy" if side == "BUY" else "Sell",
        "orderType": "Market",
        "qty": qty,
        "timeInForce": "GoodTillCancel"
    }
    headers = signed_headers(body)
    response = requests.post(url, headers=headers, json=body)
    return response.json()

# Генерация заголовков с подписью
def signed_headers(payload_dict_or_params):
    recv_window = 5000
    timestamp = str(int(time.time() * 1000))
    if isinstance(payload_dict_or_params, dict):
        body = json.dumps(payload_dict_or_params)
        sign_payload = f"{API_KEY}{timestamp}{recv_window}{body}"
    else:
        qs = "&".join(f"{k}={v}" for k, v in payload_dict_or_params.items())
        sign_payload = f"{API_KEY}{timestamp}{recv_window}{qs}"
    signature = hmac.new(bytes(API_SECRET, "utf-8"), bytes(sign_payload, "utf-8"), hashlib.sha256).hexdigest()
    return {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-SIGN": signature,
        "X-BAPI-RECV-WINDOW": str(recv_window),
        "Content-Type": "application/json"
    }

# Запуск локально (не нужен на Fly.io, только для тестов)
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
