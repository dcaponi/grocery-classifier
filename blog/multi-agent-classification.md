# Focused Agents vs. The God Model: A Grocery Classification Case Study

We built a grocery item classifier two ways: one LLM call that knows the entire taxonomy, and a pipeline of small focused agents that each make one decision. Then we ran 250 items across a real Kroger-scale taxonomy on frontier and local models.

The results don't tell a simple "one is better" story. They tell a story about engineering trade-offs — determinism, maintainability, and model flexibility versus simplicity and speed.

---

## The Setup

A realistic grocery store taxonomy: 12 departments, 38 leaf categories.

```
produce (fruit, vegetable)
meat_seafood (beef, pork, poultry, seafood)
deli_bakery (deli, bakery)
dairy_eggs (milk, cheese, yogurt, eggs_butter)
frozen (frozen_meals, frozen_treats, frozen_produce)
pantry (canned, dry_goods, condiments, baking)
snacks (chips, candy, cookies_crackers, nuts)
beverages (soda_water, juice, coffee_tea, alcohol)
health_wellness (medicine, vitamins, first_aid)
personal_care (hair, oral, body)
household (cleaning, paper, kitchen)
baby_pet (baby, pet)
```

**The god model** (`omni-classify`): one agent, one prompt containing the full taxonomy, returns the classification path in a single LLM call.

**Focused agents** (`grocery-classify`): a department-routing agent picks 1 of 12 departments, then a department-specific routing agent picks the category. Each agent only sees 2-12 options with a detailed prompt scoped to that decision. 13 routing agents total.

250 items, 5 models, both workflows. Every item has a ground-truth path.

---

## The Results

| Model | Focused Agents | God Model | Delta |
|-------|---------------|-----------|-------|
| gpt-4.1-mini (frontier) | 245/250 (98%) | 250/250 (100%) | -5 |
| claude-haiku-4-5 (frontier) | 247/250 (98%) | 247/250 (98%) | 0 |
| qwen2.5:7b (local) | 209/250 (83%) | 191/250 (76%) | **+18** |
| llama3.2:3b (local) | 215/250 (86%) | 199/250 (79%) | **+16** |
| gemma2:2b (local) | 214/250 (85%) | 171/250 (68%) | **+43** |

---

## What This Means

### The god model wins on frontier models

GPT-4.1-mini got a perfect 250/250 with a single call. No pipeline, no complexity, no latency overhead. Claude Haiku tied at 98% either way. If you're using a frontier model, the god model is the right choice — simpler, faster, cheaper.

This shouldn't be surprising. Frontier models are good at holding complex context. A 38-category taxonomy fits comfortably in their context window and they can reason about all the distinctions at once.

### Focused agents unlock small models

A 2B parameter model (gemma2:2b) went from 68% with the god model to 85% with focused agents — a 43-point delta. That's the difference between unusable and useful.

The reason is straightforward: a 2B model can't reliably hold a 38-category taxonomy in context and make multi-level decisions simultaneously. But it can reliably choose between "beef, pork, poultry, or seafood" when that's the only thing it's being asked. Each focused agent gives the small model a problem it can actually solve.

### The three properties that matter

The accuracy numbers are interesting but they're not the real pitch. Three engineering properties matter more than raw accuracy:

**1. Determinism.** A focused agent choosing between 4 options is more predictable than a god model choosing between 38 categories in one shot. On frontier models, both approaches are deterministic enough. On small models, the focused approach produces dramatically more consistent results because the decision surface is smaller.

**2. Maintainability.** When the god model misclassifies "baby lotion" as personal care instead of baby products, you add an edge case to a prompt that already has 38 categories, dozens of examples, and a page of edge cases. That change might fix "baby lotion" but regress "hand lotion" or "sunscreen." You can't predict the blast radius.

When focused agents misclassify "baby lotion," you know exactly which agent failed (the department-router), you open that one prompt, and you add the edge case. The snacks-router, dairy-router, and every other agent are untouched. They can't regress.

We tested this: GPT-4.1-mini's focused pipeline had 5 failures, all traceable to exactly 2 agents (department-router and snacks-router). We edited 2 prompts, ran again, and fixed all 5 with zero regressions.

**3. Model flexibility.** With focused agents, you can run different models at different levels. The department-level decision (12 options) might need a slightly stronger model, while the leaf-level decision (2-4 options) works fine with something tiny. You can tune cost and capability per decision point. The god model forces one model for everything.

---

## The Honest Trade-offs

### Latency

Focused agents make 2-3 sequential LLM calls instead of 1. On cloud APIs, that's ~3-5 seconds vs ~1 second. On local models, it's significantly more.

**But:** each individual call is simpler and faster. And because decisions are independent, you can profile exactly which level is slow and optimize it — swap in a faster model for just the easy decisions, or cache common routing paths.

### Complexity

13 routing agent definitions and a nested workflow YAML are more moving parts than one agent and one prompt.

**But:** when something breaks, you know exactly where. Each agent is independently testable, deployable, and upgradeable. The god model is a monolith — any prompt change can have unpredictable side effects across all 38 categories.

### Cost

For cloud models, focused agents cost 2-3x per item in API calls.

**But:** each call uses fewer tokens (focused prompt vs. full taxonomy prompt), so the per-call cost is lower. And you can mix models — cheap model for easy decisions, stronger model only where needed. On local models the cost is $0 either way.

---

## When to Use Each Approach

**Use the god model when:**
- You're on a frontier model and accuracy is already sufficient
- Latency is your primary constraint
- Your taxonomy is stable and doesn't change often
- You want the simplest possible system

**Use focused agents when:**
- You need to run local or self-hosted models (privacy, compliance, air-gapped)
- Your taxonomy is evolving and you need to fix individual categories without risking regressions
- You need deterministic, predictable behavior from smaller models
- You want to assign model capability per decision point
- Latency is acceptable (batch processing, background jobs, catalog operations)

---

## The Maintainability Test

This is the experiment we'd recommend running yourself. Take the god model's failures and try to fix them by editing the prompt. Then check if you introduced new failures. Now do the same with focused agents.

In our testing, focused agent fixes were surgical — edit one prompt, verify one decision boundary, no regressions. God model fixes were unpredictable — adding an edge case for "baby lotion" in a prompt that also handles seafood, beverages, and cleaning supplies is inherently fragile.

The accuracy gap might not justify focused agents on frontier models. The maintainability gap does — if your taxonomy changes more than once.

---

## Run It Yourself

```bash
git clone https://github.com/dcaponi/grocery-classifier.git
cd grocery-classifier
pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." > .env

# Run the eval
python run_eval.py gpt-4.1-mini

# Try local models (requires Ollama)
python run_eval.py ollama:gemma2:2b ollama:llama3.2:3b

# Run the Flask app
python app.py
curl "http://localhost:8000/classify?items=baby+lotion,salmon+fillet,frozen+pizza"
curl "http://localhost:8000/omni-classify?items=baby+lotion,salmon+fillet,frozen+pizza"
```

The focused workflow is at `agentic-spec/workflows/grocery-classify.yaml`. The god model is at `agentic-spec/workflows/omni-classify.yaml`. Both use the [routing-agent primitive](https://github.com/dcaponi/agentic-app-spec) from Agentic App Spec.
