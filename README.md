# Grocery Classifier

A Flask app that demonstrates two approaches to hierarchical taxonomy classification using [agentic-app-spec](https://github.com/dcaponi/agentic-app-spec):

- **`grocery-classify`** — multi-agent routing. Each level of the taxonomy is a focused LLM decision between 2–4 options.
- **`omni-classify`** — single-agent. One LLM call that holds the full taxonomy and classifies in one pass.

The eval harness runs both against 100 labeled items so you can compare accuracy directly.

---

## Taxonomy

```
food
├── meat
│   ├── pork
│   ├── chicken
│   └── beef
├── produce
│   ├── fruit
│   └── vegetable
├── canned
│   ├── vegetable
│   └── meat
└── snack
    ├── candy
    └── chip
non_food
├── medicine
└── merchandise
```

---

## Prerequisites

- Python 3.10+
- OpenAI API key
- `agentic` CLI — only needed if you want to regenerate the handler stubs in `generated/`

---

## Setup

```bash
git clone https://github.com/dcaponi/grocery-classifier
cd grocery-classifier
pip install -r requirements.txt
```

Create a `.env` file:

```
OPENAI_API_KEY=sk-...
```

---

## Running the App

```bash
python app.py
```

Runs on port 8000.

---

## Endpoints

### `GET /classify`

Routes the item through the full taxonomy tree using the `grocery-classify` workflow.

```bash
curl "http://localhost:8000/classify?items=chicken+breast"
curl "http://localhost:8000/classify?items=bacon,apples,ibuprofen"
```

### `GET /omni-classify`

Classifies in a single LLM pass using the `omni-classify` workflow.

```bash
curl "http://localhost:8000/omni-classify?items=chicken+breast"
curl "http://localhost:8000/omni-classify?items=bacon,apples,ibuprofen"
```

---

## Response Format

Both endpoints return the same shape:

```json
{
  "results": [
    {
      "item": "chicken breast",
      "taxonomy_path": ["food", "meat", "chicken"],
      "workflow": "grocery-classify",
      "details": {}
    }
  ]
}
```

`taxonomy_path` is an array tracing the route from root to leaf. `details` contains any additional output from the leaf agent (routed) or confidence/reasoning (omni).

---

## Running the Eval

```bash
python run_eval.py
```

Runs both workflows against all 100 items in `eval_items.json` and prints a side-by-side accuracy summary.

---

## How the Routing Workflow Works

The `grocery-classify` workflow (defined in `workflows/grocery-classify.yaml`) is a nested `route` tree. Each node is a router — a lightweight LLM call that picks between 2–4 options and returns a route key. The runtime dispatches to the next router or leaf agent based on that key.

Routers live in `routers/` and are distinct from agents. They make flow-control decisions; they don't produce content. This separation is a core design principle of agentic-app-spec — all branching is declared in the workflow YAML, not hidden in application code.

See the [router primitive docs](https://github.com/dcaponi/agentic-app-spec) for the full spec.

---

## Blog Post

[Why Multiple Agents Classify Better Than One](blog/multi-agent-classification.md)
