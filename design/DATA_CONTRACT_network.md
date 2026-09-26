# Data contract — network module ("Money network")

The dashboard reads static JSON from `network/data/site/`. `design/prototype/sample-data/network/` follows this contract; `sample-data/generate.py` is the reference writer. Fairness rules from `RULES.md` are encoded in the data, not only in the UI. Every rule is a *must* unless marked *may*.

## 1. Conventions and fairness rules (data-level)
- **Private individuals never appear as entities.** Contributions from individuals are aggregated into entities of type `individuals`: one per affiliated organization (`affiliated_with`, from the employer/occupation fields matched to a contractor or from SFEC-126(f)4 principals) and one catch-all `ind-all`. Aggregate nodes carry `count` (distinct individuals) and `basis`. No names, employers-as-text, or addresses are exported anywhere; addresses are dropped at ingest.
- Named entities: `committee` (candidate or officeholder committee, with `official` and FPPC id), `official` (elected/appointed, public role: `office`, `term`), `lobbyist` (registered firm or individual lobbyist registered with the Ethics Commission), `contractor` (party to a city contract; `principals_disclosed` is a count), `nonprofit` (with `nonprofit_org` → nonprofits module id), `donor_org` (PAC or other organization), `department` (`code` = Controller department code).
- Flows are dated, directed and typed. Amounts are nominal dollars or `null` (lobbying contacts). Counts aggregate individuals or contacts.
- Any timing-based flag is data (`review`, `flags.in_ban_window`) so the UI can label it "pattern worth checking, not proof" and cite the rule; the rule texts live in `meta.rules` with `cite` and `verify`.
- Never `NaN`; use `null`. Dates `YYYY-MM-DD`; calendar years.

## 2. Client-side computation
The dashboard filters `flows` by date, `type`, endpoint entity types and `amount ≥ min`, builds the graph (edges aggregated per from→to pair, pruned to the top-K by weight plus the focused neighborhood, deterministic layout), sums by year/type/entity type, and joins the analysis files by `flow` id. Precomputed: ban-window records with `days_from_approval`, `inside_window`, `covered_official` and the base rate; behested rows with the interested-party flag; lobbying contact aggregates; concentration per committee; the nonprofit loop rows.

## 3. Files

### `meta.json` — boot
```
sample, module: "network", as_of, generated_at, version, years: {min: 2019, max: 2026, note},
dimensions: {
  etype: {label, kind: "categorical", values: [{id, label, slot}]},     // committee 7, contractor 2, nonprofit 1, lobbyist 3, donor_org 4, individuals 0, department 0, official 7
  flow: {label, values: [{id, label, form, short}]},                    // contribution, behested, lobby_contact, lobby_payment, contract, payment
  amount_bands: [{id: int (minimum), label}]
},
rules: [{id: "ban"|"behested"|"lobby"|"limits", short, cite, text, verify}],   // plain-language rule, exact code citation, and what to verify before publication
fairness: {individuals: str, timing: str, review: str},
counts: {entities, flows, contracts_with_126f, behested_payments, lobby_contact_rows, individuals_aggregated},
small_n: 5, sources: [...], files: {...}
```

### `entities.json`
```
entities: [{id, type: etype id, name, cluster: "officials"|"city"|"lobbying"|"nonprofits"|"contractors_and_donors",
            // by type:
            official: {office, term: [int, int], sample_note?}, committee: {official: id, fppc_id}, department: {code},
            contractor: {principals_disclosed: int, sector}, nonprofit: {nonprofit_org: "org-…"}, lobbyist: {lobbyist_type: "contact"|"expenditure", registered_since},
            individuals: {count: int, affiliated_with: id|null, basis: str}}]
```
`cluster` is the layout group (may be replaced by a community id from `07_resolve.py`; the UI labels clusters from a small map). Entity resolution thresholds and the manual-review log go in DATA_NOTES.

### `flows.json` (production: `flows/flows_<year>.json`)
```
flows: [{id, from: entity id, to: entity id, type: flow id, date, amount: int|null, count: int,
         ref: {form, id, url}, aggregated?: bool, period?: str,
         // by type:
         contribution: {flags?: {in_ban_window: bool, ban_contract: contract flow id}, note?},
         behested: {behest_of: official id, purpose},
         lobby_contact: {client: entity id, topic},
         contract: {approving_body},
         payment: {}}]
```
One row per (from, to, type, date) after aggregating individuals (aggregate contributions to a committee may be monthly rows with `count` = individuals). Example: `{"id":"fl-01234","from":"ind-con-07","to":"cmte-03","type":"contribution","date":"2024-03-14","amount":1500,"count":3,"aggregated":true,"ref":{"form":"Form 460 Sch. A","id":null,"url":null},"flags":{"in_ban_window":true,"ban_contract":"fl-00087"}}`.

### `analyses/ban_window.json`
```
rule: "ban",
base_rates: {contributions_by_contractor_affiliated: int, inside_any_window: int, inside_window_covered_official: int,
             expected_share_if_unrelated: num, expected_note: str},
contracts: [{contract: contract flow id, contractor, dept, approval_date, amount, window: [start, end], approving_body, contributions: [flow ids]}],
records: [{flow, contractor, committee, date, amount, count, nearest_contract, days_from_approval: int, inside_window: bool, window_contract: id|null,
           covered_official: bool, review: "appears_to_warrant_review"|"inside_window_not_covered"|"outside_window", why: str|null}]
```
`expected_share_if_unrelated` = for each contractor, the share of days in the analysis period covered by the union of its ban windows, weighted by that contractor's record count (the sample generator implements this; production must use the window length in force on each date: 6 months after approval before 2020-01-01, 12 months after). `covered_official` = the committee's official approves the contract per the SFEC-126(f)4 filing (or the documented rule). `why` is required when `review = appears_to_warrant_review` and must mention attribution uncertainty and possible prior Ethics Commission review or return.

### `analyses/behested.json`
`rule: "behested", rows: [{flow, official, payor, payee, date, amount, purpose, payor_interested_party: bool, interested_basis?: str, filed_within_30_days: bool}]` — `payor_interested_party` computed as documented (contract, permit or lobbying matter before the official's department within 12 months); it is a check, not a finding.

### `analyses/lobbying.json`
`rule: "lobby", topics: [str], rows: [{flow, lobbyist, client, target: department or official id, month: "YYYY-MM", topic, contacts: int}]`.

### `analyses/concentration.json`
`rule: "limits", rows: [{committee, official, cycle: str, total, n_contributions, by_source_type: {individuals, contractor_affiliated, donor_org, nonprofit, …: int}, top10_share_named: num|null, n_named_sources: int}]` — precomputed per committee per election cycle; the view has no filters and says so.

### `analyses/loop.json`
`note: str, rows: [{entity, org, city_paid_fy<latest>: int, behested_received, behested_made, lobby_payments, lobby_contacts, depts_funding: [dept id], depts_lobbied: [dept id]}]` — nonprofits with city payments that also appear as behested payor/payee or lobbying client. The `note` must state that appearing here is not improper.

### `commentary/nw-*.json`, `commentary/story_nw.json`
Shared schema. Template ids and slots: `nw-overview: ov` (`flows, flows_fmt, entities_fmt, total, years`) · `nw-graph: graph` (`nodes_fmt, edges, edges_fmt, hidden_fmt, total`) · `nw-ban: ban` (`records, records_fmt, contracts_fmt, years, inside_fmt, inside_share, expected_share, covered_fmt`) · `nw-behested: beh` (`payments, payments_fmt, total, years, officials_fmt, interested_share, late_fmt`) · `nw-lobby: lob` (`contacts, contacts_fmt, lobbyists_fmt, clients_fmt, years, top_target, top_target_fmt, payments_total`) · `nw-concentration: conc` (`committees, committees_fmt, years, ind_share, org_share, contr_share`) · `nw-loop: loop` (`orgs, orgs_fmt, years, city_total, beh_total, lob_total`). Commentary text must follow the fairness rules (no assertion of violation; "appears to warrant review" only with the rule and reason).

## 4. Which view loads what
| View | Files |
|---|---|
| nw-overview | `entities.json`, `flows*.json`, `analyses/ban_window.json` |
| nw-graph, nw-entities | `entities.json`, `flows*.json` |
| nw-ban | + `analyses/ban_window.json` · nw-behested + `analyses/behested.json` · nw-lobby + `analyses/lobbying.json` · nw-loop + `analyses/loop.json`, `analyses/behested.json` |
| nw-concentration | `entities.json`, `flows*.json`, `analyses/concentration.json` |
| official profile | `entities.json`, `flows*.json`, `analyses/behested.json`, `analyses/concentration.json`, `analyses/ban_window.json` |
| org profile, dept scorecard | `entities.json`, `flows*.json` (+ `analyses/ban_window.json` for contractors) |

## 5. QA checks
1. No entity of type `individuals` has a person's name; no field anywhere contains a street address; grep the export for ZIP-like patterns.
2. Every `from`/`to`/`client`/`behest_of`/`official`/`payor`/`payee`/`target` id exists in `entities.json`; every `flow` id in the analyses exists in `flows`.
3. Σ `amount` of contributions to each committee equals `concentration.total` for the cycle.
4. For each `records[]` row, `inside_window` recomputes from the contract windows; `review = appears_to_warrant_review` ⇒ `inside_window && covered_official && why`.
5. `expected_share_if_unrelated` recomputes from `contracts[].window`.
6. Every `rules[].cite` was checked against the current code text; `verify` lists what remains unverified.
7. `nonprofit_org` ids exist in `nonprofits/orgs/index.json`.
