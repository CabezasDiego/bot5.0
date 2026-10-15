"""Investigación con walk-forward + holdout.

1. Datos BTC/USDT 4h desde 2018.
2. Se reservan los últimos HOLDOUT_MESES sin tocar.
3. Walk-forward sobre el resto: optimiza en TRAIN_MESES, evalúa en los TEST_MESES siguientes, avanza.
4. La familia con mejor resultado fuera de muestra se re-optimiza con todo el período previo
   al holdout y se evalúa UNA vez en el holdout.
5. Veredicto con reglas fijadas de antemano. Si pasa, escribe config/strategy.json con approved=true.

Uso: python research.py [--synthetic]   (--synthetic: datos simulados para probar el pipeline sin red)
"""
import argparse, json, os, sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from bot.data import load_history
from bot.backtest import signals, run
from bot.engine import Config
from bot.strategies import STRATEGIES, grid
from bot import stats

TRAIN_MESES, TEST_MESES, HOLDOUT_MESES = 24, 6, 12
MIN_TRADES_OOS, MIN_TRADES_HOLDOUT = 100, 10
CAPITAL = 10_000.0


def synthetic(n=20000, seed=3):
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0002, 0.012, n)
    c = 10000 * np.exp(np.cumsum(ret))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.004, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.004, n)))
    t = pd.date_range("2018-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame(dict(open_time=t, open=o, high=h, low=l, close=c, volume=1.0))


def idx(df, ts):
    return int(df["open_time"].searchsorted(ts))


def best_params(df, name, a, b, cache):
    best, best_obj = None, -np.inf
    for p in grid(name):
        key = (name, tuple(p.items()))
        if key not in cache:
            cache[key] = signals(df, name, p)
        tr, _ = run(df, cache[key], start=a, end=b, capital=CAPITAL)
        ob = stats.objective(tr["r"])
        if ob > best_obj:
            best, best_obj = p, ob
    return best, best_obj


def walk_forward(df, name, holdout_start, cache):
    t0 = df["open_time"].iloc[0] + pd.DateOffset(months=2)  # margen para indicadores largos
    folds, rs = [], []
    tr_start = t0
    while True:
        te_start = tr_start + pd.DateOffset(months=TRAIN_MESES)
        te_end = min(te_start + pd.DateOffset(months=TEST_MESES), holdout_start)
        if te_start >= holdout_start:
            break
        a, b, e = idx(df, tr_start), idx(df, te_start), idx(df, te_end)
        p, ob = best_params(df, name, a, b, cache)
        if p is not None:
            tr, _ = run(df, cache[(name, tuple(p.items()))], start=b, end=e, capital=CAPITAL)
            rs += list(tr["r"])
            folds.append(dict(test=f"{te_start:%Y-%m}..{te_end:%Y-%m}", params=p, trades=len(tr), exp_r=float(tr["r"].mean()) if len(tr) else 0.0))
        else:
            folds.append(dict(test=f"{te_start:%Y-%m}..{te_end:%Y-%m}", params=None, trades=0, exp_r=0.0))
        tr_start += pd.DateOffset(months=TEST_MESES)
    return folds, np.array(rs)


def equity_from_r(r, risk=0.01):
    return CAPITAL * np.cumprod(np.r_[1.0, 1 + risk * np.asarray(r)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    args = ap.parse_args()
    df = synthetic() if args.synthetic else load_history()
    fuente = "SINTÉTICOS (prueba del pipeline)" if args.synthetic else "BTCUSDT 4h"
    holdout_start = df["open_time"].iloc[-1] - pd.DateOffset(months=HOLDOUT_MESES)
    hs = idx(df, holdout_start)
    cache, res = {}, {}
    n_configs = sum(len(grid(n)) for n in STRATEGIES)
    for name in STRATEGIES:
        folds, rs = walk_forward(df, name, holdout_start, cache)
        res[name] = dict(folds=folds, oos=stats.summary(rs), r=rs)
        s = res[name]["oos"]
        print(f"{name:14s} OOS n={s['n']:4d} exp={s['exp_r']:+.3f}R IC95=[{s['ci_lo']:+.3f},{s['ci_hi']:+.3f}] PF={s['pf']:.2f}")

    ganador = max(res, key=lambda k: res[k]["oos"]["ci_lo"])
    p_final, _ = best_params(df, ganador, idx(df, df["open_time"].iloc[0] + pd.DateOffset(months=2)), hs, cache)
    sig = cache[(ganador, tuple(p_final.items()))]
    tr_h, eq_h = run(df, sig, start=hs, capital=CAPITAL)
    h = stats.summary(tr_h["r"])
    years_h = (df["open_time"].iloc[-1] - df["open_time"].iloc[hs]).days / 365.25
    bh = df["close"].iloc[hs:].to_numpy()
    oos = res[ganador]["oos"]
    eq_oos = equity_from_r(res[ganador]["r"])

    reglas = {
        f"OOS: al menos {MIN_TRADES_OOS} trades": oos["n"] >= MIN_TRADES_OOS,
        "OOS: límite inferior del IC 95% de la expectativa > 0": oos["ci_lo"] > 0,
        "OOS: expectativa > 0 aun con 0,10R extra de costos": oos["exp_r"] - 0.10 > 0,
        f"Holdout: al menos {MIN_TRADES_HOLDOUT} trades": h["n"] >= MIN_TRADES_HOLDOUT,
        "Holdout: expectativa > 0": h["exp_r"] > 0,
        "Holdout: drawdown < 20%": stats.max_dd(eq_h) < 0.20,
    }
    aprobado = all(reglas.values()) and not args.synthetic

    hoy = datetime.now(timezone.utc)
    L = [f"# Investigación {fuente}: {hoy:%Y-%m-%d %H:%M} UTC", "",
         f"Datos: {df['open_time'].iloc[0]:%Y-%m-%d} a {df['open_time'].iloc[-1]:%Y-%m-%d} ({len(df)} velas). "
         f"Holdout intocado desde {df['open_time'].iloc[hs]:%Y-%m-%d}. Walk-forward {TRAIN_MESES}m train / {TEST_MESES}m test. "
         f"Costos: 0,10% comisión + 0,05% slippage por lado. Riesgo 1% por trade. Configuraciones probadas: {n_configs}.", "",
         "## Fuera de muestra (walk-forward)", "",
         "| Estrategia | Trades | Win rate | Gan. media | Pérd. media | Expectativa | IC 95% | PF | P(edge ≤ 0) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k, v in res.items():
        s = v["oos"]
        L.append(f"| {k} | {s['n']} | {s['wr']:.1%} | {s['avg_win']:.2f}R | {s['avg_loss']:.2f}R | {s['exp_r']:+.3f}R | "
                 f"[{s['ci_lo']:+.3f}, {s['ci_hi']:+.3f}] | {s['pf']:.2f} | {s['p_le0']:.1%} |")
    L += ["", f"Mejor familia fuera de muestra: **{ganador}**. Curva OOS a 1% de riesgo: "
          f"capital x{eq_oos[-1]/eq_oos[0]:.2f}, drawdown máximo {stats.max_dd(eq_oos):.1%}.", "",
          "Parámetros elegidos en cada ventana (estabilidad):", ""]
    for f in res[ganador]["folds"]:
        L.append(f"- {f['test']}: {f['params']} → {f['trades']} trades, {f['exp_r']:+.3f}R")
    L += ["", "## Holdout (evaluado una sola vez)", "",
          f"Parámetros finales: `{p_final}`", "",
          f"- Trades: {h['n']}, win rate {h['wr']:.1%}, expectativa {h['exp_r']:+.3f}R (IC 95% [{h['ci_lo']:+.3f}, {h['ci_hi']:+.3f}])",
          f"- Retorno del bot: {eq_h.iloc[-1]/CAPITAL-1:+.1%} (drawdown máx. {stats.max_dd(eq_h):.1%})",
          f"- Comprar y mantener BTC en el mismo período: {bh[-1]/bh[0]-1:+.1%} (drawdown máx. {stats.max_dd(bh):.1%})",
          f"- Período: {years_h:.2f} años", "",
          "## Veredicto", ""]
    for k, ok in reglas.items():
        L.append(f"- {'✅' if ok else '❌'} {k}")
    L += ["", f"**{'APROBADA para paper trading' if aprobado else 'NO APROBADA: no pasa a paper trading'}**"]
    rep = "\n".join(L)
    print("\n" + rep)
    os.makedirs("reports", exist_ok=True)
    tag = "synthetic" if args.synthetic else hoy.strftime("%Y%m%d")
    open(f"reports/research_{tag}.md", "w").write(rep + "\n")
    if not args.synthetic:
        os.makedirs("config", exist_ok=True)
        json.dump(dict(strategy=ganador, params=p_final, approved=aprobado, generated=hoy.isoformat(),
                       oos_exp_r=oos["exp_r"], oos_ci_lo=oos["ci_lo"], holdout_exp_r=h["exp_r"]),
                  open("config/strategy.json", "w"), indent=2)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(rep + "\n")


if __name__ == "__main__":
    main()
