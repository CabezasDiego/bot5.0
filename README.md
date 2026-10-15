# Bot BTC/USDT

Bot de trading automático para BTC/USDT (velas de 4 h, spot, sin apalancamiento). Pasa por tres etapas, y cada una tiene que aprobarse antes de la siguiente:

| Etapa | Qué hace | Dinero | Cómo se aprueba |
|---|---|---|---|
| 1. Investigación (`research.py`) | Prueba 3 familias de estrategias con walk-forward y un holdout de 12 meses que no se toca | Ninguno | Reglas fijas: ≥100 trades fuera de muestra, IC 95% de la expectativa > 0, sobrevive a costos extra, holdout positivo con drawdown < 20% |
| 2. Paper trading (`paper.py`) | Opera solo cada 4 h con precios reales y dinero simulado, con el mismo motor del backtest | Simulado | ≥ 3 meses y ≥ 30 trades con expectativa dentro del rango de la investigación |
| 3. Dinero real | Igual que el paper, pero enviando órdenes al exchange | Capital chico, 1% de riesgo por trade | Kill switch automático al 20% de drawdown |

La etapa 3 todavía no está implementada a propósito: sólo se construye si la 2 confirma el edge.

## Reglas del motor (`bot/engine.py`)
- Señal al cierre de la vela → ejecución en la apertura siguiente (sin mirar el futuro).
- Comisión de 0,10% + slippage de 0,05% por lado.
- Tamaño de posición: 1% del capital arriesgado entre la entrada y el stop (ATR). Sin apalancamiento.
- Stop intrabar (con gap, se ejecuta en la apertura) y trailing stop.
- Kill switch: si el capital cae 20% desde el máximo, cierra la posición y se detiene.

## Uso
```bash
pip install -r requirements.txt
python -m pytest -q tests          # tests del motor
python research.py --synthetic     # prueba del pipeline con datos simulados (sin red)
python research.py                 # investigación con datos reales de Binance (respaldo: Coinbase)
python paper.py                    # un paso de paper trading (sólo si la estrategia quedó aprobada)
```

En GitHub Actions: `research` corre en cada push y deja el reporte en el resumen del job. `paper-trading` corre cada 4 h y guarda el estado en `state/` (ver `state/STATUS.md`).

No es asesoramiento financiero. Los resultados pasados no garantizan resultados futuros.
