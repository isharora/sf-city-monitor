"""Classify (person vs organization) every exported organization entity that 07b skipped (low activity).
Appends to data/er/entity_types.parquet. Run after 11_export.py, then re-run 11_export.py."""
import os, json, importlib.util, concurrent.futures as cf
import pandas as pd
import llm
HERE = os.path.dirname(os.path.abspath(__file__))
ER = os.path.join(HERE, '..', 'data', 'er')
spec = importlib.util.spec_from_file_location('t', os.path.join(HERE, '07b_entity_types.py')); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
et = pd.read_parquet(os.path.join(ER, 'entity_types.parquet'))
E = json.load(open(os.path.join(HERE, '..', 'data', 'site', 'entities.json')))['entities']
done = set(et.node_id)
todo = [(('ORG:' + e['id'].split('-', 1)[1]), e['name']) for e in E if e['type'] in ('donor_org', 'contractor', 'nonprofit')]
todo = [(n, nm) for n, nm in todo if n not in done]
print('to classify', len(todo))
items = [(i, nm, '') for i, (n, nm) in enumerate(todo)]
batches = [items[k:k + 60] for k in range(0, len(items), 60)]
def run(b):
    prompt = 'Classify each name.\n' + '\n'.join(f'{i}. "{n}"' for i, n, v in b)
    return llm.call_json('entity_typing_exported', prompt, t.SCHEMA, system=t.SYSTEM, model=llm.SONNET, effort='low')['items']
out = []
with cf.ThreadPoolExecutor(8) as ex:
    for f in cf.as_completed([ex.submit(run, b) for b in batches]):
        try: out.extend(f.result())
        except Exception as e: print('err', repr(e)[:150])
r = pd.DataFrame(out, columns=['i', 'person', 'type', 'confidence']).drop_duplicates('i').set_index('i')
new = pd.DataFrame({'node_id': [n for n, _ in todo], 'label': [nm for _, nm in todo]})
new['subtype'] = ''; new['amt'] = 0.0; new['cnt'] = 0.0
new['is_person'] = new.index.map(r.person); new['person_conf'] = new.index.map(r.confidence); new['llm_type'] = new.index.map(r.type)
pd.concat([et, new], ignore_index=True).to_parquet(os.path.join(ER, 'entity_types.parquet'), index=False)
print(new.is_person.value_counts(dropna=False)); print(f'spent ${llm.spent():.2f}')
