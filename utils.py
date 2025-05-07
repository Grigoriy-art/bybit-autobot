import requests, time, hmac, hashlib, json

def generate_signature(api_key, api_secret, timestamp, method, endpoint, body=""):
    param_str = str(timestamp) + api_key + "5000" + method + endpoint + body
    hash = hmac.new(bytes(api_secret, "utf-8"), param_str.encode("utf-8"), hashlib.sha256)
    return hash.hexdigest()

def get_symbol_filters(symbol):
    url = f"https://api.bybit.com/v5/market/instruments-info?category=linear&symbol={symbol}"
    response = requests.get(url).json()
    info = response["result"]["list"][0]
    return float(info["lotSizeFilter"]["qtyStep"]), float(info["lotSizeFilter"]["minOrderQty"]), float(info["minNotionalValue"])

def get_usdt_balance(api_key, api_secret):
    url = "https://api.bybit.com/v5/account/wallet-balance?accountType=UNIFIED"
    ts = str(int(time.time() * 1000))
    sign = generate_signature(api_key, api_secret, ts, "GET", "/v5/account/wallet-balance")

    headers = {
        "X-BYBIT-API-KEY": api_key,
        "X-BYBIT-API-SIGN": sign,
        "X-BYBIT-API-TIMESTAMP": ts,
        "X-BYBIT-API-RECV-WINDOW": "5000"
    }
    res = requests.get(url, headers=headers).json()
    return float(res["result"]["list"][0]["totalEquity"])

def calculate_order_qty(balance, leverage, price, qty_step, min_qty, min_notional):
    raw_qty = (balance * leverage) / price
    rounded_qty = max(min_qty, round(raw_qty / qty_step) * qty_step)
    if rounded_qty * price < min_notional:
        raise ValueError("Объём сделки ниже допустимого")
    return rounded_qty

def place_market_order(symbol, side, qty, api_key, api_secret):
    url = "https://api.bybit.com/v5/order/create"
    ts = str(int(time.time() * 1000))
    body = {
        "category": "linear",
        "symbol": symbol,
        "side": side.upper(),
        "orderType": "Market",
        "qty": str(qty),
        "timeInForce": "GoodTillCancel"
    }

    sign = generate_signature(api_key, api_secret, ts, "POST", "/v5/order/create", json.dumps(body))

    headers = {
        "X-BYBIT-API-KEY": api_key,
        "X-BYBIT-API-SIGN": sign,
        "X-BYBIT-API-TIMESTAMP": ts,
        "X-BYBIT-API-RECV-WINDOW": "5000",
        "Content-Type": "application/json"
    }

    res = requests.post(url, headers=headers, json=body)
    return res.json()

