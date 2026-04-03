# Why Multiple Agents Classify Better Than One

Taxonomy classification looks easy until the taxonomy gets deep. Given "bacon", most LLMs will correctly land on `food > meat > pork` without breaking a sweat. But give the same model a list of 100 grocery items spanning food subtypes, produce, canned goods, snacks, medicine, and merchandise — and ask it to route each one through a three-level tree in a single call — and accuracy starts to slip. Not dramatically. Just enough to matter.

This post explains why, walks through the two-approach comparison in this repo, and makes the case for treating deep classification as a series of decisions rather than a single judgment.

---

## The Problem with a Single Pass

The `omni-classify` workflow in this project takes the straightforward approach: one agent, one prompt, one LLM call. The agent's prompt (`agents/omni-classifier/prompt.md`) lays out the full taxonomy, enumerates every valid path, lists edge cases, and asks the model to return a `taxonomy_path` array.

It works. For unambiguous items it works well. But the prompt has to do a lot of work:

- Describe the taxonomy structure
- Give examples for every leaf category
- Handle ambiguous cases (is peanut butter `canned/vegetable`? Is ground turkey `meat/chicken`?)
- Return a structured array in the exact right format

The model is making multiple classification decisions simultaneously — food vs. non-food, subtype within food, and leaf within subtype — while holding all of that context in one pass. When it gets the subtype wrong, the leaf is wrong too. Errors at higher levels cascade.

---

## The Layered Approach

The `grocery-classify` workflow (`workflows/grocery-classify.yaml`) does the same classification, but each decision is its own focused LLM call.

The top-level `food-router` asks one question: food or non-food? Its prompt (`routers/food-router/prompt.md`) is detailed about *that distinction only* — what counts as food, what counts as non-food, edge cases like pet food and vitamins. It doesn't know or care about meat subtypes or canned goods.

If the item is food, the `food-subtype-router` takes over and asks: meat, produce, canned, or snack? Again, its prompt is scoped to *that decision*.

If the subtype is meat, the `meat-router` asks: pork, chicken, or beef?

Each router returns a single route key. The workflow YAML wires the tree together:

```yaml
- route:
    id: classify
    router: food-router
    input:
      item_name: $.input.item_name
    routes:
      food:
        route:
          id: food_sub
          router: food-subtype-router
          ...
          routes:
            meat:
              route:
                id: meat_sub
                router: meat-router
                ...
                routes:
                  pork: classify-leaf
                  chicken: classify-leaf
                  beef: classify-leaf
```

The branching tree lives in the workflow definition, not in application code. The routers make decisions; the runtime dispatches.

---

## Why It Works Better

**Focused context.** When the `meat-router` is deciding between pork, chicken, and beef, its prompt can include rich examples of each — cuts, preparations, ambiguous items like "ground turkey" or "pork belly". An omni classifier has to compress examples for *all* categories into a single prompt, which means each category gets less coverage.

**Error isolation.** If `food-subtype-router` incorrectly routes "pork rinds" to `snack` instead of `meat`, that's a recoverable mistake. The top-level `food` classification was correct. And you know exactly where the error happened. In a single-pass classifier, a wrong subtype silently cascades — you see a wrong leaf and have to infer where it went sideways.

**Independent prompt tuning.** The `meat-router` prompt can be refined without touching the `food-router` prompt or the `snack-router` prompt. Each router's accuracy can be tracked and improved in isolation. Try doing that with a monolithic prompt that covers twelve categories.

**Testable decisions.** Each router is a unit. You can test the `food-router` with a focused set of food and non-food items. You can test the `produce-router` with fruit/vegetable edge cases. The eval harness in this project (`run_eval.py`) tests the full pipeline, but there's nothing stopping you from testing each router independently.

**Taxonomies evolve.** Say you want to add a `seafood` subtype under `meat`. With the routing approach, you add a `seafood-router`, add `seafood` as a route in the `meat-router`'s available options, and wire it into the workflow YAML. The rest of the tree is untouched. With a single-agent approach, you're rewriting the entire prompt and hoping nothing regresses.

---

## The Eval Evidence

`run_eval.py` runs both workflows against 100 labeled grocery items in `eval_items.json` and prints a side-by-side comparison.

The items span the full taxonomy: pork cuts, chicken preparations, beef varieties, fresh and frozen produce, canned goods, snacks, medicine, and household merchandise. Several items are intentionally ambiguous — pork rinds (snack or meat?), ground turkey (chicken bucket or its own?), canned tuna (meat or canned?).

On this set, `grocery-classify` (routed) typically lands around 95%+ accuracy. `omni-classify` (single-agent) lands around 85-90%. The gap isn't huge, but the error patterns are different and instructive.

Routed errors tend to be router-level mistakes that are easy to diagnose and fix — a specific router that's weak on a particular edge case. Single-agent errors cluster around ambiguous items at leaf levels, where the model's one-shot judgment on a complex item breaks down. And because the error is opaque (you just get a wrong path, no intermediate decisions), it's harder to know what to fix.

---

## When Single-Agent Is Fine

Not every classification problem needs a routing tree.

If your taxonomy is flat — just a list of categories with no hierarchy — a single-agent approach is simpler and fast enough. The `omni-classify` workflow in this project is a reasonable choice for a two-level taxonomy.

If the option set is small (fewer than 6-8 categories total), the focused context advantage of routing is minimal. A good prompt with all options listed is often sufficient.

If latency matters more than accuracy — you're classifying in real-time with a user waiting — routing adds round trips. Each level of the tree is a separate LLM call. For the three-level taxonomy in this project, that's three calls per item instead of one.

The tradeoffs are real. Routing trades latency and complexity for accuracy and maintainability.

---

## Conclusion

For deep taxonomies, classification is not a single judgment — it's a series of decisions. Trying to collapse all of those decisions into one prompt forces the model to context-switch between problems it could handle well in isolation.

The routing approach in `workflows/grocery-classify.yaml` delegates each decision to a focused specialist. The prompts in `routers/` are small, tunable, and independently testable. The taxonomy tree is visible in the workflow definition rather than encoded in prompt instructions.

If you're building a classifier that needs to survive a growing taxonomy, treat it like a decision tree from the start. The infrastructure to support it — the router primitive in [agentic-app-spec](https://github.com/dcaponi/agentic-app-spec) — makes this pattern as easy to define as a workflow YAML.
