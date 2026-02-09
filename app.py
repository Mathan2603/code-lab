from flask import Flask, jsonify, render_template, request
from bot import TradingBot

app = Flask(__name__)

state = {
    "running": False,
    "tokens": ["", "", "", "", ""],
    "index_ltp": {},
    "monthly_ltp": {},
    "weekly_ltp": {},
    "nearest_strikes": [],
    "trades": [],
    "errors": [],
    "price_history": {},
    "weekly_cycle": 0,
    "last_cycle": None,
}

bot = TradingBot(state)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    return jsonify({
        "running": state["running"],
        "last_cycle": state["last_cycle"],
        "index_ltp": state["index_ltp"],
        "weekly_ltp": state["weekly_ltp"],
    })


@app.route("/trades")
def trades():
    return jsonify(state["trades"])


@app.route("/errors")
def errors():
    return jsonify(state["errors"][-100:])


@app.route("/start", methods=["POST"])
def start():
    data = request.get_json() or {}
    tokens = data.get("tokens", [])

    if len(tokens) != 5:
        return jsonify({"error": "Exactly 5 tokens required"}), 400

    active = [t for t in tokens if t.strip()]
    if len(active) < 2:
        return jsonify({"error": "At least 2 active tokens required"}), 400

    state["tokens"] = tokens
    bot.update_tokens(tokens)

    if not state["running"]:
        bot.start()

    return jsonify({"status": "started"})


@app.route("/stop", methods=["POST"])
def stop():
    bot.stop()
    return jsonify({"status": "stopped"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
