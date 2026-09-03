"""
Generates a static HTML dashboard from the pipeline's real output.

Design approach: a research "field ledger" aesthetic — deep forest-ink
background, parchment text, monospace throughout for genuine tabular
alignment (this is a data-dense financial page, not a marketing site, so
monospace is functional here, not decorative). Serif for headlines only,
to read like a research bulletin rather than a SaaS dashboard.

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

    any_significant = False  # set from diagnostics context in the narrative below; real check done in JS

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carbon credit relative-value ledger</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #14201A;
    --surface: #1C2B22;
    --border: #2E3F34;
    --text: #E8E4D6;
    --text-muted: #9BA89E;
    --under: #7FA88C;
    --over: #C97452;
    --fair: #A89B7E;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 14px;
    line-height: 1.6;
    margin: 0;
    padding: 0;
  }}
  h1, h2, h3 {{
    font-family: 'Source Serif 4', serif;
    font-weight: 600;
    margin: 0 0 0.5em 0;
  }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 56px 24px 120px; }}
  header {{ border-bottom: 1px solid var(--border); padding-bottom: 28px; margin-bottom: 56px; }}
  header h1 {{ font-size: 30px; letter-spacing: -0.01em; }}
  header p {{ color: var(--text-muted); margin: 6px 0 0; font-size: 13px; }}

  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--border); border: 1px solid var(--border); margin-bottom: 56px; }}
  .stat {{ background: var(--surface); padding: 24px 20px; }}
  .stat .n {{ font-size: 34px; font-weight: 600; font-variant-numeric: tabular-nums; }}
  .stat .label {{ color: var(--text-muted); font-size: 12px; margin-top: 6px; }}
  .stat.under .n {{ color: var(--under); }}
  .stat.over .n {{ color: var(--over); }}

  .caution {{ border: 1px solid var(--border); border-left: 3px solid var(--over); padding: 18px 22px; margin-bottom: 56px; background: var(--surface); }}
  .caution h3 {{ font-size: 14px; font-family: 'IBM Plex Mono', monospace; font-weight: 600; margin-bottom: 10px; }}
  .caution p {{ color: var(--text-muted); margin: 0 0 8px; font-size: 13px; }}
  .caution p:last-child {{ margin-bottom: 0; }}

  section {{ margin-bottom: 64px; }}
  section > h2 {{ font-size: 20px; border-bottom: 1px solid var(--border); padding-bottom: 14px; margin-bottom: 24px; }}
  section > .section-note {{ color: var(--text-muted); font-size: 12px; margin: -16px 0 20px; }}

  .outlier-card {{ border: 1px solid var(--border); padding: 18px 22px; margin-bottom: 14px; }}
  .outlier-card .head {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }}
  .outlier-card .pid {{ font-weight: 600; font-size: 15px; }}
  .outlier-card .cls {{ font-size: 12px; }}
  .outlier-card .cls.over {{ color: var(--over); }}
  .outlier-card .cls.under {{ color: var(--under); }}
  .outlier-card .detail {{ color: var(--text-muted); font-size: 13px; }}

  .notable-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 20px; }}
  .notable-card {{ border: 1px solid var(--border); padding: 14px 16px; }}
  .notable-card .row1 {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }}
  .notable-card .pid {{ font-weight: 600; font-size: 14px; }}
  .notable-card .z {{ font-size: 13px; font-variant-numeric: tabular-nums; }}
  .notable-card .z.under {{ color: var(--under); }}
  .notable-card .z.over {{ color: var(--over); }}
  .notable-card .price-line {{ color: var(--text-muted); font-size: 12px; }}

  .table-controls {{ display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }}
  .table-controls input {{ background: var(--surface); border: 1px solid var(--border); color: var(--text); font-family: 'IBM Plex Mono', monospace; font-size: 13px; padding: 8px 12px; flex: 1; }}
  .table-controls input:focus {{ outline: none; border-color: var(--under); }}
  .toggle-btn {{ background: var(--surface); border: 1px solid var(--border); color: var(--text); font-family: 'IBM Plex Mono', monospace; font-size: 13px; padding: 10px 16px; cursor: pointer; }}
  .toggle-btn:hover {{ border-color: var(--under); }}

  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; color: var(--text-muted); font-weight: 500; font-size: 11px; text-transform: none; padding: 10px 12px; border-bottom: 1px solid var(--border); cursor: pointer; user-select: none; }}
  th:hover {{ color: var(--text); }}
  th.num {{ text-align: right; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); }}
  tr:hover td {{ background: var(--surface); }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .tag {{ display: inline-block; padding: 2px 8px; border: 1px solid var(--border); font-size: 11px; }}
  .tag.under {{ color: var(--under); border-color: var(--under); }}
  .tag.over {{ color: var(--over); border-color: var(--over); }}
  .tag.fair {{ color: var(--fair); border-color: var(--fair); }}

  .chart-box {{ border: 1px solid var(--border); padding: 24px; margin-bottom: 20px; }}
  .chart-box h3 {{ font-size: 14px; margin-bottom: 4px; }}
  .chart-box .note {{ color: var(--text-muted); font-size: 12px; margin-bottom: 20px; }}
  canvas {{ max-height: 320px; }}

  footer {{ border-top: 1px solid var(--border); padding-top: 24px; color: var(--text-muted); font-size: 12px; }}
  footer a {{ color: var(--under); }}

  .ticker-strip {{ overflow: hidden; white-space: nowrap; background: var(--surface); border-bottom: 1px solid var(--border); padding: 11px 0; }}
  .ticker-label {{ display: inline-block; color: var(--text-muted); font-size: 11px; letter-spacing: 0.04em; padding: 0 20px 0 24px; border-right: 1px solid var(--border); vertical-align: middle; }}
  .ticker-viewport {{ display: inline-block; overflow: hidden; white-space: nowrap; vertical-align: middle; width: calc(100% - 130px); }}
  .ticker-track {{ display: inline-flex; gap: 36px; animation: ticker-scroll 55s linear infinite; will-change: transform; }}
  .ticker-item {{ font-size: 13px; white-space: nowrap; }}
  .ticker-item .pid {{ font-weight: 600; color: var(--text); }}
  .ticker-item .price {{ margin-left: 8px; }}
  .ticker-item .price.under {{ color: var(--under); }}
  .ticker-item .price.over {{ color: var(--over); }}
  .ticker-item .price.fair {{ color: var(--fair); }}
  @keyframes ticker-scroll {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
  @media (prefers-reduced-motion: reduce) {{
    .ticker-track {{ animation: none; }}
    .ticker-viewport {{ overflow-x: auto; }}
  }}
  @media (max-width: 640px) {{
    .stats {{ grid-template-columns: repeat(2, 1fr); }}
    .notable-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="ticker-strip">
  <span class="ticker-label">Price ticker</span>
  <span class="ticker-viewport"><span class="ticker-track" id="ticker-track"></span></span>
</div>
<div class="wrap">

<header>
  <h1>Carbon credit relative-value ledger</h1>
  <p id="run-meta"></p>
</header>

<div class="stats" id="stats-row"></div>

<div class="caution">
  <h3>Read this before the table below</h3>
  <p id="caution-text"></p>
  <p>Every classification here means "potentially" mispriced relative to a small comparable set — not a confirmed arbitrage opportunity. See the full research log in the repository for how each model and threshold was chosen.</p>
</div>

<section id="outliers-section">
  <h2>Flagged discrepancies</h2>
  <div id="outliers-container"></div>
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
  <h2>Most notable credits</h2>
  <div class="section-note">The 8 largest deviations from fair value. Full table below.</div>
  <div class="notable-grid" id="notable-grid"></div>
</section>

<section>
  <h2>Full ranked table</h2>
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
  `${{DATA.nTotal}} credits scored · registries covered: ${{DATA.registries.join(', ')}} · run at ${{DATA.runTimestamp}}`;

// Ticker strip: real prices from this run, not decorative placeholder text.
// Duplicated once so the CSS animation (translateX -50%) loops seamlessly —
// standard marquee technique, avoids a visible jump-cut at the loop point.
function tickerItemHtml(r) {{
  return `<span class="ticker-item"><span class="pid">${{r.project_id}}</span><span class="price ${{tagClass(r.classification)}}">$${{r.observed_price.toFixed(2)}}</span></span>`;
}}
const tickerHtml = DATA.rankedTable.map(tickerItemHtml).join('');
document.getElementById('ticker-track').innerHTML = tickerHtml + tickerHtml;

// One deliberate motion moment: the four hero stats count up on load,
// rather than animating everything on the page. Respects reduced-motion.
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

document.getElementById('stats-row').innerHTML = `
  <div class="stat"><div class="n" id="stat-total">0</div><div class="label">credits priced &amp; scored</div></div>
  <div class="stat under"><div class="n" id="stat-under">0</div><div class="label">potentially undervalued</div></div>
  <div class="stat"><div class="n" id="stat-fair">0</div><div class="label">fair value range</div></div>
  <div class="stat over"><div class="n" id="stat-over">0</div><div class="label">potentially overvalued</div></div>
`;
countUp(document.getElementById('stat-total'), DATA.nTotal);
countUp(document.getElementById('stat-under'), DATA.nUndervalued);
countUp(document.getElementById('stat-fair'), DATA.nFair);
countUp(document.getElementById('stat-over'), DATA.nOvervalued);

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
  outliersContainer.innerHTML = '<p style="color:var(--text-muted)">No credits currently exceed the \u00b12 z-score threshold.</p>';
}} else {{
  outliersContainer.innerHTML = DATA.outliers.map(o => `
    <div class="outlier-card">
      <div class="head">
        <span class="pid">${{o.project_id}}</span>
        <span class="cls ${{tagClass(o.classification)}}">${{o.classification}}</span>
      </div>
      <div class="detail">Observed $${{o.observed_price.toFixed(2)}} vs. hedonic model $${{o.hedonic_model_price.toFixed(2)}} and comparable model $${{o.comparable_model_price.toFixed(2)}} &middot; z = ${{o.combined_zscore.toFixed(2)}}</div>
    </div>
  `).join('');
}}

// Notable credits: the 8 largest deviations from fair value, shown as
// compact cards — this is what most people actually want to scan first,
// rather than parsing a 50-row table for the interesting rows themselves.
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

// Full table: hidden by default, toggled open, searchable, sortable by
// clicking a header. This is the progressive-disclosure fix for density —
// the data is all still here, just not forced on screen at once.
const toggleBtn = document.getElementById('toggle-table');
const tableWrap = document.getElementById('table-wrap');
document.getElementById('toggle-count').textContent = DATA.nTotal;
let tableOpen = false;
toggleBtn.addEventListener('click', () => {{
  tableOpen = !tableOpen;
  tableWrap.style.display = tableOpen ? 'block' : 'none';
  toggleBtn.textContent = tableOpen ? 'Hide table' : `Show all ${{DATA.nTotal}} credits`;
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

Chart.defaults.color = '#9BA89E';
Chart.defaults.font.family = "'IBM Plex Mono', monospace";
Chart.defaults.borderColor = '#2E3F34';

if (typeof Chart === 'undefined') {{
  // CDN blocked (corporate firewall, offline, etc.) — the table and stats above
  // still work since they don't depend on Chart.js; just skip chart rendering
  // and say so, rather than leaving three blank canvases with no explanation.
  document.querySelectorAll('.chart-box').forEach(box => {{
    box.innerHTML = '<p style="color:var(--text-muted)">Chart could not load (Chart.js CDN unreachable). Table and figures above are unaffected.</p>';
  }});
}} else {{

const registryColors = ['#7FA88C', '#C97452', '#A89B7E', '#6B8FA3', '#B08FA8'];
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
      backgroundColor: '#7FA88C',
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
    return {{ labels, datasets: [{{ label: 'Residuals', data: counts, backgroundColor: '#A89B7E' }}] }};
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
