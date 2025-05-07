from fastapi import FastAPI, Request
import os
import hmac
import hashlib
import time
import json
import requests
import uvicorn

app = FastAPI()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

@app.post("/")
async def webhook(request: Request):
    try:
        data = await request.json()
        print("📩 Получен сигнал:", data)

        symbol = data.get("symbol", "SUIUSDT")
        side = data.get("side", "").upper()
        price = float(data.get("price", 0))
        leverage = int(data.get("leverage", 10))

        # Закрытие противоположной позиции
        current_position = get_position(symbol, API_KEY, API_SECRET)
        if current_position == "Buy" and side == "SELL":
            close_position(symbol, "Sell", API_KEY, API_SECRET)
        elif current_position == "Sell" and side == "BUY":
            close_position(symbol, "Buy", API_KEY, API_SECRET)

        # Расчёт объёма ордера
        qty_step, min_qty, min_notional = get_symbol_filters(symbol)
        balance = get_usdt_balance(API_KEY, API_SECRET)
        qty = calculate_order_qty(balance, leverage, price, qty_step, min_qty, min_notional)

        # Размещение рыночного ордера
        result = place_market_order(symbol, side, qty, API_KEY, API_SECRET)
        return {"status": "success", "details": result}

    except Exception as e:
        print("❌ Ошибка:", e)
        return {"error": str(e)}

def place_market_order(symbol, side, qty, api_key, api_secret):
    url = "https://api.bybit.com/v5/order/create"
    headers = {
        "X-BAPI-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    body = {
        "category": "linear",
        "symbol": symbol,
        "side": "Buy" if side == "BUY" else "Sell",
        "orderType": "Market",
        "qty": qty,
        "timeInForce": "GoodTillCancel",
    }

    recv_window = 5000
    timestamp = str(int(time.time() * 1000))
    sign_payload = f"{api_key}{timestamp}{recv_window}{json.dumps(body)}"

    signature = hmac.new(
        bytes(api_secret, "utf-8"),
        bytes(sign_payload, "utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers.update({
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-SIGN": signature,
        "X-BAPI-RECV-WINDOW": str(recv_window),
    })

    response = requests.post(url, headers=headers, json=body)
    print("📤 Ответ от Bybit:", response.json())
    return response.json()

# ✅ Запуск сервера при запуске main.py
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
