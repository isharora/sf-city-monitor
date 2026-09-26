"""Claude API wrapper: caching, usage logging, budget stop. Per RULES.md.

Every call is logged to data/llm_usage.jsonl (timestamp, task, model, tokens, cost).
Results are cached in data/cache/llm/<sha>.json keyed on (model, system, prompt, schema, effort).
"""
import hashlib, json, os, threading, time
import anthropic

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
CACHE = os.path.join(BASE, "cache", "llm")
LOG = os.path.join(BASE, "llm_usage.jsonl")
BUDGET_USD = 600.0
PRICES = {"claude-sonnet-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0)}
os.makedirs(CACHE, exist_ok=True)
_lock = threading.Lock()
_client = None


def spent():
    tot = 0.0
    if os.path.exists(LOG):
        with open(LOG) as f:
            for line in f:
                try:
                    tot += json.loads(line).get("cost_usd", 0)
                except Exception:
                    pass
    return tot


def call_json(task, prompt, schema, model="claude-sonnet-5", system=None, effort="medium", max_tokens=8000):
    """Return parsed JSON (dict) following `schema`. Cached."""
    global _client
    key = hashlib.sha256(json.dumps([model, system, prompt, schema, effort], sort_keys=True).encode()).hexdigest()
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)["result"]
    if spent() > BUDGET_USD - 5:
        raise RuntimeError("LLM budget exhausted")
    if _client is None:
        _client = anthropic.Anthropic(timeout=300, max_retries=4)
    kwargs = dict(model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}],
                  thinking={"type": "adaptive"},
                  output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}})
    if system:
        kwargs["system"] = system
    for attempt in range(4):
        try:
            resp = _client.messages.create(**kwargs)
            break
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as e:
            if attempt == 3:
                raise
            time.sleep(20 * (attempt + 1))
    u = resp.usage
    pin, pout = PRICES[model]
    cost = (u.input_tokens * pin + u.output_tokens * pout + (getattr(u, "cache_read_input_tokens", 0) or 0) * pin * 0.1
            + (getattr(u, "cache_creation_input_tokens", 0) or 0) * pin * 1.25) / 1e6
    with _lock:
        with open(LOG, "a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task": task, "model": model,
                                "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                                "cost_usd": round(cost, 6), "stop_reason": resp.stop_reason}) + "\n")
    if resp.stop_reason == "refusal":
        raise RuntimeError("refusal")
    text = next(b.text for b in resp.content if b.type == "text")
    result = json.loads(text)
    with open(path, "w") as f:
        json.dump({"task": task, "model": model, "result": result}, f)
    return result
