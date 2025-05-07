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
        print("\U0001f4e9 Получен сигнал:", data)

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

        # Расчёт объёма
        qty_step, min_qty, min_notional = get_symbol_filters(symbol)
        balance = get_usdt_balance(API_KEY, API_SECRET)
        qty = calculate_order_qty(balance, leverage, price, qty_step, min_qty, min_notional)

        # Проверка на минимальный номинал
        if qty * price < min_notional:
            raise Exception(f"\u274c Сумма сделки {qty * price:.4f} меньше минимально допустимой {min_notional:.4f}")

        # Создание ордера
        result = place_market_order(symbol, side, qty, API_KEY, API_SECRET)
        return {"status": "success", "details": result}

    except Exception as e:
        print("\u274c Ошибка:", e)
        return {"error": str(e)}


def get_position(symbol, api_key, api_secret):
    url = "https://api.bybit.com/v5/position/list"
    params = {"category": "linear", "symbol": symbol}
    recv_window = 5000
    timestamp = str(int(time.time() * 1000))
    query_string = f"category=linear&symbol={symbol}"
    sign_payload = f"{api_key}{timestamp}{recv_window}{query_string}"
    signature = hmac.new(bytes(api_secret, "utf-8"), bytes(sign_payload, "utf-8"), hashlib.sha256).hexdigest()
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-SIGN": signature,
        "X-BAPI-RECV-WINDOW": str(recv_window),
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    print("\U0001f4e5 Позиция:", data)
    if "result" in data and "list" in data["result"] and len(data["result"]["list"]) > 0:
        pos = data["result"]["list"][0]
        side = pos["side"]
        size = float(pos["size"])
        if size > 0:
            return side
    return None


def close_position(symbol, side, api_key, api_secret):
    url = "https://api.bybit.com/v5/order/create"
    body = {
        "category": "linear",
        "symbol": symbol,
        "side": side,
        "orderType": "Market",
        "reduceOnly": True,
        "timeInForce": "GoodTillCancel",
        "qty": 100
    }
    recv_window = 5000
    timestamp = str(int(time.time() * 1000))
    sign_payload = f"{api_key}{timestamp}{recv_window}{json.dumps(body)}"
    signature = hmac.new(bytes(api_secret, "utf-8"), bytes(sign_payload, "utf-8"), hashlib.sha256).hexdigest()
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-SIGN": signature,
        "X-BAPI-RECV-WINDOW": str(recv_window),
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers, json=body)
    print("\U0001f4e4 Закрытие позиции:", response.json())
    return response.json()


def get_usdt_balance(api_key, api_secret):
    url = "https://api.bybit.com/v5/account/wallet-balance"
    params = {"accountType": "UNIFIED"}
    recv_window = 5000
    timestamp = str(int(time.time() * 1000))
    query_string = "accountType=UNIFIED"
    sign_payload = f"{api_key}{timestamp}{recv_window}{query_string}"
    signature = hmac.new(bytes(api_secret, "utf-8"), bytes(sign_payload, "utf-8"), hashlib.sha256).hexdigest()
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-SIGN": signature,
        "X-BAPI-RECV-WINDOW": str(recv_window),
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    usdt = float(next((item["availableBalance"] for item in data["result"]["list"] if item["coin"] == "USDT"), 0))
    print("\U0001f4b0 Баланс USDT:", usdt)
    return usdt


def get_symbol_filters(symbol):
    url = "https://api.bybit.com/v5/market/instruments-info"
    params = {"category": "linear", "symbol": symbol}
    response = requests.get(url, params=params)
    data = response.json()
    item = data["result"]["list"][0]
    qty_step = float(item["lotSizeFilter"]["qtyStep"])
    min_qty = float(item["lotSizeFilter"]["minOrderQty"])
    min_notional = float(item["lotSizeFilter"].get("minNotionalValue", 0))
    return qty_step, min_qty, min_notional


def calculate_order_qty(balance, leverage, price, qty_step, min_qty, min_notional):
    notional = balance * leverage
    raw_qty = notional / price
    rounded_qty = max(min_qty, round(raw_qty / qty_step) * qty_step)
    print(f"\U0001f4d0 Расчёт объема: balance={balance}, leverage={leverage}, qty={rounded_qty}")
    return rounded_qty


def place_market_order(symbol, side, qty, api_key, api_secret):
    url = "https://api.bybit.com/v5/order/create"
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
    signature = hmac.new(bytes(api_secret, "utf-8"), bytes(sign_payload, "utf-8"), hashlib.sha256).hexdigest()
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-SIGN": signature,
        "X-BAPI-RECV-WINDOW": str(recv_window),
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers, json=body)
    print("\U0001f4e4 Ответ от Bybit:", response.json())
    return response.json()

# === Запуск сервера ===
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
