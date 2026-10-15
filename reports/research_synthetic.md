# Investigación SINTÉTICOS (prueba del pipeline): 2026-10-14 23:59 UTC

Datos: 2018-01-01 a 2027-02-16 (20000 velas). Holdout intocado desde 2026-02-16. Walk-forward 24m train / 6m test. Costos: 0,10% comisión + 0,05% slippage por lado. Riesgo 1% por trade. Configuraciones probadas: 69.

## Fuera de muestra (walk-forward)

| Estrategia | Trades | Win rate | Gan. media | Pérd. media | Expectativa | IC 95% | PF | P(edge ≤ 0) |
|---|---|---|---|---|---|---|---|---|
| donchian | 164 | 40.2% | 1.16R | 0.75R | +0.017R | [-0.167, +0.208] | 1.04 | 44.1% |
| ema_cross | 98 | 30.6% | 1.76R | 0.63R | +0.104R | [-0.136, +0.372] | 1.24 | 22.1% |
| rsi_pullback | 88 | 48.9% | 0.69R | 0.78R | -0.063R | [-0.234, +0.108] | 0.84 | 76.4% |

Mejor familia fuera de muestra: **ema_cross**. Curva OOS a 1% de riesgo: capital x1.10, drawdown máximo 10.3%.

Parámetros elegidos en cada ventana (estabilidad):

- 2020-03..2020-09: {'fast': 20, 'slow': 100, 'atr_k': 4.0} → 10 trades, +0.516R
- 2020-09..2021-03: {'fast': 20, 'slow': 100, 'atr_k': 3.0} → 6 trades, +1.099R
- 2021-03..2021-09: {'fast': 20, 'slow': 200, 'atr_k': 3.0} → 4 trades, -0.641R
- 2021-09..2022-03: {'fast': 50, 'slow': 200, 'atr_k': 3.0} → 4 trades, -0.826R
- 2022-03..2022-09: {'fast': 10, 'slow': 200, 'atr_k': 3.0} → 10 trades, +0.465R
- 2022-09..2023-03: {'fast': 10, 'slow': 200, 'atr_k': 2.0} → 10 trades, +0.104R
- 2023-03..2023-09: {'fast': 10, 'slow': 100, 'atr_k': 4.0} → 15 trades, +0.231R
- 2023-09..2024-03: {'fast': 10, 'slow': 100, 'atr_k': 4.0} → 14 trades, -0.116R
- 2024-03..2024-09: {'fast': 10, 'slow': 100, 'atr_k': 3.0} → 13 trades, -0.097R
- 2024-09..2025-03: {'fast': 10, 'slow': 200, 'atr_k': 2.0} → 7 trades, -0.834R
- 2025-03..2025-09: {'fast': 20, 'slow': 200, 'atr_k': 2.0} → 4 trades, +1.022R
- 2025-09..2026-02: {'fast': 50, 'slow': 100, 'atr_k': 3.0} → 1 trades, -0.255R

## Holdout (evaluado una sola vez)

Parámetros finales: `{'fast': 20, 'slow': 100, 'atr_k': 3.0}`

- Trades: 13, win rate 15.4%, expectativa -0.312R (IC 95% [-0.707, +0.279])
- Retorno del bot: -4.0% (drawdown máx. 6.2%)
- Comprar y mantener BTC en el mismo período: +157.1% (drawdown máx. 52.3%)
- Período: 1.00 años

## Veredicto

- ❌ OOS: al menos 100 trades
- ❌ OOS: límite inferior del IC 95% de la expectativa > 0
- ✅ OOS: expectativa > 0 aun con 0,10R extra de costos
- ✅ Holdout: al menos 10 trades
- ❌ Holdout: expectativa > 0
- ✅ Holdout: drawdown < 20%

**NO APROBADA: no pasa a paper trading con dinero simulado como candidata validada**
