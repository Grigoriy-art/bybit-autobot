@app.post("/")
async def webhook(request: Request):
    try:
        body = (await request.body()).decode("utf-8")
        print("📥 Сырой JSON:", body)

        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка разбора JSON: {e}")
            return {"error": "Invalid JSON", "details": str(e)}

        print("✅ Получен сигнал:", data)

        symbol = data.get("symbol", "").upper()
        side = data.get("side", "").upper()
        qty = float(data.get("qty", 10))
        leverage = int(data.get("leverage", 10))

        if not symbol or side not in ["BUY", "SELL"]:
            return {"error": "Неверный формат сигнала"}

        current_position = get_position(symbol)
        if current_position == "Buy" and side == "SELL":
            print("🔁 Закрываем Buy → открываем Sell")
            close_position(symbol, "Buy")
        elif current_position == "Sell" and side == "BUY":
            print("🔁 Закрываем Sell → открываем Buy")
            close_position(symbol, "Sell")

        result = place_market_order(symbol, side, qty)
        print("📤 Ордер отправлен:", result)
        return {"status": "success", "details": result}

    except Exception as e:
        print("🔥 Общая ошибка обработки запроса:", str(e))
        return {"error": "Internal Server Error", "details": str(e)}
