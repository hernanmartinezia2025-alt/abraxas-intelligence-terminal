# ABRAXAS Recovery Matrix

## Proyecto vivo

`C:\Users\marti\OneDrive\Escritorio\PROGRAMACION\New folder\abraxas-intelligence-terminal`

Las carpetas viejas quedan solo como referencia. No son la base de ejecucion.

## Estado actual V1

### Ya migrado / activo

- Market Radar con Binance, Fear & Greed y SQLite.
- Radar ampliado a 12 pares crypto.
- Candles endpoint base.
- Trade page visual base.
- Chart real basico en `Trade` con `lightweight-charts`.
- Selector global de activo basico.
- Live World Map con Leaflet, USGS, GDACS y health por fuente.
- Cache local para eventos globales en SQLite.
- Layout React/Vite limpio, sin Streamlit.

### Todavia incompleto

- Chart avanzado interactivo dentro de `Trade`.
- Integracion visual tipo TradingView para charts.
- Watchlist avanzada y selector global.
- Selector global de activos.
- Asset Universe separado por crypto, macro, commodities, indices y FX.
- Herramientas de analisis de datos.
- Strategy Lab real.
- Backtest real.
- Regime Engine.
- Statistics / Probability Study.
- Pine exporter.
- Bot Forge / Saved Bots.
- Bot scanner.
- Bot reports.
- Risk module.
- Tools layer.

## No perder otra vez

ABRAXAS no es solo un radar de precios ni solo un mapa.

El producto final debe recuperar estas familias de herramientas:

### Analisis de datos

- Estadisticas de retornos.
- Volatilidad.
- Z-score.
- Drawdown.
- Correlaciones.
- Probabilidad historica.
- Regimen de mercado.
- Comparacion entre activos.
- Reportes legibles.

### Charts / TradingView layer

- Chart principal serio dentro de `Trade`.
- Candles reales.
- Timeframes.
- Volumen.
- Indicadores basicos: EMA, RSI, ATR, volumen relativo.
- Overlays de eventos del Live Map sobre el activo cuando tenga sentido.
- Exportador Pine para llevar reglas a TradingView.
- Evaluar integracion visual tipo TradingView sin depender de APIs privadas ni romper local-first.

Nota: no asumir que existe una API gratuita completa de TradingView para backend. Usar una combinacion prudente:

- `lightweight-charts` para charts propios.
- Widget/embed si sirve para visualizacion.
- Pine exporter para trasladar estrategias.
- Datos propios desde Binance/Stooq/Yahoo u otra fuente gratuita.

### Bots / Strategy Lab

- Strategy Builder.
- Templates de estrategias.
- Indicadores reutilizables.
- Risk rules.
- Backtester.
- Bot scanner.
- Bot report.
- Saved Bots.
- Versionado de bots.
- Auditoria de sesgos.
- Paper mode solo despues.
- Nunca ejecucion real ni claves privadas en esta fase.

### Pipeline central

La secuencia mental de ABRAXAS debe ser:

```text
datos -> indicadores -> estrategia -> backtest -> reporte -> bot versionado -> paper mode
```

Nada de esto debe quedar enterrado en una pantalla unica ni en un monolito.

## Cosas utiles del proyecto viejo

Estas partes existen como ideas o codigo de referencia en las carpetas viejas:

- `backend/engines/statistics.py`
- `backend/engines/regimes.py`
- `backend/data_sources/yahoo.py`
- `backend/data_sources/stooq.py`
- `src/indicators.py`
- `src/strategies.py`
- `src/backtester.py`
- `src/risk.py`
- `src/bot_scanner.py`
- `src/bot_report.py`
- `src/pine_exporter.py`
- `src/control_room.py`
- `frontend/src/components/GlobalAssetSelector.jsx`
- `frontend/src/components/Tabs.jsx`
- `frontend/src/components/MetricTile.jsx`
- `frontend/src/components/RiskPill.jsx`
- `frontend/src/panels/MarketCharts.jsx`
- `frontend/src/panels/BotLab.jsx`
- `frontend/src/panels/AlgorithmicLabs.jsx`
- `frontend/src/sections/TacticalMarket.jsx`
- `frontend/src/sections/StrategyLayer.jsx`
- `frontend/src/sections/WorldVectors.jsx`
- `frontend/src/sections/DataLayer.jsx`
- `frontend/src/sections/Tools.jsx`
- `FREQTRADE_RESEARCH.md`
- `BOT_FORGE_BLUEPRINT.md`

## Regla de migracion

No copiar pantallas completas del viejo proyecto.

Migrar en este orden:

1. Extraer la idea.
2. Reescribirla en la arquitectura V1.
3. Agregar endpoint fino si hace falta.
4. Agregar componente o panel pequeno.
5. Verificar build y endpoint.

## Organizacion propuesta del producto

### 1. Markets

Funcion: lectura rapida del mercado.

Debe contener:

- Market Radar.
- Top movers.
- Heatmap simple.
- Tabla de activos.
- Fear & Greed.
- Volumen y cambio 24h.

### 2. Trade

Funcion: desk de observacion de un activo.

Debe contener:

- Selector global de activo.
- Chart real con candles.
- Timeframes.
- Indicadores basicos.
- Watchlist / selector lateral.
- Comparador rapido.
- Order book placeholder o real si la fuente lo permite.
- Lectura ABRAXAS del activo.

### 3. Map

Funcion: mapa vivo de eventos del mundo.

Debe contener:

- Mapa grande.
- Capas activables.
- Alert queue.
- Filtros por severidad, fuente, tipo y activos relacionados.
- Click en evento centra mapa.
- Source health.
- Panel de impacto de mercado.

### 4. Research

Funcion: laboratorio de hipotesis.

Debe contener:

- Statistics.
- Regime Engine.
- Probability Study.
- Strategy Builder.
- Backtest.
- Report.
- Correlation Lab.
- Indicator Lab.

### 5. Bots

Funcion: laboratorio de bots, sin ejecucion real.

Debe contener:

- Saved Bots.
- Versionado.
- Templates.
- Scanner.
- Risk profile.
- Backtest por bot.
- Report por bot.
- Auditoria de sesgos.
- Paper mode solo mas adelante.

### 6. Data

Funcion: salud y fuentes.

Debe contener:

- Binance.
- Alternative.me.
- USGS.
- GDACS.
- GDELT.
- Stooq/Yahoo u otra fuente gratuita para macro.
- SQLite health.
- Ultima actualizacion por fuente.

### 7. Tools

Funcion: utilidades.

Debe contener:

- Pine exporter.
- Report exporter.
- Diagnostics.
- Local database tools.

## Proximo paso recomendado

Antes de agregar features nuevas grandes:

1. Crear `GlobalAssetSelector`.
2. Ordenar `Trade` alrededor del chart real y watchlist.
3. Crear tabla de mercado/asset universe basica.
4. Crear estructura de subpaneles dentro de `Map`.
5. Migrar Statistics + Regime como endpoints nuevos.
6. Migrar Backtest + Indicator Lab.
7. Recien despues migrar Strategy Lab y Bot Forge.
