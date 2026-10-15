"""Paper trading: opera con dinero simulado sobre precios reales, vela por vela, con el MISMO motor del backtest.
Pensado para correr cada 4 h (GitHub Actions o cron). Es idempotente: procesa sólo velas cerradas nuevas.

Uso: python paper.py [--allow-unapproved]
"""
import argparse, json, os, sys
from datetime import datetime, timezone
import pandas as pd
from bot.data import load_recent
from bot.backtest import signals
from bot.engine import Config, State, Engine
from bot import stats

STATE, STATUS, CFG = "state/paper_state.json", "state/STATUS.md", "config/strategy.json"
CAPITAL = 10_000.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-unapproved", action="store_true")
    args = ap.parse_args()
    if not os.path.exists(CFG):
        sys.exit("No hay config/strategy.json: corré research.py primero.")
    cfg_s = json.load(open(CFG))
    if not cfg_s.get("approved") and not args.allow_unapproved:
        print("La estrategia no está aprobada por research.py: el paper trading no se ejecuta.")
        return
    df = load_recent(bars=900)
    sig = signals(df, cfg_s["strategy"], cfg_s["params"])
    st = State(**json.load(open(STATE))) if os.path.exists(STATE) else State(cash=CAPITAL, peak=CAPITAL)
    eng = Engine(Config(), st)
    times = df["open_time"].astype(str).to_numpy()
    nuevas = [i for i in range(len(df)) if times[i] > st.last_bar] if st.last_bar else [len(df) - 1]
    eq = eng.equity(df["close"].iloc[-1])
    for i in nuevas:
        r = df.iloc[i]
        eq = eng.step(times[i], r.open, r.high, r.low, r.close, sig[0][i], sig[1][i], sig[2][i])
    os.makedirs("state", exist_ok=True)
    json.dump(st.to_dict(), open(STATE, "w"), indent=1)
    tr = pd.DataFrame(st.trades)
    s = stats.summary(tr["r"]) if len(tr) else stats.summary([])
    precio = df["close"].iloc[-1]
    pos = (f"Comprado {st.qty:.6f} BTC a {st.entry:,.2f}, stop {st.stop:,.2f}" if st.qty > 0 else "Sin posición")
    lines = [f"# Paper trading: {cfg_s['strategy']} {cfg_s['params']}", "",
             f"Actualizado: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · última vela: {st.last_bar} · BTC {precio:,.2f}", "",
             f"- Capital simulado: **{eq:,.2f}** (inicial {CAPITAL:,.0f}, {eq/CAPITAL-1:+.2%}) · drawdown desde el pico {1-eq/st.peak:.1%}",
             f"- Posición: {pos}" + (f" · orden pendiente: {st.pending}" if st.pending else ""),
             f"- Estado: {'⛔ DETENIDO por kill switch (drawdown ≥ 20%)' if st.halted else '✅ operando'}",
             f"- Trades cerrados: {s['n']} · win rate {s['wr']:.0%} · expectativa {s['exp_r']:+.3f}R "
             f"(esperada según investigación: {cfg_s.get('oos_exp_r', 0):+.3f}R)", ""]
    if s["n"] >= 30 and s["ci_hi"] < cfg_s.get("oos_exp_r", 0):
        lines.append("⚠️ La expectativa en paper está por debajo del rango de la investigación: revisar antes de pasar a dinero real.")
    open(STATUS, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
