"""Descarga de velas BTC/USDT. Fuente principal: Binance (data.binance.vision + data-api.binance.vision,
endpoints públicos sin clave). Respaldo: Coinbase Exchange (BTC-USD 1h re-muestreado)."""
import io, json, os, time, urllib.request, zipfile
from datetime import datetime, timezone
import pandas as pd

UA = {"User-Agent": "bot5.0-research"}
COLS = ["open_time", "open", "high", "low", "close", "volume"]
INTERVAL_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _to_ms(ts):
    ts = int(ts)
    return ts // 1000 if ts > 10**14 else ts  # Binance spot usa microsegundos desde 2025


def _frame(rows):
    df = pd.DataFrame(rows, columns=COLS)
    df["open_time"] = pd.to_datetime(df["open_time"].map(_to_ms), unit="ms", utc=True)
    for c in COLS[1:]:
        df[c] = df[c].astype(float)
    return df.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)


def binance_monthly(symbol, interval, start="2018-01"):
    rows, y, m = [], *map(int, start.split("-"))
    now = datetime.now(timezone.utc)
    while (y, m) < (now.year, now.month):
        url = f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{y}-{m:02d}.zip"
        try:
            z = zipfile.ZipFile(io.BytesIO(_get(url)))
            for line in z.read(z.namelist()[0]).decode().splitlines():
                p = line.split(",")
                if p[0].isdigit():
                    rows.append(p[:6])
        except Exception as e:
            print(f"  aviso: {y}-{m:02d} no disponible ({e})")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return rows


def binance_recent(symbol, interval, start_ms):
    rows = []
    while True:
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&startTime={start_ms}&limit=1000"
        batch = json.loads(_get(url))
        if not batch:
            break
        rows += [b[:6] for b in batch]
        start_ms = int(batch[-1][0]) + INTERVAL_MS[interval]
        if len(batch) < 1000:
            break
    return rows


def coinbase(interval, start_ms):
    """Respaldo: BTC-USD 1h de Coinbase, re-muestreado al intervalo pedido."""
    rows, step = [], 300 * 3600
    t, end = start_ms // 1000, int(time.time())
    while t < end:
        a, b = datetime.fromtimestamp(t, timezone.utc).isoformat(), datetime.fromtimestamp(min(t + step, end), timezone.utc).isoformat()
        url = f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600&start={a}&end={b}"
        for ts, lo, hi, op, cl, vol in json.loads(_get(url)):
            rows.append([ts * 1000, op, hi, lo, cl, vol])
        t += step
        time.sleep(0.15)
    df = _frame(rows).set_index("open_time")
    rule = {"1h": "1h", "4h": "4h", "1d": "1D"}[interval]
    out = df.resample(rule, origin="epoch").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    return out.reset_index()


def drop_open_bar(df, interval):
    """Quita la vela en curso: sólo se opera sobre velas cerradas."""
    now = pd.Timestamp.now(tz="UTC")
    return df[df["open_time"] + pd.Timedelta(milliseconds=INTERVAL_MS[interval]) <= now].reset_index(drop=True)


def load_history(symbol="BTCUSDT", interval="4h", start="2018-01", cache="data"):
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, f"{symbol}_{interval}.csv")
    if os.path.exists(path):
        df = pd.read_csv(path, parse_dates=["open_time"])
    else:
        try:
            df = _frame(binance_monthly(symbol, interval, start))
            print(f"Datos: Binance {symbol} {interval}")
            last = int(df["open_time"].iloc[-1].timestamp() * 1000) + INTERVAL_MS[interval]
            reciente = _frame(binance_recent(symbol, interval, last))
            df = pd.concat([df, reciente]).drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)
        except Exception as e:
            print(f"Binance no disponible ({e}); uso Coinbase BTC-USD como respaldo")
            df = coinbase(interval, int(pd.Timestamp(start + "-01", tz="UTC").timestamp() * 1000))
        df.to_csv(path, index=False)
    return drop_open_bar(df, interval)


def load_recent(symbol="BTCUSDT", interval="4h", bars=600):
    start_ms = int(time.time() * 1000) - bars * INTERVAL_MS[interval]
    try:
        df = _frame(binance_recent(symbol, interval, start_ms))
    except Exception as e:
        print(f"Binance no disponible ({e}); uso Coinbase como respaldo")
        df = coinbase(interval, start_ms)
    return drop_open_bar(df, interval)
