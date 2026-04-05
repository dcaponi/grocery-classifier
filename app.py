"""Grocery classifier Flask app with hierarchical and omni classification endpoints.

Each run saves its workflow trail to tmp/runs/ for visualization.
Visit /viz to see an interactive graph of all recorded runs.
"""

import asyncio
import json
import os
import time
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from agentic_engine import orchestrate

# ── Bootstrap ───────────────────────────────────────────────────────────────

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

RUNS_DIR = Path(_dir) / "tmp" / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)


# ── Helpers ─────────────────────────────────────────────────────────────────

def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def save_run(item_name: str, workflow: str, envelope: dict) -> str:
    """Persist a run envelope to tmp/runs/ and return the filename."""
    ts = int(time.time() * 1000)
    safe_name = item_name.replace(" ", "_").replace("/", "_")[:40]
    fname = f"{ts}_{safe_name}.json"
    run_data = {
        "item_name": item_name,
        "workflow": workflow,
        "envelope": envelope,
    }
    (RUNS_DIR / fname).write_text(json.dumps(run_data, indent=2, default=str))
    return fname


def extract_taxonomy_from_steps(envelope: dict) -> tuple[list[str], dict]:
    """Extract [department, category] path and leaf details from v4 envelope steps."""
    steps = {s["step_id"]: s for s in envelope.get("steps", []) if s.get("status") == "success"}
    path = []
    leaf_details = {}

    # Department
    dept_step = steps.get("department")
    if dept_step and isinstance(dept_step.get("output"), dict):
        dept = dept_step["output"].get("department", "")
        if dept:
            path.append(dept)

    # Sub-category — find whichever category classifier ran
    category_step_ids = [
        "produce-category", "meat-seafood-category", "deli-bakery-category",
        "dairy-eggs-category", "frozen-category", "pantry-category",
        "snacks-category", "beverages-category", "health-wellness-category",
        "personal-care-category", "household-category", "baby-pet-category",
    ]
    for sid in category_step_ids:
        if sid in steps and isinstance(steps[sid].get("output"), dict):
            cat = steps[sid]["output"].get("category", "")
            if cat:
                path.append(cat)
            break

    # Leaf details
    leaf_step = steps.get("leaf")
    if leaf_step and isinstance(leaf_step.get("output"), dict):
        leaf_details = leaf_step["output"]

    return path, leaf_details


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.route("/classify")
def classify():
    items_param = request.args.get("items", "")
    if not items_param:
        return jsonify({"error": "items query parameter required"}), 400

    items = [i.strip() for i in items_param.split(",") if i.strip()]
    results = []

    for item in items:
        envelope = run_async(orchestrate("grocery-classify", {"item_name": item}))
        taxonomy_path, leaf_details = extract_taxonomy_from_steps(envelope)
        save_run(item, "grocery-classify", envelope)

        results.append({
            "item": item,
            "taxonomy_path": taxonomy_path,
            "workflow": "grocery-classify",
            "details": leaf_details,
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
        classification = envelope.get("output", {}).get("classification", {})
        taxonomy_path = classification.get("taxonomy_path", [])
        confidence = classification.get("confidence", 0)
        reasoning = classification.get("reasoning", "")
        save_run(item, "omni-classify", envelope)

        results.append({
            "item": item,
            "taxonomy_path": taxonomy_path,
            "workflow": "omni-classify",
            "details": {"confidence": confidence, "reasoning": reasoning},
        })

    return jsonify({"results": results})


@app.route("/runs")
def list_runs():
    """Return all saved runs as JSON."""
    runs = []
    for f in sorted(RUNS_DIR.glob("*.json"), reverse=True):
        runs.append(json.loads(f.read_text()))
    return jsonify(runs)


@app.route("/viz")
def viz():
    return send_from_directory("static", "viz.html")


if __name__ == "__main__":
    app.run(debug=True, port=8000)
