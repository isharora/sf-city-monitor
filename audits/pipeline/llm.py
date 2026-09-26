"""Shared Claude API helper: disk cache, usage logging, budget guard.

Every call is logged to audits/data/llm_usage.jsonl with timestamp, task,
model, tokens and cost. Results are cached by a hash of the full request
so reruns are free. A hard budget stop is enforced from the log.
"""
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone

import anthropic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
USAGE_LOG = os.path.join(DATA, "llm_usage.jsonl")
CACHE_DIR = os.path.join(DATA, "cache", "llm")
os.makedirs(CACHE_DIR, exist_ok=True)

BUDGET_USD = 500.0
SOFT_STOP_USD = 480.0  # leave headroom for in-flight calls

# $ per million tokens (input, output) - from RULES.md
PRICES = {
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}
SONNET = "claude-sonnet-5"
OPUS = "claude-opus-5-5"

_lock = threading.Lock()
_client = None


class BudgetExceeded(Exception):
    pass


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(timeout=600.0, max_retries=4)
    return _client


def spent():
    total = 0.0
    if os.path.exists(USAGE_LOG):
        with open(USAGE_LOG) as f:
            for line in f:
                try:
                    total += json.loads(line)["cost_usd"]
                except Exception:
                    pass
    return total


def cost_of(model, usage):
    pin, pout = PRICES[model]
    inp = usage.get("input_tokens", 0) or 0
    cw = usage.get("cache_creation_input_tokens", 0) or 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    return (inp * pin + cw * pin * 1.25 + cr * pin * 0.1 + out * pout) / 1e6


def _log(task, model, usage, cost, key):
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "model": model,
        "input_tokens": usage.get("input_tokens", 0),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cost_usd": round(cost, 6),
        "cache_key": key,
    }
    with _lock:
        with open(USAGE_LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")


_spent_cache = {"v": None, "t": 0}


def _check_budget():
    with _lock:
        now = time.time()
        if _spent_cache["v"] is None or now - _spent_cache["t"] > 20:
            _spent_cache["v"] = spent()
            _spent_cache["t"] = now
        if _spent_cache["v"] >= SOFT_STOP_USD:
            raise BudgetExceeded(f"spent ${_spent_cache['v']:.2f} >= soft stop")


def call_json(task, model, system, content, schema, effort="medium",
              max_tokens=32000, cache_tag=""):
    """Call Claude with structured JSON output. Returns (data, meta).

    content: list of content blocks or a string for the user turn.
    """
    req = {
        "model": model, "system": system, "content": content,
        "schema": schema, "effort": effort, "tag": cache_tag,
    }
    key = hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()
    path = os.path.join(CACHE_DIR, key[:2], key + ".json")
    if os.path.exists(path):
        with open(path) as f:
            d = json.load(f)
        return d["data"], {"cached": True, "key": key, **d.get("meta", {})}
    _check_budget()
    msgs = [{"role": "user", "content": content}]
    params = dict(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system,
                 "cache_control": {"type": "ephemeral"}}],
        messages=msgs,
        thinking={"type": "adaptive"},
        output_config={"effort": effort,
                       "format": {"type": "json_schema", "schema": schema}},
    )
    last_err = None
    for attempt in range(4):
        try:
            with client().messages.stream(**params) as stream:
                resp = stream.get_final_message()
            break
        except (anthropic.RateLimitError, anthropic.APIConnectionError,
                anthropic.InternalServerError) as e:
            last_err = e
            time.sleep(15 * (attempt + 1))
        except anthropic.APIStatusError as e:
            if e.status_code in (529, 503, 502, 500):
                last_err = e
                time.sleep(20 * (attempt + 1))
            else:
                raise
    else:
        raise last_err
    usage = resp.usage.model_dump() if hasattr(resp.usage, "model_dump") else dict(resp.usage)
    cost = cost_of(model, usage)
    _log(task, model, usage, cost, key)
    if resp.stop_reason == "refusal":
        raise RuntimeError("refusal")
    text = next((b.text for b in resp.content if b.type == "text"), None)
    if resp.stop_reason == "max_tokens" or text is None:
        raise RuntimeError(f"bad stop: {resp.stop_reason}")
    data = json.loads(text)
    meta = {"model": model, "cost_usd": cost, "stop_reason": resp.stop_reason,
            "usage": {k: usage.get(k) for k in ("input_tokens", "output_tokens",
                                                 "cache_read_input_tokens")}}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"data": data, "meta": meta}, f)
    return data, {"cached": False, "key": key, **meta}


if __name__ == "__main__":
    d, m = call_json("smoke_test", SONNET, "Reply with JSON.",
                     "Say hello.", {"type": "object", "properties": {"msg": {"type": "string"}},
                                    "required": ["msg"], "additionalProperties": False},
                     effort="low", max_tokens=2000)
    print(d, m)
    print("spent", spent())
