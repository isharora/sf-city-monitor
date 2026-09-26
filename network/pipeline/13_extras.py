"""Extras for the site export (run after 11_export.py):
  graph.json                 pruned, graph-ready network (top edges by weight, aggregated per from->to pair and type)
  summaries/officials.json   per-official summaries (money raised by own committees 2015-2026, top org donors, IE for/against,
                             behested requested, lobbying contacts received, contracts approved by their body)
  summaries/orgs.json        per-organization summaries (contracts, city payments, contributions, lobbying, behested)
  (commentary_facts.json and commentary/*.json moved to 15_commentary.py)
  qa_report.json             data-contract QA checks
"""
import os, re, json, collections
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, '..', 'data', 'site')
AN = os.path.join(HERE, '..', 'data', 'analysis')
VAL = os.path.join(HERE, '..', 'data', 'validation')


def L(rel):
    return json.load(open(os.path.join(SITE, rel)))


def A(rel):
    return json.load(open(os.path.join(AN, rel)))


def W(rel, obj):
    p = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(obj, open(p, 'w'), separators=(',', ':'), ensure_ascii=False, default=lambda o: None if (isinstance(o, float) and o != o) else str(o))
    return os.path.getsize(p)


def money(x):
    a = abs(x)
    if a >= 1e9: return f'${x/1e9:.1f} billion'
    if a >= 1e6: return f'${x/1e6:.1f} million'
    if a >= 1e3: return f'${x/1e3:,.0f}k'
    return f'${x:,.0f}'


def pct(x, d=0):
    return f'{x*100:.{d}f}%'


def main():
    ents = L('entities.json')['entities']
    E = {e['id']: e for e in ents}
    flows = L('flows.json')['flows']
    meta = L('meta.json')
    fl = pd.DataFrame(flows)
    fl['year'] = fl.date.str[:4].astype(int)

    # ---------------- graph.json
    g = fl[fl.type != 'payment'].copy()
    g['w'] = np.where(g.amount.notna(), g.amount.fillna(0).abs(), g['count'] * 1000.0)   # contacts weighted $1,000 each for pruning only
    agg = g.groupby(['from', 'to', 'type']).agg(amount=('amount', 'sum'), count=('count', 'sum'), w=('w', 'sum'), first=('date', 'min'), last=('date', 'max'), n_flows=('id', 'size')).reset_index()
    # collapse committees into their official where known, for readability
    def fold(x):
        e = E.get(x, {})
        return e.get('official') or x if e.get('type') == 'committee' else x
    agg['f2'] = agg['from'].map(fold); agg['t2'] = agg['to'].map(fold)
    agg2 = agg.groupby(['f2', 't2', 'type']).agg(amount=('amount', 'sum'), count=('count', 'sum'), w=('w', 'sum'), first=('first', 'min'), last=('last', 'max')).reset_index()
    agg2 = agg2[agg2.f2 != agg2.t2]
    top = []
    for t, gg in agg2.groupby('type'):
        top.append(gg.sort_values('w', ascending=False).head({'contribution': 400, 'contract': 250, 'lobby_contact': 300, 'lobby_payment': 200, 'behested': 225}.get(t, 200)))
    top = pd.concat(top)
    top = top[top.w > 0]
    nodes_used = set(top.f2) | set(top.t2)
    gnodes = []
    for n in nodes_used:
        e = E.get(n, {'id': n, 'type': 'other', 'name': n})
        wsum = float(top[(top.f2 == n) | (top.t2 == n)].w.sum())
        gnodes.append({'id': n, 'type': e['type'], 'name': e.get('name'), 'cluster': e.get('cluster'), 'weight': round(wsum)})
    gedges = [{'from': r.f2, 'to': r.t2, 'type': r.type, 'amount': None if pd.isna(r.amount) or r.type == 'lobby_contact' else int(r.amount),
               'count': int(r['count']), 'first': r['first'], 'last': r['last']} for _, r in top.iterrows()]
    W('graph.json', {'sample': False, 'as_of': meta['as_of'], 'note': ('Pruned view: the strongest edges per flow type (2015-2026), aggregated per from->to pair; committees folded into their '
                                                                        'official; city payments omitted (they dwarf everything else). Lobbying contacts are weighted as $1,000 per contact for pruning only. '
                                                                        'Individuals appear only as aggregate nodes.'),
                     'nodes': gnodes, 'edges': gedges})

    # ---------------- summaries
    offs = [e for e in ents if e['type'] == 'official']
    com_of = collections.defaultdict(list)
    for e in ents:
        if e['type'] == 'committee' and e.get('official'):
            com_of[e['official']].append(e['id'])
    beh = L('analyses/behested.json')['rows']
    contrib = fl[fl.type == 'contribution']
    lob = fl[fl.type == 'lobby_contact']
    osum = []
    for o in offs:
        cs = com_of.get(o['id'], [])
        c = contrib[contrib.to.isin(cs)]
        if not len(c) and not len(lob[lob.to == o['id']]):
            continue
        named = c[~c['from'].str.startswith('ind-')].groupby('from').amount.sum().sort_values(ascending=False).head(10)
        by_type = c.groupby(c['from'].map(lambda x: 'individuals' if x == 'ind-all' else ('contractor-affiliated individuals' if str(x).startswith('ind-') else E.get(x, {}).get('type', 'other')))).amount.sum()
        b = [r for r in beh if r['official'] == o['id']]
        l = lob[lob.to == o['id']]
        osum.append({'official': o['id'], 'name': o['name'], 'office': o.get('office'), 'committees': cs,
                     'raised_2015_2026': float(c.amount.sum()), 'raised_by_source_type': {k: float(v) for k, v in by_type.items()},
                     'top_named_organizations': [{'entity': k, 'name': E.get(k, {}).get('name'), 'amount': float(v)} for k, v in named.items()],
                     'behested_requested': {'n': len(b), 'amount': float(sum(x['amount'] or 0 for x in b))},
                     'lobbying_contacts_received': int(l['count'].sum()), 'top_lobbying_clients': [{'entity': k, 'name': E.get(k, {}).get('name'), 'contacts': int(v)} for k, v in l.groupby('client')['count'].sum().sort_values(ascending=False).head(10).items()]})
    W('summaries/officials.json', {'sample': False, 'as_of': meta['as_of'], 'note': 'Money raised = contributions to the official\'s own and controlled committees, 2015-2026, nominal dollars.', 'officials': osum})
    orgs = [e for e in ents if e['type'] in ('contractor', 'nonprofit', 'donor_org')]
    by_from = fl.groupby(['from', 'type']).agg(amount=('amount', 'sum'), n=('count', 'sum'))
    by_to = fl.groupby(['to', 'type']).agg(amount=('amount', 'sum'), n=('count', 'sum'))
    lob_client = lob.groupby('client')['count'].sum()
    gsum = []
    for e in orgs:
        def gf(t):
            return float(by_from.loc[(e['id'], t), 'amount']) if (e['id'], t) in by_from.index else 0.0
        def gt(t):
            return float(by_to.loc[(e['id'], t), 'amount']) if (e['id'], t) in by_to.index else 0.0
        row = {'entity': e['id'], 'name': e['name'], 'type': e['type'], 'contracts_2015_2026': gt('contract'), 'city_payments_fy2015_on': gt('payment'),
               'contributions_given': gf('contribution'), 'lobbyist_payments': gf('lobby_payment'), 'lobbying_contacts_as_client': int(lob_client.get(e['id'], 0)),
               'behested_given': gf('behested'), 'behested_received': gt('behested')}
        emp = f"ind-emp-{e['id'].split('-', 1)[1]}"; prin = f"ind-prin-{e['id'].split('-', 1)[1]}"
        row['employee_giving'] = float(contrib[contrib['from'] == emp].amount.sum())
        row['principal_giving'] = float(contrib[contrib['from'] == prin].amount.sum())
        if any(v for k, v in row.items() if k not in ('entity', 'name', 'type')):
            gsum.append(row)
    W('summaries/orgs.json', {'sample': False, 'as_of': meta['as_of'], 'note': 'Totals from flows.json (2015-2026, nominal). employee_giving and principal_giving are aggregates of private individuals linked to the organization; they are not the organization\'s own money.', 'orgs': gsum})

    # commentary facts and commentary/*.json are written by 15_commentary.py (red-team pass 2); run it after this script.
    banw = L('analyses/ban_window.json')

    # ---------------- QA
    qa = {}
    ids = set(E)
    bad = [f['id'] for f in flows if f['from'] not in ids or f['to'] not in ids or (f.get('client') and f['client'] not in ids) or (f.get('behest_of') and f['behest_of'] not in ids)]
    qa['flow_endpoints_missing'] = len(bad)
    fids = {f['id'] for f in flows}
    an_refs = [r['flow'] for r in banw['records']] + [r['flow'] for r in L('analyses/behested.json')['rows']] + [r['flow'] for r in L('analyses/lobbying.json')['rows']] + [c['contract'] for c in banw['contracts']]
    qa['analysis_flow_ids_missing'] = sum(1 for x in an_refs if x not in fids)
    ind_names = [e['name'] for e in ents if e['type'] == 'individuals']
    qa['individual_entities'] = len(ind_names)
    qa['individual_entity_names_sample'] = ind_names[:5]
    zip_like = 0
    for e in ents:
        for k, val in e.items():
            if isinstance(val, str) and re.search(r'\b9[45]\d{3}\b', val) and k not in ('id',):
                zip_like += 1
    qa['zip_like_strings_in_entities'] = zip_like
    conc = L('analyses/concentration.json')['rows']
    cf = fl[fl.type == 'contribution'].copy(); cf['cycle'] = cf.year.map(lambda y: str(y if y % 2 == 0 else y + 1))
    tots = cf.groupby(['to', 'cycle']).amount.sum()
    mism = sum(1 for r in conc if abs(tots.get((r['committee'], r['cycle']), 0) - r['total']) > 1 + 0.001 * abs(r['total']))
    qa['concentration_total_mismatches'] = mism
    rv = [r for r in banw['records'] if r['review'] == 'appears_to_warrant_review']
    qa['review_rows_violating_rule'] = sum(1 for r in rv if not (r['inside_window'] and r['covered_official'] and r['why']))
    wins = {c['contract']: c for c in banw['contracts']}
    bad_in = 0
    for r in banw['records']:
        if r['inside_window']:
            c = wins.get(r['window_contract'])
            if c and not (c['window_post_approval'][0] <= r['date'] <= c['window_post_approval'][1]):
                bad_in += 1
    qa['inside_window_not_recomputable'] = bad_in
    npi = os.path.expanduser('~/sf-city-monitor/nonprofits/data/site/orgs/index.json')
    npids = {o['id'] for o in json.load(open(npi))['orgs']} if os.path.exists(npi) else set()
    qa['nonprofit_org_ids_missing'] = sum(1 for e in ents if e['type'] == 'nonprofit' and e.get('nonprofit_org') and e['nonprofit_org'] not in npids)
    qa['nonprofit_entities_with_org_link'] = sum(1 for e in ents if e['type'] == 'nonprofit' and e.get('nonprofit_org'))
    qa['nan_in_files'] = sum(open(os.path.join(SITE, p)).read().count('NaN') for p in ['flows.json', 'entities.json', 'analyses/ban_window.json', 'analyses/behested.json', 'analyses/lobbying.json', 'analyses/concentration.json', 'analyses/loop.json'])
    qa['rules_verified_note'] = ('rules[].cite/verify checked on 2026-09-26 against the enacted code text and history notes on American Legal Publishing, '
                                 'Ordinance 129-18 (sfbos.org), SFEC guidance and the FPPC behested-payment page; see verify fields and data/redteam/redteam2.json.')
    W('qa_report.json', qa)
    # update meta.files with extras
    meta = L('meta.json')
    for rel in ['graph.json', 'summaries/officials.json', 'summaries/orgs.json', 'commentary_facts.json', 'qa_report.json']:
        meta['files'][f'network/{rel}'] = {'bytes': os.path.getsize(os.path.join(SITE, rel))}
    for f in sorted(os.listdir(os.path.join(SITE, 'commentary'))):
        meta['files'][f'commentary/{f}'] = {'bytes': os.path.getsize(os.path.join(SITE, 'commentary', f))}
    W('meta.json', meta)
    print(json.dumps(qa, indent=1))


if __name__ == '__main__':
    main()
