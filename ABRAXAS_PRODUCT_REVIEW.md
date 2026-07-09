# ABRAXAS Product Review

## Fecha

2026-07-09

## Objetivo

Revisar el estado real del producto antes de seguir agregando funciones.

ABRAXAS debe avanzar como centro operativo, no como acumulacion de pantallas.

## Estado general

El backend ya tiene una columna de datos inicial:

```text
market_candles -> asset_features -> statistics_runs -> regime_snapshots
```

El frontend todavia no muestra todo el universo de producto. Antes de construir Bot Forge real, la navegacion debe exponer claramente:

- Markets
- Trade
- Research
- Data
- Map
- Bots
- Risk

## Modulos existentes

### Markets

Estado: activo.

Incluye:

- market radar
- snapshots
- Fear & Greed
- lecturas ABRAXAS

Riesgo:

- todavia depende de refresh y de fuentes publicas.

### Trade

Estado: activo, incompleto.

Incluye:

- chart con candles
- selector de timeframe
- watchlist basica
- order book visual simulado

Riesgo:

- el order book no es real.
- no debe confundirse con ejecucion.

### Research

Estado: activo.

Incluye:

- Statistical Intelligence
- Monte Carlo
- distribucion de retornos
- Regime Engine

Riesgo:

- Strategy Lab sigue siendo placeholder.

### Data

Estado: activo.

Incluye:

- catalogo de APIs
- health
- dataset previews
- CSV exports
- readiness para PowerBI

Riesgo:

- todavia faltan jobs programados robustos.

### Map

Estado: prototipo activo.

Incluye:

- mapa Leaflet
- eventos globales
- USGS/GDACS/GDELT

Riesgo:

- visualmente no cumple aun la vision semi-3D.
- GDELT puede rate-limitear.

### Bots

Estado: visible, bloqueado para ejecucion.

Debe contener:

- Bot Forge
- Saved Bots
- Backtests
- Paper Mode
- ROI profile
- Risk limits

No debe contener todavia:

- ordenes reales
- API keys de exchange
- ejecucion live

### Risk

Estado: visible, bloqueado para ejecucion real.

Debe contener:

- max position size
- max daily loss
- max drawdown
- cooldown after loss
- symbol whitelist
- kill switch

No debe permitir live trading hasta que Bot Forge y Paper Mode existan.

## Errores detectados

1. Bots no aparecia en la navegacion.
2. Risk no aparecia como modulo independiente.
3. La estructura visible no reflejaba la ambicion real del producto.
4. Algunas piezas backend estaban listas pero ocultas para el usuario.
5. El producto podia sentirse como radar y no como command center.

## Correccion aplicada

Se agregan paginas visibles:

- `#bots`
- `#risk`

Ambas aparecen como areas operativas planificadas, sin fingir capacidades que todavia no existen.

## Proximo paso recomendado

Antes de Bot Forge real:

1. Backtest Engine v1.
2. Bot profile schema.
3. Risk rules schema.
4. Paper Mode mock controlado.
5. Recien despues, exchange integration segura.

## Regla de producto

Toda pantalla debe responder una pregunta operativa.

Si una pantalla no ayuda a decidir, auditar, medir o controlar, es ruido.
