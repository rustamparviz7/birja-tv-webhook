import os, json, logging
from datetime import datetime
from flask import Flask, request, jsonify

# === Konfiqurasiya ============================================================
SECRET = os.environ.get("SECRET", "CHANGE_ME_SECRET")
ENABLE_SELFTEST = os.environ.get("ENABLE_SELFTEST", "true").lower() == "true"

app = Flask(__name__)

# Logging konfiqurasiyası
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
app.logger.setLevel(logging.INFO)

# Son qəbul edilən mesaj üçün yaddaş
LAST = {}

# === Util =====================================================================
NUMERIC_FIELDS = {
    "open", "close", "high", "low", "volume",
    "kernel_regression_estimate", "buy", "sell",
    "stopbuy", "stopsell", "backtest_stream",
    "plot_0", "plot_1", "plot_2", "plot_3", "plot_4", "plot_5"
}

def to_float_or_none(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None

def process_and_log(data: dict):
    """Gələn TradingView JSON-u pars et və lokal logs/ altına yaz."""
    payload = data.get("payload", {}) or {}
    parsed = {k: (to_float_or_none(v) if k in NUMERIC_FIELDS else v) for k, v in payload.items()}

    try:
        os.makedirs("logs", exist_ok=True)
        ts_file = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        with open(f"logs/tv_{ts_file}.json", "w", encoding="utf-8") as f:
            json.dump({"raw": data, "parsed": parsed}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return ts, parsed

def log_incoming(tag: str, data: dict, parsed: dict):
    pretty_raw = json.dumps(data, ensure_ascii=False)[:4096]
    pretty_parsed = json.dumps(parsed, ensure_ascii=False)[:4096]

    app.logger.info("%s RAW   : %s", tag, pretty_raw)
    app.logger.info("%s PARSED: %s", tag, pretty_parsed)

    print(f"{tag} | {pretty_parsed}", flush=True)

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
        app.logger.warning("TV NO JSON BODY | headers=%s", dict(request.headers))
        return jsonify(ok=False, error="No JSON body"), 400

    # Auth token
    if data.get("token") != SECRET:
        app.logger.warning("TV BAD TOKEN | got=%s", data.get("token"))
        print("TV BAD TOKEN", flush=True)
        return jsonify(ok=False, error="Bad token"), 403

    ts, parsed = process_and_log(data)

    # Log
    app.logger.info(
        "TV OK | %s %s | o=%s c=%s buy=%s sell=%s",
        parsed.get("ticker"),
        (data.get("payload") or {}).get("interval"),
        parsed.get("open"), parsed.get("close"),
        parsed.get("buy"), parsed.get("sell")
    )

    print(
        f"TV OK | {parsed.get('ticker')} {(data.get('payload') or {}).get('interval')} "
        f"o={parsed.get('open')} c={parsed.get('close')} buy={parsed.get('buy')} sell={parsed.get('sell')}",
        flush=True
    )

    global LAST
    LAST = {"ts": ts, "raw": data, "parsed": parsed}

    log_incoming("TV IN", data, parsed)

    return jsonify(ok=True, received_at=ts, parsed=parsed, raw=data), 200

@app.get("/tv/example")
def tv_example():
    """TradingView Alert Message üçün nümunə JSON."""
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

# === Run (local üçündür) =======================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
