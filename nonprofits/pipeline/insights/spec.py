"""Text and chart templates for the nonprofit-money insights page, shared by build_insights.py and verify_insights.py.

Every number shown to readers is a placeholder {key|fmt} filled from a computed value (V) or an '@CH:key' chart
array, so verify_insights.py can recompute each one independently from the source tables. Template text may contain
only years (FY2019, 2024) and a few fixed tokens (Form 990, Tier 2, COVID-19 ...), which build and verify check.
"""
import re

AS_OF = '2026-09-26'
INTRO = ('These findings about the city\'s payments to nonprofits were chosen from about thirty candidates we tested against '
         'the city\'s vendor payments, contracts and fund records, the organizations\' own IRS Form 990 filings, the Controller\'s '
         'monitoring reports and published outcome measures. Each survived at least three robustness checks (other base years and '
         'deflators, excluding organizations that mostly pass money on, alternative definitions and thresholds), and a separate script '
         'recomputes every number from the source tables. Checks that weakened a finding are reported, and findings that did not hold under every test '
         'are labeled fragile. One insight uses an AI-assisted (Claude) classification of contract records, checked against model-free measures. '
         'FY2026 (July 2025 to June 2026) is included where noted; a few late invoices may still post. Dollar figures are city payments to organizations matched to IRS '
         'exempt-organization records; real dollars are FY2025 dollars. Unusual is not improper: these are patterns worth '
         'discussing, not findings about anyone\'s conduct.')

MINUS = '−'


def _signed(v, s):
    return ('+' if round(v * 100) > 0 else (MINUS if round(v * 100) < 0 else '')) + s


FMT = {
    'int': lambda v: f'{round(round(v, 6)):,}',
    'aint': lambda v: f'{abs(round(round(v, 6))):,}',
    'pct': lambda v: f'{v * 100:.0f}%',
    'pct1': lambda v: f'{v * 100:.1f}%',
    'apct': lambda v: f'{abs(v) * 100:.0f}%',
    'spct': lambda v: _signed(v, f'{abs(v) * 100:.0f}%'),
    'mil': lambda v: f'${v / 1e6:,.0f} million',
    'amil': lambda v: f'${abs(v) / 1e6:,.0f} million',
    'mil1': lambda v: f'${v / 1e6:,.1f} million',
    'bil2': lambda v: f'${v / 1e9:,.2f} billion',
    'bil1': lambda v: f'${v / 1e9:,.1f} billion',
    'usdk': lambda v: f'${round(v / 1000.0) * 1000:,}',
    'x1': lambda v: f'{v:.1f}',
    'x0': lambda v: f'{v:.0f}',
    'f1': lambda v: f'{v:.1f}',
    'f2': lambda v: f'{v:.2f}',
    'f3': lambda v: f'{v:.3f}',
    'fy': lambda v: f'FY{int(v)}',
    'str': lambda v: str(v),
    'inv': lambda v: f'{round(1 / v):.0f}',
    'r10': lambda v: f'{int(round(v / 10.0)) * 10:,}',
    'r100': lambda v: f'{int(round(v / 100.0)) * 100:,}',
}
PH = re.compile(r'\{(\w+)\|(\w+)\}')


def render_str(s, V):
    def rep(m):
        k, f = m.group(1), m.group(2)
        if k not in V:
            raise KeyError(f'missing value {k}')
        return FMT[f](V[k])
    return PH.sub(rep, s)


def render(obj, V, CH):
    """Recursively render a template. Strings get placeholders filled; '@CH:key' pulls a chart array."""
    if isinstance(obj, str):
        if obj.startswith('@CH:'):
            return [None if v is None else (round(float(v), 2) if isinstance(v, float) or hasattr(v, 'dtype') else v) for v in CH[obj[4:]]]
        return render_str(obj, V)
    if isinstance(obj, list):
        return [render(o, V, CH) for o in obj]
    if isinstance(obj, dict):
        return {k: render(v, V, CH) for k, v in obj.items()}
    return obj


ALLOWED_DIGIT_TOKENS = [r'FY\d{4}–\d{2}\b', r'FY\d{4}', r'\b(19|20)\d{2}\b', r'Form 990', r'\b990s?\b', r'Tier [23]\b', r'COVID-19',
                        r'CUURS49BSA0', r'\b[a-z0-9]{4}-[a-z0-9]{4}\b', r'= 100\b', r'Prop [A-Z] of 20\d\d', r'June 30', r'\$1 million', r'\$2 million', r'\$4 million', r'\$500,000', r'\$250,000', r'\$1 in\b',
                        r'\b(25|50|60|75|100|105)%', r'\b1\.5\b', r'\b0\.7\b', r'\b[Tt]op[- ](20|50)\b', r'\b20 largest\b', r'Chapter 21', r'measure 7169', r'95% interval']

P = 'nonprofits/data/'
SRC = {
    'cells': P + 'site/payments/cells_2007.json … cells_2026.json#amt',
    'cells1625': P + 'site/payments/cells_2016.json; ' + P + 'site/payments/cells_2025.json#amt (deflated with ' + P + 'site/meta.json#deflator)',
    'cells1925': P + 'site/payments/cells_2019.json; ' + P + 'site/payments/cells_2025.json#amt (deflated with ' + P + 'site/meta.json#deflator)',
    'orgs': P + 'site/orgs/index.json#area',
    'fund': P + 'raw/insights/payments_fund_fy2019.csv … payments_fund_fy2026.csv#fund (DataSF n9pm-xkyq by fund)',
    'fin': P + 'site/finances/form990_2011.json … form990_2025.json#total_revenue,months_reserves,exec_comp',
    'fin24': P + 'site/finances/form990_2024.json#total_revenue,months_reserves',
    'find': P + 'site/reviews/findings.json#result',
    'rt': P + 'redteam/redteam.json',
    'llm': P + 'redteam/parts/contracts_llm.json#primary_driver',
    'dbl': P + 'redteam/parts/doubled_contracts.json#term_extended_days,annualized_ratio',
    'con': P + 'site/contracts/all_1.json … all_5.json#authority_class,agreed,start',
    'out': P + 'site/aggregates/outcomes.json#value',
    'sc': P + 'raw/supplier_contracts.csv (DataSF cqi5-hm2d)#Supplier Type,Non-Profit,Contract Type',
    'm23': P + 'reviews/text/monitoring_FY23_annual_report.txt',
    'm22': P + 'reviews/text/monitoring_FY22_annual_report.txt',
    'm24': P + 'reviews/text/monitoring_FY24_annual_report.txt',
}

FY_NOTE = 'Fiscal years run July to June and are labeled by the year they end.'
REAL_NOTE = 'Real dollars are FY2025 dollars (SF-Oakland-Hayward CPI-U, BLS CUURS49BSA0).'
PAY_NOTE = ('Source: city Vendor Payments (DataSF n9pm-xkyq), expenditure payments to organizations matched to IRS exempt-organization '
            'records.')
DEP_NOTE = ('City dependency = city payments in the fiscal year divided by total revenue on the organization\'s Form 990 for the '
            'matching year.')

# display names for chart labels (organizations' own spellings)
DISPLAY = {"CHILDREN'S COUNCIL OF SAN FRANCISCO": "Children's Council of SF", 'THE SF HOUSING ACCELERATOR FUND': 'SF Housing Accelerator Fund',
           "WU YEE CHILDREN'S SERVICES": "Wu Yee Children's Services", 'TIDES CENTER': 'Tides Center', 'HELUNA HEALTH': 'Heluna Health',
           'SAN FRANCISCO STUDY CENTER INC': 'San Francisco Study Center', 'SAN FRANCISCO PUBLIC HEALTH FOUNDATION': 'SF Public Health Foundation',
           'HOMEBRIDGE INC': 'Homebridge', 'COMMUNITY ARTS STABLIZATION TRUST': 'Community Arts Stabilization Trust',
           'MAIN STREET LAUNCH': 'Main Street Launch', 'SAN FRANCISCO HOUSING DEVELOPMENT CORPOR': 'SF Housing Development Corp.',
           'CHINESE CULTURE FOUNDATION OF SF': 'Chinese Culture Foundation', 'FIVE KEYS SCHOOLS AND PROGRAMS': 'Five Keys Schools and Programs',
           'Mid Market Foundation': 'Mid Market Foundation', 'COMMUNITY INITIATIVES': 'Community Initiatives'}


def disp(n):
    return DISPLAY.get(n, n.title())


INSIGHTS = [
    # 1 -----------------------------------------------------------------------------------------------------------------
    dict(key='growth_areas', id='homelessness-led-the-growth', theme='spending-growth',
         title='Homelessness groups accounted for {sh_homeless|pct} of the {dtot|bil2} real rise in nonprofit payments',
         dek='City payments to nonprofits rose from {t16|mil} (in FY2025 dollars) in FY2016 to {t25|bil2} in FY2025. Organizations working on '
             'homelessness and housing added {d_homeless|mil} of the {dtot|bil2} increase; children, youth and families added {d_youth|mil} and '
             'health and behavioral health {d_health|mil}.',
         why_it_matters='Three service areas account for {sh_top3|pct} of the growth, so decisions about homelessness, early childhood and behavioral '
                        'health budgets largely determine how much the city spends through nonprofits. The figures do not separate higher costs, such as wages and rents, from expanded services. Arts and culture, by contrast, received no more '
                        'in real terms than in FY2016.',
         surprise='Health was the largest service area in FY2016, but homelessness organizations grew {g_homeless|spct} in real terms, {rel|x1} times as fast as health organizations.',
         numbers=[
             dict(label='City payments to nonprofits, real, FY2016 → FY2025', value='{t16|mil} → {t25|bil2} ({g|spct})', source=SRC['cells1625']),
             dict(label='Added by homelessness and housing organizations', value='{d_homeless|mil} ({sh_homeless|pct} of the increase)', source=SRC['cells1625'] + '; ' + SRC['orgs']),
             dict(label='Added by children, youth and families organizations', value='{d_youth|mil} ({sh_youth|pct})', source=SRC['cells1625'] + '; ' + SRC['orgs']),
             dict(label='Added by health and behavioral health organizations', value='{d_health|mil} ({sh_health|pct})', source=SRC['cells1625'] + '; ' + SRC['orgs']),
         ],
         chart=dict(type='waterfall', title='Where the extra billion went',
                    subtitle='Change in city payments to nonprofits by the organization\'s main service area, FY2016 to FY2025, millions of FY2025 dollars',
                    x=dict(label='Service area', values='@CH:x'), y=dict(label='Millions of FY2025 dollars', unit='$M'),
                    series=[dict(name='Payments', values='@CH:v')], highlight='Homelessness and housing',
                    note=PAY_NOTE + ' Each organization has one service area (its main line of work), so a homelessness nonprofit\'s health contracts count as homelessness. ' + REAL_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Held from FY2019 instead of FY2016 (after the accounting-system change): homelessness organizations {sh19_homeless|pct} of the growth, the top three areas {sh19_top3|pct}.',
             'Held to FY2026: homelessness organizations {sh26_homeless|pct} of the growth since FY2016.',
             'Held excluding organizations that mostly pass money on (childcare-subsidy administrators, a loan fund, fiscal sponsors): homelessness {shx_homeless|pct}, children and families {shx_youth|pct}.',
             'Held with other deflators: real growth {g_us|pct} with the U.S. CPI and {g_svc|pct} with the U.S. services CPI (independent re-check).',
         ], what_could_make_it_wrong='Service areas are assigned per organization, not per contract, so multi-service agencies are counted in one area. '
                                     'Department reorganizations (the homelessness department began in FY2017) do not affect this split, which is by organization.'),
         caveats=['In nominal dollars payments grew {nom_x|x1} times over the same period; the real (inflation-adjusted) change is shown, and the total depends on the base year (see the base-year card).',
                  'Much of the children, youth and families growth is childcare subsidy money that administrators pass on to providers; excluding such organizations, that area\'s share of the growth falls from {sh_youth|pct} to {shx_youth|pct}.'],
         explore=dict(view='np-flows', params={'years': '2016-2025', 'area': 'homeless'}, label='See payments by service area'),
         departments=['HOM', 'DPH', 'DEC', 'HSA'], tags=['growth', 'homelessness', 'service areas']),

    # 2 -----------------------------------------------------------------------------------------------------------------
    dict(key='funding', id='dedicated-funds-paid-for-growth', theme='spending-growth',
         title='Voter-approved funds, led by Our City Our Home, paid {sh_ded|pct} of nonprofit growth since FY2019',
         dek='Payments to nonprofits rose {dt|mil} before inflation from FY2019 to FY2025. The Our City Our Home homelessness fund went from nothing to {ocoh25|mil}, '
             'the Children and Families Fund from {cff19|mil} to {cff25|mil}, while General Fund payments grew {gf_g|pct} and fell from '
             '{gf_share19|pct} to {gf_share25|pct} of the total.',
         why_it_matters='Money from voter-approved funds must be spent on the purposes voters set, so a growing share of the nonprofit budget is '
                        'partly insulated from ordinary budget trade-offs, and also tied to the tax revenue behind each fund. That shapes what can be cut '
                        'or expanded when the budget tightens.',
         surprise='Payments charged directly to federal COVID-19 stimulus funds peaked at {covid_peak|mil} ({covid_peak_fy|fy}); federal aid that went into the General Fund, such as revenue replacement or FEMA reimbursement, is not visible in fund labels.',
         numbers=[
             dict(label='Increase in payments to nonprofits, FY2019 → FY2025 (nominal)', value='{dt|mil}', source=SRC['fund']),
             dict(label='Our City Our Home Fund (homelessness gross receipts tax), FY2019 → FY2025', value='{ocoh19|usdk} → {ocoh25|mil} ({sh_ocoh|pct} of the increase)', source=SRC['fund'] + ' (funds named Our City Our Home / OCOH)'),
             dict(label='Children and Families Fund, FY2019 → FY2025', value='{cff19|mil} → {cff25|mil} ({sh_cff|pct} of the increase)', source=SRC['fund']),
             dict(label="Children's Fund and Dignity Fund (seniors and adults with disabilities)", value='{cdf19|mil} → {cdf25|mil} ({sh_cdf|pct})', source=SRC['fund']),
             dict(label='General Fund, FY2019 → FY2025', value='{gf19|mil} → {gf25|mil} ({sh_gf|pct} of the increase)', source=SRC['fund'] + ' (fund type GEN_FUND)'),
             dict(label='Largest year of payments charged to federal COVID-19 stimulus funds', value='{covid_peak|mil} ({covid_peak_fy|fy})', source=SRC['fund'] + ' (funds with COVID in the name)'),
         ],
         chart=dict(type='stacked', title='New dedicated funds carried much of the growth',
                    subtitle='City payments to nonprofits by fund, millions of nominal dollars',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='Millions of dollars', unit='$M'),
                    series=[dict(name='General Fund', values='@CH:gf'), dict(name='Our City Our Home', values='@CH:ocoh'),
                            dict(name='Children and Families Fund', values='@CH:cff'), dict(name="Children's Fund and Dignity Fund", values='@CH:cdf'),
                            dict(name='Grants and other funds', values='@CH:oth')],
                    highlight='Our City Our Home',
                    note='Source: Vendor Payments (DataSF n9pm-xkyq) aggregated by fund for organizations matched to IRS exempt-organization records; totals equal the dashboard\'s. '
                         '"Grants and other funds" are state and federal grant funds, the hotel-tax arts fund, the opioid settlement fund and other special revenue and enterprise funds. ' + FY_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Held in real dollars: dedicated funds {sh_ded_real|pct} of the real increase, the General Fund {sh_gf_real|pct}.',
             'Held to FY2026: dedicated funds {sh_ded26|pct} of the increase since FY2019, the General Fund {sh_gf26|pct}.',
             'Held as a reconciliation check: fund-level payments add up to the dashboard total (FY2025 within {recon_25|aint} dollars).',
             'Held when checking where Our City Our Home money goes: {ocoh_hom_share|pct} of it was paid by the homelessness department (HSH) in FY2025.',
         ], what_could_make_it_wrong='Fund names describe the account the city charged, not every revenue source behind it; the Children and Families Fund also '
                                     'holds state money and existed before FY2019. Starting in FY2019 avoids the older accounting system, whose fund names differ.'),
         caveats=['Nominal dollars: the fund mix is an accounting identity in the year of payment.',
                  'Payments from Our City Our Home (the November 2018 Proposition C business tax for homelessness) begin in FY2020 and scale up from FY2022, after legal challenges to the tax were resolved.'],
         explore=dict(view='np-flows', params={'years': '2019-2025', 'dept': 'HOM'}, label="See HSH's nonprofit payments"),
         departments=['HOM', 'DEC', 'CHF', 'HSA'], tags=['funding', 'Our City Our Home', 'set-asides']),

    # 3 -----------------------------------------------------------------------------------------------------------------
    dict(key='incumbents', id='growth-went-to-existing-partners', theme='spending-growth',
         title='{sh_cont|pct} of the growth went to nonprofits the city already paid in FY2016',
         dek='The {n_cont|int} organizations paid in both FY2016 and FY2025 received {d_cont|mil} more in real terms, a {g_cont|pct} increase; the {n_ent|int} '
             'organizations new since FY2016 received {d_ent|mil} in FY2025. Each year, first-time recipients got on average {ent_share_avg|pct1} of the dollars.',
         why_it_matters='The city mostly expanded existing relationships rather than bringing in new providers. That can mean continuity for clients and '
                        'experienced partners able to scale up; it also means most new money went to incumbents. These data do not show whether that came through '
                        'competitive solicitations or amendments to existing contracts.',
         surprise='Growth was uneven: the median continuing organization grew {g_cont_median|pct} after inflation, while the 20 largest recipients of FY2025 '
                  'account for {sh_top20_growth|pct} of the total increase (a group that, by construction, includes those that grew most).',
         numbers=[
             dict(label='Real increase at organizations paid in both FY2016 and FY2025', value='{d_cont|mil} ({n_cont|int} organizations, {g_cont|spct})', source=SRC['cells1625']),
             dict(label='FY2025 payments to organizations not paid in FY2016', value='{d_ent|mil} ({n_ent|int} organizations)', source=SRC['cells1625']),
             dict(label='FY2016 payments to organizations not paid in FY2025', value='{d_ex|amil} ({n_ex|int} organizations)', source=SRC['cells1625']),
             dict(label='Share of each year\'s dollars going to first-time recipients, FY2008–FY2026 average', value='{ent_share_avg|pct1} (highest {ent_share_max|pct1})', source=SRC['cells']),
         ],
         chart=dict(type='waterfall', title='Existing partners took most of the new money',
                    subtitle='City payments to nonprofits, FY2016 to FY2025, millions of FY2025 dollars',
                    x=dict(label='Component', values='@CH:x'), y=dict(label='Millions of FY2025 dollars', unit='$M'),
                    series=[dict(name='Payments', values='@CH:v')], highlight='Growth at continuing organizations',
                    note=PAY_NOTE + ' "Continuing" = paid in both FY2016 and FY2025. ' + REAL_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Held from FY2019: continuing organizations took {sh_cont19|pct} of the growth.',
             'Held counting as new only organizations never paid from FY2007 to FY2016: they account for {sh_never|pct} of the growth.',
             'Held excluding organizations that mostly pass money on: continuing organizations {sh_cont_x|pct} of the growth.',
             'Held at the median across all organizations paid in each year: real payment {med16|usdk} in FY2016, {med25|usdk} in FY2025.',
         ], what_could_make_it_wrong='Organizations that merged or changed their tax ID look like an exit plus an entry. A new organization may also run a program '
                                     'that an older one ran before, so "new" does not always mean a new program.'),
         caveats=['Counts organizations, not programs; a continuing organization may have won new contracts.'],
         explore=dict(view='np-orgs', params={'years': '2016-2025'}, label='See every organization paid'),
         departments=[], tags=['growth', 'incumbents', 'new providers']),

    # 4 -----------------------------------------------------------------------------------------------------------------
    dict(key='stepup', id='pandemic-step-up-stayed', theme='spending-growth',
         title='Payments kept rising after the pandemic: up {g19_25|pct} in real terms from FY2019 to FY2025',
         dek='Real payments to nonprofits rose {g19_21|pct} from FY2019 to FY2021 and another {g21_25|pct} from FY2021 to FY2025, to {r2025|bil2}, '
             'while the number of organizations paid rose only from {n19|int} to {n25|int}. FY2026 figures show a {g25_26|apct} dip.',
         why_it_matters='The higher level of spending has become the baseline. Voter-approved dedicated taxes paid for a large part of the growth and the General '
                        'Fund for most of the rest, which may include federal pandemic aid that fund labels do not show. The figures do not separate higher costs from '
                        'expanded services. With city revenues under pressure, whether that level can be sustained is a live budget question.',
         surprise='One might expect spending to recede after the pandemic; instead it rose another {g21_25|pct} from FY2021 to FY2025, though at a slower yearly pace than in FY2019–FY2021.',
         numbers=[
             dict(label='Real payments FY2019 → FY2021 → FY2025', value='{r2019|bil2} → {r2021|bil2} → {r2025|bil2}', source=SRC['cells']),
             dict(label='Change FY2025 → FY2026 (real)', value='{g25_26|spct}', source=SRC['cells']),
             dict(label='Organizations paid, FY2019 → FY2025', value='{n19|int} → {n25|int}', source=SRC['cells']),
         ],
         chart=dict(type='line', title='No post-pandemic retreat',
                    subtitle='City payments to nonprofits, millions of FY2025 dollars',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='Millions of FY2025 dollars', unit='$M'),
                    series=[dict(name='Payments (real)', values='@CH:v')],
                    annotations=[dict(x=2018, label='Accounting change'), dict(x=2020, label='COVID-19')],
                    note=PAY_NOTE + ' FY2018 is low partly because of the switch to a new accounting system. ' + REAL_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Held in the Controller\'s own nonprofit spending dataset (qkex-vh98): nominal growth FY2019–FY2025 {ctrl_nom|pct}, against {dash_nom|pct} here.',
             'Held excluding organizations that mostly pass money on: real growth FY2019–FY2025 {g19_25_x|pct}.',
             'Held without the ten largest FY2025 recipients: real growth FY2019–FY2025 {g19_25_t10|pct}.',
         ], what_could_make_it_wrong='FY2026 payments could still rise slightly as late invoices post. The consumer price index is an imperfect deflator for '
                                     'wage-heavy nonprofit budgets; the U.S. services index gives somewhat lower real growth (independent re-check).'),
         caveats=['FY2019 is used as the pre-pandemic year because FY2018 is distorted by the accounting-system change.'],
         explore=dict(view='np-overview', params={'years': '2019-2026'}, label='See the payment trend'),
         departments=[], tags=['pandemic', 'baseline', 'trend']),

    # 16 ----------------------------------------------------------------------------------------------------------------
    dict(key='base_year', id='growth-rate-depends-on-base-year', theme='measurement',
         title='Real growth ranges from {g_min|pct} to {g_max|pct} depending on a start in FY2015, FY2016 or FY2017',
         dek='Measured to FY2025, real growth in nonprofit payments is {g2015|pct} from FY2015, {g2016|pct} from FY2016 and {g2017|pct} from FY2017. '
             'FY2017 was unusually high and FY2018 unusually low ({dip18|spct}), around the city\'s switch to a new accounting system, before a {jump19|spct} jump in FY2019.',
         why_it_matters='Any single "growth since year X" figure for nonprofit spending can look large or modest depending on the start year. Comparisons across the FY2018 system '
                        'change should report several base years: the average real growth rate is {cagr|pct1} a year from FY2016 but {cagr17|pct1} from FY2017.',
         surprise='Public Health\'s nonprofit payments dropped from {dph17|mil} to {dph18|mil} in FY2018 and recovered to {dph19|mil} in FY2019, a swing that more likely reflects payment timing or recording than changes in services.',
         numbers=[
             dict(label='Real growth to FY2025 from FY2015 / FY2016 / FY2017', value='{g2015|spct} / {g2016|spct} / {g2017|spct}', source=SRC['cells']),
             dict(label='Real change FY2017 → FY2018 and FY2018 → FY2019', value='{dip18|spct} and {jump19|spct}', source=SRC['cells']),
             dict(label='Public Health payments to nonprofits FY2017 / FY2018 / FY2019 (nominal)', value='{dph17|mil} / {dph18|mil} / {dph19|mil}', source=SRC['cells'] + ' (dept DPH)'),
             dict(label='Average real growth per year, FY2016 → FY2025', value='{cagr|pct1}', source=SRC['cells']),
         ],
         chart=dict(type='bar', title='Pick a year, get a growth rate',
                    subtitle='Real growth in city payments to nonprofits to FY2025, by starting fiscal year (%)',
                    x=dict(label='Starting year', values='@CH:x'), y=dict(label='Percent growth to FY2025', unit='%'),
                    series=[dict(name='Real growth to FY2025', values='@CH:v')], highlight='From FY2016',
                    note=PAY_NOTE + ' ' + REAL_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Held over a longer window: {cagr_1319|pct1} a year after inflation from FY2013 to FY2025.',
             'Held in an independent recomputation from the raw payment files: {rt_g2017|pct} from FY2017.',
             'Held with the U.S. CPI instead of the Bay Area CPI (independent re-check): real growth from FY2016 {g_us|pct}.',
         ], what_could_make_it_wrong='Part of the FY2017–FY2019 swing may be real timing of contract payments rather than accounting; the data cannot separate them.'),
         caveats=['The dashboard\'s headline uses FY2016 as the base; the independent recomputation reports every base year from FY2015 to FY2019.'],
         explore=dict(view='np-overview', params={'years': '2013-2025'}, label='See the long-run trend'),
         departments=['DPH'], tags=['measurement', 'base year', 'accounting change']),

    # 5 -----------------------------------------------------------------------------------------------------------------
    dict(key='dep_flat', id='dependency-held-steady', theme='financial-health',
         title='City payments grew fast, but large recipients\' median reliance on the city held at {med24|pct}',
         dek='Among organizations paid at least $1 million, the median got {med16|pct} of its revenue from the city in FY2016 and {med24|pct} in FY2024. '
             'For the {panel_n|int} organizations in both years, city payments rose {panel_city_g|pct} (nominal) but the median share moved only from {panel_a|pct} to {panel_b|pct}.',
         why_it_matters='The growth did not simply make existing nonprofits more reliant on the city: at the typical organization, revenue from other '
                        'sources (including state, federal and other government money) grew roughly in step. The number of large, highly dependent organizations still rose, because more organizations crossed the $1 million line.',
         surprise='With city payments to these organizations up {panel_city_g|pct} before inflation, a reader might expect reliance on the city to climb steeply; the median barely moved.',
         numbers=[
             dict(label='Median city share of revenue, organizations paid ≥ $1 million, FY2016 → FY2024', value='{med16|pct} → {med24|pct} ({n16|int} → {n24|int} organizations)', source=SRC['fin'] + '; ' + SRC['cells']),
             dict(label='Share of those organizations above 75% dependent', value='{gt75_16|pct} → {gt75_24|pct}', source=SRC['fin'] + '; ' + SRC['cells']),
             dict(label='Same organizations in both years: median share', value='{panel_a|pct} → {panel_b|pct} ({panel_n|int} organizations)', source=SRC['fin'] + '; ' + SRC['cells']),
             dict(label='Same organizations: city payments FY2016 → FY2024 (before inflation)', value='{panel_city_g|spct}', source=SRC['cells']),
         ],
         chart=dict(type='line', title='Reliance on the city has stayed in a narrow band',
                    subtitle='Organizations paid at least $1 million in the year: median city share of revenue, and share above 75% dependent (%)',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='Percent', unit='%'),
                    series=[dict(name='Median city share of revenue', values='@CH:med'), dict(name='Share of organizations above 75% dependent', values='@CH:gt75')],
                    highlight='Median city share of revenue',
                    note=DEP_NOTE + ' FY2018 is low partly because of the city\'s switch to a new accounting system. Source: city Vendor Payments and IRS Form 990 (e-file and ProPublica). ' + FY_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Held excluding organizations that mostly pass money on: median {medx16|pct} in FY2016 and {medx24|pct} in FY2024.',
             'Held with a $1 million threshold in real dollars: median {med16_real|pct} in FY2016 and {med24_real|pct} in FY2024.',
             'Held with city payments prorated to each organization\'s own tax year (independent re-check): FY2024 median {med24_pro|pct}.',
             'Held in FY2025: median {med25|pct}; every year from FY2012 to FY2025 falls between {med_min|pct} and {med_max|pct}.',
         ], what_could_make_it_wrong='Organizations whose tax year does not end in June are compared with the city fiscal year that ends in the same '
                                     'calendar year, which blurs single years. Money the city passes through other nonprofits shows up as non-city revenue.'),
         caveats=['Total revenue on the Form 990 includes government money from all sources; "city share" counts only direct city payments.'],
         explore=dict(view='np-dependency', params={'years': '2016-2024'}, label='See city dependency by organization'),
         departments=[], tags=['dependency', 'Form 990']),

    # 6 -----------------------------------------------------------------------------------------------------------------
    dict(key='corrective', id='dependency-and-corrective-action', theme='financial-health',
         title='Nonprofits 75%+ city-funded were {ratio|x1} times as likely to get a serious monitoring status',
         dek='In the Controller\'s monitoring for FY2023–FY2025, {rate_hi|pct} of organization-years with 75% or more of revenue from the city ended on '
             'corrective action, elevated concern, Tier 3 or red-flag status, against {rate_lo|pct1} for the rest. Counting each organization once, it was '
             '{org_hi_sev|int} of {org_hi_n|int} against {org_lo_sev|int} of {org_lo_n|int}.',
         why_it_matters='If heavy reliance on the city goes with weaker finances or administration, monitoring and technical assistance can be aimed where risk '
                        'is highest. The pattern is an association based on few cases, not evidence that city funding causes problems: organizations in difficulty may lose '
                        'other funders and so become more city-dependent, city contracts often leave little money for administration, and heavily funded groups may be '
                        'reviewed more closely. A monitoring designation is not a finding of misuse of funds.',
         surprise=None,
         numbers=[
             dict(label='Most serious statuses (corrective action, elevated concern, Tier 3 or red flag), org-years 75% or more city-funded', value='{sev_hi|int} of {n_hi|int} ({rate_hi|pct})', source=SRC['find'] + '; ' + SRC['fin'] + '; ' + SRC['cells']),
             dict(label='Most serious statuses, all other org-years', value='{sev_lo|int} of {n_lo|int} ({rate_lo|pct1})', source=SRC['find'] + '; ' + SRC['fin'] + '; ' + SRC['cells']),
             dict(label='Organizations counted once: a serious status at least once', value='{org_hi_sev|int} of {org_hi_n|int} vs {org_lo_sev|int} of {org_lo_n|int}', source=SRC['find']),
             dict(label='Adjusted odds ratio (size, service area, year), 95% interval', value='{or_adj|x1} ({or_lo|x1} to {or_hi|x1})', source=SRC['rt'] + '#dependency_corrective_action'),
         ],
         chart=dict(type='bar', title='Serious monitoring statuses were more common at more city-dependent nonprofits',
                    subtitle='Share of organization-years ending on corrective action, elevated concern, Tier 3 or red flag, by city share of revenue, FY2023–FY2025 (%)',
                    x=dict(label='City share of revenue', values='@CH:x'), y=dict(label='Percent of organization-years', unit='%'),
                    series=[dict(name='Serious monitoring status', values='@CH:v', n='@CH:n')], highlight='75% or more',
                    note='Source: Controller, Citywide Nonprofit Monitoring and Capacity Building Program annual reports FY2023–FY2025 (per-organization appendices); '
                         + DEP_NOTE + ' Monitoring checks fiscal and administrative standards; a designation is not a finding of misuse of funds.'),
         robustness=dict(verdict='robust', checks=[
             'Held after controlling for size, service area and year (independent re-check): odds ratio {or_adj|x1}, 95% interval {or_lo|x1} to {or_hi|x1}; {or_res|x1} when also controlling for thin reserves.',
             'Held when shuffling dependency labels between organizations (permutation test): p = {perm_p|f3}.',
             'Held within size bands, service areas and years (Mantel-Haenszel risk ratios at least {mh_min|x1}).',
             'Did not hold clearly in each organization\'s first monitored year only: {first_hi|int} vs {first_lo|int} cases, too few to tell.',
         ], what_could_make_it_wrong='The pattern rests on {sev_total|int} org-years with a serious status at {sev_orgs|int} organizations, many of them repeat designations of the same '
                                     'organization. Organizations that rely heavily on the city may also be the ones departments watch most closely.'),
         caveats=['The corrective-action tier policy began in FY2024; earlier years use elevated-concern and red-flag statuses.',
                  'Only organizations in the Controller\'s joint monitoring pool are included.'],
         explore=dict(view='np-reviews', params={'years': '2023-2025'}, label='See monitoring results'),
         departments=[], tags=['monitoring', 'corrective action', 'dependency']),

    # 7 -----------------------------------------------------------------------------------------------------------------
    dict(key='contract_growth', id='doubled-contracts-mostly-got-longer', theme='contracting',
         title='Of {n_dbl|int} nonprofit contracts that doubled, only {n_ann2|int} doubled in amount per year of term',
         dek='Among {n_con|int} nonprofit contracts of at least $4 million, {n_dbl|int} at least doubled from their first observed amount. {n_ext|int} of those had their end date '
             'pushed out by six months or more, and the amount per year of term doubled in only {n_ann2|int}. An AI-assisted review of each record (Claude) classed '
             '{llm_extension|int} as mainly longer terms and {llm_expansion|int} as mainly larger yearly amounts.',
         why_it_matters='A contract that "doubled" sounds like costs doubling, but in most of these cases the city extended the same provider for more years. Actual '
                        'yearly payments still grew on most of those with payment records ({n_rr15|int} of {n_rr|int} rose by half or more before inflation). Extensions '
                        'keep services running without a break, and many solicitations authorize multi-year terms up front; the policy question is how long '
                        'services should run before they are solicited again.',
         surprise='In the contract amounts, most of the doubling reflects longer terms rather than bigger yearly amounts, even though spending grew too: the amount per year of term doubled in only {n_ann2|int} of the {n_dbl|int} cases.',
         numbers=[
             dict(label='Large nonprofit contracts that at least doubled since first observed', value='{n_dbl|int} of {n_con|int}', source=SRC['dbl'] + '; ' + P + 'site/contracts/contracts.json'),
             dict(label='Of those, end date extended by six months or more', value='{n_ext|int}', source=SRC['dbl']),
             dict(label='Of those, amount per year of term at least doubled', value='{n_ann2|int}', source=SRC['dbl']),
             dict(label='Classified mainly as a longer term / a larger yearly amount', value='{llm_extension|int} / {llm_expansion|int}', source=SRC['llm']),
         ],
         chart=dict(type='hbar', title='Why contracts doubled',
                    subtitle='Contracts of at least $4 million that doubled since first observed, by main driver (count)',
                    x=dict(label='Main driver', values='@CH:x'), y=dict(label='Contracts', unit='count'),
                    series=[dict(name='Contracts', values='@CH:v')], highlight='Mainly a longer term',
                    note='Source: Supplier Contracts (DataSF cqi5-hm2d) snapshots from 2021, 2022, 2025 and 2026, with vendor payments per contract. '
                         'Drivers were classified by Claude (Opus, high effort) from each contract\'s term history, per-year amounts and payments, and checked against the model-free measures in the evidence.'),
         robustness=dict(verdict='robust', checks=[
             'Held without the model: {n_ext|int} of {n_dbl|int} had the end date pushed out, and {n_ann_lt15|int} grew less than 1.5 times per year of term.',
             'Held among confident classifications (at least 0.7): {hi_ext|int} of {hi_n|int} mainly longer terms.',
             'Did not fully hold on actual spending: yearly payments rose 1.5 times or more (nominal) on {n_rr15|int} of the {n_rr|int} contracts with a payment history, so many longer contracts also spent more per year.',
         ], what_could_make_it_wrong='Contracts first observed in 2022 or 2025 may have been amended before then, which the snapshots cannot see. Short title fields '
                                     'rarely show whether scope changed ({cannot_tell|int} of {n_dbl|int} cannot tell).'),
         caveats=['"Doubled" compares the current amount with the first snapshot, not with the original signed amount.'],
         explore=dict(view='np-growth', params={}, label='See contract growth by contract'),
         departments=['DPH', 'HOM', 'HSA'], tags=['contracts', 'amendments', 'extensions']),

    # 8 -----------------------------------------------------------------------------------------------------------------
    dict(key='homeless_pit', id='homelessness-spending-and-the-count', theme='outcomes',
         title='HSH nonprofit spending rose {s_g|pct}; preliminary 2026 count: fewer outside, total about flat',
         dek='Real payments by the homelessness department (HSH) to nonprofits rose from {s19|mil} in FY2019 to {s26|mil} in FY2026. Between the January 2019 and '
             '2026 counts, people counted unsheltered fell from {uns19|int} to {uns26|int} and people in shelter rose from {sh19|int} to about {sh26|r10}, while the '
             'total went from {tot19|int} to {tot26|int}.',
         why_it_matters='The count shifted from street to shelter while the total held roughly steady. These counts cannot show what the spending caused: shelter '
                        'expansion, housing placements that take people out of the count, new people becoming homeless and regional housing costs all move the '
                        'numbers at once. Deciding where the next dollar should go would take program-level outcome data.',
         surprise='The total is about where it was in 2019, but the split changed sharply: about {d_uns|r100} fewer people were counted outside and about {d_sh|r100} more in shelter (2026 figures preliminary).',
         numbers=[
             dict(label='HSH payments to nonprofits, real, FY2019 → FY2026', value='{s19|mil} → {s26|mil} ({s_g|spct})', source=SRC['cells'] + ' (dept HOM)'),
             dict(label='Unsheltered, January count 2019 → 2026', value='{uns19|int} → {uns26|int} ({uns_g|spct})', source=SRC['out'] + ' (pit_unsheltered)'),
             dict(label='Sheltered (total minus unsheltered; 2026 derived from preliminary, rounded figures)', value='{sh19|int} → about {sh26|r10} ({sh_g|spct})', source=SRC['out'] + ' (pit_total, pit_unsheltered)'),
             dict(label='Total homeless count', value='{tot19|int} → {tot26|int} ({tot_g|spct})', source=SRC['out'] + ' (pit_total)'),
         ],
         chart=dict(type='hbar', title='More spending, fewer people outside, same total',
                    subtitle='Percent change, FY2019 to FY2026 (spending, real dollars) and January 2019 to January 2026 (Point-in-Time counts)',
                    x=dict(label='Measure', values='@CH:x'), y=dict(label='Percent change', unit='%'),
                    series=[dict(name='Change', values='@CH:v')], highlight='People unsheltered',
                    note='Sources: city Vendor Payments (department HOM); Point-in-Time counts from HSH and the Controller (DataSF kc49-udxn, measure 7169) and the preliminary '
                         '2026 results on sf.gov. ' + REAL_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Held in direction but weaker with the final 2024 count instead of the preliminary 2026 one: unsheltered {uns_g24|spct}, total {tot_g24|spct}, spending FY2019–FY2024 {s_g24|spct}.',
             'Held counting all homelessness-area organizations, whichever department paid them: real spending {area_g|spct}.',
             'Held in nominal dollars: HSH payments {s_g_nom|spct}.',
         ], what_could_make_it_wrong='The 2026 figures are preliminary and the unsheltered number is rounded. Point-in-Time counts are single January nights and '
                                     'depend on methods and weather; they measure the population, not the effect of any one program.'),
         caveats=['No causal claim: regional housing costs, the economy and inflows from other counties also drive the count.',
                  'Spending also pays for permanent supportive housing for formerly homeless people, who are not in the count at all.'],
         explore=dict(view='np-flows', params={'years': '2019-2026', 'dept': 'HOM'}, label="See HSH's payments to nonprofits"),
         departments=['HOM'], tags=['homelessness', 'outcomes', 'Point-in-Time count']),

    # 9 -----------------------------------------------------------------------------------------------------------------
    dict(key='reserves', id='dependent-nonprofits-thin-reserves', theme='financial-health',
         title='Under a month of reserves: {hi_lt1|pct} of heavily city-funded nonprofits vs {lo_lt1|pct} of others',
         dek='In FY2024, {hi_lt1|pct} of large recipients getting at least 75% of revenue from the city had less than one month of unrestricted net assets, against '
             '{lo_lt1|pct} of the others; their median cushion was {hi_med|f1} months against {lo_med|f1}.',
         why_it_matters='Organizations with thin reserves depend on the city paying on time; a late payment or a delayed contract can force layoffs or borrowing. '
                        'Thin cushions are not a sign of mismanagement: city contracts often reimburse costs and leave little room for surpluses, so organizations '
                        'funded mostly by the city have few ways to build reserves.',
         surprise='Heavily city-funded organizations were no more likely to run a deficit ({hi_def|pct} vs {lo_def|pct}); the difference is in the cushion, not the annual result.',
         numbers=[
             dict(label='Under one month of reserves, organizations ≥ 75% city-funded (FY2024)', value='{hi_lt1|pct} ({hi_k|int} of {hi_n|int} organizations)', source=SRC['fin24'] + '; ' + SRC['cells']),
             dict(label='Under one month of reserves, other organizations paid ≥ $1 million', value='{lo_lt1|pct} ({lo_k|int} of {lo_n|int} organizations)', source=SRC['fin24'] + '; ' + SRC['cells']),
             dict(label='Median months of unrestricted reserves', value='{hi_med|f1} vs {lo_med|f1}', source=SRC['fin24']),
             dict(label='Ran a deficit in FY2024 (expenses above revenue)', value='{hi_def|pct} vs {lo_def|pct}', source=SRC['fin24'] + '#total_expenses,total_revenue'),
         ],
         chart=dict(type='bar', title='Thin cushions cluster among the most city-dependent',
                    subtitle='Organizations paid at least $1 million in FY2024: share with under one month of unrestricted reserves, by city share of revenue (%)',
                    x=dict(label='City share of revenue', values='@CH:x'), y=dict(label='Percent of organizations', unit='%'),
                    series=[dict(name='Under one month of reserves', values='@CH:v', n='@CH:n')], highlight='75% or more',
                    note='Months of reserves = unrestricted net assets divided by one month of expenses, from the Form 990. ' + DEP_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Held in FY2023: {hi_lt1_2023|pct} vs {lo_lt1_2023|pct}.',
             'Held in FY2025: {hi_lt1_2025|pct} vs {lo_lt1_2025|pct}.',
             'Held excluding pass-through organizations and dependency above 100%: {x_hi|pct} vs {x_lo|pct}.',
             'Held with a two-month threshold: {hi_lt2|pct} vs {lo_lt2|pct}.',
         ], what_could_make_it_wrong='Unrestricted net assets include buildings and equipment, so they overstate cash for property-owning organizations and '
                                     'the comparison is rough. Only {hi_n|int} organizations are in the high-dependency group.'),
         caveats=['Form 990 year-end figures are a snapshot; reserves can change quickly.',
                  '"Reserves" here means unrestricted net assets, which include buildings and equipment, not cash on hand; differing fiscal years make some dependency ratios imprecise.'],
         explore=dict(view='np-pay', params={'years': '2024'}, label='See reserves by organization'),
         departments=[], tags=['reserves', 'dependency', 'Form 990']),

    # 10 ----------------------------------------------------------------------------------------------------------------
    dict(key='emergency', id='emergency-authority-contracts', theme='contracting',
         title='Emergency or waiver authority covered {sh21|pct} of nonprofit contract dollars begun in FY2021',
         dek='Of {all_total|bil1} in current nonprofit contract amounts, {em_total|bil2} ({em_share|pct}) was awarded under emergency procurement or ordinances '
             'that waived competitive solicitation, {em_hom|pct} of it at the homelessness department (HSH), which was created in FY2017 and absorbed programs from other departments. The share rose from {sh19|pct1} of contracts starting '
             'in FY2019 to {sh21|pct} in FY2021 and was still {sh25|pct} in FY2025.',
         why_it_matters='The jump coincides with the COVID-19 emergency, when the city had to stand up shelter and health services quickly. These authorities come from city law and from ordinances the Board of Supervisors passed to speed up shelter and behavioral-health services. '
                        'Faster contracting can cost competition and price discovery, so how long such authority stays in place is a fair question.',
         surprise='The share fell after the pandemic but did not return to pre-2020 levels: {core_share|pct} of such dollars in contracts starting FY2024 or later used an ordinance the Board of Supervisors approved in 2023 for homelessness, overdose and behavioral-health contracting.',
         numbers=[
             dict(label='Contract amounts under emergency or waiver authority (current awarded amount)', value='{em_total|bil2} of {all_total|bil1} ({em_share|pct})', source=SRC['con']),
             dict(label='Share of that at the homelessness department', value='{em_hom|pct}', source=SRC['con']),
             dict(label='Share of dollars in contracts starting FY2019 / FY2021 / FY2025', value='{sh19|pct1} / {sh21|pct} / {sh25|pct}', source=SRC['con']),
             dict(label='Emergency or waiver dollars in contracts starting FY2024 or later under the 2023 homelessness and behavioral-health ordinance', value='{core_share|pct}', source=SRC['con'] + '; ' + SRC['sc'].split(' (')[0] + '#Purchasing Authority'),
         ],
         chart=dict(type='bar', title='Emergency and waiver contracting rose in the pandemic and stays above pre-2020 levels',
                    subtitle='Share of nonprofit contract dollars awarded under emergency or bid-waiver authority, by fiscal year the contract started (%)',
                    x=dict(label='Fiscal year the contract started', values='@CH:x'), y=dict(label='Percent of contract dollars', unit='%'),
                    series=[dict(name='Emergency or waiver authority', values='@CH:v')], highlight='2021',
                    note='Source: Supplier Contracts (DataSF cqi5-hm2d), prime contracts of at least $250,000 with matched nonprofits. Authority classes from the '
                         'contracts\' purchasing-authority text; emergency or waiver includes Chapter 21 emergency procurement and ordinances that waived solicitation.'),
         robustness=dict(verdict='robust', checks=[
             'Held counting contracts rather than dollars: {shn21|pct} of contracts starting in FY2021, {shn25|pct} in FY2025.',
             'Held for contracts of at least $1 million: {big21|pct} of FY2021 dollars.',
             'Held without the five largest FY2021 contracts: {x5_21|pct}.',
             'Did not hold outside the homelessness department: only {nh21|pct1} of other departments\' FY2021 contract dollars.',
         ], what_could_make_it_wrong='Contract amounts are current ceilings, which may include later amendments, not spending; contracts starting in FY2026 may still be added; and the authority text is how the city recorded it; a few '
                                     'contracts may have been competed informally even under a waiver.'),
         caveats=['Using emergency or waiver authority is legal when authorized; it is unusual, not improper.'],
         explore=dict(view='np-growth', params={'dept': 'HOM'}, label="See HSH's contracts"),
         departments=['HOM', 'DPH'], tags=['contracts', 'emergency procurement', 'competition']),

    # 11 ----------------------------------------------------------------------------------------------------------------
    dict(key='churn', id='top-recipients-reshuffled', theme='concentration',
         title='The top 20 still get {sh25|pct} of dollars, but only {kept_16_25|int} of FY2016\'s top 20 remain',
         dek='The 20 largest recipients have received between {sh_min|pct} and {sh_max|pct} of nonprofit dollars every year since FY2008. Membership turned over '
             'faster after FY2018: about {avg_post|x1} entries a year (including organizations re-entering), against {avg_pre|x1} a year from FY2009 to FY2017.',
         why_it_matters='Concentration is steady, but membership changes: {n_newcomers|int} organizations paid under $1 million in FY2016 were in the FY2025 top 20, including '
                        'a housing loan fund whose city payments are largely loans. Some of this reflects new or transferred programs rather than open competition.',
         surprise='Only {always|int} organizations have been in the top 20 every year since FY2007.',
         numbers=[
             dict(label='Top-20 share of nonprofit dollars, FY2016 → FY2025', value='{sh16|pct} → {sh25|pct}', source=SRC['cells']),
             dict(label='FY2016 top-20 organizations still in the FY2025 top 20', value='{kept_16_25|int}', source=SRC['cells1625']),
             dict(label='Entries into the top 20 per year (including re-entries), FY2009–FY2017 vs FY2019–FY2026', value='{avg_pre|x1} vs {avg_post|x1}', source=SRC['cells']),
             dict(label='FY2025 top-20 members paid under $1 million (nominal) in FY2016', value='{n_newcomers|int}', source=SRC['cells']),
         ],
         chart=dict(type='bar', title='More turnover at the top since FY2018',
                    subtitle='Number of organizations entering the top 20 recipients each fiscal year, including re-entries',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='Entries into the top 20', unit='count'),
                    series=[dict(name='Entries', values='@CH:v')], annotations=[dict(x=2018, label='Accounting change')],
                    note=PAY_NOTE + ' Ranked by nominal payments within each year.'),
         robustness=dict(verdict='robust', checks=[
             'Held for first-time entries only (never in the top 20 since FY2007): {ft_pre|x1} a year before FY2018 vs {ft_post|x1} after.',
             'Held for the top 50: {t50_pre|x1} entries a year before FY2018 vs {t50_post|x1} after.',
             'Held excluding pass-through organizations: {x_pre|x1} vs {x_post|x1} entries a year.',
             'Held for concentration: the top-20 share stayed between {sh_min|pct} and {sh_max|pct} in every year FY2008–FY2026.',
         ], what_could_make_it_wrong='Reorganizations and new departments move contracts between providers in bulk (for example childcare subsidies and '
                                     'shelter operations), so some turnover reflects a few large program transfers rather than broad competition.'),
         caveats=['Ranks are by city payments, not by organization size.'],
         explore=dict(view='np-flows', params={'years': '2016-2025'}, label='See the largest recipients'),
         departments=[], tags=['concentration', 'top recipients', 'turnover']),

    # 12 ----------------------------------------------------------------------------------------------------------------
    dict(key='passthrough', id='pass-through-organizations', theme='concentration',
         title='About $1 in {pt_share|inv} goes to groups that mostly pass money on, led by childcare subsidies',
         dek='In FY2025, {pt25|mil} ({pt_share|pct}) went to {n_pt|int} organizations that mainly pass city money to families, borrowers or projects: '
             "childcare-subsidy administrators, a housing loan fund and fiscal sponsors. Children's Council of San Francisco alone received {cc25|mil}, up from {cc16|mil} in FY2016 (nominal); {cc_cff_share|pct} of its FY2025 city payments were "
             "charged to the Children and Families Fund, the city\'s early-childhood fund.",
         why_it_matters='Counting these dollars as "nonprofit spending" overstates what nonprofits themselves spend on staff and services, and makes the largest '
                        'recipient look like the largest provider. Excluding them, real growth since FY2016 is {g_x|pct} rather than {g_all|pct}.',
         surprise="The city's largest nonprofit recipient is mainly a childcare-subsidy administrator: grants and assistance were {cc_grants_share|pct} of its expenses in its 2025 Form 990.",
         numbers=[
             dict(label='FY2025 payments to pass-through and fiscal-sponsor organizations', value='{pt25|mil} ({pt_share|pct} of {t25|bil2})', source=SRC['cells'] + '; ' + SRC['rt'] + '#total_fy2025'),
             dict(label="Children's Council of San Francisco, FY2016 → FY2025 (nominal dollars, before inflation)", value='{cc16|mil} → {cc25|mil}', source=SRC['cells']),
             dict(label='Real growth FY2016 → FY2025, all vs excluding pass-through organizations', value='{g_all|pct} vs {g_x|pct}', source=SRC['rt'] + '#real_growth_fy2016_2025'),
             dict(label="Children's Council: grants and assistance as a share of expenses (Form 990, tax year ending June 2025)", value='{cc_grants_share|pct}', source=P + 'interim/aligned.parquet#grants_paid,total_expenses'),
             dict(label="Controller's own FY2025 nonprofit spending total (narrower definition)", value='{ctrl25|bil2}', source=SRC['rt'] + '#total_fy2025 (DataSF qkex-vh98)'),
         ],
         chart=dict(type='hbar', title='The largest pass-through recipients',
                    subtitle='FY2025 city payments, millions of dollars',
                    x=dict(label='Organization', values='@CH:x'), y=dict(label='Millions of dollars', unit='$M'),
                    series=[dict(name='FY2025 payments', values='@CH:v')], highlight="Children's Council of SF",
                    note=PAY_NOTE + ' Pass-through list from the independent re-check: childcare-subsidy administrators, a loan fund and fiscal sponsors or intermediaries.'),
         robustness=dict(verdict='robust', checks=[
             'Held in FY2016 on the same list: {pt_share16|pct} of dollars, so the share roughly doubled.',
             'Held against the Controller\'s narrower definition, which excludes the main childcare-subsidy contracts: {ctrl25|bil2} in FY2025, about {ctrl_gap|mil} less.',
             'Held when loans are separated: {loans25|mil} of FY2025 payments were city loans to nonprofits, so grants and service payments to pass-through organizations were still about {pt_noloan|mil}.',
         ], what_could_make_it_wrong='The list is a judgment: fiscal sponsors and organizations such as Wu Yee Children\'s Services and Heluna Health also deliver services directly, and some service providers regrant part of '
                                     'their funds. The share depends on which organizations are included.'),
         caveats=['Pass-through is a description of the funding role, not a criticism; administering subsidies is the service.'],
         explore=dict(view='org', params={'id': 'org-942221305'}, label="See Children's Council's profile"),
         departments=['DEC', 'HSA', 'MYR'], tags=['pass-through', 'childcare', 'fiscal sponsors']),

    # 13 ----------------------------------------------------------------------------------------------------------------
    dict(key='monitoring', id='monitoring-findings-returned-to-normal', theme='measurement',
         title='Monitoring findings more than tripled after FY2022, back to about the FY2019 level',
         dek='The share of monitored nonprofits ending the Controller\'s review with unresolved findings or worse rose from {f2022|pct1} in FY2022 to {f2023|pct} '
             'in FY2023, {f2024|pct} in FY2024 and {f2025|pct} in FY2025. In FY2019, before the pandemic, the Controller reported {f2019|pct} not in full conformance.',
         why_it_matters='Read naively, the jump suggests nonprofits got worse at managing money. The Controller attributes it to the end of pandemic-era '
                        'discretionary and streamlined monitoring, fewer good-performance waivers and more consistent monitors, which points to FY2022 as the outlier rather than FY2023 onward.',
         surprise='Among the {panel_n|int} organizations monitored in both FY2022 and FY2023, the share with findings rose from {panel_f22|pct} to {panel_f23|pct}, '
                  'so a change in who was monitored does not explain the jump.',
         numbers=[
             dict(label='Unresolved findings or worse at final status, FY2022 → FY2023 → FY2025', value='{f2022|pct1} → {f2023|pct} → {f2025|pct}', source=SRC['find']),
             dict(label='Not in full conformance at final status, FY2019 (from the Controller\'s FY2023 report; the definition may differ slightly from later years)', value='{f2019|pct}', source=SRC['m23'] + ' ("In FY19, … ended the cycle in full conformance")'),
             dict(label='Good-performance waivers granted, FY2022 → FY2023 → FY2024', value='{w22|int} → {w23|int} → {w24|int}', source=SRC['m22'] + '; ' + SRC['m23'] + '; ' + SRC['m24']),
             dict(label='Corrective action, elevated concern, Tier 3 or red flag, FY2022 → FY2025', value='{tier2022|int} → {tier2025|int}', source=SRC['find']),
         ],
         chart=dict(type='bar', title='FY2022 was the outlier',
                    subtitle='Share of monitored nonprofits ending the review with unresolved findings or a more severe status (%)',
                    x=dict(label='Monitoring year', values='@CH:x'), y=dict(label='Percent of monitored nonprofits', unit='%'),
                    series=[dict(name='Unresolved findings or worse', values='@CH:v')], highlight='2022',
                    note='Source: Controller, Citywide Nonprofit Monitoring and Capacity Building Program annual reports; FY2019 is the share not in full conformance from the FY2023 report\'s comparison, whose definition may differ slightly; '
                         'FY2020 and FY2021 were not published. ' + FY_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Held for the same organizations: {panel_f22|pct} → {panel_f23|pct} among {panel_n|int} monitored both years.',
             'Held against the report\'s own count: {fy23_unres|pct} with unresolved findings in FY2023.',
             'Held in the report narrative: FY2023 conformance was the same as pre-COVID years; waivers fell from {w22|int} to {w24|int}.',
         ], what_could_make_it_wrong='Standards also changed (for example the operating-cash test was halved in FY2024), so years are not strictly '
                                     'comparable. Severe designations rose too ({tier2022|int} to {tier2025|int}), partly because the tier policy only began in FY2024.'),
         caveats=['A monitoring finding concerns fiscal and administrative standards; it is not evidence of misuse of funds.'],
         explore=dict(view='np-reviews', params={}, label='See monitoring results by year'),
         departments=['CON'], tags=['monitoring', 'measurement', 'Controller']),

    # 14 ----------------------------------------------------------------------------------------------------------------
    dict(key='exec_pay', id='executive-pay-below-peers', theme='staffing',
         title='Top pay at the most city-dependent nonprofits trails same-size peers by {large_g_hi|apct} to {g_hi|apct}',
         dek='Comparing each organization\'s highest-paid officer with the pay expected for its budget size in FY2024, the {n_hi|int} organizations getting at least 75% '
             'of revenue from the city paid a median {g_hi|apct} less than expected; those under 25% city-funded were at {g_lo|spct}. Limiting peers to organizations '
             'paid at least $1 million by the city shrinks the gap to {large_g_hi|apct}.',
         why_it_matters='Concern about executive pay at city-funded nonprofits is common. On this evidence, the organizations that rely most on the city do not '
                        'pay their leaders more than same-size peers, and probably pay less. That may reflect the kind of work they do, limits on administrative costs '
                        'in city contracts or part-year officers; it could also affect recruiting.',
         surprise=None,
         numbers=[
             dict(label='Median pay gap vs same-size organizations, ≥ 75% city-funded (FY2024)', value='{g_hi|spct} ({n_hi|int} organizations)', source=SRC['fin'] + '#exec_comp,total_expenses'),
             dict(label='Median pay gap, under 25% city-funded', value='{g_lo|spct}', source=SRC['fin'] + '#exec_comp,total_expenses'),
             dict(label='Pay rises with size: elasticity of top pay to expenses', value='{b|f2} ({n|int} organizations)', source=SRC['fin'] + '#exec_comp,total_expenses'),
         ],
         chart=dict(type='bar', title='More city-dependent, lower pay for size',
                    subtitle='Median gap between top-officer pay and the pay expected for an organization of the same expense size, FY2024 (%); with a narrower peer group the top band is {large_g_hi|spct}',
                    x=dict(label='City share of revenue', values='@CH:x'), y=dict(label='Percent above or below expected', unit='%'),
                    series=[dict(name='Pay gap', values='@CH:v', n='@CH:n')], highlight='75% or more',
                    note='Organizations with at least $1 million in expenses and any city payment; expected pay from a log-log fit of top-officer pay (Form 990 Part VII, '
                         'all compensation) on total expenses across the same organizations. ' + DEP_NOTE),
         robustness=dict(verdict='fragile', checks=[
             'Held in other years: {g_hi_2022|spct} (FY2022), {g_hi_2023|spct} (FY2023), {g_hi_2025|spct} (FY2025).',
             'Held with service-area controls: {adj_hi|spct} for the most dependent group.',
             'Held excluding organizations that mostly pass money on (whose large pass-through expenses make pay look low for size): {x_g_hi|spct}.',
             'Did not hold at full strength when the peer group is limited to organizations paid at least $1 million by the city: {large_g_hi|spct}, still below but much smaller.',
         ], what_could_make_it_wrong='The peer group matters: the wider comparison includes hospitals, universities and museums that pay more at any size, and '
                                     'service-area controls may not fully capture that; restricting peers to large city contractors cuts the gap to {large_g_hi|apct}. '
                                     'The Form 990 does not say whether the top officer worked full time or the full year, and the most dependent group has only {n_hi|int} organizations.'),
         caveats=['Compares organizations, not individuals; no executive is singled out.',
                  'Sector pay norms here come from the city\'s own nonprofit vendors, not a national survey.'],
         explore=dict(view='np-pay', params={'years': '2024'}, label='See executive pay against size'),
         departments=[], tags=['executive pay', 'Form 990', 'dependency']),

    # 15 ----------------------------------------------------------------------------------------------------------------
    dict(key='measures', id='spending-outpaced-people-served', theme='outcomes',
         title='Department nonprofit payments rose {s_min|pct}–{s_max|pct} in real terms, faster than counts served',
         dek='In five services with a consistent published measure, real payments to nonprofits by the department rose faster than the count served, which '
             'fell, held or grew slowly: children and youth served by DCYF {m0|spct} (spending {s0|spct}), DPH mental health clients {m1|spct} ({s1|spct}), '
             'households HSH placed in housing {m3|spct} ({s3|spct}).',
         why_it_matters='In all {n_up|int} comparisons the department\'s nonprofit payments rose faster than the published count of people served. Because the '
                        'payments fund much more than the measured service, this is not a cost per person. Higher wages, deeper services, costlier clients or '
                        'other programs could all explain it, but it is a fair question for budget hearings.',
         surprise=None,
         numbers=[
             dict(label='DCYF: children and youth served vs real nonprofit payments, FY2019 → FY2025', value='{m0|spct} vs {s0|spct}', source=SRC['out'] + '; ' + SRC['cells']),
             dict(label='DPH: unique mental health clients vs payments, FY2020 → FY2025', value='{m1|spct} vs {s1|spct}', source=SRC['out'] + '; ' + SRC['cells']),
             dict(label='DPH: unique substance use clients vs payments, FY2020 → FY2025', value='{m2|spct} vs {s2|spct}', source=SRC['out'] + '; ' + SRC['cells']),
             dict(label='HSH: households placed vs payments, FY2023 → FY2025', value='{m3|spct} vs {s3|spct}', source=SRC['out'] + '; ' + SRC['cells']),
             dict(label='HSA: home-delivered meals vs payments, FY2018 → FY2025', value='{m4|spct} vs {s4|spct}', source=SRC['out'] + '; ' + SRC['cells']),
         ],
         chart=dict(type='bar', title='Spending up, counts flat or down',
                    subtitle='Percent change in the department\'s real payments to nonprofits and in the published count served, over each measure\'s consistent years',
                    x=dict(label='Measure', values='@CH:x'), y=dict(label='Percent change', unit='%'),
                    series=[dict(name='Real payments to nonprofits', values='@CH:spend'), dict(name='Count served', values='@CH:served')],
                    highlight='Count served',
                    note='Windows: DCYF FY2019–FY2025, DPH FY2020–FY2025, HSH FY2023–FY2025 (one consistent placement series), HSA FY2018–FY2025. Counts cover '
                         'all providers, including city staff. The two DPH bars share one department-wide payment figure. ' + REAL_NOTE),
         robustness=dict(verdict='fragile', checks=[
             'Did not hold for DCYF from FY2022: spending {chf22_s|spct}, served {chf22_m|spct}, because DCYF payments fell in FY2025.',
             'Held for DCYF to FY2024: spending {chf24_s|spct}, served {chf24_m|spct}.',
             'Held for HSH to FY2026 (placements as first published for the full year through June): spending {hom26_s|spct}, placements {hom26_m|spct}.',
         ], what_could_make_it_wrong='Department payments cover far more than the measured service, and counts of unique clients say nothing about the intensity '
                                     'or quality of care. The pandemic depressed some counts in the base years and raised costs.'),
         caveats=['Descriptive only; no measure here isolates what nonprofit contracts bought.',
                  'Results depend on the window, and the HSH comparison covers only two years.',
                  'Counts include clients served by city staff, while the payments cover nonprofits only.'],
         explore=dict(view='np-overview', params={'years': '2019-2025'}, label='See outcomes against payments'),
         departments=['CHF', 'DPH', 'HOM', 'HSA'], tags=['outcomes', 'cost per person', 'measures']),

    # 17 ----------------------------------------------------------------------------------------------------------------
    dict(key='fast_risers', id='fastest-rising-dependency', theme='financial-health',
         title='{n|int} nonprofits went from under 25% to over 60% city-funded within five years',
         dek="Children's Council of San Francisco, a childcare-subsidy administrator, went from {o0_d0|pct} to {o0_d1|pct} of revenue from the city between {o0_y0|fy} and {o0_y1|fy}, as its city "
             'payments grew from {o0_c0|mil} to {o0_c1|mil}; Homebridge went from {o1_d0|pct1} to {o1_d1|pct} between {o1_y0|fy} and {o1_y1|fy}. Such shifts often reflect the city choosing an established organization to run or expand a program, or a change in how the money is paid.',
         why_it_matters='Whatever the reason, a quick shift to city funding changes an organization\'s risk profile: it needs the cash-flow and compliance capacity of a government '
                        'contractor, and the city becomes exposed if that single provider struggles.',
         surprise=None,
         numbers=[
             dict(label='Organizations (revenue ≥ $500,000) that went from under 25% to 60%–105% city-funded within five years, with ≥ $2 million from the city', value='{n|int}', source=SRC['fin'] + '; ' + SRC['cells']),
             dict(label="Children's Council of San Francisco", value='{o0_d0|pct} ({o0_y0|fy}) → {o0_d1|pct} ({o0_y1|fy})', source=SRC['fin'] + '; ' + SRC['cells']),
             dict(label='Homebridge', value='{o1_d0|pct1} ({o1_y0|fy}) → {o1_d1|pct} ({o1_y1|fy})', source=SRC['fin'] + '; ' + SRC['cells']),
             dict(label='Of the {n|int}, still at least 50% city-funded in their latest filing', value='{n_still|int}', source=SRC['fin']),
         ],
         chart=dict(type='slope', title='From a minor funder to the main one',
                    subtitle='City share of revenue (%) in the starting year and when it first passed 60%, the six largest by city dollars (years differ by organization)',
                    x=dict(label='Point', values='@CH:x'), y=dict(label='City share of revenue (%)', unit='%'),
                    series='@SLOPE', note=DEP_NOTE + ' Source: city Vendor Payments and IRS Form 990.'),
         robustness=dict(verdict='robust', checks=[
             'Held with a 50% end threshold: {n50|int} organizations.',
             'Held beyond a single filing: {n_conf|int} of the {n|int} were at least 50% city-funded again in one of the next two years\' filings.',
             'Held excluding organizations that mostly pass money on: {n_x|int} of the {n|int} remain (the one dropped is {x_drop|str}).',
             'Did not always last: only {n_still|int} of the {n|int} remain at least 50% city-funded in their latest filing.',
         ], what_could_make_it_wrong='A one-year mismatch between the city fiscal year and a non-June tax year can inflate a single year\'s ratio; the threshold '
                                     'of 105% screens out the worst mismatches. City loans and money passed on to others can appear in city payments but not in Form 990 revenue, which inflates the ratio for lenders and housing developers.'),
         caveats=['Rising dependency is a description of funding mix, not a judgment about the organization.',
                  'A rise can also reflect a change in payment channel: money that earlier reached an organization through another public agency now shows as a direct city payment.'],
         explore=dict(view='np-dependency', params={}, label='See dependency by organization'),
         departments=[], tags=['dependency', 'organizations']),

    # 18 ----------------------------------------------------------------------------------------------------------------
    dict(key='subcontractors', id='subcontracting-is-invisible', theme='measurement',
         title='The city\'s contract data list subcontractors on {np_sub|int} of {np_n|int} nonprofit contracts',
         dek='Supplier Contracts records subcontractors on {fp_ps|pct} of for-profit professional-services contracts but on {np_ps|pct1} of nonprofit ones, and on '
             '{gr_sub|int} of the {gr_n|int} grant agreements for any recipient; grants are {np_grant_share|pct} of nonprofit contracts.',
         why_it_matters='When a funded nonprofit passes work to other organizations, the city\'s contract dataset usually does not show it. The field may mainly '
                        'track certified local-business subcontracting goals, which often do not apply to grants or nonprofit contracts. The Controller\'s "Subcontracts" '
                        'monitoring standard is one check; otherwise, tracing where money ends up requires contract documents or the organizations\' own filings.',
         surprise='Part of the gap is about contract type: grant agreements almost never list subcontractors, whoever the recipient is. But even among professional-services contracts, nonprofits rarely have one listed.',
         numbers=[
             dict(label='Nonprofit prime contracts with any subcontractor listed', value='{np_sub|int} of {np_n|int}', source=SRC['sc']),
             dict(label='Professional-services contracts with subcontractors listed, for-profit vs nonprofit primes', value='{fp_ps|pct} vs {np_ps|pct1}', source=SRC['sc']),
             dict(label='Grant agreements with subcontractors listed (all recipients)', value='{gr_sub|int} of {gr_n|int}', source=SRC['sc']),
             dict(label='Subcontract findings in Controller monitoring, FY2022–FY2025', value='{sub_findings|int} in {n_reviews|int} organization reviews', source=SRC['find'] + '#categories'),
         ],
         chart=dict(type='hbar', title='Subcontracting shows up for vendors, not for grants',
                    subtitle='Share of prime contracts with at least one subcontractor listed in Supplier Contracts (%)',
                    x=dict(label='Contract group', values='@CH:x'), y=dict(label='Percent of contracts', unit='%'),
                    series=[dict(name='Subcontractor listed', values='@CH:v', n='@CH:n')], highlight='Nonprofit professional services',
                    note='Source: Supplier Contracts (DataSF cqi5-hm2d), current extract; nonprofit = the dataset\'s own Non-Profit flag.'),
         robustness=dict(verdict='robust', checks=[
             'Held with this dashboard\'s matched organizations instead of the city\'s flag: {ours_sub|int} of {ours_n|int} large nonprofit contracts list a subcontractor.',
             'Held across all for-profit contract types: {fp_all|pct} list a subcontractor.',
             'Held for grants to any recipient: {gr_sub|int} of {gr_n|int}.',
         ], what_could_make_it_wrong='Some nonprofits deliver all services with their own staff, and the dataset may record subcontractors only where local-business '
                                     'participation rules require it, so a missing listing is not evidence of undisclosed subcontracting.'),
         caveats=['Form 990 Schedule I and Part VII show some regranting and large contractors, but only for the organization\'s whole budget.'],
         explore=dict(view='np-growth', params={}, label='See nonprofit contracts'),
         departments=[], tags=['subcontracting', 'transparency', 'contracts']),
]
