import json
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

START = "2016-01-01"
OUTPUT_FILE = "divergence.html"

TICKERS = {
    "BTC": "BTC-USD",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "NASDAQ": "^IXIC",
    "S&P500": "^GSPC",
    "KOSPI": "^KS11",
}


def load_prices():
    raw = yf.download(
        list(TICKERS.values()),
        start=START,
        auto_adjust=True,
        progress=False,
    )
    close = raw["Close"]
    close = close.rename(columns={v: k for k, v in TICKERS.items()})

    missing = [k for k in TICKERS if k not in close.columns or close[k].dropna().empty]
    if missing:
        print("Download failed for:", missing)
        sys.exit(1)

    close = close[list(TICKERS.keys())]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close = close.sort_index().ffill()

    # Align everything to weekdays so that N rows is about N trading days
    weekdays = pd.bdate_range(close.index.min(), close.index.max())
    close = close.reindex(weekdays).ffill().dropna(how="any")
    return close


def main():
    close = load_prices()
    if len(close) < 300:
        print("Too little data:", len(close))
        sys.exit(1)

    payload = {"dates": [d.strftime("%Y-%m-%d") for d in close.index]}
    for name in TICKERS:
        payload[name] = [round(float(v), 4) for v in close[name].tolist()]

    html = TEMPLATE.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
    html = html.replace("__UPDATED__", close.index[-1].strftime("%Y-%m-%d"))
    Path(OUTPUT_FILE).write_text(html, encoding="utf-8")
    print("Wrote", OUTPUT_FILE, "rows:", len(close), "last:", close.index[-1].date())


TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BTC Divergence Strategy</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body{margin:0;background:#0f1218;color:#d7dce5;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif}
  .wrap{max-width:1400px;margin:0 auto;padding:12px}
  h1{font-size:18px;margin:4px 0 10px}
  .row{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin-bottom:10px}
  .box{background:#171c26;border:1px solid #262d3b;border-radius:8px;padding:8px 10px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .box label{font-size:13px;color:#9aa4b5}
  input[type=number]{width:70px;background:#0f1218;color:#d7dce5;border:1px solid #333c4e;border-radius:4px;padding:4px}
  input[type=range]{width:140px}
  button{background:#0f1218;color:#d7dce5;border:1px solid #333c4e;border-radius:4px;padding:5px 10px;cursor:pointer;font-size:13px}
  button.on{background:#2c5fd8;border-color:#2c5fd8;color:#fff}
  #summary{font-size:13px;color:#9aa4b5;margin:6px 0 8px;line-height:1.6}
  #chart{width:100%;height:820px}
  .note{font-size:12px;color:#7d8798;margin-top:8px}
</style>
</head>
<body>
<div class="wrap">
  <h1>BTC vs Assets - Return Divergence (data until __UPDATED__)</h1>

  <div class="row">
    <div class="box">
      <label>Rolling days N</label>
      <input type="number" id="n" min="20" max="756" step="1" value="252">
      <input type="range" id="nr" min="20" max="756" step="1" value="252">
    </div>
    <div class="box">
      <label>Upper Z</label>
      <input type="number" id="up" min="0.5" max="4" step="0.1" value="2.0">
      <input type="range" id="upr" min="0.5" max="4" step="0.1" value="2.0">
    </div>
    <div class="box">
      <label>Lower Z</label>
      <input type="number" id="lo" min="-4" max="-0.5" step="0.1" value="-1.5">
      <input type="range" id="lor" min="-4" max="-0.5" step="0.1" value="-1.5">
    </div>
  </div>

  <div class="row">
    <div class="box" id="assetBox"><label>Asset</label></div>
    <div class="box" id="scaleBox"><label>BTC scale</label></div>
    <div class="box" id="metricBox"><label>Bottom panel</label></div>
  </div>

  <div id="summary"></div>
  <div id="chart"></div>
  <div class="note">
    BUY = asset buy / BTC sell (BTC looks overheated, Z at or above upper). SELL = asset sell / BTC buy (BTC looks cheap, Z at or below lower).
    Mean and std of the spread use only data up to each day. Weekdays only; holidays filled with previous value.
    This is an experiment, not investment advice.
  </div>
</div>

<script>
const D = __DATA__;
const ASSETS = ["GOLD","SILVER","NASDAQ","S&P500","KOSPI"];
const COLORS = {"GOLD":"#f5c542","SILVER":"#b0b8c4","NASDAQ":"#4da3ff","S&P500":"#ff8c42","KOSPI":"#c77dff"};
const MIN_OBS = 60;
const ZWIN = 504;
const st = {asset:"ALL", scale:"log", metric:"z"};

function calc(name, N, up, lo){
  const n = D.dates.length, b = D.BTC, a = D[name];
  const spread = new Array(n).fill(null);
  const mean = new Array(n).fill(null);
  const std = new Array(n).fill(null);
  const z = new Array(n).fill(null);
  const sigs = [];
  let sum = 0, sq = 0, last = 0;
  for(let i = N; i < n; i++){
    const s = ((b[i]/b[i-N] - 1) - (a[i]/a[i-N] - 1)) * 100;
    spread[i] = s; sum += s; sq += s*s;
    const k = i - N + 1;
    if(k > ZWIN){ const o = spread[i - ZWIN]; sum -= o; sq -= o*o; }
    const cnt = Math.min(k, ZWIN);
    if(cnt >= MIN_OBS){
      const m = sum/cnt;
      const sd = Math.sqrt(Math.max(sq/cnt - m*m, 0));
      mean[i] = m; std[i] = sd;
      if(sd > 0){
        const zz = (s - m)/sd;
        z[i] = zz;
        if(zz >= up && last !== 1){ sigs.push({i:i, type:"BUY", z:zz}); last = 1; }
        else if(zz <= lo && last !== -1){ sigs.push({i:i, type:"SELL", z:zz}); last = -1; }
      }
    }
  }
  return {spread, mean, std, z, sigs};
}

function readNum(id, fallback){
  const v = parseFloat(document.getElementById(id).value);
  return isNaN(v) ? fallback : v;
}

function render(){
  let N = Math.round(readNum("n", 252));
  N = Math.min(756, Math.max(20, N));
  const up = readNum("up", 2.0);
  const lo = readNum("lo", -1.5);
  const show = st.asset === "ALL" ? ASSETS : [st.asset];

  const traces = [];
  traces.push({
    x: D.dates, y: D.BTC, type: "scatter", mode: "lines", name: "BTC",
    line: {color:"#f7931a", width:1.5}, xaxis: "x", yaxis: "y"
  });

  const summary = [];
  show.forEach(function(name){
    const r = calc(name, N, up, lo);
    const col = COLORS[name];

    if(r.sigs.length){
      traces.push({
        x: r.sigs.map(function(s){return D.dates[s.i];}),
        y: r.sigs.map(function(s){return D.BTC[s.i];}),
        type: "scatter", mode: "markers+text",
        name: name + " signals",
        text: r.sigs.map(function(s){return name + " " + s.type;}),
        textposition: r.sigs.map(function(s){return s.type === "BUY" ? "top center" : "bottom center";}),
        textfont: {size: 10, color: col},
        marker: {
          size: 11,
          symbol: r.sigs.map(function(s){return s.type === "BUY" ? "triangle-down" : "triangle-up";}),
          color: r.sigs.map(function(s){return s.type === "BUY" ? "#ff4d4f" : "#2ecc71";}),
          line: {color: col, width: 1.5}
        },
        hovertext: r.sigs.map(function(s){
          return D.dates[s.i] + "<br>" + name + " " + s.type + " / BTC " + (s.type === "BUY" ? "SELL" : "BUY") + "<br>Z=" + s.z.toFixed(2);
        }),
        hoverinfo: "text", xaxis: "x", yaxis: "y"
      });
      const l = r.sigs[r.sigs.length - 1];
      summary.push(name + " " + l.type + " (" + D.dates[l.i] + ")");
    } else {
      summary.push(name + ": none");
    }

    const series = st.metric === "z" ? r.z : r.spread;
    traces.push({
      x: D.dates, y: series, type: "scatter", mode: "lines", name: name,
      line: {color: col, width: 1.2}, xaxis: "x2", yaxis: "y2", connectgaps: false
    });

    if(st.metric === "s" && show.length === 1){
      traces.push({
        x: D.dates, y: r.mean.map(function(m, i){return m === null ? null : m + up * r.std[i];}),
        type: "scatter", mode: "lines", name: "mean + upper*std",
        line: {color:"#ff4d4f", width:1, dash:"dash"}, xaxis: "x2", yaxis: "y2"
      });
      traces.push({
        x: D.dates, y: r.mean.map(function(m, i){return m === null ? null : m + lo * r.std[i];}),
        type: "scatter", mode: "lines", name: "mean + lower*std",
        line: {color:"#2ecc71", width:1, dash:"dash"}, xaxis: "x2", yaxis: "y2"
      });
    }
  });

  const shapes = [];
  if(st.metric === "z"){
    shapes.push({type:"line", xref:"paper", x0:0, x1:1, yref:"y2", y0:up, y1:up, line:{color:"#ff4d4f", width:1, dash:"dash"}});
    shapes.push({type:"line", xref:"paper", x0:0, x1:1, yref:"y2", y0:lo, y1:lo, line:{color:"#2ecc71", width:1, dash:"dash"}});
    shapes.push({type:"line", xref:"paper", x0:0, x1:1, yref:"y2", y0:0, y1:0, line:{color:"#555", width:1}});
  }

  const layout = {
    paper_bgcolor: "#0f1218", plot_bgcolor: "#0f1218",
    font: {color: "#d7dce5", size: 12},
    margin: {l: 60, r: 20, t: 10, b: 40},
    legend: {orientation: "h", y: 1.06},
    hovermode: "x unified",
    uirevision: "keep",
    xaxis: {anchor: "y", gridcolor: "#1d2330", rangeslider: {visible: false}},
    xaxis2: {anchor: "y2", matches: "x", gridcolor: "#1d2330"},
    yaxis: {domain: [0.38, 1], type: st.scale, title: "BTC (USD)", gridcolor: "#1d2330"},
    yaxis2: {domain: [0, 0.32], title: st.metric === "z" ? "Z-Score" : "Spread (%)", gridcolor: "#1d2330", zeroline: false},
    shapes: shapes
  };

  document.getElementById("summary").textContent = "Last signals: " + summary.join("  |  ");
  Plotly.react("chart", traces, layout, {responsive: true});
}

function bindPair(numId, rangeId){
  const num = document.getElementById(numId);
  const rng = document.getElementById(rangeId);
  rng.addEventListener("input", function(){ num.value = rng.value; render(); });
  num.addEventListener("input", function(){
    const v = parseFloat(num.value);
    if(!isNaN(v)){ rng.value = v; render(); }
  });
}

function makeButtons(boxId, items, key){
  const box = document.getElementById(boxId);
  items.forEach(function(it){
    const b = document.createElement("button");
    b.textContent = it.label;
    b.dataset.v = it.value;
    if(st[key] === it.value) b.className = "on";
    b.addEventListener("click", function(){
      st[key] = it.value;
      box.querySelectorAll("button").forEach(function(x){ x.className = (x.dataset.v === it.value) ? "on" : ""; });
      render();
    });
    box.appendChild(b);
  });
}

bindPair("n", "nr");
bindPair("up", "upr");
bindPair("lo", "lor");
makeButtons("assetBox", [{label:"ALL", value:"ALL"}].concat(ASSETS.map(function(a){return {label:a, value:a};})), "asset");
makeButtons("scaleBox", [{label:"Log", value:"log"}, {label:"Linear", value:"linear"}], "scale");
makeButtons("metricBox", [{label:"Z-Score", value:"z"}, {label:"Spread %", value:"s"}], "metric");
render();
</script>
</body>
</html>
'''

if __name__ == "__main__":
    main()
