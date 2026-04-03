"""Eval harness: runs both classification workflows against ground truth items."""

import asyncio
import json
import os
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


async def main():
    with open("eval_items.json") as f:
        items = json.load(f)

    print(f"Running eval on {len(items)} items with both workflows...\n")

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

    total = len(items)
    print("\n" + "=" * 120)
    print(f"Summary:")
    print(f"  grocery-classify (routed): {routed_correct}/{total} correct ({routed_correct*100//total}%)")
    print(f"  omni-classify (single):    {omni_correct}/{total} correct ({omni_correct*100//total}%)")


if __name__ == "__main__":
    asyncio.run(main())
