"""
Generates a static HTML dashboard from the pipeline's real output.

Design direction: a carbon credit register — a registry-issued credit is a
serialized, verified certificate, so the page borrows from that world
rather than from generic SaaS analytics: light archival paper (not the
common warm-cream/terracotta default, a cooler sage tone instead), a
bordered masthead with corner registration marks, an asymmetric hero frame
around one thesis number instead of four equal stat boxes, and a rotated
circular verification stamp — the page's one signature element — marking
every flagged or notable credit, echoing an actual registry stamp.

Type carries three distinct jobs rather than one font doing everything:
Bricolage Grotesque for identity (masthead + hero number only), Spectral
serif for reading (captions, notes, section framing), and Martian Mono
for every real data value (prices, IDs, the ticker, the table) — so data
reads like a serial number, not decoration.

Data is embedded directly as a JSON blob in a <script> tag rather than
fetched from a separate file — this means the page works when opened
directly as a local file (file:// URLs block fetch() of local JSON due to
browser CORS restrictions), not just when served from GitHub Pages or a
local server. Re-run this generator (via notebook 03) to refresh the
embedded snapshot.
"""

import json
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def _fig_to_chartjs_data(model_df: pd.DataFrame, fitted_df: pd.DataFrame, result_resid) -> dict:
    """Package the numbers needed for the in-browser charts (Chart.js draws
    them client-side, rather than shipping static matplotlib images — keeps
    the page interactive and the file small)."""
    return {
        "priceByRegistry": {
            reg: model_df.loc[model_df["registry"] == reg, "price_usd"].round(3).tolist()
            for reg in model_df["registry"].unique()
        },
        "actualVsPredicted": {
            "actual": fitted_df["observed_price"].round(3).tolist(),
            "predicted": fitted_df["hedonic_model_price"].round(3).tolist(),
            "projectIds": fitted_df["project_id"].tolist(),
        },
        "residuals": [round(float(r), 4) for r in result_resid],
    }


def build_dashboard_html(
    ranked_df: pd.DataFrame,
    diagnostics: dict,
    model_df: pd.DataFrame,
    fitted_df: pd.DataFrame,
    result_resid,
    run_timestamp: str,
    output_path: str,
) -> None:
    """
    Render the full dashboard to a single self-contained HTML file at output_path.
    All data (ranked table, diagnostics, chart series) is embedded inline.
    """
    n_total = len(ranked_df)
    n_undervalued = ranked_df["classification"].str.contains("undervaluation").sum()
    n_overvalued = ranked_df["classification"].str.contains("overvaluation").sum()
    n_fair = (ranked_df["classification"] == "fair value range").sum()
    registries = sorted(model_df["registry"].unique().tolist())

    # Outliers: anything with |z| > 2 gets flagged in the "discrepancies" panel,
    # with an explicit caution about small-sample artifacts rather than
    # presenting every flag as an equally confident finding.
    outliers = ranked_df[ranked_df["combined_zscore"].abs() > 2].copy()

    chart_data = _fig_to_chartjs_data(model_df, fitted_df, result_resid)

    def _to_native(v):
        """Convert numpy scalar types (bool_, int64, float64, etc.) to plain
        Python types so json.dumps doesn't choke on them — caught by actually
        running this against real diagnostics output, which contains
        np.True_ for multicollinearity_flag, not a plain bool."""
        if isinstance(v, (np.bool_, bool)):
            return bool(v)
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating, float)):
            return round(float(v), 4)
        return v

    payload = {
        "runTimestamp": run_timestamp,
        "nTotal": int(n_total),
        "nUndervalued": int(n_undervalued),
        "nOvervalued": int(n_overvalued),
        "nFair": int(n_fair),
        "registries": registries,
        "diagnostics": {k: _to_native(v) for k, v in diagnostics.items()},
        "rankedTable": json.loads(ranked_df.to_json(orient="records")),
        "outliers": json.loads(outliers.to_json(orient="records")),
        "charts": chart_data,
    }
    payload_json = json.dumps(payload)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carbon credit register</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400..800&family=Spectral:ital,wght@0,400;0,500;1,400&family=Martian+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js"></script>
<style>
  :root {{
    --paper: #EDEFE3;
    --paper-raised: #F6F7EF;
    --ink: #1B211D;
    --ink-muted: #5B6259;
    --rule: #C7CDBE;
    --rule-strong: #9BA495;
    --stamp-red: #B23A2A;
    --stamp-green: #2F6B4F;
    --stamp-tan: #8A7440;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    background: var(--paper);
    color: var(--ink);
    font-family: 'Spectral', serif;
    font-size: 15px;
    line-height: 1.7;
    margin: 0;
    padding: 0;
  }}
  .data, table, .ticker-item, .stamp, .hero-n, .table-controls input, .toggle-btn, .pid, .num, code {{
    font-family: 'Martian Mono', monospace;
  }}
  h1, h2 {{ font-family: 'Bricolage Grotesque', sans-serif; margin: 0; }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 48px 24px 120px; }}

  .masthead {{ position: relative; border: 1.5px solid var(--rule-strong); padding: 28px 32px; margin-bottom: 48px; }}
  .reg-mark {{ position: absolute; font-family: 'Martian Mono', monospace; font-size: 13px; color: var(--rule-strong); line-height: 1; }}
  .reg-mark.tl {{ top: 8px; left: 8px; }}
  .reg-mark.tr {{ top: 8px; right: 8px; }}
  .reg-mark.bl {{ bottom: 8px; left: 8px; }}
  .reg-mark.br {{ bottom: 8px; right: 8px; }}
  .eyebrow {{ font-family: 'Martian Mono', monospace; font-size: 11px; color: var(--ink-muted); letter-spacing: 0.08em; margin-bottom: 10px; }}
  .masthead h1 {{ font-size: 34px; font-weight: 800; letter-spacing: -0.01em; }}
  .masthead .meta {{ font-style: italic; color: var(--ink-muted); font-size: 13px; margin-top: 10px; }}

  .hero {{ border: 1px solid var(--rule-strong); box-shadow: 0 0 0 4px var(--paper), 0 0 0 5px var(--rule); margin: 0 0 48px; padding: 32px; text-align: center; }}
  .hero-n {{ font-family: 'Bricolage Grotesque', sans-serif; font-size: 84px; font-weight: 800; line-height: 1; }}
  .hero-label {{ font-style: italic; color: var(--ink-muted); font-size: 14px; margin-top: 8px; }}
  .hero-totals {{ margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--rule); font-size: 13px; }}
  .hero-totals span {{ margin: 0 10px; }}
  .hero-totals .under {{ color: var(--stamp-green); }}
  .hero-totals .over {{ color: var(--stamp-red); }}
  .hero-totals .fair {{ color: var(--stamp-tan); }}

  .caution {{ border-left: 3px solid var(--stamp-red); padding: 16px 22px; margin-bottom: 48px; background: var(--paper-raised); }}
  .caution h3 {{ font-family: 'Bricolage Grotesque', sans-serif; font-size: 15px; font-weight: 700; margin-bottom: 8px; }}
  .caution p {{ color: var(--ink-muted); margin: 0 0 8px; font-size: 14px; font-style: italic; }}
  .caution p:last-child {{ margin-bottom: 0; }}

  section {{ margin-bottom: 60px; }}
  section > h2 {{ font-size: 20px; font-weight: 700; border-bottom: 1px solid var(--rule-strong); padding-bottom: 12px; margin-bottom: 22px; }}
  section > .section-note {{ color: var(--ink-muted); font-size: 13px; font-style: italic; margin: -12px 0 20px; }}

  .stamp {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 52px; height: 52px; border-radius: 50%; border: 2px solid currentColor;
    transform: rotate(-8deg); font-size: 10px; letter-spacing: 0.02em; text-align: center;
    flex-shrink: 0;
  }}
  .stamp.under {{ color: var(--stamp-green); }}
  .stamp.over {{ color: var(--stamp-red); }}

  .outlier-card {{ border: 1px solid var(--rule-strong); padding: 18px 22px; margin-bottom: 14px; display: flex; align-items: center; gap: 18px; }}
  .outlier-card .body {{ flex: 1; }}
  .outlier-card .head {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }}
  .outlier-card .pid {{ font-weight: 700; font-size: 15px; }}
  .outlier-card .cls {{ font-family: 'Spectral', serif; font-style: italic; font-size: 13px; }}
  .outlier-card .cls.over {{ color: var(--stamp-red); }}
  .outlier-card .cls.under {{ color: var(--stamp-green); }}
  .outlier-card .detail {{ color: var(--ink-muted); font-size: 13px; }}

  .notable-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; margin-bottom: 20px; }}
  .notable-card {{ position: relative; border: 1px solid var(--rule-strong); border-left: 2px dashed var(--rule-strong); padding: 14px 16px 14px 22px; }}
  .notable-card::before {{
    content: ""; position: absolute; left: -6px; top: 50%; transform: translateY(-50%);
    width: 11px; height: 11px; border-radius: 50%; background: var(--paper); border: 1px solid var(--rule-strong);
  }}
  .notable-card .row1 {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }}
  .notable-card .pid {{ font-weight: 700; font-size: 14px; }}
  .notable-card .z {{ font-size: 13px; }}
  .notable-card .z.under {{ color: var(--stamp-green); }}
  .notable-card .z.over {{ color: var(--stamp-red); }}
  .notable-card .price-line {{ color: var(--ink-muted); font-size: 12px; font-family: 'Spectral', serif; font-style: italic; }}

  .table-controls {{ display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }}
  .table-controls input {{ background: var(--paper-raised); border: 1px solid var(--rule-strong); color: var(--ink); font-size: 13px; padding: 9px 12px; flex: 1; }}
  .table-controls input:focus {{ outline: none; border-color: var(--stamp-green); }}
  .toggle-btn {{ background: var(--paper-raised); border: 1px solid var(--rule-strong); color: var(--ink); font-size: 13px; padding: 11px 18px; cursor: pointer; }}
  .toggle-btn:hover {{ border-color: var(--stamp-green); color: var(--stamp-green); }}

  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead tr {{ border-top: 3px double var(--ink); border-bottom: 1px solid var(--rule-strong); }}
  th {{ text-align: left; color: var(--ink-muted); font-weight: 500; font-size: 11px; padding: 10px 12px; cursor: pointer; user-select: none; font-family: 'Martian Mono', monospace; }}
  th:hover {{ color: var(--ink); }}
  th.num {{ text-align: right; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid var(--rule); }}
  tbody tr:last-child {{ border-bottom: 3px double var(--ink); }}
  tbody tr:nth-child(even) {{ background: var(--paper-raised); }}
  .num {{ text-align: right; }}
  .tag {{ display: inline-block; padding: 2px 8px; border: 1px solid currentColor; font-size: 11px; }}
  .tag.under {{ color: var(--stamp-green); }}
  .tag.over {{ color: var(--stamp-red); }}
  .tag.fair {{ color: var(--stamp-tan); }}

  .chart-box {{ border: 1px solid var(--rule-strong); padding: 24px; margin-bottom: 20px; background: var(--paper-raised); }}
  .chart-box h3 {{ font-family: 'Bricolage Grotesque', sans-serif; font-size: 15px; font-weight: 700; margin-bottom: 4px; }}
  .chart-box .note {{ color: var(--ink-muted); font-size: 12px; font-style: italic; margin-bottom: 20px; }}
  canvas {{ max-height: 320px; }}

  footer {{ border-top: 1px solid var(--rule-strong); padding-top: 22px; color: var(--ink-muted); font-size: 12px; font-style: italic; }}
  footer a {{ color: var(--stamp-green); }}

  .ticker-strip {{ overflow: hidden; white-space: nowrap; background: var(--paper-raised); border-bottom: 1.5px solid var(--rule-strong); padding: 11px 0; }}
  .ticker-label {{ display: inline-block; font-family: 'Martian Mono', monospace; color: var(--ink-muted); font-size: 11px; letter-spacing: 0.05em; padding: 0 20px 0 24px; border-right: 1px dashed var(--rule-strong); vertical-align: middle; }}
  .ticker-viewport {{ display: inline-block; overflow: hidden; white-space: nowrap; vertical-align: middle; width: calc(100% - 150px); }}
  .ticker-track {{ display: inline-flex; animation: ticker-scroll 55s linear infinite; will-change: transform; }}
  .ticker-item {{ font-size: 13px; white-space: nowrap; padding: 0 18px; border-right: 1px dashed var(--rule-strong); }}
  .ticker-item .pid {{ font-weight: 700; color: var(--ink); }}
  .ticker-item .price {{ margin-left: 8px; }}
  .ticker-item .price.under {{ color: var(--stamp-green); }}
  .ticker-item .price.over {{ color: var(--stamp-red); }}
  .ticker-item .price.fair {{ color: var(--stamp-tan); }}
  @keyframes ticker-scroll {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
  @media (prefers-reduced-motion: reduce) {{
    .ticker-track {{ animation: none; }}
    .ticker-viewport {{ overflow-x: auto; }}
  }}

  @media (max-width: 640px) {{
    .notable-grid {{ grid-template-columns: 1fr; }}
    .hero-n {{ font-size: 56px; }}
  }}
</style>
</head>
<body>
<div class="ticker-strip">
  <span class="ticker-label">Price register</span>
  <span class="ticker-viewport"><span class="ticker-track" id="ticker-track"></span></span>
</div>
<div class="wrap">

<div class="masthead">
  <span class="reg-mark tl">+</span>
  <span class="reg-mark tr">+</span>
  <span class="reg-mark bl">+</span>
  <span class="reg-mark br">+</span>
  <div class="eyebrow">Relative-value review</div>
  <h1>Carbon credit register</h1>
  <p class="meta" id="run-meta"></p>
</div>

<div class="hero">
  <div class="hero-n" id="hero-total">0</div>
  <div class="hero-label">credits reviewed against comparable credits this run</div>
  <div class="hero-totals" id="hero-totals"></div>
</div>

<div class="caution">
  <h3>Read this before the register below</h3>
  <p id="caution-text"></p>
  <p>Every classification here means "potentially" mispriced relative to a small comparable set — not a confirmed arbitrage opportunity. See the full research log in the repository for how each model and threshold was chosen.</p>
</div>

<section id="outliers-section">
  <h2>Flagged on review</h2>
  <div id="outliers-container"></div>
</section>

<section>
  <h2>Most notable credits</h2>
  <div class="section-note">The 8 largest deviations from fair value. Full register below.</div>
  <div class="notable-grid" id="notable-grid"></div>
</section>

<section>
  <h2>Price distribution by registry</h2>
  <div class="chart-box">
    <div class="note">Where price data actually exists right now — coverage may be concentrated in one registry.</div>
    <canvas id="chart-registry"></canvas>
  </div>
</section>

<section>
  <h2>Model fit: actual vs. model-implied price</h2>
  <div class="chart-box">
    <div class="note">Points far from the diagonal are the large-residual credits driving the relative-value flags.</div>
    <canvas id="chart-fit"></canvas>
  </div>
</section>

<section>
  <h2>Residual distribution</h2>
  <div class="chart-box">
    <div class="note">Should be roughly symmetric around zero. Skew here is real information about model reliability, not noise to ignore.</div>
    <canvas id="chart-residuals"></canvas>
  </div>
</section>

<section>
  <h2>The register</h2>
  <button class="toggle-btn" id="toggle-table">Show all <span id="toggle-count"></span> credits</button>
  <div id="table-wrap" style="display:none; margin-top: 20px;">
    <div class="table-controls">
      <input type="text" id="table-search" placeholder="Search by project ID...">
    </div>
    <table id="ranked-table">
      <thead>
        <tr>
          <th data-key="project_id">Project</th>
          <th class="num" data-key="observed_price">Observed</th>
          <th class="num" data-key="hedonic_model_price">Hedonic model</th>
          <th class="num" data-key="comparable_model_price">Comparable model</th>
          <th class="num" data-key="combined_zscore">z-score</th>
          <th data-key="classification">Classification</th>
        </tr>
      </thead>
      <tbody id="ranked-tbody"></tbody>
    </table>
  </div>
</section>

<footer>
  Generated from a real pipeline run — see <code>docs/research_decisions_log.md</code> for methodology, known limitations, and what each modelling decision traded off. Not investment advice.
</footer>

</div>

<script>
const DATA = {payload_json};

function tagClass(classification) {{
  if (classification.includes('undervaluation')) return 'under';
  if (classification.includes('overvaluation')) return 'over';
  return 'fair';
}}

document.getElementById('run-meta').textContent =
  `${{DATA.nTotal}} credits scored \u00b7 registries covered: ${{DATA.registries.join(', ')}} \u00b7 run at ${{DATA.runTimestamp}}`;

function tickerItemHtml(r) {{
  return `<span class="ticker-item"><span class="pid">${{r.project_id}}</span><span class="price ${{tagClass(r.classification)}}">$${{r.observed_price.toFixed(2)}}</span></span>`;
}}
const tickerHtml = DATA.rankedTable.map(tickerItemHtml).join('');
document.getElementById('ticker-track').innerHTML = tickerHtml + tickerHtml;

const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function countUp(el, target, duration = 700) {{
  if (prefersReducedMotion || target === 0) {{ el.textContent = target; return; }}
  const start = performance.now();
  function tick(now) {{
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(eased * target);
    if (progress < 1) requestAnimationFrame(tick);
  }}
  requestAnimationFrame(tick);
}}
countUp(document.getElementById('hero-total'), DATA.nTotal);
document.getElementById('hero-totals').innerHTML =
  `<span class="under">${{DATA.nUndervalued}} undervalued</span>\u00b7<span class="fair">${{DATA.nFair}} fair</span>\u00b7<span class="over">${{DATA.nOvervalued}} overvalued</span>`;

const rsq = DATA.diagnostics.r_squared;
const condNum = DATA.diagnostics.condition_number;
const multicollinear = DATA.diagnostics.multicollinearity_flag;
document.getElementById('caution-text').textContent =
  `This run has ${{DATA.nTotal}} priced credits. The hedonic model's R\u00B2 is ${{rsq.toFixed(2)}}` +
  (multicollinear
    ? `, and the condition number (${{condNum.toFixed(0)}}) exceeds the conventional multicollinearity threshold of 30 \u2014 with a sample this size, treat individual model coefficients with real skepticism, not as settled findings.`
    : `.`);

const outliersContainer = document.getElementById('outliers-container');
if (DATA.outliers.length === 0) {{
  outliersContainer.innerHTML = '<p style="color:var(--ink-muted); font-style:italic;">No credits currently exceed the \u00b12 z-score threshold.</p>';
}} else {{
  outliersContainer.innerHTML = DATA.outliers.map(o => `
    <div class="outlier-card">
      <div class="stamp ${{tagClass(o.classification)}}">${{o.combined_zscore > 0 ? '+' : ''}}${{o.combined_zscore.toFixed(1)}}</div>
      <div class="body">
        <div class="head">
          <span class="pid">${{o.project_id}}</span>
          <span class="cls ${{tagClass(o.classification)}}">${{o.classification}}</span>
        </div>
        <div class="detail">Observed $${{o.observed_price.toFixed(2)}} vs. hedonic model $${{o.hedonic_model_price.toFixed(2)}} and comparable model $${{o.comparable_model_price.toFixed(2)}}</div>
      </div>
    </div>
  `).join('');
}}

const notable = [...DATA.rankedTable]
  .sort((a, b) => Math.abs(b.combined_zscore) - Math.abs(a.combined_zscore))
  .slice(0, 8);
document.getElementById('notable-grid').innerHTML = notable.map(r => `
  <div class="notable-card">
    <div class="row1">
      <span class="pid">${{r.project_id}}</span>
      <span class="z ${{tagClass(r.classification)}}">${{r.combined_zscore.toFixed(2)}}</span>
    </div>
    <div class="price-line">$${{r.observed_price.toFixed(2)}} observed vs. $${{r.hedonic_model_price.toFixed(2)}} model</div>
  </div>
`).join('');

const toggleBtn = document.getElementById('toggle-table');
const tableWrap = document.getElementById('table-wrap');
document.getElementById('toggle-count').textContent = DATA.nTotal;
let tableOpen = false;
toggleBtn.addEventListener('click', () => {{
  tableOpen = !tableOpen;
  tableWrap.style.display = tableOpen ? 'block' : 'none';
  toggleBtn.textContent = tableOpen ? 'Hide register' : `Show all ${{DATA.nTotal}} credits`;
}});

let currentSort = {{ key: 'combined_zscore', dir: 1 }};
let currentFilter = '';

function renderTable() {{
  let rows = DATA.rankedTable.filter(r => r.project_id.toLowerCase().includes(currentFilter));
  rows.sort((a, b) => {{
    const av = a[currentSort.key], bv = b[currentSort.key];
    if (typeof av === 'string') return av.localeCompare(bv) * currentSort.dir;
    return (av - bv) * currentSort.dir;
  }});
  const tbody = document.getElementById('ranked-tbody');
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${{r.project_id}}</td>
      <td class="num">$${{r.observed_price.toFixed(2)}}</td>
      <td class="num">$${{r.hedonic_model_price.toFixed(2)}}</td>
      <td class="num">$${{r.comparable_model_price.toFixed(2)}}</td>
      <td class="num">${{r.combined_zscore.toFixed(2)}}</td>
      <td><span class="tag ${{tagClass(r.classification)}}">${{r.classification}}</span></td>
    </tr>
  `).join('');
}}
renderTable();

document.getElementById('table-search').addEventListener('input', (e) => {{
  currentFilter = e.target.value.toLowerCase();
  renderTable();
}});

document.querySelectorAll('#ranked-table th[data-key]').forEach(th => {{
  th.addEventListener('click', () => {{
    const key = th.dataset.key;
    currentSort.dir = (currentSort.key === key) ? -currentSort.dir : 1;
    currentSort.key = key;
    renderTable();
  }});
}});

Chart.defaults.color = '#5B6259';
Chart.defaults.font.family = "'Martian Mono', monospace";
Chart.defaults.borderColor = '#C7CDBE';

if (typeof Chart === 'undefined') {{
  document.querySelectorAll('.chart-box').forEach(box => {{
    box.innerHTML = '<p style="color:var(--ink-muted)">Chart could not load (Chart.js CDN unreachable). Register and figures above are unaffected.</p>';
  }});
}} else {{

const registryColors = ['#2F6B4F', '#B23A2A', '#8A7440', '#5B7A94', '#8A5B7A'];
new Chart(document.getElementById('chart-registry'), {{
  type: 'bar',
  data: {{
    labels: Object.keys(DATA.charts.priceByRegistry),
    datasets: [{{
      label: 'Median price (USD)',
      data: Object.values(DATA.charts.priceByRegistry).map(arr => {{
        const sorted = [...arr].sort((a,b) => a-b);
        return sorted[Math.floor(sorted.length/2)] || 0;
      }}),
      backgroundColor: registryColors,
    }}]
  }},
  options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true }} }} }}
}});

new Chart(document.getElementById('chart-fit'), {{
  type: 'scatter',
  data: {{
    datasets: [{{
      label: 'Credits',
      data: DATA.charts.actualVsPredicted.actual.map((a, i) => ({{ x: DATA.charts.actualVsPredicted.predicted[i], y: a }})),
      backgroundColor: '#2F6B4F',
    }}]
  }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ title: {{ display: true, text: 'Model-implied price (USD)' }} }},
      y: {{ title: {{ display: true, text: 'Observed price (USD)' }} }},
    }}
  }}
}});

new Chart(document.getElementById('chart-residuals'), {{
  type: 'bar',
  data: (() => {{
    const vals = DATA.charts.residuals;
    const bins = 15;
    const min = Math.min(...vals), max = Math.max(...vals);
    const width = (max - min) / bins || 1;
    const counts = new Array(bins).fill(0);
    vals.forEach(v => {{
      let idx = Math.floor((v - min) / width);
      if (idx >= bins) idx = bins - 1;
      if (idx < 0) idx = 0;
      counts[idx]++;
    }});
    const labels = counts.map((_, i) => (min + i * width).toFixed(2));
    return {{ labels, datasets: [{{ label: 'Residuals', data: counts, backgroundColor: '#8A7440' }}] }};
  }})(),
  options: {{ plugins: {{ legend: {{ display: false }} }} }}
}});

}}
</script>
</body>
</html>
"""

    with open(output_path, "w") as f:
        f.write(html)
    logger.info(f"Dashboard written to {output_path}")
