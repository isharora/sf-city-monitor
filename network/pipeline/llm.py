"""Thin Claude API wrapper: caching, usage logging, budget stop.

Every call is logged to network/data/llm_usage.jsonl with timestamp, task, model, tokens, cost.
Results are cached on disk (data/cache/llm/<sha>.json) keyed on model+system+prompt+schema.
"""
import hashlib, json, os, threading, time
import anthropic

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
LOG = os.path.join(DATA, 'llm_usage.jsonl')
CACHE = os.path.join(DATA, 'cache', 'llm')
os.makedirs(CACHE, exist_ok=True)

BUDGET_USD = 700.0
STOP_AT_USD = 680.0  # safety margin
PRICES = {  # $ per million tokens (input, output) per RULES.md
    'claude-sonnet-5': (2.0, 10.0),
    'claude-opus-5-5': (4.0, 20.0),
}
SONNET = 'claude-sonnet-5'
OPUS = 'claude-opus-5-5'

_lock = threading.Lock()
_client = anthropic.Anthropic(timeout=300.0, max_retries=3)


class BudgetExceeded(Exception):
    pass


def spent():
    tot = 0.0
    if os.path.exists(LOG):
        with open(LOG) as fh:
            for line in fh:
                try:
                    tot += json.loads(line).get('cost_usd', 0)
                except Exception:
                    pass
    return tot


def _key(model, system, prompt, schema, effort):
    h = hashlib.sha256(json.dumps([model, system, prompt, schema, effort], sort_keys=True).encode()).hexdigest()
    return h


def call_json(task, prompt, schema, system='', model=SONNET, effort='medium', max_tokens=16000):
    """Return parsed JSON dict following `schema`. Cached. Logs usage."""
    k = _key(model, system, prompt, schema, effort)
    path = os.path.join(CACHE, k + '.json')
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)['result']
    with _lock:
        if spent() >= STOP_AT_USD:
            raise BudgetExceeded('LLM budget reached')
    kw = dict(model=model, max_tokens=max_tokens,
              thinking={'type': 'adaptive'},
              output_config={'effort': effort, 'format': {'type': 'json_schema', 'schema': schema}},
              messages=[{'role': 'user', 'content': prompt}])
    if system:
        kw['system'] = system
    t0 = time.time()
    resp = _client.messages.create(**kw)
    if resp.stop_reason == 'refusal':
        raise RuntimeError('refusal')
    text = next(b.text for b in resp.content if b.type == 'text')
    result = json.loads(text)
    u = resp.usage
    pin, pout = PRICES[model]
    inp = (u.input_tokens or 0) + (getattr(u, 'cache_creation_input_tokens', 0) or 0) + (getattr(u, 'cache_read_input_tokens', 0) or 0)
    cost = inp * pin / 1e6 + (u.output_tokens or 0) * pout / 1e6
    rec = dict(ts=time.strftime('%Y-%m-%dT%H:%M:%S'), task=task, model=model, effort=effort,
               input_tokens=inp, output_tokens=u.output_tokens, cost_usd=round(cost, 6),
               seconds=round(time.time() - t0, 1), cache_key=k)
    with _lock:
        with open(LOG, 'a') as fh:
            fh.write(json.dumps(rec) + '\n')
        with open(path, 'w') as fh:
            json.dump(dict(task=task, model=model, prompt=prompt, result=result), fh)
    return result
