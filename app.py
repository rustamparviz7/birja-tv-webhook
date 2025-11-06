import os, json
from datetime import datetime
from flask import Flask, request, jsonify

# === Konfiqurasiya (env-dən gəlir) ============================================
SECRET = os.environ.get("SECRET", "CHANGE_ME_SECRET")   # Render-də env kimi ver
ENABLE_SELFTEST = os.environ.get("ENABLE_SELFTEST", "true").lower() == "true"

app = Flask(__name__)

# Son qəbul edilən mesaj üçün sadə yaddaş (RAM)
LAST = {}

# === Util =====================================================================
NUMERIC_FIELDS = {
    "open","close","high","low","volume",
    "kernel_regression_estimate","buy","sell",
    "stopbuy","stopsell","backtest_stream",
    "plot_0","plot_1","plot_2","plot_3","plot_4","plot_5"
}

def to_float_or_none(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None

def process_and_log(data: dict):
    """Gələn TradingView JSON-u pars et və logs/ altına yaz."""
    payload = data.get("payload", {}) or {}
    parsed = {k: (to_float_or_none(v) if k in NUMERIC_FIELDS else v) for k, v in payload.items()}

    # Ephemeral mühitlər üçün fayla yazmaq şərt deyil; amma lokal üçün saxlayırıq
    os.makedirs("logs", exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    with open(f"logs/tv_{ts}.json", "w", encoding="utf-8") as f:
        json.dump({"raw": data, "parsed": parsed}, f, ensure_ascii=False, indent=2)
    return ts, parsed

# === Routes ===================================================================
@app.get("/")
def home():
    return {"ok": True, "service": "Birja TV Webhook", "time": datetime.utcnow().isoformat()}

@app.get("/healthz")
def health():
    return {"status": "ok"}

@app.post("/tv")
def tv():
    data = request.get_json(silent=True, force=True)
    if not data:
        return jsonify(ok=False, error="No JSON body"), 400

    # Sadə auth token
    if data.get("token") != SECRET:
        app.logger.warning("TV BAD TOKEN")
        return jsonify(ok=False, error="Bad token"), 403

    ts, parsed = process_and_log(data)

    # >>> LOGS-a görünən, aydın sətir
    app.logger.info(
        "TV OK | %s %s | o=%s c=%s buy=%s sell=%s",
        parsed.get("ticker"),
        (data.get("payload") or {}).get("interval"),
        parsed.get("open"), parsed.get("close"),
        parsed.get("buy"), parsed.get("sell"),
    )

    # >>> Son mesajı yadda saxla
    global LAST
    LAST = {"ts": ts, "raw": data, "parsed": parsed}

    # Postman üçün daha dolğun cavab
    return jsonify(ok=True, received_at=ts, parsed=parsed, raw=data), 200

@app.get("/tv/example")
def tv_example():
    """TradingView Alert Message üçün nümunə JSON (copy-paste)."""
    return {
        "token": SECRET,
        "source": "tradingview",
        "payload": {
            "ticker": "{{ticker}}",
            "exchange": "{{exchange}}",
            "interval": "{{interval}}",
            "time": "{{time}}",
            "timenow": "{{timenow}}",
            "open": "{{open}}",
            "close": "{{close}}",
            "high": "{{high}}",
            "low": "{{low}}",
            "volume": "{{volume}}",
            "currency": "{{syminfo.currency}}",
            "basecurrency": "{{syminfo.basecurrency}}",
            "kernel_regression_estimate": "{{plot(\"Kernel Regression Estimate\")}}",
            "buy": "{{plot(\"Buy\")}}",
            "sell": "{{plot(\"Sell\")}}",
            "stopbuy": "{{plot(\"StopBuy\")}}",
            "stopsell": "{{plot(\"StopSell\")}}",
            "backtest_stream": "{{plot(\"Backtest Stream\")}}",
            "plot_0": "{{plot_0}}",
            "plot_1": "{{plot_1}}",
            "plot_2": "{{plot_2}}",
            "plot_3": "{{plot_3}}",
            "plot_4": "{{plot_4}}",
            "plot_5": "{{plot_5}}"
        }
    }

# Özündən test (prod-da söndürmək üçün ENABLE_SELFTEST=false ver)
@app.get("/tv/selftest")
def tv_selftest():
    if not ENABLE_SELFTEST:
        return jsonify(ok=False, error="selftest disabled"), 403

    q = request.args
    token = q.get("token", SECRET)
    payload = {
        "ticker": q.get("ticker", "BTCUSD"),
        "exchange": q.get("exchange", "BINANCE"),
        "interval": q.get("interval", "3"),
        "time": q.get("time", "2025-11-06 22:30:00"),
        "timenow": q.get("timenow", "2025-11-06 22:30:01"),
        "open": q.get("open", "100"),
        "close": q.get("close", "101"),
        "high": q.get("high", "102"),
        "low": q.get("low", "99.5"),
        "volume": q.get("volume", "12345"),
        "currency": q.get("currency", "USD"),
        "basecurrency": q.get("basecurrency", "BTC"),
        "kernel_regression_estimate": q.get("kre", "100.8"),
        "buy": q.get("buy", "0"),
        "sell": q.get("sell", "1"),
        "stopbuy": q.get("stopbuy", "0"),
        "stopsell": q.get("stopsell", "1"),
        "backtest_stream": q.get("bt", "0"),
        "plot_0": q.get("plot_0", "0"),
        "plot_1": q.get("plot_1", "0"),
        "plot_2": q.get("plot_2", "0"),
        "plot_3": q.get("plot_3", "0"),
        "plot_4": q.get("plot_4", "0"),
        "plot_5": q.get("plot_5", "0"),
    }
    data = {"token": token, "source": "selftest", "payload": payload}

    if data.get("token") != SECRET:
        return jsonify(ok=False, error="Bad token in selftest"), 403

    ts, parsed = process_and_log(data)

    # Log sətiri selftest üçün də
    app.logger.info(
        "SELFTEST OK | %s %s | o=%s c=%s",
        parsed.get("ticker"), payload.get("interval"),
        parsed.get("open"), parsed.get("close"),
    )

    global LAST
    LAST = {"ts": ts, "raw": data, "parsed": parsed}

    return jsonify(ok=True, mode="selftest", received_at=ts, sent=payload, parsed=parsed), 200

# Son gələn mesajı göstərən endpoint
@app.get("/last")
def last():
    if not LAST:
        return {"ok": False, "error": "no messages yet"}, 404
    return {"ok": True, **LAST}

# === Local dev / Render entrypoint ============================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5087))  # Render PORT verir
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port)
    except Exception:
        app.run(host="0.0.0.0", port=port)
