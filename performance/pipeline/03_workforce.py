"""Workforce: headcount, FTE, salaries, overtime, benefits by department and fiscal year.

Input: data/raw/employee_comp.csv (88g8-5mnd). Fiscal-year rows only (Year Type == 'Fiscal').
One row = one employee x job x department x year (a person with 2 jobs appears twice).
Outputs:
  data/interim/workforce_dept_fy.csv
  data/interim/workforce_dept_jobfamily_fy.csv
Definitions:
  people_paid   rows with total_salary > 0 (employee-job records paid in the year)
  fte_hours     sum(hours)/2080 (hours available FY2017+ only; hours include all paid hours
                reported by the Controller, see DATA_NOTES)
  ot_share_pay  overtime / total_salary
  benefit_load  total_benefits / (salaries + other_salaries)  (benefits relative to non-OT pay)
Names are never exported; only aggregates.
"""
import pandas as pd, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

NUM = ['Salaries', 'Overtime', 'Other Salaries', 'Total Salary', 'Retirement', 'Health and Dental',
       'Other Benefits', 'Total Benefits', 'Total Compensation', 'Hours']


def main():
    e = pd.read_csv(os.path.join(RAW, 'employee_comp.csv'), dtype=str,
                    usecols=['Year Type', 'Year', 'Department Code', 'Job Family', 'Job', 'Employment Type', 'Employee Name'] + NUM)
    e = e[e['Year Type'] == 'Fiscal'].copy()
    for c in NUM:
        e[c] = pd.to_numeric(e[c], errors='coerce').fillna(0.0)
    e['fy'] = e['Year'].astype(int)
    e['dept'] = e['Department Code'].str.strip().map(canon_dept)
    e['paid'] = (e['Total Salary'] > 0).astype(int)
    e['perm'] = e['Employment Type'].fillna('').str.startswith('Permanent').astype(int) * e['paid']

    def summarize(g):
        out = g.agg(people_paid=('paid', 'sum'), permanent_paid=('perm', 'sum'),
                    hours=('Hours', 'sum'), salaries=('Salaries', 'sum'), overtime=('Overtime', 'sum'),
                    other_salaries=('Other Salaries', 'sum'), total_salary=('Total Salary', 'sum'),
                    retirement=('Retirement', 'sum'), health_dental=('Health and Dental', 'sum'),
                    other_benefits=('Other Benefits', 'sum'), total_benefits=('Total Benefits', 'sum'),
                    total_comp=('Total Compensation', 'sum'))
        out['fte_hours'] = np.where(out.index.get_level_values('fy') >= 2017, out['hours'] / 2080.0, np.nan)
        out['ot_share_pay'] = out['overtime'] / out['total_salary'].replace(0, np.nan)
        out['benefit_load'] = out['total_benefits'] / (out['salaries'] + out['other_salaries']).replace(0, np.nan)
        return out.reset_index()

    d = summarize(e.groupby(['dept', 'fy']))
    # distinct employees (the identifier field holds names in recent years, numeric ids in older years; never exported)
    # and employees whose overtime summed across their jobs in the department exceeds $100,000
    per = e[e['Total Salary'] > 0].groupby(['dept', 'fy', 'Employee Name']).agg(ot=('Overtime', 'sum'), sal=('Salaries', 'sum')).reset_index()
    dh = per.groupby(['dept', 'fy']).agg(headcount=('Employee Name', 'nunique'), employees_ot_over_100k=('ot', lambda s: int((s > 100000).sum()))).reset_index()
    d = d.merge(dh, on=['dept', 'fy'], how='left')
    d['ot_share_base_plus_ot'] = d.overtime / (d.salaries + d.overtime).replace(0, np.nan)
    d['dept_name'] = d.dept.map(DEPT_NAMES).fillna(d.dept)
    d.to_csv(os.path.join(INTERIM, 'workforce_dept_fy.csv'), index=False)
    j = summarize(e.groupby(['dept', 'Job Family', 'fy']))
    j.to_csv(os.path.join(INTERIM, 'workforce_dept_jobfamily_fy.csv'), index=False)
    # job-level for overtime vs vacancy analysis (average pay per class)
    jb = summarize(e.groupby(['dept', 'Job', 'fy']))
    jb.to_csv(os.path.join(INTERIM, 'workforce_dept_job_fy.csv'), index=False)
    c = summarize(e.assign(dept='CITY').groupby(['dept', 'fy']))
    ch = per.groupby('fy').agg(headcount=('Employee Name', 'nunique'), employees_ot_over_100k=('ot', lambda s: int((s > 100000).sum()))).reset_index()
    c = c.merge(ch, on='fy', how='left')
    c.to_csv(os.path.join(INTERIM, 'workforce_city_fy.csv'), index=False)
    print(c[['fy', 'people_paid', 'fte_hours', 'total_salary', 'overtime', 'ot_share_pay', 'benefit_load']].round(3).to_string())


if __name__ == '__main__':
    main()
