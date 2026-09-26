"""Claude API helper: cached, logged, budget-guarded JSON calls.

Every call is cached on disk (data/cache/llm/<sha>.json) keyed on model+system+prompt+schema+effort,
logged to data/llm_usage.jsonl (timestamp, task, model, tokens, cost), and refused once the
module budget (BUDGET_USD in common.py) would be exceeded.
"""
import os, sys, json, hashlib, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(__file__))
from common import CACHE, log_usage, spent_usd, BUDGET_USD
import anthropic

_client = None
_lock = threading.Lock()
_spent = None
LLM_CACHE = os.path.join(CACHE, 'llm')
os.makedirs(LLM_CACHE, exist_ok=True)
HARD_STOP = BUDGET_USD - 5.0  # keep a safety margin


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(timeout=600.0, max_retries=4)
    return _client


def _key(model, system, prompt, schema, effort):
    h = hashlib.sha256(json.dumps([model, system, prompt, schema, effort], sort_keys=True).encode()).hexdigest()
    return os.path.join(LLM_CACHE, h + '.json')


def call_json(task, model, system, prompt, schema, effort='medium', max_tokens=16000):
    """Return parsed JSON dict. Cached. Raises RuntimeError when budget exhausted."""
    global _spent
    path = _key(model, system, prompt, schema, effort)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)['result']
    with _lock:
        if _spent is None:
            _spent = spent_usd()
        if _spent >= HARD_STOP:
            raise RuntimeError(f'LLM budget exhausted: ${_spent:.2f} spent')
    kwargs = dict(model=model, max_tokens=max_tokens,
                  system=[{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}],
                  messages=[{'role': 'user', 'content': prompt}],
                  thinking={'type': 'adaptive'},
                  output_config={'effort': effort, 'format': {'type': 'json_schema', 'schema': schema}})
    last = None
    for attempt in range(3):
        try:
            with client().messages.stream(**kwargs) as s:
                resp = s.get_final_message()
            break
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as e:
            last = e
            time.sleep(20 * (attempt + 1))
    else:
        raise last
    cost = log_usage(task, model, resp.usage)
    with _lock:
        _spent += cost
    if resp.stop_reason == 'refusal':
        raise RuntimeError('refusal')
    text = next(b.text for b in resp.content if b.type == 'text')
    result = json.loads(text)
    with open(path, 'w') as f:
        json.dump({'task': task, 'model': model, 'stop_reason': resp.stop_reason, 'result': result}, f)
    return result


def run_many(jobs, workers=8):
    """jobs: list of (key, kwargs for call_json). Returns dict key->result or Exception."""
    out = {}
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(call_json, **kw): k for k, kw in jobs}
        for i, f in enumerate(as_completed(futs)):
            k = futs[f]
            try:
                out[k] = f.result()
            except Exception as e:  # keep going; caller inspects
                out[k] = e
            if (i + 1) % 50 == 0:
                print(f'  {i+1}/{len(jobs)} done; spent ${spent_usd():.2f}', flush=True)
    return out


if __name__ == '__main__':
    r = call_json('smoke_test', 'claude-sonnet-5', 'You answer in JSON.', 'What is 2+2? Also name the capital of France.',
                  {'type': 'object', 'properties': {'sum': {'type': 'integer'}, 'capital': {'type': 'string'}},
                   'required': ['sum', 'capital'], 'additionalProperties': False}, effort='low', max_tokens=2000)
    print(r, 'spent', spent_usd())
