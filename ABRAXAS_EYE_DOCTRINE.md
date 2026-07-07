# ABRAXAS Eye Doctrine

## Thesis

ABRAXAS no es un dashboard, no es una IA y no es un bot aislado.

ABRAXAS es una terminal de inteligencia operativa para leer mercados, eventos, datos, riesgo y ejecucion desde una sola arquitectura.

## Ley principal

```text
Data first. Intelligence second. Bots third. Execution last.
```

Si los bots nacen antes que los datos persistidos, las features y el backtesting, el sistema se convierte en una interfaz bonita para tomar malas decisiones mas rapido.

## Principio del sistema

```text
El frontend muestra.
El backend calcula.
La base recuerda.
Los algoritmos miden.
Los bots ejecutan solo cuando estan auditados.
La IA acompana.
El humano gobierna.
```

## Orden correcto

1. Ingesta de datos.
2. Persistencia historica.
3. Normalizacion.
4. Feature store.
5. Estadistica.
6. Deteccion de regimenes.
7. Backtesting.
8. Paper trading.
9. Risk engine.
10. Ejecucion real.
11. IA como capa de interpretacion.

## Fase actual

La fase obligatoria ahora es:

```text
ABRAXAS Data Spine v1
```

Objetivo:

Hacer que ABRAXAS recuerde mercado, no solo lo mire.

## Tareas inmediatas

1. Crear y llenar `market_candles`.
2. Crear caching/ingesta de candles.
3. Crear `asset_features`.
4. Crear `statistics_runs`.
5. Mostrar frescura y cantidad de datos en Data API Center.

Estado actual:

- `market_candles` iniciado.
- `asset_features` iniciado.
- `statistics_runs` iniciado.
- `regime_snapshots` iniciado.

## Regla para bots

Los bots no deben leer frases. Deben leer datos estructurados.

Incorrecto:

```text
BTC esta fuerte.
```

Correcto:

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "return_1": 0.42,
  "volatility": 0.31,
  "z_score": 1.4,
  "risk_score": 62,
  "regime_label": "momentum"
}
```

## Advertencia

La vision es grande, pero ABRAXAS muere si se convierte en acumulacion de pantallas.

Cada nueva idea debe fortalecer una de estas columnas:

- Data Spine
- Statistical Intelligence
- Bot Forge
- Risk Engine
- Command Center

Si no fortalece una columna, se congela.
