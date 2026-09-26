"""Claude Sonnet sector labels for organization donors to ballot-measure and independent/general-purpose committees.

Scope: every non-individual donor name (Form 460 Schedule A, entity code not IND) that gave $10,000+ in 2010-2026 to
ballot-measure committees, or to general-purpose / primarily-formed-candidate committees (the committees that make
independent expenditures). Individuals are never sent or labelled (they are only reported in aggregate).
Output: data/insights/sector_labels.parquet (donor_name, sector, confidence, rationale). Cached and logged via pipeline/llm.py
(task insights_sector_classify). Hand-check sample: data/insights/sector_labels_check.csv (top 40 by dollars).
"""
import os, sys, json
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from llm import call_json, SONNET

ROOT = os.path.dirname(os.path.dirname(HERE))
INT = os.path.join(ROOT, 'data', 'interim')
OUTD = os.path.join(ROOT, 'data', 'insights')
os.makedirs(OUTD, exist_ok=True)
OUT = os.path.join(OUTD, 'sector_labels.parquet')

SECTORS = {
    'tech': 'technology companies: software, internet platforms, ride-hail and gig companies, home-sharing, crypto, AI, and committees they sponsor',
    'real_estate': 'real estate developers, landlords and property owners, realtors, building-owner and apartment associations, construction and development firms',
    'labor': 'labor unions, union councils and union-sponsored PACs (including police, fire and other public-employee associations)',
    'soda_tobacco_vape': 'soft-drink, tobacco and vaping companies and their trade associations',
    'business_group': 'cross-industry business groups: chambers of commerce, business alliances, Committee on Jobs, business-backed civic PACs that name a business sponsor',
    'finance': 'banks, investment firms, insurance',
    'health': 'hospitals, health systems, health-care companies, medical and public-health organizations',
    'sports_hospitality': 'sports teams, hotels, restaurants, tourism, entertainment venues',
    'utilities_waste': 'energy utilities, waste haulers, telecom carriers',
    'nonprofit_advocacy': 'nonprofits, foundations, advocacy and civic organizations, environmental, housing-advocacy and community groups',
    'party_political': 'political parties, candidate committees, ideological or slate PACs whose funding source is not evident from the name',
    'government': 'public agencies',
    'other_business': 'businesses not in the categories above',
    'unknown': 'cannot tell from the name',
}

SYSTEM = ('You label organizations that gave to San Francisco political committees by economic sector, for an aggregate chart. '
          'Use only what the name itself (and widely known facts about well-known organizations) supports; when unsure, say unknown '
          'or party_political. Trade associations go to their industry (e.g. a realtors association is real_estate, a beverage '
          'association is soda_tobacco_vape). A committee "sponsored by" an organization takes the sponsor\'s sector. Committees or PACs '
          'whose funders are not evident from the name are party_political.')

SCHEMA = {'type': 'object', 'properties': {'labels': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'i': {'type': 'integer'}, 'sector': {'type': 'string', 'enum': list(SECTORS)},
    'confidence': {'type': 'number'}, 'rationale': {'type': 'string'}},
    'required': ['i', 'sector', 'confidence', 'rationale'], 'additionalProperties': False}}},
    'required': ['labels'], 'additionalProperties': False}


# Analyst overrides after the hand check of the top 40 (data/insights/sector_labels_check.csv)
OVERRIDES = {
    'NEIGHBORS FOR A BETTER SAN FRANCISCO ADVOCACY': ('party_political', 'analyst override: a 501(c)(4) whose own funders are not evident from the name'),
    'NEIGHBORS FOR A BETTER SAN FRANCISCO': ('party_political', 'analyst override: funders not evident from the name'),
    'Neighbors for a Better San Francisco Advocacy': ('party_political', 'analyst override: funders not evident from the name'),
    'Dignity CA SEIU Local 2015': ('labor', 'analyst override: SEIU Local 2015 is a labor union'),
    'Dignity CA Service Employees International Union SEIU Local 2015': ('labor', 'analyst override: SEIU Local 2015 is a labor union'),
}


def apply_overrides(d):
    for n, (sec, why) in OVERRIDES.items():
        m = d.donor_name == n
        d.loc[m, 'sector'] = sec
        d.loc[m, 'rationale'] = why
        d.loc[m, 'confidence'] = 1.0
    return d


def donor_names():
    c = pd.read_parquet(os.path.join(INT, 'contributions.parquet'),
                        columns=['date', 'amount', 'recip_kind', 'is_individual', 'donor_name'])
    c = c[c.date.dt.year.between(2010, 2026) & (c.amount > 0) & ~c.is_individual]
    names = set()
    for kinds in (['ballot_measure'], ['general_purpose', 'candidate_pf']):
        o = c[c.recip_kind.isin(kinds)].groupby('donor_name').amount.sum()
        names |= set(o[o >= 10000].index)
    tot = c[c.donor_name.isin(names)].groupby('donor_name').amount.sum().sort_values(ascending=False)
    return list(tot.index), tot


def main():
    names, tot = donor_names()
    rows = []
    B = 120
    cats = '\n'.join(f'- {k}: {v}' for k, v in SECTORS.items())
    for k in range(0, len(names), B):
        batch = names[k:k + B]
        prompt = ('Sectors:\n' + cats + '\n\nLabel each organization (i = its number). Give a one-line rationale and a confidence 0-1.\n\n'
                  + '\n'.join(f'{i}. {n}' for i, n in enumerate(batch)))
        r = call_json('insights_sector_classify', prompt, SCHEMA, system=SYSTEM, model=SONNET, effort='low', max_tokens=32000)
        got = {x['i']: x for x in r['labels']}
        for i, n in enumerate(batch):
            x = got.get(i, {'sector': 'unknown', 'confidence': 0.0, 'rationale': 'not returned'})
            rows.append({'donor_name': n, 'sector': x['sector'], 'confidence': float(x['confidence']), 'rationale': x['rationale']})
        print(f'{k + len(batch)}/{len(names)}', flush=True)
    d = pd.DataFrame(rows)
    d['total_2010_2026'] = d.donor_name.map(tot)
    d = apply_overrides(d)
    d.to_parquet(OUT, index=False)
    d.sort_values('total_2010_2026', ascending=False).head(40).to_csv(os.path.join(OUTD, 'sector_labels_check.csv'), index=False)
    print(d.groupby('sector').total_2010_2026.agg(['size', 'sum']).sort_values('sum', ascending=False))


if __name__ == '__main__':
    main()
