#!/usr/bin/env python3
"""Aggregate static outcome sources (downloaded by 11b) to year-level CSVs in data/raw/outcomes/.
Outputs:
  city_survey_ratings_by_year.csv   weighted mean grade (1=F..5=A) and share A/B by question x survey year
  street_eval_fy13_fy18_summary.csv  pass rates by FY (FY12 standards, Controller/DPW)
  street_eval_2022_2025_summary.csv  litter/feces/syringe/dumping stats by evaluation period and by FY
  scorecard_outcome_extracts.csv     selected direct-outcome series from kc49-udxn (monthly scorecards), FY-aggregated
  citywide_metrics_outcome_extracts.csv selected series from 6dpt-7w23 (annual target/actual)
  311_call_metrics_fy.csv            311 call center answered-within-60s etc. by FY
"""
import os, re
import numpy as np, pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
D = os.path.join(ROOT, 'data', 'raw', 'outcomes')
fp = lambda n: os.path.join(D, n)


def city_survey():
    d = pd.read_csv(fp('city_survey_microdata.csv'), low_memory=False)
    d.columns = [c.strip() for c in d.columns]
    # CSV export uses field names? detect
    meta_cols = {'year', 'weight', 'id', 'mode', 'svylanguage', 'bosdistrict'}
    lower = {c: c.lower() for c in d.columns}
    d = d.rename(columns=lower)
    rating_like = []
    for c in d.columns:
        if c in meta_cols or c.startswith('dem_') or c.startswith('child_0') or c.startswith('child_6'):
            continue
        v = pd.to_numeric(d[c], errors='coerce')
        ok = v.dropna()
        if len(ok) > 200 and ok.isin([1, 2, 3, 4, 5]).mean() > 0.98 and ok.nunique() >= 4:
            rating_like.append(c)
    rows = []
    w = pd.to_numeric(d['weight'], errors='coerce').fillna(1.0)
    for c in rating_like:
        v = pd.to_numeric(d[c], errors='coerce')
        for y, idx in d.groupby('year').groups.items():
            vv, ww = v.loc[idx], w.loc[idx]
            m = vv.isin([1, 2, 3, 4, 5])
            if m.sum() < 100:
                continue
            rows.append({'survey_year': int(y), 'question': c, 'n_responses': int(m.sum()),
                         'response_rate_in_year': round(m.mean(), 3),
                         'weighted_mean_grade_1to5': round(np.average(vv[m], weights=ww[m]), 3),
                         'weighted_share_A_or_B': round(np.average(vv[m] >= 4, weights=ww[m]), 4),
                         'weighted_share_D_or_F': round(np.average(vv[m] <= 2, weights=ww[m]), 4)})
    out = pd.DataFrame(rows).sort_values(['question', 'survey_year'])
    out['scale'] = '5=A Excellent/Very safe, 4=B, 3=C, 2=D, 1=F Failing/Very unsafe (codebook 1996-2023_City_Survey_Codebook.xlsb)'
    out['source_url'] = 'https://data.sf.gov/api/views/nufj-bfbw/rows.csv?accessType=DOWNLOAD'
    out.to_csv(fp('city_survey_ratings_by_year.csv'), index=False)
    print('city survey', len(out), 'rows;', out.question.nunique(), 'questions')


def street_old():
    a = pd.read_csv(fp('street_eval_fy13_fy18.csv'), low_memory=False)
    a['fy'] = a['FY'].str[:4].astype(int) + 1
    pcols = {'11 pass': 'street_litter_pass', '21  Pass': 'sidewalk_litter_pass', '22  Pass': 'grime_pass',
             '31  Pass': 'graffiti_public_dpw_pass', '41  Pass': 'receptacle_fullness_pass', '51  Pass': 'tree_cleanliness_pass'}
    g = a.groupby('fy')
    out = g[list(pcols)].mean().rename(columns=pcols).round(4)
    out['evaluations'] = g.size()
    out['mean_street_litter_score_1to3'] = g['11  Score (10, 20, or 30 score)'].mean().round(3)
    out['mean_sidewalk_litter_score_1to3'] = g['21  Litter (10, 20, or 30 score)'].mean().round(3)
    out = out.reset_index()
    out['definition'] = ('Controller/DPW Street & Sidewalk Maintenance Standards (FY12 standards). "pass" = route met the standard; '
                         'litter scores 1 (cleanest) to 3. Not comparable with 2022+ methodology.')
    out['source_url'] = 'https://data.sf.gov/api/views/83ki-hu3p/rows.csv?accessType=DOWNLOAD'
    out.to_csv(fp('street_eval_fy13_fy18_summary.csv'), index=False)
    print(out.to_string())


def street_new():
    b = pd.read_csv(fp('street_eval_2022_2025.csv'), low_memory=False)
    col = lambda pat: [c for c in b.columns if re.search(pat, c, re.I)][0]
    st, sw = col(r'litter in the street'), col(r'litter on the sidewalk')
    fe, sy, du = col('instances of feces'), col('abandoned syringes'), col('large abandoned items')
    rc = col('receptacles overflowing')
    hasrc = col('one or more trash receptacles')
    b['date'] = pd.to_datetime(b['CreationDate'], errors='coerce', format='mixed')
    b['fy'] = b.date.dt.year + (b.date.dt.month >= 7).astype(int)
    for c in [st, sw, fe, sy, du, rc]:
        b[c] = pd.to_numeric(b[c], errors='coerce')
    res = []
    for key in ['Evaluation Period', 'fy']:
        for k, g in b.groupby(key):
            res.append({'group_type': key, 'group': k, 'evaluations': len(g),
                        'mean_street_litter_1to5': round(g[st].mean(), 3),
                        'share_street_litter_3plus': round((g[st] >= 3).mean(), 4),
                        'mean_sidewalk_litter_1to5': round(g[sw].mean(), 3),
                        'share_sidewalk_litter_3plus': round((g[sw] >= 3).mean(), 4),
                        'share_routes_any_feces': round((g[fe] > 0).mean(), 4), 'mean_feces_per_route': round(g[fe].mean(), 3),
                        'share_routes_any_syringe': round((g[sy] > 0).mean(), 4),
                        'share_routes_any_dumping': round((g[du] > 0).mean(), 4),
                        'share_receptacles_overflowing_of_routes_with_receptacles': round((pd.to_numeric(g[rc], errors='coerce')[pd.to_numeric(g[hasrc], errors='coerce') == 1] == 1).mean(), 4)})
    out = pd.DataFrame(res)
    out['definition'] = ('Controller Street & Sidewalk Maintenance Standards (2022+ methodology). Litter scale 1=None, 2=A few traces, '
                         '3=More than a few traces but no accumulation, 4-5 = accumulations (see data dictionary). Counts per evaluated route.')
    out['source_url'] = 'https://data.sf.gov/api/views/qya8-uhsz/rows.csv?accessType=DOWNLOAD'
    out.to_csv(fp('street_eval_2022_2025_summary.csv'), index=False)
    print(out.to_string())


SCORECARD_CODES = {  # measure_code in kc49-udxn -> short name, aggregation over months within FY
    973: ('ambulance_within_10min_life_threatening_pct', 'mean'),
    441: ('muni_scheduled_service_hours_delivered_pct', 'mean'),
    428: ('muni_avg_weekday_boardings', 'mean'),
    425: ('muni_collisions_per_100k_miles', 'mean'),
    7273: ('muni_headway_adherence', 'mean'),
    1022: ('library_ebook_emedia_circulation', 'sum'),
    1023: ('library_physical_circulation', 'sum'),
    7169: ('pit_count_total_homeless', 'last'),
    7282: ('hsh_exits_to_permanent_housing', 'sum_or_annual'),
    7277: ('hsh_unique_exits_monthly_not_dedup', 'sum'),
    7285: ('hsh_psh_move_ins_households', 'sum_or_annual'),
    7284: ('hsh_rrh_move_ins_households', 'sum_or_annual'),
    7055: ('hsh_psh_move_ins_households_old', 'sum'),
    7054: ('hsh_rrh_move_ins_households_old', 'sum'),
    279: ('hsh_shelter_occupancy_pct', 'mean'),
    7073: ('dpw_street_cleaning_requests_abated_48h_pct', 'mean'),
    7079: ('dpw_street_cleaning_requests_volume', 'sum'),
    7051: ('sfpd_median_response_priority_A_min', 'mean'),
    7052: ('sfpd_median_response_priority_B_min', 'mean'),
    7053: ('sfpd_median_response_priority_C_min', 'mean'),
    953: ('dem_911_answered_10s_pct', 'mean'),
    954: ('dem_911_answered_15s_pct', 'mean'),
    664: ('pavement_condition_index', 'last'),
}


def scorecards():
    s = pd.read_csv(fp('scorecard_measures_monthly.csv'), low_memory=False)
    s.columns = [c.strip().lower().replace(' ', '_') for c in s.columns]
    s['measure_code'] = pd.to_numeric(s['measure_code'], errors='coerce')
    s = s[s.measure_code.isin(SCORECARD_CODES)].copy()
    s['month'] = pd.to_datetime(s['calendar_month'], errors='coerce')
    s['fy'] = s.month.dt.year + (s.month.dt.month >= 7).astype(int)
    s['actual'] = pd.to_numeric(s['actual'], errors='coerce')
    s['monthly'] = s['monthly'].astype(str).str.lower().isin(['true', '1'])
    s.to_csv(fp('scorecard_outcome_extracts_monthly_rows.csv'), index=False)
    rows = []
    s = s[s.actual.notna()].copy()
    # PIT (7169) is split Sheltered/Unsheltered in category_2 -> total = sum of the two rows per count
    pit = s[s.measure_code == 7169]
    if len(pit):
        for fy, g in pit.groupby('fy'):
            for cat in ['Sheltered', 'Unsheltered']:
                v = g[g.category_2 == cat].actual.sum()
                rows.append({'measure_code': 7169, 'series': f'pit_count_{cat.lower()}', 'department': g.department.iloc[0],
                             'measure_title': g.measure_title.iloc[0], 'fy': int(fy), 'value': float(v),
                             'months_reported': 0, 'aggregation': 'count-date value (January count)', 'flag': ''})
            rows.append({'measure_code': 7169, 'series': 'pit_count_total_homeless', 'department': g.department.iloc[0],
                         'measure_title': g.measure_title.iloc[0], 'fy': int(fy), 'value': float(g.actual.sum()),
                         'months_reported': 0, 'aggregation': 'sheltered+unsheltered (January count)', 'flag': ''})
    for (code, fy), g in s[s.measure_code != 7169].groupby(['measure_code', 'fy']):
        name, how = SCORECARD_CODES[int(code)]
        g = g.sort_values('month').drop_duplicates(['calendar_month'])
        vals = g.actual.values
        cumulative = len(vals) >= 2 and all(b >= a for a, b in zip(vals, vals[1:])) and vals[-1] >= 1.5 * vals[0]
        flag = ''
        if how == 'mean':
            v = vals.mean()
        elif how == 'last':
            v = vals[-1]
        else:  # sums: detect year-to-date cumulative reporting (value grows monotonically) -> take last
            v = vals[-1] if cumulative else vals.sum()
            if cumulative:
                flag = 'cumulative YTD reporting detected; used final month'
            if g.month.dt.month.iloc[-1] != 6 and not cumulative:
                flag = (flag + '; ' if flag else '') + 'partial year'
        if code == 7073 and fy <= 2015 and np.nanmax(vals) < 0.05:
            flag = 'unit error suspected (values ~0.009 vs target 0.85-0.90); value excluded'
            v = np.nan
        tgt = g.target.dropna()
        rows.append({'measure_code': int(code), 'series': name, 'department': g.department.iloc[0],
                     'measure_title': g.measure_title.iloc[0], 'fy': int(fy), 'value': (round(float(v), 4) if pd.notna(v) else None),
                     'months_reported': int(len(g)), 'aggregation': how if not cumulative or how == 'mean' else 'ytd-final',
                     'target_latest': tgt.iloc[-1] if len(tgt) else None, 'flag': flag})
    out = pd.DataFrame(rows)
    out['source_url'] = 'https://data.sf.gov/api/views/kc49-udxn/rows.csv?accessType=DOWNLOAD'
    out.to_csv(fp('scorecard_outcome_extracts.csv'), index=False)
    print(out.pivot_table(index='fy', columns='series', values='value').round(1).tail(16).T.to_string())


CITYWIDE_TITLES = ['Muni on-time performance', 'Percentage of scheduled service hours delivered', 'Expenditures per Number of Visits',
                   'Paratransit on-time performance']


def citywide_metrics():
    m = pd.read_csv(fp('citywide_performance_metrics.csv'), low_memory=False)
    m.columns = [c.strip().lower().replace(' ', '_') for c in m.columns]
    title_col = [c for c in m.columns if 'measure_title' in c][0]
    dept_col = [c for c in m.columns if 'department' in c][0]
    keep = m[m[title_col].isin(CITYWIDE_TITLES) | (m[dept_col].str.upper().isin(['PUBLIC LIBRARY', 'MUNICIPAL TRANSPORTATION AGENCY',
                                                                                  'HOMELESSNESS AND SUPPORTIVE HOUSING']))].copy()
    keep['source_url'] = 'https://data.sf.gov/api/views/6dpt-7w23/rows.csv?accessType=DOWNLOAD'
    keep.to_csv(fp('citywide_metrics_outcome_extracts.csv'), index=False)
    print('citywide extracts', len(keep), keep[title_col].nunique(), 'measures')


def call_metrics():
    c = pd.read_csv(fp('311_call_metrics_monthly.csv'), low_memory=False)
    c.columns = [x.strip().lower() for x in c.columns]
    mcol = [x for x in c.columns if x.startswith('month')][0]
    c['m'] = pd.to_datetime(c[mcol], errors='coerce', format='mixed')
    c['fy'] = c.m.dt.year + (c.m.dt.month >= 7).astype(int)
    num = [x for x in c.columns if x not in (mcol, 'm', 'fy')]
    for x in num:
        c[x] = pd.to_numeric(c[x].astype(str).str.replace('%', '').str.replace(',', ''), errors='coerce')
    agg = {x: ('sum' if x.replace('_', ' ').strip() == 'calls answered' else 'mean') for x in num}
    out = c.groupby('fy').agg(agg).round(3)
    out['months'] = c.groupby('fy').size()
    out = out.reset_index()
    out['source_url'] = 'https://data.sf.gov/api/views/mwjb-biik/rows.csv?accessType=DOWNLOAD'
    out.to_csv(fp('311_call_metrics_fy.csv'), index=False)
    print(out.to_string())


KEY_ANNUAL = {
    'Muni on-time performance': 'muni_on_time_performance',
    'Percentage of scheduled service hours delivered': 'muni_scheduled_service_hours_delivered_pct',
    'Muni total annual ridership': 'muni_total_annual_ridership',
    'Customer rating: Overall satisfaction with Muni': 'muni_customer_satisfaction',
    'Paratransit on-time performance': 'paratransit_on_time_performance',
    'Expenditures per Number of Visits': 'library_expenditure_per_visit_dept_reported',
    'Circulation of physical books and materials': 'library_physical_circulation',
    'Circulation of eBooks and eMedia': 'library_ebook_circulation',
    'Number of people exiting homelessness to a permanent housing situation': 'hsh_exits_to_permanent_housing',
    'Number of households who moved into housing through Permanent Supportive Housing': 'hsh_psh_move_ins',
    'Number of households who moved into housing through a Rapid Rehousing program': 'hsh_rrh_move_ins',
}


def citywide_key_series():
    m = pd.read_csv(fp('citywide_performance_metrics.csv'), low_memory=False)
    m.columns = [c.strip().lower().replace(' ', '_') for c in m.columns]
    res = [c for c in m.columns if 'full' in c and 'result' in c][0]
    m = m.copy()
    m['series'] = m['measure_title'].map(KEY_ANNUAL)
    visits = m['measure_title'].str.startswith('Number of persons entering San Francisco Main', na=False)
    m.loc[visits, 'series'] = 'library_visits'
    k = m[m.series.notna()].copy()
    k['fy'] = k['fiscal_year'].str.extract(r'FY(\d{4})-')[0].astype(int) + 1
    k = k.rename(columns={res: 'actual'})[['series', 'department_name', 'measure_title', 'fy', 'target', 'actual']]
    k['source_url'] = 'https://data.sf.gov/api/views/6dpt-7w23/rows.csv?accessType=DOWNLOAD'
    k.sort_values(['series', 'fy']).to_csv(fp('citywide_metrics_key_series.csv'), index=False)
    print('key series', k.series.value_counts().to_dict())


def street_oldest():
    a = pd.read_csv(fp('street_eval_fy07_fy11.csv'), low_memory=False)
    a['fy'] = pd.to_numeric(a['Fiscal Year'].astype(str).str[:4], errors='coerce') + 1
    a = a[a.fy.notna()]; a['fy'] = a.fy.astype(int)
    for c in ['1.1', '2.1']:
        a[c] = pd.to_numeric(a[c], errors='coerce')
    out = a.groupby('fy').agg(evaluations=('1.1', 'size'), mean_street_litter_score_1_1=('1.1', 'mean'),
                              mean_sidewalk_litter_score_2_1=('2.1', 'mean')).round(3).reset_index()
    out['definition'] = ('FY07-FY11 street evaluation results under pre-FY12 standards (items 1.1 street litter, 2.1 sidewalk litter; '
                         'lower = cleaner). Not comparable to later standards.')
    out['source_url'] = 'https://data.sf.gov/api/views/i8y7-m763/rows.csv?accessType=DOWNLOAD'
    out.to_csv(fp('street_eval_fy07_fy11_summary.csv'), index=False)
    print(out.to_string())


if __name__ == '__main__':
    city_survey(); street_oldest(); street_old(); street_new(); scorecards(); citywide_metrics(); citywide_key_series(); call_metrics()
