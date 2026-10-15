"""Motor de simulación compartido por el backtest y el paper trading (mismo código, mismas reglas).
Reglas: señal al cierre de la vela i -> orden en la apertura de i+1. Stop protectivo evaluado intrabar
(si hay gap, se ejecuta en la apertura). Comisión y slippage en cada lado. Spot, sin apalancamiento."""
from dataclasses import dataclass, field, asdict


@dataclass
class Config:
    risk: float = 0.01          # fracción del equity arriesgada por trade (1R)
    fee: float = 0.001          # 0,10% por lado (Binance spot sin descuento)
    slip: float = 0.0005        # 0,05% de slippage por lado
    max_dd: float = 0.20        # kill switch: drawdown del equity que apaga el bot
    trailing: bool = True       # stop dinámico: max(stop, cierre - stop_dist)


@dataclass
class State:
    cash: float
    peak: float
    qty: float = 0.0
    entry: float = 0.0
    stop: float = 0.0
    risk_amt: float = 0.0
    entry_time: str = ""
    pending: str = ""           # "buy" | "sell" | ""
    pending_stop_dist: float = 0.0
    halted: bool = False
    last_bar: str = ""
    trades: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


class Engine:
    def __init__(self, cfg: Config, state: State):
        self.cfg, self.s = cfg, state

    def equity(self, price):
        return self.s.cash + self.s.qty * price

    def _close(self, t, price, reason):
        s, cfg = self.s, self.cfg
        px = price * (1 - cfg.slip)
        s.cash += s.qty * px * (1 - cfg.fee)
        pnl = s.qty * px * (1 - cfg.fee) - s.qty * s.entry * (1 + cfg.fee)
        s.trades.append(dict(entry_time=s.entry_time, exit_time=t, entry=s.entry, exit=px, qty=s.qty,
                             pnl=pnl, r=pnl / s.risk_amt if s.risk_amt else 0.0, reason=reason))
        s.qty = s.entry = s.stop = s.risk_amt = 0.0
        s.entry_time = ""

    def step(self, t, o, h, l, c, entry_sig, exit_sig, stop_dist):
        s, cfg = self.s, self.cfg
        t = str(t)
        # 1) órdenes pendientes en la apertura
        if s.pending == "buy" and s.qty == 0 and not s.halted:
            px = o * (1 + cfg.slip)
            stop = px - s.pending_stop_dist
            if stop > 0:
                eq = s.cash
                qty = min(eq * cfg.risk / (px - stop), eq / (px * (1 + cfg.fee)))
                s.cash -= qty * px * (1 + cfg.fee)
                s.qty, s.entry, s.stop, s.entry_time = qty, px, stop, t
                s.risk_amt = qty * (px - stop)
        elif s.pending == "sell" and s.qty > 0:
            self._close(t, o, "salida")
        s.pending = ""
        # 2) stop intrabar
        if s.qty > 0 and l <= s.stop:
            self._close(t, min(o, s.stop), "stop")
        # 3) trailing stop con info del cierre
        if s.qty > 0 and cfg.trailing and stop_dist == stop_dist:
            s.stop = max(s.stop, c - stop_dist)
        # 4) señales al cierre
        if s.qty > 0 and exit_sig:
            s.pending = "sell"
        elif s.qty == 0 and entry_sig and not s.halted:
            s.pending, s.pending_stop_dist = "buy", stop_dist
        # 5) kill switch por drawdown
        eq = self.equity(c)
        s.peak = max(s.peak, eq)
        if not s.halted and eq <= s.peak * (1 - cfg.max_dd):
            s.halted = True
            s.pending = "sell" if s.qty > 0 else ""
        s.last_bar = t
        return eq
