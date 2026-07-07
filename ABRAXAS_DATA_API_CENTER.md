# ABRAXAS Data API Center

## Decision

ABRAXAS necesita un centro de APIs y datos.

No alcanza con traer datos y mostrarlos. Los datos deben quedar normalizados, persistidos y disponibles para:

- analisis interno
- graficos estadisticos
- PowerBI u otras herramientas externas
- bots
- auditoria
- reportes
- IA por tareas

Regla central:

```text
APIs externas -> normalizacion -> SQLite/cache -> datasets analiticos -> frontend/bots/PowerBI
```

El frontend no debe inventar datos. El frontend visualiza. El backend y la base son la fuente de verdad.

## Objetivo

Crear un modulo llamado `Data API Center`.

Debe responder:

- que fuentes existen
- que datos trae cada fuente
- cuando fue la ultima actualizacion
- que tablas/datasets hay disponibles
- que datos estan listos para bots
- que datos estan listos para PowerBI
- que fuente fallo
- que dato esta vencido

## Capas

### 1. Source Registry

Catalogo de fuentes externas.

Ejemplos:

- Binance
- Alternative.me
- USGS
- GDACS
- GDELT
- Yahoo/Stooq futuro
- CoinGecko/CoinPaprika futuro
- exchanges conectados futuro

Campos sugeridos:

- source_id
- name
- type
- base_url
- status
- last_success_at
- last_error
- latency_ms
- max_stale_minutes
- enabled

### 2. Raw Cache

Guarda respuesta cruda cuando tenga sentido.

No todo debe quedar para siempre, pero si suficiente para auditar errores y reproducir calculos importantes.

Campos sugeridos:

- id
- source
- endpoint
- fetched_at
- raw_payload
- status_code
- error

### 3. Normalized Tables

Tablas limpias para analisis.

Ejemplos:

- market_snapshots
- market_candles
- sentiment_snapshots
- live_events
- source_health
- exchange_balances futuro
- bot_trades futuro
- bot_equity_curves futuro

### 4. Analytical Datasets

Datos derivados listos para graficos, PowerBI y bots.

Ejemplos:

- return_series
- volatility_series
- drawdown_series
- correlation_matrix
- monte_carlo_runs
- probability_studies
- regime_snapshots
- asset_features
- bot_performance_snapshots

### 5. Feature Store

Capa para bots.

Los bots no deben leer "texto bonito". Deben leer features numericas y estados normalizados.

Ejemplos:

- symbol
- timestamp
- timeframe
- return_pct
- volatility_pct
- z_score
- rsi
- atr
- volume_relative
- drawdown_pct
- fear_greed_value
- regime
- event_risk_score
- liquidity_score
- trend_score
- risk_state

Esto permite:

```text
bot -> consulta features -> decide segun reglas/modelo -> registra decision -> auditoria
```

## PowerBI / herramientas externas

ABRAXAS debe permitir sacar datos para PowerBI sin depender del frontend.

Opciones:

1. Conectar PowerBI a SQLite mediante ODBC.
2. Exportar CSV desde endpoints.
3. Exportar archivos `.csv` programados en `/data/exports`.
4. Mas adelante, usar una base externa si el producto escala.

Endpoints sugeridos:

```text
GET /api/data/catalog
GET /api/data/sources
GET /api/data/health
GET /api/data/datasets
GET /api/data/export/market-snapshots.csv
GET /api/data/export/candles.csv
GET /api/data/export/statistics.csv
GET /api/data/features
```

## Bots y datos

Los bots deben consumir datos estructurados.

Incorrecto:

```text
"BTC esta fuerte, quizas sube"
```

Correcto:

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "return_pct": 0.42,
  "volatility_pct": 0.31,
  "z_score": 1.4,
  "rsi": 62.8,
  "volume_relative": 1.7,
  "regime": "momentum",
  "risk_state": "elevated"
}
```

La interpretacion textual sirve para el usuario. Las features sirven para bots.

## Frontend

El frontend debe mostrar:

- catalogo de APIs
- health por fuente
- datasets disponibles
- cantidad de registros
- ultima actualizacion
- exportaciones
- vista previa de tablas
- errores de fuente

No debe recalcular estadistica pesada.

## Backend

El backend debe:

- conectar fuentes
- normalizar datos
- persistir datos
- calcular datasets analiticos
- exponer endpoints limpios
- exportar CSV
- servir features para bots

## Orden de implementacion

### Paso 1

Crear `Data API Center` minimo:

- `/api/data/catalog`
- `/api/data/sources`
- `/api/data/health`
- `/api/data/datasets`

### Paso 2

Persistir candles en SQLite.

Hoy se consultan candles para chart/estadistica. Deben quedar guardadas para analisis historico.

Estado: iniciado con tabla `market_candles` y cache desde `/api/candles`.

### Paso 3

Guardar resultados estadisticos.

Monte Carlo, z-score, volatilidad, drawdown y distribuciones deben poder auditarse.

Estado: iniciado con tabla `statistics_runs`.

### Paso 4

Crear `asset_features`.

Primera tabla pensada para bots.

Estado: iniciado con features numericas desde candles locales.

Features v1:

- return_1
- return_5
- return_20
- volatility
- z_score
- drawdown
- trend_strength
- volume_change
- risk_score
- regime_label

### Paso 5

Exportadores:

- CSV
- PowerBI-ready
- reportes por simbolo/timeframe

## Regime Engine v1

Estado: iniciado.

Input:

- `asset_features`

Output:

- `regime_snapshots`

Campos principales:

- regime_label
- confidence
- risk_score
- market_bias
- volatility_state
- trend_state
- drawdown_state
- reasons
- reading

Uso:

- Research
- Bot Forge futuro
- Risk Engine futuro
- PowerBI

## Definicion de exito

ABRAXAS Data API Center funciona cuando:

- cualquier dato importante tiene origen claro
- cualquier calculo importante puede repetirse o auditarse
- PowerBI puede leer datasets sin tocar el frontend
- los bots leen features, no textos
- el usuario ve salud y frescura de datos
- el sistema sigue funcionando aunque una API externa falle
