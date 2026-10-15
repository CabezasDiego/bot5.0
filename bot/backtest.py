import numpy as np
import pandas as pd
from .engine import Config, State, Engine
from .strategies import STRATEGIES


def signals(df, name, params):
    return STRATEGIES[name](df, **params)


def run(df, sig, cfg=None, start=0, end=None, capital=10_000.0):
    """Simula sobre df[start:end] con señales precalculadas sobre todo df (indicadores con historia previa)."""
    cfg = cfg or Config()
    entry, exit_, stop = sig
    eng = Engine(cfg, State(cash=capital, peak=capital))
    end = len(df) if end is None else end
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    t = df["open_time"].astype(str).to_numpy()
    eq = np.empty(end - start)
    for k, i in enumerate(range(start, end)):
        eq[k] = eng.step(t[i], o[i], h[i], l[i], c[i], entry[i], exit_[i], stop[i])
    if eng.s.qty > 0:  # cierre forzado al final de la ventana para medir el trade
        eng._close(t[end - 1], c[end - 1], "fin_ventana")
        eq[-1] = eng.s.cash
    trades = pd.DataFrame(eng.s.trades, columns=["entry_time", "exit_time", "entry", "exit", "qty", "pnl", "r", "reason"])
    return trades, pd.Series(eq, index=df["open_time"].iloc[start:end].to_numpy())
