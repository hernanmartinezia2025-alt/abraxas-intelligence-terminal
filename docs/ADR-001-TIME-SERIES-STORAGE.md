# ADR-001: almacenamiento de series temporales

- Estado: aceptado como dirección, no implementado
- Fecha: 2026-07-17
- Alcance: datos de mercado, features y backtests de ABRAXAS

## Contexto medido

La base local `data/abraxas.db` ocupa 32,12 MB. Contiene aproximadamente 6.638 velas, 29.430 snapshots, 6.138 features, 581 eventos y 4 backtests. Esta carga no justifica operar otra base de datos todavía.

`market_candles` ya protege unicidad por `(symbol, timeframe, open_time)` y tiene un índice compuesto con ese mismo orden. La afirmación de que una base relacional estándar colapsará inevitablemente no es correcta: el resultado depende del volumen, patrón de consulta, particionado, índices, retención y hardware.

## Decisión

ABRAXAS adopta una arquitectura de almacenamiento por planos:

1. **Control plane local-first — SQLite:** usuarios locales, bots, versiones, risk limits, auditoría, paper trading, carteras y configuración.
2. **Time-series data plane — TimescaleDB candidato:** trades/ticks, OHLCV y rollups cuando la carga real supere los SLO definidos abajo.
3. **Analytics plane opcional — ClickHouse:** solo si backtests masivos o análisis columnar sobre cientos de millones/miles de millones de filas demuestran que TimescaleDB no alcanza el SLO.
4. **Archivo frío futuro — Parquet/object storage:** historial crudo que no necesita consulta operacional inmediata.

InfluxDB no se selecciona como primera migración. Su ingestión, retención y downsampling son sólidos, pero duplicaría el ecosistema relacional que ABRAXAS necesita para bots, riesgo y auditoría.

No se instala ninguna base nueva en esta fase.

## Disparadores de migración

La migración comienza al cumplirse uno o más criterios medidos durante una ventana sostenida:

- consulta p95 de las últimas 1.000 velas por símbolo/timeframe mayor a 250 ms;
- backtest que necesita candles mayor a 2 s antes de ejecutar el motor;
- ingestión sostenida superior a 5.000 eventos por segundo;
- tabla de series temporales mayor a 50 millones de filas o base mayor a 20 GB;
- contención de escritura que afecte paper trading, riesgo o auditoría.

Estos valores son SLO iniciales revisables, no promesas universales de rendimiento.

## Esquema objetivo

### Trades crudos

`exchange`, `symbol`, `trade_id`, `event_time`, `price`, `quantity`, `side`, `ingested_at`.

La identidad debe ser `(exchange, symbol, trade_id)`. Un trade no equivale a un snapshot de order book. Los datos tardíos y fuera de orden deben conservar su `event_time` original.

### OHLCV

`exchange`, `symbol`, `timeframe`, `bucket_time`, `open`, `high`, `low`, `close`, `base_volume`, `quote_volume`, `trade_count`, `source_from`, `source_to`.

La identidad debe ser `(exchange, symbol, timeframe, bucket_time)`. Los agregados OHLC requieren primer y último precio ordenados por tiempo; no pueden obtenerse promediando ticks.

## Rollups y retención

- raw trades: retención corta y configurable, inicialmente 7–30 días si se habilitan;
- 1m OHLCV: fuente operacional primaria para derivar 5m, 15m y 1h;
- 4h, 1d y 1w: rollups jerárquicos o agregados directos con reconciliación;
- toda agregación debe registrar ventana de origen, conteo y estado de completitud;
- una vela abierta nunca puede entrar en features, señales o backtests cerrados;
- las políticas de retención del raw y de cada agregado se administran por separado.

## Plan de adopción

1. Instrumentar latencia, filas leídas, tamaño y tasa de escritura en SQLite.
2. Definir una interfaz `TimeSeriesStore` sin cambiar consumidores existentes.
3. Ejecutar TimescaleDB en shadow mode y reconciliar conteos/OHLCV contra SQLite.
4. Mover primero candles y luego, si existe un caso real, trades crudos.
5. Mantener SQLite como control plane y fuente de auditoría local.
6. Evaluar ClickHouse únicamente con benchmarks reproducibles de backtest.

## Referencias oficiales

- Timescale hypertables: https://docs.timescale.com/use-timescale/latest/hypertables/
- Timescale continuous aggregates: https://docs.timescale.com/use-timescale/latest/continuous-aggregates/create-a-continuous-aggregate/
- PostgreSQL BRIN: https://www.postgresql.org/docs/current/brin.html
- InfluxDB 3 downsampling: https://docs.influxdata.com/influxdb3/core/plugins/library/official/downsampler/
