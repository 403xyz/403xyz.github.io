import json
import pandas as pd
import yfinance as yf

q = yf.download("QQQ", period="max", auto_adjust=True, progress=False)
v = yf.download("^VIX", period="max", progress=False)["Close"].squeeze()

q.columns = [c[0] if isinstance(c, tuple) else c for c in q.columns]
df = q[["Open", "High", "Low", "Close"]].copy()
df["vix"] = v
df = df.dropna().round(2)

rows = [
    {
        "time": idx.strftime("%Y-%m-%d"),
        "open": float(r["Open"]),
        "high": float(r["High"]),
        "low": float(r["Low"]),
        "close": float(r["Close"]),
        "vix": float(r["vix"]),
    }
    for idx, r in df.iterrows()
]

with open("data.json", "w") as f:
    json.dump(rows, f)

print(f"saved {len(rows)} rows, last = {rows[-1]}")
