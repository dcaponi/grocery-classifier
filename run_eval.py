"""Eval harness: runs both classification workflows against ground truth items.

Supports multiple models — rewrites router/agent YAML files with the target
model before each run, clears loader caches, and restores originals after.

Usage:
    python run_eval.py                          # default model only (gpt-4.1-mini)
    python run_eval.py gpt-4.1-mini gpt-4.1-nano deepseek-chat
"""

import asyncio
import glob
import json
import os
import re
import sys

_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(_dir)
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

from agentic_engine import orchestrate
from agentic_engine.loader import clear_caches


# -- YAML model swapping -----------------------------------------------------

MODEL_RE = re.compile(r"^(model:\s*)(.+)$", re.MULTILINE)

def find_yaml_files():
    """Find all router.yaml and agent.yaml files."""
    files = glob.glob("routers/*/router.yaml") + glob.glob("agents/*/agent.yaml")
    return sorted(files)


def read_originals(yaml_files):
    """Read and store original contents of all YAML files."""
    originals = {}
    for path in yaml_files:
        with open(path) as f:
            originals[path] = f.read()
    return originals


def swap_model(yaml_files, originals, model):
    """Rewrite all YAML files with the given model, clear loader caches."""
    for path in yaml_files:
        content = originals[path]
        new_content = MODEL_RE.sub(rf"\g<1>{model}", content)
        with open(path, "w") as f:
            f.write(new_content)
    clear_caches()


def restore_originals(yaml_files, originals):
    """Restore all YAML files to their original contents."""
    for path in yaml_files:
        with open(path, "w") as f:
            f.write(originals[path])
    clear_caches()


# -- Classification -----------------------------------------------------------

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


def format_path(path):
    return " > ".join(path) if path else "(none)"


async def classify_item(item_name, workflow_name):
    try:
        envelope = await orchestrate(workflow_name, {"item_name": item_name})
        classification = (envelope.get("result") or envelope.get("output") or {}).get("classification", {})
        if workflow_name == "grocery-classify":
            return extract_taxonomy_path(classification)
        else:
            return classification.get("taxonomy_path", [])
    except Exception as e:
        print(f"  ERROR classifying '{item_name}' with {workflow_name}: {e}", file=sys.stderr)
        return []


# -- Single model eval run ----------------------------------------------------

async def run_eval_for_model(items, model_name):
    """Run eval for a single model. Returns (routed_correct, omni_correct, results)."""
    routed_correct = 0
    omni_correct = 0
    results = []

    for i, entry in enumerate(items):
        item = entry["item"]
        expected = entry["expected_path"]

        print(f"  [{i+1}/{len(items)}] {item}...", end="", flush=True)

        routed_path, omni_path = await asyncio.gather(
            classify_item(item, "grocery-classify"),
            classify_item(item, "omni-classify"),
        )

        routed_match = routed_path == expected
        omni_match = omni_path == expected

        if routed_match:
            routed_correct += 1
        if omni_match:
            omni_correct += 1

        if routed_match and omni_match:
            match_str = "both correct"
        elif routed_match and not omni_match:
            match_str = "omni wrong"
        elif not routed_match and omni_match:
            match_str = "routed wrong"
        else:
            match_str = "BOTH WRONG"

        results.append({
            "item": item,
            "expected": expected,
            "routed": routed_path,
            "omni": omni_path,
            "match": match_str,
        })
        print(f" {match_str}")

    return routed_correct, omni_correct, results


def print_results_table(results):
    print("\n" + "=" * 120)
    print(f"{'Item':<25} {'Expected':<28} {'Routed':<28} {'Omni':<28} {'Match'}")
    print("-" * 120)
    for r in results:
        print(
            f"{r['item']:<25} "
            f"{format_path(r['expected']):<28} "
            f"{format_path(r['routed']):<28} "
            f"{format_path(r['omni']):<28} "
            f"{r['match']}"
        )


# -- Main ---------------------------------------------------------------------

async def main():
    models = sys.argv[1:] if len(sys.argv) > 1 else ["gpt-4.1-mini"]

    with open("eval_items.json") as f:
        items = json.load(f)

    yaml_files = find_yaml_files()
    originals = read_originals(yaml_files)

    summaries = []

    try:
        for model in models:
            print(f"\n{'#' * 120}")
            print(f"# Model: {model}")
            print(f"# Items: {len(items)}")
            print(f"{'#' * 120}\n")

            swap_model(yaml_files, originals, model)

            routed_correct, omni_correct, results = await run_eval_for_model(items, model)
            total = len(items)

            print_results_table(results)

            print(f"\n{'=' * 120}")
            print(f"Summary for {model}:")
            print(f"  grocery-classify (routed): {routed_correct}/{total} correct ({routed_correct*100//total}%)")
            print(f"  omni-classify (single):    {omni_correct}/{total} correct ({omni_correct*100//total}%)")

            summaries.append({
                "model": model,
                "routed_correct": routed_correct,
                "omni_correct": omni_correct,
                "total": total,
            })

    finally:
        restore_originals(yaml_files, originals)

    # Cross-model summary
    if len(summaries) > 1:
        print(f"\n\n{'#' * 80}")
        print(f"# CROSS-MODEL SUMMARY")
        print(f"{'#' * 80}\n")
        print(f"{'Model':<30} {'Routed':<20} {'Omni':<20} {'Delta'}")
        print("-" * 80)
        for s in summaries:
            t = s["total"]
            rp = f"{s['routed_correct']}/{t} ({s['routed_correct']*100//t}%)"
            op = f"{s['omni_correct']}/{t} ({s['omni_correct']*100//t}%)"
            delta = s["routed_correct"] - s["omni_correct"]
            delta_str = f"+{delta}" if delta > 0 else str(delta)
            print(f"{s['model']:<30} {rp:<20} {op:<20} {delta_str} routed")


if __name__ == "__main__":
    asyncio.run(main())
