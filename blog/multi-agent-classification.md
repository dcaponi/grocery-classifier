# Why Smaller Focused Agents Classify Better Than One Big One

Taxonomy classification looks easy until the taxonomy gets deep. Given "bacon", most LLMs will correctly land on `food > meat > pork` without breaking a sweat. But give the same model a list of 100 grocery items spanning food subtypes, produce, canned goods, snacks, medicine, and merchandise — and ask it to route each one through a three-level tree in a single call — and accuracy starts to slip. Not dramatically for frontier models. But for smaller or local models, the difference between asking one agent to do everything and giving each agent a focused job is the difference between usable and not.

This post walks through the two-approach comparison in this repo, presents results across 10 models (4 frontier, 6 local), and makes an honest assessment of when focused multi-agent decomposition helps and when it doesn't.

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

### Focused agents barely help frontier models

GPT-4.1-mini, Claude Sonnet, Claude Haiku, and GPT-4.1-nano all show +1 to +2 point improvements from decomposition. On 102 items, that's 1-2 items — well within noise. Frontier models are already good enough at multi-level classification that the extra complexity isn't justified for accuracy alone. (Though the maintainability and debuggability arguments still apply — see trade-offs below.)

### Focused agents transform small models

This is where the architecture earns its keep:

- **gemma2:2b** (Google's 2B parameter model): 82% single-agent → 97% focused. A 15-point jump that puts a 2B model on par with GPT-4.1-mini.
- **llama3.2:3b**: 78% single-agent → 95% focused. +17 points. Unusable as a general classifier, production-viable with focused agents.
- **llama3.1:8b**: 89% single-agent → 98% focused. +9 points and the highest focused score of any model tested.
- **qwen2.5:7b**: 85% single-agent → 96% focused. +11 points.

The pattern is clear: the smaller the model, the more focused decomposition helps. A small model struggling to make three classification decisions simultaneously in one prompt can handle each decision individually when the prompt is scoped to just that decision.

### It's not universal

Mistral 7B actually does **worse** with focused agents (-6 points). Some models don't respond well to the focused prompt format. And qwen2.5:3b only gets +5 from decomposition — it's hitting a floor where even focused prompts can't fully compensate for model capability.

### The caramel apple test

"Caramel apples" is the hardest item in the eval. It's a candy made from apples — it should classify as `food > snack > candy`. The single-agent omni classifier on frontier models consistently gets this wrong, sending it to `food > produce > fruit` because "apples" dominates the full-taxonomy context. The focused agents get it right on most models because the snack-routing agent's prompt is scoped to distinguishing candy from chips — in that narrow context, "caramel" is the dominant signal, not "apples."

Interestingly, all three small local models (gemma2:2b, llama3.2:3b, qwen2.5:3b) get caramel apples right on both workflows. The frontier models' omni classifiers overthink it.

---

## The Honest Trade-offs

### Latency

Focused agents add sequential LLM calls. For a three-level taxonomy, that's 3-4 calls instead of 1. On cloud APIs, that's ~3-5 seconds vs ~1 second. On local models, it's 20-30 seconds vs 5-10 seconds. For real-time user-facing classification, this matters.

**The flip side:** each individual call is simpler and faster than the single complex call. And because decisions are independent, you can profile exactly which level of the tree is slow and optimize it — swap in a faster model for just the top-level decision, or cache common routing paths. With a monolithic call, your only optimization lever is "use a faster model for everything."

### Complexity

Seven agent definitions, a nested workflow YAML, and the orchestration engine are more moving parts than one agent and one workflow. More things to maintain, more things that can break.

**The flip side:** when something does break, you know exactly where. If meat classification accuracy drops, you look at the meat-routing agent's prompt — not a 200-line monolithic prompt where any change can regress any category. Each agent is independently testable, independently deployable, and independently upgradeable. You can swap a stronger model in for just the decision that's struggling, and keep the cheap model everywhere else. That's not possible with a single-agent approach.

### Cost

For cloud models, focused agents cost 3-4x per item in API calls. On frontier models where the accuracy benefit is negligible, you're paying more for the same result.

**The flip side:** each call uses a simpler prompt with fewer tokens, so the per-call cost is lower than 1/4 of the monolithic call. And because you can mix models — a cheap model for easy top-level decisions, a stronger model only for the ambiguous leaf classifications — you can tune your cost/accuracy ratio per decision point. On local models the cost is $0 either way, so decomposition is free accuracy.

---

## When to Use Each Approach

**Use a single agent when:**
- You're on a frontier model (GPT-4.1, Claude Sonnet/Haiku) and accuracy is already good enough
- Latency is your primary constraint (user-facing, real-time)
- Your taxonomy is shallow (2 levels or fewer)
- You don't expect the taxonomy to change often

**Use focused multi-agent decomposition when:**
- You're running local or self-hosted models (privacy, compliance, air-gapped environments)
- Your taxonomy is deep (3+ levels) and actively evolving
- You need to diagnose, isolate, and fix classification errors at specific decision points
- Different levels of the taxonomy have different difficulty — you want to assign model capacity accordingly
- You want to upgrade or downgrade models for individual decisions without rewriting the whole system
- Latency is acceptable (batch processing, background jobs, catalog operations, overnight imports)

**The killer use case** is constrained environments where you can't call cloud APIs. Focused agents are the difference between "this 2B model doesn't work for classification" and "this 2B model matches GPT-4.1-mini." That's not a cost optimization — it's an accuracy unlock that comes from giving small models problems they can actually solve.

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

Decomposing classification into focused agents doesn't universally beat a single-agent approach. On frontier models, the accuracy difference is negligible. But the architecture has value beyond accuracy: each agent is independently testable, independently tunable, and independently upgradeable. When your taxonomy changes — and it will — you modify one agent's prompt instead of rewriting a monolithic one.

The accuracy wins are specific and dramatic: small models gain 10-17 points from decomposition, making them viable for tasks they'd otherwise fail at. If you're in an environment where you must use local models, focused agents are what makes classification work. And even on frontier models, the ability to isolate errors, swap models per decision point, and evolve the taxonomy incrementally has operational value that doesn't show up in an accuracy number.

The focused workflow in `agentic-spec/workflows/grocery-classify.yaml` and the single-agent baseline in `agentic-spec/workflows/omni-classify.yaml` are both in this repo. Run the eval, see the numbers for your models, and make the call based on your constraints.
