"""Classify resolved organization entities that carry money or contacts in the network:
  - is the name actually a private individual (e.g., a person listed as a behested payor, or a sole proprietorship named after a person)?
  - organization type (company, nonprofit, labor, trade/business association, political committee, government, other)

Private-individual names are suppressed from public outputs (fairness rules). Uses claude-sonnet-5 in batches of 60 names.
Output: data/er/entity_types.parquet
"""
import os, json, concurrent.futures as cf
import pandas as pd
import llm

HERE = os.path.dirname(os.path.abspath(__file__))
ER = os.path.join(HERE, '..', 'data', 'er')
NET = os.path.join(HERE, '..', 'data', 'network')

SYSTEM = """You classify names from San Francisco campaign-finance, lobbying, behested-payment and city-contract records.
For each name decide:
- person: true if the name refers to a private individual human (e.g. "John Smith", "Smith, Mary", "Dr. Jane Doe"), including individual professionals ("John Smith DDS", "Law Office of Jane Doe" counts as person=false only if it reads as a firm). Trusts or foundations named after people are NOT persons ("Lui Foundation" = organization).
- type: one of company, nonprofit, labor, business_association, political_committee, government, education_health, other.
Return confidence 0-1 for the person flag."""

SCHEMA = {'type': 'object', 'properties': {'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'i': {'type': 'integer'}, 'person': {'type': 'boolean'}, 'type': {'type': 'string', 'enum': ['company', 'nonprofit', 'labor', 'business_association', 'political_committee', 'government', 'education_health', 'other']},
    'confidence': {'type': 'number'}}, 'required': ['i', 'person', 'type', 'confidence'], 'additionalProperties': False}}},
    'required': ['items'], 'additionalProperties': False}


def main():
    ed = pd.read_parquet(os.path.join(NET, 'edges.parquet'))
    nd = pd.read_parquet(os.path.join(NET, 'nodes.parquet'))
    orgs = nd[nd.node_type == 'org'][['node_id', 'label', 'subtype']]
    ents = pd.read_parquet(os.path.join(ER, 'org_entities.parquet')).set_index('entity_default')
    # activity score: money + contacts
    act = pd.concat([ed[['source', 'amount']].rename(columns={'source': 'n'}), ed[['target', 'amount']].rename(columns={'target': 'n'})])
    act = act[act.n.str.startswith('ORG:')].groupby('n').agg(amt=('amount', lambda s: s.abs().sum()), cnt=('amount', 'size'))
    orgs = orgs.merge(act, left_on='node_id', right_index=True, how='left').fillna({'amt': 0, 'cnt': 0})
    todo = orgs[(orgs.amt >= 1000) | (orgs.cnt >= 3)].copy()
    outp = os.path.join(ER, 'entity_types.parquet')
    prev = pd.read_parquet(outp) if os.path.exists(outp) else None
    if prev is not None:
        # incremental: keep earlier judgments for entities whose id and label are unchanged
        keep = prev.merge(todo[['node_id', 'label']], on=['node_id', 'label'])
        todo = todo[~todo.node_id.isin(set(keep.node_id))]
        print('incremental: already classified', len(keep))
    todo['variants'] = todo.node_id.map(lambda e: ents.at[e, 'keys'] if e in ents.index else '')
    todo = todo.reset_index(drop=True)
    print('entities to classify', len(todo))
    items = [(i, r.label, str(r.variants)[:120]) for i, r in todo.iterrows()]
    batches = [items[k:k + 60] for k in range(0, len(items), 60)]

    def run(b):
        prompt = 'Classify each name.\n' + '\n'.join(f'{i}. "{n}" (variants: {v})' for i, n, v in b)
        return llm.call_json('entity_typing', prompt, SCHEMA, system=SYSTEM, model=llm.SONNET, effort='low')['items']
    out = []
    with cf.ThreadPoolExecutor(8) as ex:
        for f in cf.as_completed([ex.submit(run, b) for b in batches]):
            try:
                out.extend(f.result())
            except Exception as e:
                print('err', repr(e)[:200])
    r = pd.DataFrame(out, columns=['i', 'person', 'type', 'confidence']).drop_duplicates('i').set_index('i')
    todo['is_person'] = todo.index.map(r.person)
    todo['person_conf'] = todo.index.map(r.confidence)
    todo['llm_type'] = todo.index.map(r.type)
    out = todo[['node_id', 'label', 'subtype', 'amt', 'cnt', 'is_person', 'person_conf', 'llm_type']]
    if prev is not None:
        out = pd.concat([keep[out.columns], out], ignore_index=True)
    out.to_parquet(outp, index=False)
    print(out.is_person.value_counts(dropna=False)); print(f'spent ${llm.spent():.2f}')


if __name__ == '__main__':
    main()
