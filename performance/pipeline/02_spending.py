"""Build the spending cube: department x program x character class x fiscal year x fund scope,
budget (adopted, Annual Appropriation Ordinance) vs actual (Spending and Revenue).

Inputs: data/raw/budget.csv (xdgd-c79v), data/raw/spending_revenue.csv (bpnb-jwfb)
Outputs:
  data/interim/spend_long.parquet   one row per source row (spending only), normalized
  data/interim/spend_cube.parquet   aggregated dept x program x char_class x fy x gf x fund_category
  data/interim/spend_dept_fy.csv    dept x fy summary (budget, actual; all funds and GF)
"""
import pandas as pd, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

USE = ['Fiscal Year', 'Department Code', 'Department', 'Program Code', 'Program', 'Character',
       'Object', 'Fund Type Code', 'Fund Type', 'Fund Category', 'Revenue or Spending']


def load(path, amount_col, measure, related_col=None):
    cols = USE + [amount_col] + ([related_col] if related_col else [])
    df = pd.read_csv(path, dtype=str, usecols=cols)
    df = df[df['Revenue or Spending'] == 'Spending'].copy()
    df['amount'] = pd.to_numeric(df[amount_col]).fillna(0.0)
    n0 = len(df)
    if related_col:
        rel = df[related_col].str.upper().eq('YES')
        df = df[~rel]
    df = df[~df['Fund Type'].isin(EXCLUDED_FUND_TYPES)]
    print(f'{measure}: {n0} spending rows, {len(df)} after excluding fiduciary/component units')
    df['fy'] = df['Fiscal Year'].astype(int)
    df['dept_raw'] = df['Department Code'].str.strip()
    df['dept'] = df['dept_raw'].map(canon_dept)
    df['Character'] = df['Character'].fillna('(missing)')
    df['char_class'] = df['Character'].map(CHAR_CLASS)
    df.loc[df.Character.eq('(missing)'), 'char_class'] = 'other'  # verified: all zero-amount rows
    unk = df[df.char_class.isna()]['Character'].unique()
    if len(unk):
        raise SystemExit(f'Unmapped characters: {unk}')
    df['gf'] = df['Fund Type Code'].isin(GF_FUND_TYPE_CODES)
    df['overtime'] = (df['char_class'] == 'salaries') & df['Object'].str.contains('Overtime', case=False, na=False)
    df['program_era'] = np.where(df.fy <= 2017, 'legacy_program', 'program_type')
    df['measure'] = measure
    return df[['fy', 'dept', 'dept_raw', 'Department', 'Program Code', 'Program', 'program_era', 'Character',
               'char_class', 'Object', 'overtime', 'gf', 'Fund Type', 'Fund Category', 'measure', 'amount']].rename(
        columns={'Department': 'dept_name_raw', 'Program Code': 'program_code', 'Program': 'program',
                 'Character': 'character_raw', 'Object': 'object', 'Fund Type': 'fund_type',
                 'Fund Category': 'fund_category'})


def main():
    b = load(os.path.join(RAW, 'budget.csv'), 'Budget', 'budget')
    a = load(os.path.join(RAW, 'spending_revenue.csv'), 'Amount', 'actual', 'Related Govt Units')
    long = pd.concat([b, a], ignore_index=True)
    long.to_parquet(os.path.join(INTERIM, 'spend_long.parquet'), index=False)

    keys = ['fy', 'dept', 'program_era', 'program_code', 'program', 'char_class', 'gf', 'fund_category']
    cube = long.groupby(keys + ['measure'], dropna=False)['amount'].sum().unstack('measure').fillna(0).reset_index()
    cube.to_parquet(os.path.join(INTERIM, 'spend_cube.parquet'), index=False)

    sp = long[long.char_class.isin(SPEND_CLASSES)]
    def agg(df, suffix):
        g = df.groupby(['dept', 'fy', 'measure'])['amount'].sum().unstack('measure').fillna(0)
        g.columns = [f'{c}_{suffix}' for c in g.columns]
        return g
    parts = [agg(sp, 'all'), agg(sp[sp.gf], 'gf'),
             agg(sp[sp.char_class.isin(OPERATING_CLASSES)], 'oper_all'),
             agg(sp[sp.char_class.isin(['capital', 'projects'])], 'capital_all'),
             agg(sp[sp.char_class == 'salaries'], 'salaries'),
             agg(sp[sp.char_class == 'benefits'], 'benefits'),
             agg(sp[sp.overtime], 'overtime'),
             agg(sp[sp.fund_category == 'Operating'], 'opfund')]
    d = pd.concat(parts, axis=1).fillna(0).reset_index()
    d['dept_name'] = d.dept.map(DEPT_NAMES).fillna(d.dept)
    d.to_csv(os.path.join(INTERIM, 'spend_dept_fy.csv'), index=False)

    # citywide totals (excluding inter-department work orders and overhead allocations)
    c = long[long.char_class.isin(CITY_CLASSES)].groupby(['fy', 'measure', 'gf'])['amount'].sum().unstack(['measure', 'gf'])
    c.columns = [f'{m}_{"gf" if g else "nongf"}' for m, g in c.columns]
    c = c.fillna(0)
    c['budget_all'] = c.get('budget_gf', 0) + c.get('budget_nongf', 0)
    c['actual_all'] = c.get('actual_gf', 0) + c.get('actual_nongf', 0)
    c.reset_index().to_csv(os.path.join(INTERIM, 'spend_city_fy.csv'), index=False)
    print((c[['budget_all', 'actual_all', 'budget_gf', 'actual_gf']] / 1e9).round(2).to_string())


if __name__ == '__main__':
    main()
