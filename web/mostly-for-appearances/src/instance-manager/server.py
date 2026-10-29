import logging

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, request

import orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

sched = BackgroundScheduler(daemon=True)
sched.add_job(orchestrator.cleanup_expired, "interval", minutes=60)
sched.start()


@app.route("/")
def index():
    with open("/sha", "r") as s:
        return f"instance-manager\nversion: {s.read()}"


@app.route("/readyz")
def ready():
    return "OK\n"


@app.route("/available", methods=["GET"])
def available():
    try:
        ext = orchestrator.reserve_extension()
    except RuntimeError:
        return jsonify({"error": "no extensions available"}), 507
    except Exception:
        logger.exception("Failed to reserve extension")
        return jsonify({"error": "failed to reserve extension"}), 500

    return jsonify({"ext": ext}), 200


@app.route("/new", methods=["POST"])
def new():
    ext = request.args.get("ext")
    if not ext:
        return {"error": "missing ext parameter"}, 400

    try:
        info = orchestrator.deploy_extension(ext)
    except ValueError as e:
        return {"error": str(e)}, 409
    except Exception:
        logger.exception(f"Failed to deploy extension {ext}")
        return {"error": "failed to deploy kubernetes resources"}, 500

    return info, 201


@app.route("/info", methods=["GET"])
def info():
    ext = request.args.get("ext")
    if not ext:
        return {"error": "missing ext parameter"}, 400

    try:
        result = orchestrator.get_extension_info(ext)
    except Exception:
        logger.exception(f"Failed to look up extension {ext}")
        return {"error": "internal error"}, 500

    if result is None:
        return {"error": "extension not found"}, 404

    return result, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
