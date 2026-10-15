import numpy as np


def summary(r, seed=0, sims=5000):
    r = np.asarray(r, float)
    n = len(r)
    if n == 0:
        return dict(n=0, exp_r=0.0, ci_lo=0.0, ci_hi=0.0, wr=0.0, avg_win=0.0, avg_loss=0.0, pf=0.0, p_le0=1.0)
    w, lo = r[r > 0], r[r <= 0]
    boot = np.random.default_rng(seed).choice(r, size=(sims, n)).mean(axis=1)
    return dict(n=n, exp_r=r.mean(), ci_lo=np.percentile(boot, 2.5), ci_hi=np.percentile(boot, 97.5),
                wr=len(w) / n, avg_win=w.mean() if len(w) else 0.0, avg_loss=-lo.mean() if len(lo) else 0.0,
                pf=w.sum() / -lo.sum() if lo.sum() < 0 else float("inf"), p_le0=float((boot <= 0).mean()))


def max_dd(eq):
    eq = np.asarray(eq, float)
    pk = np.maximum.accumulate(eq)
    return float(((pk - eq) / pk).max()) if len(eq) else 0.0


def cagr(eq, years):
    eq = np.asarray(eq, float)
    return (eq[-1] / eq[0]) ** (1 / years) - 1 if years > 0 and eq[0] > 0 else 0.0


def objective(r, min_trades=15):
    """Criterio de selección en train: estadístico t de la expectativa en R (penaliza muestras chicas)."""
    r = np.asarray(r, float)
    if len(r) < min_trades or r.std(ddof=1) == 0:
        return -np.inf
    return r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
