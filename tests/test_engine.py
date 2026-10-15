import numpy as np
import pandas as pd
from bot.engine import Config, State, Engine
from bot.backtest import run
from bot.strategies import STRATEGIES, grid


def bars(closes):
    c = np.array(closes, float)
    o = np.r_[c[0], c[:-1]]
    t = pd.date_range("2024-01-01", periods=len(c), freq="4h", tz="UTC")
    return pd.DataFrame(dict(open_time=t, open=o, high=np.maximum(o, c) + 1, low=np.minimum(o, c) - 1, close=c, volume=1.0))


def test_entra_en_la_apertura_siguiente_y_respeta_riesgo():
    df = bars([100] * 5 + [110] * 5)
    entry = np.zeros(10, bool); entry[2] = True
    sig = (entry, np.zeros(10, bool), np.full(10, 5.0))
    cfg = Config(fee=0, slip=0, trailing=False)
    tr, eq = run(df, sig, cfg, capital=10_000)
    assert tr.iloc[0]["entry_time"] == str(df["open_time"][3])   # señal en 2 -> ejecuta en 3
    assert abs(tr.iloc[0]["entry"] - df["open"][3]) < 1e-9
    risk = tr.iloc[0]["qty"] * 5.0
    assert abs(risk - 100.0) < 1e-6  # 1% de 10.000


def test_stop_con_gap_ejecuta_en_la_apertura():
    df = bars([100, 100, 100, 100, 80, 80])
    df.loc[4, "open"] = 85
    entry = np.zeros(6, bool); entry[1] = True
    tr, _ = run(df, (entry, np.zeros(6, bool), np.full(6, 5.0)), Config(fee=0, slip=0, trailing=False))
    assert tr.iloc[0]["reason"] == "stop" and abs(tr.iloc[0]["exit"] - 85) < 1e-9
    assert tr.iloc[0]["r"] < -1  # el gap hace perder más de 1R


def test_costos_reducen_resultado():
    df = bars(list(np.linspace(100, 200, 60)))
    entry = np.zeros(60, bool); entry[5] = True
    sig = (entry, np.zeros(60, bool), np.full(60, 10.0))
    a, _ = run(df, sig, Config(fee=0, slip=0))
    b, _ = run(df, sig, Config())
    assert b["pnl"].sum() < a["pnl"].sum()


def test_kill_switch_detiene_el_bot():
    df = bars([100] * 3 + list(np.linspace(100, 50, 30)))
    entry = np.ones(len(df), bool)
    st = State(cash=10_000, peak=10_000)
    eng = Engine(Config(risk=1.0, max_dd=0.2, trailing=False), st)
    for i in range(len(df)):
        r = df.iloc[i]
        eng.step(str(r.open_time), r.open, r.high, r.low, r.close, True, False, 60.0)
    assert st.halted and st.qty == 0


def test_sin_look_ahead():
    rng = np.random.default_rng(0)
    df = bars(list(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 600)))))
    for name in STRATEGIES:
        p = grid(name)[0]
        full = STRATEGIES[name](df, **p)
        cut = STRATEGIES[name](df.iloc[:400].reset_index(drop=True), **p)
        for a, b in zip(full, cut):
            assert np.array_equal(np.nan_to_num(a[:400]), np.nan_to_num(b))
