"""Eval harness: runs both classification workflows against ground truth items.

Supports multiple models — rewrites routing-agent/agent YAML files with the
target model before each run, clears loader caches, and restores originals after.

Usage:
    python run_eval.py                                      # default (gpt-4.1-mini)
    python run_eval.py gpt-4.1-mini gpt-4.1-nano           # cloud models
    python run_eval.py ollama:llama3.1:8b                   # local via Ollama
    python run_eval.py deepseek-r1:8b@http://localhost:11434/v1  # explicit base_url
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


# -- Model arg parsing --------------------------------------------------------

def parse_model_arg(arg):
    """Parse a model argument into (model_name, base_url_or_None).

    Formats:
      ollama:llama3.1:8b               -> model="llama3.1:8b", base_url="http://localhost:11434/v1"
      deepseek-r1:8b@http://host/v1    -> model="deepseek-r1:8b", base_url="http://host/v1"
      gpt-4.1-mini                     -> model="gpt-4.1-mini", base_url=None
    """
    if arg.startswith("ollama:"):
        model = arg[len("ollama:"):]
        base_url = "http://localhost:11434/v1"
        return model, base_url

    if "@" in arg:
        # Split on the last '@' to support models like "deepseek-r1:8b@http://..."
        at_idx = arg.rfind("@")
        model = arg[:at_idx]
        base_url = arg[at_idx + 1:]
        return model, base_url

    return arg, None


# -- YAML model swapping -------------------------------------------------------

MODEL_RE = re.compile(r"^([ \t]*model:\s*)(.+)$", re.MULTILINE)
BASE_URL_RE = re.compile(r"^[ \t]*base_url:\s*.+\n?", re.MULTILINE)


def find_yaml_files():
    """Find all agent.yaml files."""
    return sorted(glob.glob("agentic-spec/agents/*/agent.yaml"))


def read_originals(yaml_files):
    """Read and store original contents of all YAML files."""
    originals = {}
    for path in yaml_files:
        with open(path) as f:
            originals[path] = f.read()
    return originals


def swap_model(yaml_files, originals, model, base_url=None):
    """Rewrite all YAML files with the given model (and optional base_url)."""
    for path in yaml_files:
        content = originals[path]

        # Replace the model line
        new_content = MODEL_RE.sub(rf"\g<1>{model}", content)

        # Remove any existing base_url line first (clean slate)
        new_content = BASE_URL_RE.sub("", new_content)

        # If a base_url is needed, insert it after each model: line
        if base_url:
            def insert_base_url(m):
                indent = re.match(r"^([ \t]*)", m.group(0)).group(1)
                return m.group(0) + f"\n{indent}base_url: {base_url}"
            new_content = MODEL_RE.sub(insert_base_url, new_content)

        with open(path, "w") as f:
            f.write(new_content)
    clear_caches()


def restore_originals(yaml_files, originals):
    """Restore all YAML files to their original contents."""
    for path in yaml_files:
        with open(path, "w") as f:
            f.write(originals[path])
    clear_caches()


# -- Classification ------------------------------------------------------------

def extract_taxonomy_path_from_envelope(envelope):
    """Extract [department, category] from v4 envelope step results."""
    steps = {s["step_id"]: s for s in envelope.get("steps", []) if s.get("status") == "success"}
    path = []

    dept_step = steps.get("department")
    if dept_step and isinstance(dept_step.get("output"), dict):
        dept = dept_step["output"].get("department", "")
        if dept:
            path.append(dept)

    category_ids = [
        "produce-category", "meat-seafood-category", "deli-bakery-category",
        "dairy-eggs-category", "frozen-category", "pantry-category",
        "snacks-category", "beverages-category", "health-wellness-category",
        "personal-care-category", "household-category", "baby-pet-category",
    ]
    for sid in category_ids:
        if sid in steps and isinstance(steps[sid].get("output"), dict):
            cat = steps[sid]["output"].get("category", "")
            if cat:
                path.append(cat)
            break

    return path


def format_path(path):
    return " > ".join(path) if path else "(none)"


async def classify_item(item_name, workflow_name):
    try:
        envelope = await orchestrate(workflow_name, {"item_name": item_name})
        if workflow_name == "grocery-classify":
            return extract_taxonomy_path_from_envelope(envelope)
        else:
            classification = envelope.get("output", {}).get("classification", {})
            return classification.get("taxonomy_path", [])
    except Exception as e:
        print(f"  ERROR classifying '{item_name}' with {workflow_name}: {e}", file=sys.stderr)
        return []


# -- Single model eval run -----------------------------------------------------

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


# -- Main ----------------------------------------------------------------------

async def main():
    raw_args = sys.argv[1:] if len(sys.argv) > 1 else ["gpt-4.1-mini"]
    model_configs = [parse_model_arg(a) for a in raw_args]

    with open("eval_items.json") as f:
        items = json.load(f)

    yaml_files = find_yaml_files()
    originals = read_originals(yaml_files)

    summaries = []

    try:
        for model, base_url in model_configs:
            display_name = model if not base_url else f"{model} @ {base_url}"
            print(f"\n{'#' * 120}")
            print(f"# Model: {display_name}")
            print(f"# Items: {len(items)}")
            print(f"{'#' * 120}\n")

            swap_model(yaml_files, originals, model, base_url)

            routed_correct, omni_correct, results = await run_eval_for_model(items, model)
            total = len(items)

            print_results_table(results)

            print(f"\n{'=' * 120}")
            print(f"Summary for {display_name}:")
            print(f"  grocery-classify (routed): {routed_correct}/{total} correct ({routed_correct*100//total}%)")
            print(f"  omni-classify (single):    {omni_correct}/{total} correct ({omni_correct*100//total}%)")

            summaries.append({
                "model": display_name,
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
        print(f"{'Model':<40} {'Routed':<20} {'Omni':<20} {'Delta'}")
        print("-" * 90)
        for s in summaries:
            t = s["total"]
            rp = f"{s['routed_correct']}/{t} ({s['routed_correct']*100//t}%)"
            op = f"{s['omni_correct']}/{t} ({s['omni_correct']*100//t}%)"
            delta = s["routed_correct"] - s["omni_correct"]
            delta_str = f"+{delta}" if delta > 0 else str(delta)
            print(f"{s['model']:<40} {rp:<20} {op:<20} {delta_str} routed")


if __name__ == "__main__":
    asyncio.run(main())
