# Why Multiple Agents Classify Better Than One

Taxonomy classification looks easy until the taxonomy gets deep. Given "bacon", most LLMs will correctly land on `food > meat > pork` without breaking a sweat. But give the same model a list of 100 grocery items spanning food subtypes, produce, canned goods, snacks, medicine, and merchandise — and ask it to route each one through a three-level tree in a single call — and accuracy starts to slip. Not dramatically for frontier models. But for smaller or local models, the difference between one-shot and layered classification is the difference between usable and not.

This post walks through the two-approach comparison in this repo, presents results across 10 models (4 frontier, 6 local), and makes an honest assessment of when routing helps and when it doesn't.

---

## The Setup

We ran 102 grocery items through two workflows across 10 models:

- **`grocery-classify`** (routed) — 7 routing agents forming a taxonomy tree, each making a focused 2-4 option decision, dispatching to a leaf classifier
- **`omni-classify`** (single-agent) — one LLM call, one prompt describing the entire taxonomy, returns the full path

The taxonomy:
```
food > meat > pork | chicken | beef
food > produce > fruit | vegetable
food > canned > vegetable | meat
food > snack > candy | chip
non_food > medicine
non_food > merchandise
```

---

## The Results

| Model | Params | Routed | Omni | Delta | Candy Apple | Caramel Apple |
|-------|--------|--------|------|-------|-------------|---------------|
| llama3.1:8b | 8B | 100 (98%) | 91 (89%) | **+9** | R:correct O:correct | R:correct O:correct |
| **gemma2:2b** | 2B | **99 (97%)** | 84 (82%) | **+15** | R:correct O:correct | R:correct O:correct |
| gpt-4.1-mini | frontier | 99 (97%) | 97 (95%) | +2 | R:correct O:correct | R:correct O:**wrong** |
| claude-sonnet-4-5 | frontier | 98 (96%) | 96 (94%) | +2 | R:correct O:correct | R:correct O:**wrong** |
| claude-haiku-4-5 | frontier | 98 (96%) | 97 (95%) | +1 | R:correct O:correct | R:correct O:correct |
| qwen2.5:7b | 7B | 98 (96%) | 87 (85%) | **+11** | R:correct O:correct | R:**wrong** O:**wrong** |
| llama3.2:3b | 3B | 97 (95%) | 80 (78%) | **+17** | R:correct O:correct | R:correct O:correct |
| gpt-4.1-nano | frontier | 96 (94%) | 94 (92%) | +2 | R:**wrong** O:correct | R:**wrong** O:**wrong** |
| qwen2.5:3b | 3B | 88 (86%) | 83 (81%) | +5 | R:correct O:correct | R:correct O:correct |
| mistral:7b | 7B | 82 (80%) | 88 (86%) | **-6** | R:correct O:correct | R:correct O:correct |

*(R = routed workflow, O = omni classifier. "Candy apple" and "caramel apple" are edge case items that test whether the model is fooled by "apple" into classifying as produce instead of snack > candy.)*

---

## What the Data Actually Says

### Routing barely helps frontier models

GPT-4.1-mini, Claude Sonnet, Claude Haiku, and GPT-4.1-nano all show +1 to +2 point improvements from routing. On 102 items, that's 1-2 items — well within noise. Frontier models are already good enough at multi-level classification that the extra complexity of routing isn't justified. If you're using a frontier model, just use the omni classifier. It's simpler, faster, and equally accurate.

### Routing transforms small models

This is where the architecture earns its keep:

- **gemma2:2b** (Google's 2B parameter model): 82% omni → 97% routed. A 15-point jump that puts a 2B model on par with GPT-4.1-mini.
- **llama3.2:3b**: 78% omni → 95% routed. +17 points. Unusable as a general classifier, production-viable with routing.
- **llama3.1:8b**: 89% omni → 98% routed. +9 points and the highest routed score of any model tested.
- **qwen2.5:7b**: 85% omni → 96% routed. +11 points.

The pattern is clear: the smaller the model, the more routing helps. A small model struggling to make three classification decisions simultaneously in one prompt can handle each decision individually when the prompt is focused.

### It's not universal

Mistral 7B actually does **worse** with routing (-6 points). Some models don't respond well to the focused routing prompt format. And qwen2.5:3b only gets +5 from routing — it's hitting a floor where even focused prompts can't fully compensate for model capability.

### The caramel apple test

"Caramel apples" is the hardest item in the eval. It's a candy made from apples — it should classify as `food > snack > candy`. The omni classifier on frontier models consistently gets this wrong, sending it to `food > produce > fruit` because "apples" dominates the context. The routed workflow gets it right on most models because the snack-router's focused prompt about candy catches the "caramel" signal.

Interestingly, all three small local models (gemma2:2b, llama3.2:3b, qwen2.5:3b) get caramel apples right on both workflows. The frontier models' omni classifiers overthink it.

---

## The Honest Trade-offs

### Latency

Routing adds sequential LLM calls. For a three-level taxonomy, that's 3-4 calls instead of 1. On cloud APIs, that's ~3-5 seconds vs ~1 second. On local models, it's 20-30 seconds vs 5-10 seconds. For real-time user-facing classification, this matters.

### Complexity

Seven routing agent definitions, a nested workflow YAML, and the routing engine itself are more moving parts than one agent and one workflow. More things to maintain, more things that can break.

### Cost

For cloud models, routing costs 3-4x per item. On frontier models where the accuracy benefit is negligible, you're paying more for the same result. On local models the cost is $0 either way, so routing is free accuracy.

---

## When to Use Each Approach

**Use the omni classifier when:**
- You're on a frontier model (GPT-4.1, Claude Sonnet/Haiku)
- Latency matters (user-facing, real-time)
- Your taxonomy is shallow (2 levels or fewer)
- Cost per item matters and accuracy is already sufficient

**Use routing when:**
- You're running local or self-hosted models (privacy, compliance, air-gapped environments)
- Accuracy is critical and you can't use frontier models
- Your taxonomy is deep (3+ levels) and evolving
- You need to diagnose and fix classification errors at specific decision points
- Latency is acceptable (batch processing, background jobs, catalog operations)

**The killer use case** is constrained environments where you can't call cloud APIs. Routing is the difference between "this 2B model doesn't work for classification" and "this 2B model matches GPT-4.1-mini." That's not a cost optimization — it's an accuracy unlock.

---

## Running the Eval Yourself

```bash
# Default (gpt-4.1-mini)
python run_eval.py

# Multiple cloud models
python run_eval.py gpt-4.1-mini gpt-4.1-nano claude-sonnet-4-5-20250929

# Local models via Ollama
python run_eval.py ollama:gemma2:2b ollama:llama3.2:3b ollama:qwen2.5:3b

# Mix of cloud and local
python run_eval.py gpt-4.1-mini ollama:gemma2:2b
```

The eval runs both workflows for each model against `eval_items.json` (102 items with ground truth paths) and prints per-item results, per-model summaries, and a cross-model comparison table.

---

## Conclusion

Routing doesn't universally beat single-agent classification. On frontier models, the difference is negligible and the extra complexity isn't worth it. The wins are specific and significant: small models gain 10-17 points of accuracy from routing structure, making them viable for tasks they'd otherwise fail at. If you're in an environment where you must use local models, routing is what makes classification work.

The routing workflow in `workflows/grocery-classify.yaml` and the comparison omni classifier in `workflows/omni-classify.yaml` are both in this repo. Run the eval, see the numbers for your models, and make the call based on your constraints — not dogma about which architecture is "better."
