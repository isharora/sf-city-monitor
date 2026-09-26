"""Claude adjudication of grey-zone organization name pairs.

Reads data/er/org_pairs.parquet (rule_decision == 'llm'), sends batches of pairs to claude-sonnet-5,
and writes data/er/org_pair_judgments.parquet with relation / confidence / rationale per pair.
Hard cases (Sonnet unsure or confidence < 0.6 on a cross-source pair) are re-judged by claude-opus-5-5 at high effort.
"""
import os, sys, json, concurrent.futures as cf
import pandas as pd
import llm

HERE = os.path.dirname(os.path.abspath(__file__))
ER = os.path.join(HERE, '..', 'data', 'er')

SRC_LABEL = {
    'cf_org_donor': 'campaign contributor (organization)', 'cf_employer': 'employer named by individual campaign donors',
    'lobby_client': 'lobbyist client', 'lobby_firm': 'lobbying firm', 'bp_payor': 'behested-payment payor',
    'bp_payee': 'behested-payment recipient', 'f126_contractor': 'city contractor (contract approval notice)',
    'f126_subcontractor': 'subcontractor on a city contract', 'f126f2_party': 'bidder on a city contract',
    'sc_prime': 'prime contractor (Controller contracts)', 'sc_supplier': 'contract team supplier (Controller contracts)',
    'vendor': 'payee in city vendor payments (names often truncated/abbreviated)', 'f124_entity': 'business entity giving $10k+ to a committee',
    'dev_3500': 'major-project developer', 'f1145_contributor': 'contributor to a ballot/IE committee at an official\'s behest',
    'committee': 'registered campaign committee',
}

SYSTEM = """You are an expert in entity resolution for public-records data about San Francisco city government: campaign finance, lobbying, city contracts and vendor payments.
For each candidate pair of organization names decide the relationship:
- "same": the two strings refer to the same organization (typos, abbreviations, truncation, legal suffixes, d/b/a, a committee's minor name variants, a union local's PAC vs the same local's other PAC is NOT same - see family).
- "family": clearly related but distinct legal entities or units: parent/subsidiary, a company and its PAC, different locals or chapters of one union, a nonprofit and its foundation, numbered funds/phases of the same sponsor (Fund I vs Fund II), different project LLCs of one developer.
- "different": distinct organizations that merely share words.
- "unsure": not enough information.
Be conservative: generic shared words (e.g. "Mission", "Community", "Housing", "Pacific") are not evidence. Surname-only law or architecture firms can be matched only if the remaining name parts are consistent.
Confidence is your probability (0-1) that your stated relation is correct. Keep rationales under 25 words."""

SCHEMA = {
    'type': 'object',
    'properties': {
        'judgments': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'pair_id': {'type': 'integer'},
                    'relation': {'type': 'string', 'enum': ['same', 'family', 'different', 'unsure']},
                    'confidence': {'type': 'number'},
                    'rationale': {'type': 'string'},
                },
                'required': ['pair_id', 'relation', 'confidence', 'rationale'],
                'additionalProperties': False,
            },
        }
    },
    'required': ['judgments'],
    'additionalProperties': False,
}


def describe(key, info):
    r = info.get(key, {})
    srcs = ', '.join(SRC_LABEL.get(s, s) for s in r.get('srcs', '').split(',') if s)
    parts = [f'raw names: {r.get("examples", key)}', f'appears as: {srcs}']
    if r.get('cities'):
        parts.append(f'cities: {r["cities"]}')
    if r.get('np'):
        parts.append('flagged nonprofit in city data')
    return '; '.join(parts)


def build_info():
    ms = pd.read_parquet(os.path.join(ER, 'org_mentions.parquet'))
    kt = pd.read_parquet(os.path.join(ER, 'org_keys.parquet')).set_index('key')
    info = {}
    ex = ms.sort_values('n', ascending=False).groupby('key').examples.agg(lambda s: ' | '.join(dict.fromkeys(' | '.join(s).split(' | ')).keys()) )
    ci = ms.dropna(subset=['cities']).groupby('key').cities.agg(lambda s: ' | '.join(dict.fromkeys(' | '.join(s).split(' | ')).keys()))
    npf = ms.dropna(subset=['extra']).groupby('key').extra.agg(lambda s: 'X' in ' '.join(s))
    for k in kt.index:
        info[k] = {'srcs': kt.at[k, 'srcs'], 'examples': ' | '.join(str(ex.get(k, k)).split(' | ')[:4]),
                   'cities': ' | '.join(str(ci.get(k, '')).split(' | ')[:3]) if k in ci.index else '', 'np': bool(npf.get(k, False))}
    return info


def run_batch(batch, info, model=llm.SONNET, effort='medium', task='org_pair_adjudication'):
    lines = []
    for pid, a, b in batch:
        lines.append(f'Pair {pid}:\n  A = "{a}" ({describe(a, info)})\n  B = "{b}" ({describe(b, info)})')
    prompt = ('Judge each pair of organization names below. Names shown in quotes are normalized keys '
              '(uppercase, punctuation and legal suffixes removed, SAN FRANCISCO->SF, FOUNDATION->FDN, ASSOCIATION->ASSN).\n\n'
              + '\n'.join(lines) + '\n\nReturn one judgment per pair_id.')
    res = llm.call_json(task, prompt, SCHEMA, system=SYSTEM, model=model, effort=effort)
    return res['judgments']


def main(limit=None, workers=8):
    pr = pd.read_parquet(os.path.join(ER, 'org_pairs.parquet'))
    todo = pr[pr.rule_decision == 'llm'].reset_index(drop=True)
    prev_path = os.path.join(ER, 'org_pair_judgments.parquet')
    prev = pd.read_parquet(prev_path) if (os.path.exists(prev_path) and not limit) else None
    if prev is not None:
        done = set(zip(prev.a, prev.b))
        todo = todo[[(a, b) not in done for a, b in zip(todo.a, todo.b)]].reset_index(drop=True)
        todo['pair_id'] = todo.index + int(prev.pair_id.max()) + 1
        print('incremental run: new pairs to judge', len(todo))
    else:
        todo['pair_id'] = todo.index
    if limit:
        todo = todo.sample(limit, random_state=7)
    info = build_info()
    todo = todo.sort_values(['a', 'b'])
    items = list(zip(todo.pair_id, todo.a, todo.b))
    batches = [items[i:i + 25] for i in range(0, len(items), 25)]
    out = []
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(run_batch, b, info): b for b in batches}
        for i, f in enumerate(cf.as_completed(futs)):
            try:
                out.extend(f.result())
            except llm.BudgetExceeded:
                print('budget stop'); break
            except Exception as e:
                print('batch error', repr(e)[:200])
            if i % 50 == 0:
                print(f'{i}/{len(batches)} batches, spent ${llm.spent():.2f}', flush=True)
    j = pd.DataFrame(out).drop_duplicates('pair_id')
    j['model'] = llm.SONNET
    # escalate hard cases to Opus
    m = todo.merge(j, on='pair_id', how='left')
    hard = m[(m.relation.isna()) | (m.relation == 'unsure') | ((m.confidence < 0.6) & m.cross_source)]
    print('escalating', len(hard), 'hard pairs to Opus')
    items = list(zip(hard.pair_id, hard.a, hard.b))
    hb = [items[i:i + 15] for i in range(0, len(items), 15)]
    out2 = []
    with cf.ThreadPoolExecutor(4) as ex:
        futs = [ex.submit(run_batch, b, info, llm.OPUS, 'high', 'org_pair_adjudication_opus') for b in hb]
        for f in cf.as_completed(futs):
            try:
                out2.extend(f.result())
            except Exception as e:
                print('opus batch error', repr(e)[:200])
    if out2:
        j2 = pd.DataFrame(out2).drop_duplicates('pair_id'); j2['model'] = llm.OPUS
        j = pd.concat([j[~j.pair_id.isin(j2.pair_id)], j2], ignore_index=True)
    res = todo[['pair_id', 'a', 'b']].merge(j, on='pair_id', how='left')
    if prev is not None:
        res = pd.concat([prev, res], ignore_index=True)
    name = 'org_pair_judgments.parquet' if not limit else 'org_pair_judgments_trial.parquet'
    res.to_parquet(os.path.join(ER, name), index=False)
    print(res.relation.value_counts(dropna=False)); print(f'spent ${llm.spent():.2f}')


if __name__ == '__main__':
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(lim)
