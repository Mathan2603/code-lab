from flask import Flask, jsonify, render_template, request

from bot import TradingBot

app = Flask(__name__)
BOT = TradingBot()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    return jsonify(BOT.status())


@app.route("/trades")
def trades():
    return jsonify(BOT.get_trades())


@app.route("/errors")
def errors():
    return jsonify(BOT.get_errors())


@app.route("/start", methods=["POST"])
def start():
    payload = request.get_json(silent=True) or {}
    tokens = payload.get("tokens", [])
    if not isinstance(tokens, list):
        return jsonify({"ok": False, "message": "Tokens must be a list"}), 400
    tokens = [str(token) for token in tokens]
    BOT.set_tokens(tokens)
    BOT.start()
    return jsonify({"ok": True})


@app.route("/stop", methods=["POST"])
def stop():
    BOT.stop()
    return jsonify({"ok": True})


# Manual test results (local):
# - Unable to start Flask server because Flask is not installed in the sandbox.
# - Ran one bot polling cycle directly with dummy tokens via Python; completed without crash.
# - Groww API calls errored with dummy tokens and were logged without crashing.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
