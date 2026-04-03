"""Grocery classifier Flask app with routed and omni classification endpoints."""

import asyncio
import json
import os

from flask import Flask, request, jsonify
from agentic_engine import orchestrate

# Load .env
_dir = os.path.dirname(os.path.abspath(__file__))
_env = os.path.join(_dir, ".env")
if os.path.exists(_env):
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if value and key not in os.environ:
                    os.environ[key] = value

os.chdir(_dir)

app = Flask(__name__)


def extract_taxonomy_path(output):
    """Walk nested route output to build taxonomy path from route keys."""
    path = []
    current = output
    while isinstance(current, dict) and "route" in current:
        route = current["route"]
        if route == "_none":
            break
        path.append(route)
        current = current.get("result")
    return path


def run_async(coro):
    """Run an async coroutine from sync Flask context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.route("/classify")
def classify():
    items_param = request.args.get("items", "")
    if not items_param:
        return jsonify({"error": "items query parameter required"}), 400

    items = [i.strip() for i in items_param.split(",") if i.strip()]
    results = []

    for item in items:
        envelope = run_async(orchestrate("grocery-classify", {"item_name": item}))
        classification = (envelope.get("result") or envelope.get("output") or {}).get("classification", {})
        taxonomy_path = extract_taxonomy_path(classification)

        # Get leaf agent details — walk past all route wrappers to the leaf output
        leaf_details = classification
        while isinstance(leaf_details, dict) and "route" in leaf_details:
            leaf_details = leaf_details.get("result", {})
        if not isinstance(leaf_details, dict):
            leaf_details = {}

        results.append({
            "item": item,
            "taxonomy_path": taxonomy_path,
            "workflow": "grocery-classify",
            "details": leaf_details if isinstance(leaf_details, dict) else {},
        })

    return jsonify({"results": results})


@app.route("/omni-classify")
def omni_classify():
    items_param = request.args.get("items", "")
    if not items_param:
        return jsonify({"error": "items query parameter required"}), 400

    items = [i.strip() for i in items_param.split(",") if i.strip()]
    results = []

    for item in items:
        envelope = run_async(orchestrate("omni-classify", {"item_name": item}))
        classification = (envelope.get("result") or envelope.get("output") or {}).get("classification", {})
        taxonomy_path = classification.get("taxonomy_path", [])
        confidence = classification.get("confidence", 0)
        reasoning = classification.get("reasoning", "")

        results.append({
            "item": item,
            "taxonomy_path": taxonomy_path,
            "workflow": "omni-classify",
            "details": {"confidence": confidence, "reasoning": reasoning},
        })

    return jsonify({"results": results})


if __name__ == "__main__":
    app.run(debug=True, port=8000)
