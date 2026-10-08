"""Build the EU Grid Pulse dashboard from the marts.

Queries the star schema in DuckDB, computes the headline metrics (renewable
share, demand vs generation, fuel mix, peak load, diurnal demand), and writes a
self-contained HTML dashboard to dashboards/index.html. This stands in for the
Power BI dashboard so the project is viewable with no extra tooling.
"""
from __future__ import annotations

import json
from pathlib import Path

from .warehouse import PROJECT_ROOT, get_connection

OUT = PROJECT_ROOT / "dashboards" / "index.html"


def _metrics(con) -> dict:
    kpi = con.execute("""
        select
            (select count(distinct country_code) from fact_load)                    as n_countries,
            (select count(distinct date_key)     from dim_date)                      as n_hours,
            (select max(load_mw)                 from fact_load)                      as peak_load_mw,
            (select avg(load_mw)                 from fact_load)                      as avg_load_mw,
            (select min(datetime_utc)            from fact_load)                      as ts_min,
            (select max(datetime_utc)            from fact_load)                      as ts_max
    """).df().iloc[0].to_dict()

    renewable_share = con.execute("""
        select 100.0 * sum(case when f.is_renewable then g.generation_mw else 0 end)
                     / nullif(sum(g.generation_mw), 0) as pct
        from fact_generation g join dim_fuel f using (fuel_key)
    """).fetchone()[0]

    ren_by_country = con.execute("""
        select c.country_name,
               100.0 * sum(case when f.is_renewable then g.generation_mw else 0 end)
                     / nullif(sum(g.generation_mw), 0) as pct
        from fact_generation g
        join dim_fuel f    using (fuel_key)
        join dim_country c using (country_key)
        group by 1 order by 2 desc
    """).df()

    peak_by_country = con.execute("""
        select c.country_name, max(l.load_mw) as peak_mw
        from fact_load l join dim_country c using (country_key)
        group by 1 order by 2 desc
    """).df()

    fuel_mix = con.execute("""
        select c.country_name, g.production_type,
               sum(g.generation_mw) / 1000.0 as gwh
        from fact_generation g
        join dim_country c using (country_key)
        group by 1, 2
    """).df()

    daily = con.execute("""
        with l as (select date, sum(load_mw)/1000.0 as load_gwh
                   from fact_load f join dim_date d using (date_key) group by 1),
             g as (select date, sum(generation_mw)/1000.0 as gen_gwh
                   from fact_generation f join dim_date d using (date_key) group by 1)
        select l.date, l.load_gwh, g.gen_gwh
        from l join g using (date) order by l.date
    """).df()

    diurnal = con.execute("""
        select d.hour, avg(f.load_mw)/1000.0 as avg_load_gw
        from fact_load f join dim_date d using (date_key)
        group by 1 order by 1
    """).df()

    # shape fuel mix into stacked-bar structure
    countries = sorted(fuel_mix["country_name"].unique().tolist())
    fuels = sorted(fuel_mix["production_type"].unique().tolist())
    mix_pivot = {fuel: [0.0] * len(countries) for fuel in fuels}
    for _, r in fuel_mix.iterrows():
        mix_pivot[r["production_type"]][countries.index(r["country_name"])] = round(float(r["gwh"]), 1)

    return {
        "kpi": {
            "n_countries": int(kpi["n_countries"]),
            "n_hours": int(kpi["n_hours"]),
            "peak_load_gw": round(float(kpi["peak_load_mw"]) / 1000, 2),
            "avg_load_gw": round(float(kpi["avg_load_mw"]) / 1000, 2),
            "renewable_share": round(float(renewable_share), 1),
            "ts_min": str(kpi["ts_min"])[:16],
            "ts_max": str(kpi["ts_max"])[:16],
        },
        "ren_by_country": {
            "labels": ren_by_country["country_name"].tolist(),
            "values": [round(v, 1) for v in ren_by_country["pct"].tolist()],
        },
        "peak_by_country": {
            "labels": peak_by_country["country_name"].tolist(),
            "values": [round(v / 1000, 2) for v in peak_by_country["peak_mw"].tolist()],
        },
        "fuel_mix": {"countries": countries, "fuels": fuels, "series": mix_pivot},
        "daily": {
            "labels": [str(d)[:10] for d in daily["date"].tolist()],
            "load": [round(v, 1) for v in daily["load_gwh"].tolist()],
            "gen": [round(v, 1) for v in daily["gen_gwh"].tolist()],
        },
        "diurnal": {
            "labels": [int(h) for h in diurnal["hour"].tolist()],
            "values": [round(v, 2) for v in diurnal["avg_load_gw"].tolist()],
        },
    }


def build() -> Path:
    con = get_connection()
    try:
        data = _metrics(con)
    finally:
        con.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(_render(data), encoding="utf-8")
    return OUT


def _render(d: dict) -> str:
    payload = json.dumps(d)
    synth_note = ""  # mode note is added by the runner context; kept generic here
    return _TEMPLATE.replace("/*DATA*/", payload).replace("<!--NOTE-->", synth_note)


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EU Grid Pulse</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root{
    --bg:#0f1419; --panel:#1a212b; --panel2:#222b38; --text:#e6edf3; --muted:#8b98a9;
    --line:#2b3545; --accent:#36c58f; --accent2:#f2c811; --grid:#273041;
    --c0:#36c58f; --c1:#4aa3ff; --c2:#f2c811; --c3:#ff7a59; --c4:#b48cff;
    --c5:#2dd4bf; --c6:#f87171; --c7:#9ca3af; --c8:#60a5fa; --c9:#fbbf24;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
       font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
  .wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
  header h1{margin:0 0 4px;font-size:26px;letter-spacing:-.4px}
  header h1 span{color:var(--accent)}
  .sub{color:var(--muted);font-size:13px;margin-bottom:22px}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:22px}
  .kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
  .kpi .v{font-size:26px;font-weight:700}
  .kpi .v.ac{color:var(--accent)}
  .kpi .l{color:var(--muted);font-size:12px;margin-top:4px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
  .card.full{grid-column:1 / -1}
  .card h3{margin:0 0 12px;font-size:14px;font-weight:600;color:var(--text)}
  canvas{max-height:300px}
  footer{color:var(--muted);font-size:12px;margin-top:26px;text-align:center}
  @media(max-width:760px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>⚡ EU Grid <span>Pulse</span></h1>
    <div class="sub" id="sub"></div>
  </header>
  <div class="kpis" id="kpis"></div>
  <div class="grid">
    <div class="card"><h3>Renewable share by country (%)</h3><canvas id="ren"></canvas></div>
    <div class="card"><h3>Peak load by country (GW)</h3><canvas id="peak"></canvas></div>
    <div class="card full"><h3>Fuel mix by country (GWh)</h3><canvas id="mix"></canvas></div>
    <div class="card full"><h3>Daily demand vs generation (GWh)</h3><canvas id="daily"></canvas></div>
    <div class="card full"><h3>Average demand by hour of day (GW, UTC)</h3><canvas id="diurnal"></canvas></div>
  </div>
  <footer>EU Grid Pulse · ENTSO-E medallion pipeline · DuckDB + dbt · dashboard generated from marts<!--NOTE--></footer>
</div>
<script>
const D = /*DATA*/;
const PAL = ['#36c58f','#4aa3ff','#f2c811','#ff7a59','#b48cff','#2dd4bf','#f87171','#9ca3af','#60a5fa','#fbbf24'];
Chart.defaults.color = '#8b98a9';
Chart.defaults.borderColor = '#273041';
Chart.defaults.font.family = 'Segoe UI, system-ui, sans-serif';

document.getElementById('sub').textContent =
  `${D.kpi.n_countries} countries · ${D.kpi.n_hours} hours · ${D.kpi.ts_min} → ${D.kpi.ts_max} UTC`;

const kpis = [
  ['renewable share','v ac', D.kpi.renewable_share + '%'],
  ['peak load','v', D.kpi.peak_load_gw + ' GW'],
  ['average demand','v', D.kpi.avg_load_gw + ' GW'],
  ['countries','v', D.kpi.n_countries],
  ['hours modelled','v', D.kpi.n_hours],
];
document.getElementById('kpis').innerHTML = kpis.map(k =>
  `<div class="kpi"><div class="${k[1]}">${k[2]}</div><div class="l">${k[0]}</div></div>`).join('');

new Chart(ren, {type:'bar', data:{labels:D.ren_by_country.labels,
  datasets:[{data:D.ren_by_country.values, backgroundColor:'#36c58f'}]},
  options:{plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true,max:100}}}});

new Chart(peak, {type:'bar', data:{labels:D.peak_by_country.labels,
  datasets:[{data:D.peak_by_country.values, backgroundColor:'#4aa3ff'}]},
  options:{indexAxis:'y', plugins:{legend:{display:false}}}});

new Chart(mix, {type:'bar', data:{labels:D.fuel_mix.countries,
  datasets:D.fuel_mix.fuels.map((f,i)=>({label:f, data:D.fuel_mix.series[f],
    backgroundColor:PAL[i%PAL.length]}))},
  options:{plugins:{legend:{position:'bottom'}}, responsive:true,
    scales:{x:{stacked:true}, y:{stacked:true}}}});

new Chart(daily, {type:'line', data:{labels:D.daily.labels,
  datasets:[{label:'Demand', data:D.daily.load, borderColor:'#f2c811', tension:.3, pointRadius:0},
            {label:'Generation', data:D.daily.gen, borderColor:'#36c58f', tension:.3, pointRadius:0}]},
  options:{plugins:{legend:{position:'bottom'}}}});

new Chart(diurnal, {type:'line', data:{labels:D.diurnal.labels,
  datasets:[{label:'avg load (GW)', data:D.diurnal.values, borderColor:'#4aa3ff',
    backgroundColor:'rgba(74,163,255,.15)', fill:true, tension:.4, pointRadius:0}]},
  options:{plugins:{legend:{display:false}}}});
</script>
</body>
</html>
"""
