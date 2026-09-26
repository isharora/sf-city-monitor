# Insights-first page — design specification

The insights page is the new front door of each dashboard. It leads with about twenty ranked, tested findings, each with one chart that makes its point, and links every finding into the existing dashboard views with the filters already applied. It reads like a data-journalism piece crossed with an analyst's briefing: scannable in thirty seconds, rich on demand, and trustworthy because the robustness verdict and the sources are visible rather than buried.

Input: one `insights.json` per dashboard at `<module>/data/site/insights/insights.json`, following `design/insights/INSIGHTS_CONTRACT.json`. Prototype: `design/insights/prototype/insights.html` (open from `file://`; `?theme=dark`, `?insight=<id>`, `?data=1`, `?evidence=all`). The prototype's sample (`prototype/sample-data/insights.sample.js` and its JSON twin `insights.json`, both `"sample": true`) has twenty budget-vs-outcomes insights and uses every chart type in the contract. Where this document and the prototype disagree, the prototype wins for interaction and this document wins for copy and rules. Everything in `DESIGN.md` still applies (principles, colour roles, typography, keyboard, small samples, data strip).

## 1. Where it lives

- Each dashboard gets a view `<prefix>-insights` (`pf-insights`, `np-insights`, `au-insights`, `nw-insights`) listed **first** in the sidebar as `★ Insights`, above the numbered views. Clicking the dashboard in the switcher opens Insights, not Overview. Landing cards on Home link to Insights and show the top three claims as text.
- The page keeps the shell: sidebar, top bar (Print · Dark · Copy link; search stays), sticky filter bar, and the **Data on this page** strip. Story mode is not offered on this view (the page is itself the story); `s` does nothing here.
- One component renders all four dashboards. Dashboard-specific values (number, title, noun in the page title, view list for the sidebar) come from a registry keyed by `data.dashboard`; everything else comes from the file. Themes are read from the data (chips are built from the ids present), with a label map for the contract's vocabulary and title-cased fallbacks for anything new.

## 2. Page anatomy (top to bottom)

1. **Kicker** `2 · Budget vs outcomes · Insights` + `Sample insights` badge while `sample: true`.
2. **Title** (34/700, max 24ch): `20 things the numbers say about budget and outcomes` (the count is `insights.length`; the noun per dashboard: *budget and outcomes* · *nonprofit money* · *audit recommendations* · *the money network*).
3. **Intro**: `data.intro` verbatim (2–3 sentences: what these are, how chosen and tested).
4. **Summary line**: `● 15 robust · ● 5 fragile · 8 themes · 15 departments named` (dots use the verdict colours below).
5. **How to read this page** (`<details>`, closed): the two paragraphs in §9.
6. **Data on this page** strip (dashed border, same component as every view): `N insights` (or `N of 20 insights` when filtered; red when 0) · `53 cited numbers` · `19 source files` · `1 file loaded (49 KB)` · `sample` badge · `as of 2026-09-26` · **Details** → three-column panel: *Insights for your current filters* (by theme with bars, shown / total) · *Source files cited by the numbers* (path, count; the module's verify script checks every path) · *File for this page* (path, size, contract reference).
7. **Read in 30 seconds**: a numbered two-column list of every insight's title claim in rank order, each with its verdict badge (and theme on wide screens). Clicking a claim jumps to its card and marks it current (no evidence expansion). This list obeys the filters.
8. **Cards**: two-column grid (`repeat(2, minmax(0, 1fr))`, 18px gap), rank order, one column under 1100px. See §3.
9. **Reading these insights** (the standard caveats box): three severity-tagged lines (§9) and the fairness note.

## 3. Card anatomy

```
┌ 1   [Outcomes] [● ROBUST]  Fire                                   [Share] ┐
│ Fire/EMS calls rose 51% while real Fire spending rose 16%                 │  claim, 20/650
│ Dispatched calls grew from 121,148 … about a minute slower.               │  dek, 14.5 secondary
│ ┌ chart title                                             [Table] ┐       │
│ │ chart subtitle (what is plotted, units, real vs nominal)         │       │
│ │ ── one chart, 220px, highlighted series blue, rest grey ──        │       │
│ │ legend (if ≥ 2 series)                                           │       │
│ │ note: sources and definitions (11.5 muted)                        │       │
│ └───────────────────────────────────────────────────────────────────┘       │
│ ▌WHY IT MATTERS  one to three sentences (left rule, ink)                    │
│ ░THE SURPRISE   optional, inset grey box                                    │
│ ─────────────────────────────────────────────────────────────────────────── │
│ [Evidence  3 numbers · 4 checks]                See Fire's measures vs targets → │
│ ┌ evidence (hidden until opened) ─────────────────────────────────────────┐ │
│ │ THE NUMBERS      value (bold) · label · Source: path#field (mono)       │ │
│ │ ROBUSTNESS [● ROBUST]  ● held …  ● held …  ▪ did not hold …             │ │
│ │ WHAT COULD MAKE IT WRONG  paragraph                                     │ │
│ │ CAVEATS  bullets                                                        │ │
│ │ Tags: demand, response times                 Link to this insight       │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Header row**: rank (26/700 muted), theme tag (grey `tag`), verdict badge, department links (short names → `?view=dept&id=<code>`), Share button at the right.
- **Verdict badge** (always text + dot, never colour alone): `● ROBUST` is an ink-outlined pill on the card surface (a calm fact); `● FRAGILE` uses the site's amber warning tag colours (`#fff1de/#7a3d00`, dark `#3a2a10/#ffd39a`), the only warm UI accent, shared with the sample badge and review tag. Tooltip: *Held under every alternative tried* / *At least one reasonable alternative weakened it; see Evidence*.
- **Claim** is `title` verbatim (contract: under ~90 characters; the sample check rejects > 92). **Dek**, **Why it matters** and **The surprise** are verbatim. The surprise block is omitted when `surprise` is null.
- **Chart** is a bordered inset (`--surface-1`, 8px radius) with the chart title, subtitle, a `Table` toggle that swaps the SVG for its table twin, the chart, a legend when there are two or more series, and the `note`.
- **Actions**: `Evidence` button with a count (`3 numbers · 4 checks`), pressed = ink on surface; `Explore in the dashboard →` at the right, labelled with `explore.label` when present (`See Fire's measures vs targets →`), otherwise `Explore in the dashboard →`. Its `title` attribute names the view and parameters.
- **Evidence panel** (`--surface-2`, single column): each number as a block — value first (15/650), label (secondary), `Source: <code>` (mono 10.5 muted, breaks anywhere); robustness with the verdict badge repeated and one bullet per check — a **blue round dot** for a check that held, an **amber square** for one that did not (a check is coded as failed when it starts with *did not*, *does not*, *sign flip*, *fail*, *not held*, *reversed*; analysts should write checks that way); *What could make it wrong* as a paragraph; caveats as bullets; footer with tags and `Link to this insight`.
- **Current card**: 1px ink ring (`box-shadow: 0 0 0 1px var(--text-primary)`), set by the glance list, `j`/`k`, or `?insight=`.

## 4. Filters (Principle 1: every filter shown applies to everything on the page)

Filter bar (sticky under the top bar): **Theme** chips with counts (from the data) · **Department** multi-select popover (only departments named in at least one insight, with counts; stays open while ticking) · **Verdict** chips `● Robust 15` · `● Fragile 5` (mutually exclusive) · `Reset filters` (only when a filter is active) · absent-filter note: *Not on this page: **Fiscal years**, **Dollars** (each insight fixes its own years and dollar basis; see its chart subtitle)*.

Filters apply to the glance list, the cards and the data strip counts together. Filtering never re-ranks (rank numbers are the file's) and never recolours.

## 5. Chart rendering rules

General (all nine types, `js/insights-charts.js`):
- **One idea per chart.** `highlight` (a series name, a category, a point label, or an array of them) is drawn in `--series-1` blue; everything else in `--neutral` grey (dark: the dark neutral). With no highlight: a single series is blue; two to four series take slots 1–4 in order; more than four without a highlight is a data error (fold or highlight).
- Text never wears the series colour: labels are `--text-primary` (highlighted, 650) or `--text-secondary`/`--text-muted`. Inside a blue fill, white.
- Hairline solid gridlines (`--grid`), darker baseline/zero line (`--axis`), no dual axes ever; indexed series draw a baseline at 100.
- Marks: lines 2px round-joined with r 3.2 dots (≤ 20 points) ringed in surface; bars ≤ 24px thick, 4px rounded data end, square at the baseline; stacked segments separated by a 2px surface gap; scatter points r 5 with a 1.5px surface ring; dumbbell dots r 5.5 on a 2.5px link.
- **Direct labels, selectively**: the highlighted mark(s), the extremes, and the endpoints; never a number on every mark. End labels nudge apart by 13–14px and are pushed back inside the plot. Category labels wrap to two lines (three on waterfalls), breaking at spaces and hyphens.
- **Annotations** `{x, label}`: a dashed hairline at `x` with a boxed label at the top of the plot, flipped left when it would overflow and staggered 20px down when two boxes would overlap (adjacent years); lines get 12% headroom so the box never sits on the data.
- **Reference line** (optional `y.ref: {value, label}`): a dashed secondary-ink line at the value (e.g. `100%` = spent exactly the adopted budget) with its label at the end, on line, bar and hbar charts.
- Long row names on hbar and dumbbell charts wrap to two lines (rows grow to 34–36px) rather than overflowing the inset; column labels wrap to two lines (three on waterfalls).
- Years read `FY13` on ticks and `FY2013` in tooltips when the x label says fiscal year; calendar years (survey years) stay plain.
- Units (`y.unit`): `$` → `$5,472` / `$1.2B`; `$M` → `$147M` / `$1.06B`; `$B` → `$4.60B`; `%` → `21%` (one decimal under 10); `min` → `6:17`; `ratio` → `2.26×`; `index` → `151` (`0.5`, `−1` under 2); `count` → `182,458`; zero dollars → `$0`.
- Every mark (or column band / row band) is a ≥ 24px hit target, focusable (`tabindex=0`, `role=img`), and shows the shared tooltip (title; colour key · **value** · label; muted rows for n and change) on hover and focus. Focus draws a 2px `--focus` outline on the band.
- Legend always for ≥ 2 series, never for one. Every chart returns a **table twin** (`Table` button and print).
- Errors: an unknown type or a thrown render shows *Chart failed to render* in that inset only; the rest of the card stays.

Per type (data shape → drawing):
| Type | Shape | Rules |
|---|---|---|
| **line** | `x.values` periods; `series[].values` aligned | Highlighted line drawn last (on top). End labels `151 Calls` for ≤ 4 series, else legend. Column hit bands give one tooltip listing every series at that x. |
| **bar** (columns) | categories in `x.values`, one series | `highlight` names a category (e.g. `2025`). Value on the cap for the highlighted bar, the maximum, and all bars when ≤ 6. Optional `series[0].n` shows `n = …` in the tooltip. |
| **bar, grouped** | categories in `x.values`, two or more series | One cluster per category, ≤ 24px columns with a 3px gap; `highlight` names a **series** (blue; the others grey) or, absent, slots 1–k; legend always; values on the caps of the highlighted series (all when ≤ 8 columns). Column tooltips list every series. |
| **hbar** (rows) | categories, one series, optional `n` | Rows 26px in file order (the analyst sorts). Value at the tip; if any value is negative the chart is **diverging** (blue over / red under, zero line, legend) and a long negative bar carries its value inside in white so it never lands on the row name. `n` column at the right margin, muted. |
| **dumbbell** | categories; `series[0]` first period, `series[1]` second | Grey first dot → blue second dot (grey when not highlighted), % change at the right, legend `FY2013 · FY2025 · change at right`; long row labels wrap to two lines. |
| **slope** | `x.values` two periods; one series per entity | Labels on both sides `Name value` / `value Name`, nudged apart and kept inside the plot; highlighted entity blue and bold; `y.scale: "log"` draws a log axis labelled *log scale*. Height grows with the number of entities (27px each, min 240). |
| **stacked** | periods; one series per segment | Segment order = file order = legend order. With a highlight, that segment is blue and the rest three greys; without, slots 1–7. 100% when every column sums to 100 (`%`). Labels inside segments when they fit; a highlighted segment too thin for a label gets `4.2% Redefined` beside the column. |
| **smallmultiples** | shared `x.values`; one panel per series | 3 columns (2 under 520px), 128px panels, shared y by default; `y.shared: false` gives each panel its own scale and the subtitle must say so. Highlighted panel tinted blue at 7%; end value labelled on every panel; first/last x labelled; annotation line on every panel, labelled once. |
| **scatter** | `x.values` x coordinates; `series[0].values` y; `series[0].labels` point names; `x.unit` | Grey points; highlighted points blue and bold-labelled; extremes labelled; labels clamped inside the plot and nudged upward on collision. Axis titles above (`↑`) and below right (`→`). |
| **waterfall** | steps in `x.values`; `series[0].values` = totals at first and last index (or `chart.totals`), signed deltas between | Totals `--neutral-2`, increases blue, decreases red, dashed connectors; the y axis starts at zero (totals are drawn honestly even when that compresses the steps, so the staggered value labels carry them). `highlight` names a step; other steps dim to 45%. |

## 6. Interactions

- **Expand to evidence**: `Evidence` toggles the panel (`aria-expanded`, `aria-controls`); the button turns ink-on-surface while open. `?insight=<id>` opens that card's evidence; `?evidence=all` opens every card (used by Print).
- **Explore in the dashboard →**: `index.html?view=<explore.view>&<params>` (+ `theme=dark` when dark). For the department scorecard, `view=dept&id=<code>`. Same-tab link; the dashboard's filter bar then shows exactly those parameters and its live sentences reflect them.
- **Share**: per card, copies `<page>?insight=<id>` (plus `theme` when it is in the URL) and reads `Link copied` for 1.6s; falls back to a prompt when the clipboard is unavailable. The evidence footer repeats the link as `Link to this insight`. The top bar's `Copy link` copies the whole page state (filters, open card, data panel).
- **Table twin**: `Table` swaps the chart for a plain `data-table` of the same data.
- **Keyboard**: `j`/`k` (or `↓`/`↑` once a card is current) move between cards and scroll; `e` or `Enter` on a card toggles evidence; `o` follows Explore; `c` copies the card's link; `t` toggles the table; `d` dark; `?` help; `Esc` closes help and clears the current card. Tab order covers every chip, button, link and chart mark; marks show their tooltip on focus and set `aria-label` to its text. Skip link to `#content`.
- **Theme**: `data-theme` on `<html>` set before first paint (URL › saved › OS); the charts re-colour through CSS custom properties without re-rendering.
- **Resize**: charts re-render on a 120ms debounce.
- **Print / PDF**: the Print button opens every evidence panel and calls `print()`; `@media print` hides the shell, filter bar, buttons and help, prints one card per column with `break-inside: avoid`, forces evidence open, prints the Explore URL after its label, and puts a page break after the glance list.

## 7. URL state

`insights.html?topic=staffing,outcomes&dept=POL,FIR&verdict=fragile&insight=<id>&evidence=all&data=1&theme=dark`

- `topic` — insight theme filter (comma list). Named *topic* because `theme` is already the site's light/dark parameter; the UI label is still *Theme*.
- `dept` — department codes (comma list). `verdict` — `robust` | `fragile`. `insight` — the current card (scrolled to, evidence open). `evidence=all` — every panel open. `data=1` — data panel open. In the site shell add `view=pf-insights`.
- Defaults are omitted; `history.replaceState` on every change; `Copy link` copies `location.href`.
- `shot=1` is QA-only: with `insight=`, it hides everything except that card and its neighbour so headless Chrome (which does not paint scrolled content) can screenshot any card without scrolling.

## 8. States

- **Empty** (no insight matches): the glance list disappears; one full-width card reads **No insights match these filters** / *Pick another theme or department, or reset the filters.* (link resets); the data strip shows `0 of 20 insights` in red; the closing box stays.
- **File missing or invalid**: *Could not load data: performance/data/site/insights/insights.json*, same as other views. A chart that fails renders *Chart failed to render* in its inset only.
- **Fewer than ~20 insights**: the title uses the real count (`12 things the numbers say…`); nothing else changes. `rank` values must be 1..n.
- **Small screens (< 1100px)**: sidebar collapses to the brand; filter bar wraps; one column for the glance list and cards; evidence numbers stack; the Explore link takes its own line; title 26px. Charts measure their container and re-layout (small multiples fall to two columns).
- **Sample**: `sample: true` shows the `Sample insights` badge in the kicker and the `sample` badge in the strip and file panel; the top bar's sample note stays as on other views.

## 9. Copy (exact)

- Sidebar item: `★ Insights`. Kicker: `<n> · <Dashboard> · Insights`. Badge: `Sample insights`.
- Title: `<count> things the numbers say about <noun>`.
- Summary: `<r> robust`, `<f> fragile`, `<t> themes`, `<d> departments named`.
- How to read this page: *Each card makes one claim, shows the one chart that carries it, and says how sturdy it is. Robust means the finding held under every alternative we tried (other deflators, year ranges, definitions); fragile means at least one reasonable alternative weakened or reversed it, and the card says which. "Evidence" opens the numbers with their sources, the checks run, what could make the claim wrong, and caveats. "Explore in the dashboard" opens the full view with the filters already applied.* / *Unusual is not improper. A pattern here is a reason to ask a question, not an answer to it.*
- Glance list: `Read in 30 seconds` · `All 20, in rank order. Click a claim to jump to its chart and evidence.` · filtered: `<n> of 20 match your filters. Click a claim to jump to it.`
- Filter bar: `Theme` · `Department · All` / `Department · Police, Fire` · `Verdict` · `Robust` / `Fragile` · `Reset filters` · `Not on this page: Fiscal years, Dollars (each insight fixes its own years and dollar basis; see its chart subtitle)`.
- Card labels: `Why it matters` · `The surprise` · `Evidence` · `<n> numbers · <c> checks` · `Explore in the dashboard →` (default) · `Share` / `Link copied` · `Table` · `The numbers` · `Source:` · `Robustness` · `What could make it wrong` · `Caveats` · `Tags:` · `Link to this insight`.
- Verdict tooltips: `Held under every alternative tried` · `At least one reasonable alternative weakened it; see Evidence`.
- Data strip: `Data on this page` · `<n> insights` / `<n> of <N> insights` · `<k> cited numbers` · `<f> source files` · `1 file loaded (<size>)` · `as of <date>` · `Details` / `Hide details`. Panel: `Insights for your current filters` · `Source files cited by the numbers` · `File for this page` · *Every number on this page carries a source path; the module's verify script checks each one against the file it names.*
- Closing box `Reading these insights`: **Could move the finding** *Robust is not proven. It means the finding survived the alternatives listed under Evidence; a check we did not think of could still move it.* · **Worth knowing** *Fragile is not wrong. It means a reasonable alternative changed the picture; the card names it so you can judge.* · **Minor** *Ranking is editorial: how much a finding should change what a careful reader believes, given how sturdy it is. Rank <n> is still worth a look.* Fairness: **Unusual is not improper.** *Every pattern on this page is a reason to ask a question, not a finding about anyone's conduct. Organizations and officials are named only in public roles; nobody below executive level is named.*
- Empty: `No insights match these filters` · `Pick another theme or department, or reset the filters.`
- Help dialog: `Keyboard` with the shortcuts in §6.

Writing rules for the file (for analysts): title is a claim in plain words with the number in it; dek gives the two numbers behind it; why_it_matters names the public stake without implying wrongdoing; surprise states what a reader would expect; checks are written as *held …* / *did not hold …* so the evidence panel can mark them; every number has a `source` path the verify script can resolve; `explore.label` reads as a verb phrase (*See Fire's measures vs targets*).

## 10. Contract notes and small extensions used by the renderer

All optional and backward-compatible with `INSIGHTS_CONTRACT.json`: `highlight` may be an array (an empty string counts as none; on hbar/dumbbell a highlight that names a series rather than a row is ignored); `bar` with two or more series renders as grouped columns; `series[].n` (per-category counts for bar/hbar); `series[].labels` (point names for scatter) and `x.unit` (scatter x unit); `y.scale: "log"` (slope); `y.shared: false` (small multiples); `y.ref: {value, label}` (reference line); `chart.totals` (waterfall total indices, default first and last); `y.unit: "ratio"`.

Checked against the analyst's first real export (`performance/data/site/insights/insights.json`, 18 insights, 2026-09-26): renders with a clean console in both themes; it uses line, bar (grouped), hbar, dumbbell and stacked. Two things for the analysts: write department names, not codes, in `x.values` (the chart shows them verbatim), and keep annotation labels short (under ~24 characters) when two fall in adjacent years. `tools/emit_json.py` in the prototype checks required fields, chart types, title length, ranks 1..n, series/x lengths and that every number has a source; the module's verify script should do the same plus resolve the sources.

## 11. Integration notes (site/)

- Add `js/insights-charts.js` and `js/insights.js` (the page module; drop the shell-rendering part and register `pf-insights` etc. as views with `filters: []` plus their own in-view filter bar, or extend the filter registry with `topic`/`verdict`) and `css/insights.css`. Set `EXPLORE_BASE` to `index.html` (the prototype uses `data-explore-base` on `<body>`). Read department short names from `site.json › departments` instead of the built-in map.
- Loader: `insights/insights.json` is one file per module (≤ 400 KB; ~75 KB for 20 insights). Bundle it like any other export; `sample: false` removes the badges. Register `ctx.feed('insights', shown, total)` so the strip and the self-test see the filter applied.
- Deep links: `explore.params` keys are the site's URL keys (`dept`, `years`, `group`, `real`, `id`, `v.*`); pass them straight to `state.set`. The bundler should warn when `explore.view` is not a registered view or a param key is unknown.
- QA: screenshot `?view=pf-insights` top, `&shot=1&insight=<id>` for every id, both themes; `&topic=…&verdict=fragile` (empty state); `&data=1`; `--print-to-pdf` with `&evidence=all`. Console must be clean. Scripts: `design/insights/shots/shoot.sh`, `console.sh`.
