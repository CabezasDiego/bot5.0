"""Estrategias long-only. Cada una devuelve, por vela CERRADA i:
entry[i], exit[i] (señales que se ejecutan en la apertura de i+1) y stop_dist[i] (distancia del stop en precio).
Sólo usan información hasta el cierre de i: sin look-ahead."""
import itertools
import numpy as np
from .indicators import ema, atr, rsi


def _out(entry, exit_, stop):
    ok = ~np.isnan(stop)
    return entry.fillna(False).to_numpy(bool) & ok, exit_.fillna(False).to_numpy(bool), stop.to_numpy(float)


def donchian(df, n_entry=55, n_exit=20, atr_k=3.0, trend=200):
    c = df["close"]
    hi = df["high"].rolling(n_entry).max().shift(1)
    lo = df["low"].rolling(n_exit).min().shift(1)
    entry = (c > hi) & (c > ema(c, trend))
    return _out(entry, c < lo, atr_k * atr(df))


def ema_cross(df, fast=20, slow=100, atr_k=3.0):
    c = df["close"]
    f, s = ema(c, fast), ema(c, slow)
    up = (f > s) & (f.shift(1) <= s.shift(1))
    dn = f < s
    return _out(up, dn, atr_k * atr(df))


def rsi_pullback(df, n=14, low=30, exit_level=55, atr_k=2.0, trend=200):
    c = df["close"]
    r = rsi(c, n)
    entry = (r < low) & (c > ema(c, trend))
    return _out(entry, r > exit_level, atr_k * atr(df))


STRATEGIES = {"donchian": donchian, "ema_cross": ema_cross, "rsi_pullback": rsi_pullback}

GRIDS = {
    "donchian": dict(n_entry=[20, 55, 100], n_exit=[10, 20, 40], atr_k=[2.0, 3.0, 4.0]),
    "ema_cross": dict(fast=[10, 20, 50], slow=[100, 200], atr_k=[2.0, 3.0, 4.0]),
    "rsi_pullback": dict(n=[7, 14], low=[25, 30, 35], exit_level=[50, 60], atr_k=[1.5, 2.5]),
}


def grid(name):
    g = GRIDS[name]
    return [dict(zip(g, v)) for v in itertools.product(*g.values())]
