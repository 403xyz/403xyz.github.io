import json
import pandas as pd
import yfinance as yf

qqq = yf.download("QQQ", period="max", auto_adjust=True, progress=False)["Close"].squeeze()
vix = yf.download("^VIX", period="max", progress=False)["Close"].squeeze()

df = pd.concat([qqq.rename("close"), vix.rename("vix")], axis=1).dropna()
df = df.round(2)

rows = [
    {"time": idx.strftime("%Y-%m-%d"), "close": float(r.close), "vix": float(r.vix)}
    for idx, r in df.iterrows()
]

with open("data.json", "w") as f:
    json.dump(rows, f)

print(f"saved {len(rows)} rows, last = {rows[-1]}")
