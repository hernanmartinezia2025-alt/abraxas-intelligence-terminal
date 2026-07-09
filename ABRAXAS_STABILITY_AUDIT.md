# ABRAXAS Stability Audit

## Fecha

2026-07-09

## Alcance

Auditoria rapida del estado actual antes de seguir agregando funciones.

Carpeta viva:

```text
C:\Users\marti\OneDrive\Escritorio\PROGRAMACION\New folder\abraxas-intelligence-terminal
```

## Estado del producto

ABRAXAS ya tiene una base util, pero todavia mezcla tres niveles de madurez:

- operativo real: datos de mercado, candles, SQLite, radar, estadisticas, regimen, data center;
- laboratorio: Monte Carlo, distribuciones, lectura de regimen, Live Map con fuentes publicas;
- maqueta: Strategy Lab, Context Lab, Bot Forge real, Risk Engine real, execution, order book real.

La prioridad no es agregar mas pantallas. La prioridad es convertir cada modulo en algo verificable.

## Pantallas

### Markets

Estado: usable.

Usa snapshots reales desde backend y SQLite. Requiere mejorar profundidad de mercado y cobertura de activos, pero no esta roto.

### Trade

Estado: mixto, con order book real inicial.

El chart usa candles reales via backend. La lectura ABRAXAS viene del radar. El order book ahora usa snapshot real de Binance Spot via `/api/order-book` y se refresca desde el frontend.

Pendiente:

- migrar order book a WebSocket cuando se necesite menor latencia;
- trades recientes reales;
- separar observacion de simulacion;
- no mostrar nada como ejecucion hasta tener paper mode y risk engine.

### Research

Estado: parcialmente real.

Statistical Intelligence, Gaussian y Monte Carlo usan backend. Regime Engine usa features calculadas. Strategy Lab y Context Lab siguen siendo placeholders y ahora quedan etiquetados como laboratorio/manual.

Pendiente:

- backtest engine persistente;
- reportes de estrategia;
- datasets de features para bots.

### Data

Estado: base fuerte.

Ya expone datasets, preview y export CSV. Es el camino correcto para PowerBI, analisis externo y motores de bots.

Pendiente:

- versionar datasets;
- agregar auditoria de calidad;
- diferenciar raw, processed y features.

### Map

Estado: funcional inicial.

Tiene eventos normalizados y health de fuentes. Todavia no es el mapa semi 3D deseado. No debe crecer mas sin ordenar primero ingestion, cache y severidad.

### Bots

Estado: visible, no operativo.

El apartado existe para dejar claro el universo de Bot Forge. Todavia no hay bots guardados, backtests ni paper mode.

Pendiente inmediato:

- tablas `bots`, `bot_versions`, `backtest_runs`;
- endpoints CRUD para bots;
- perfil de ROI por bot;
- conexion con datasets reales.

### Risk

Estado: visible, bloqueado.

Debe existir antes de cualquier ejecucion. Todavia no hay limites persistidos ni kill switch real.

Pendiente inmediato:

- tabla `risk_limits`;
- endpoint de estado del kill switch;
- validacion backend antes de cualquier paper/live order.

## Riesgos tecnicos

- Frontend todavia tiene pantallas grandes que conviene dividir mas.
- El bundle de Vite supera 500 kB; no rompe, pero pide code splitting.
- Algunas secciones todavia son placeholders y deben quedar marcadas hasta tener backend real.
- El proyecto puede escalar, pero necesita contratos de datos claros antes de bots reales.

## Siguiente bloque recomendado

1. Crear el modelo SQLite de Bot Forge sin UI pesada.
2. Crear endpoints backend para bots guardados y versiones.
3. Mostrar listado real de bots en `#bots`.
4. Recien despues crear backtest v1 conectado a `market_candles`.
5. Mantener live execution bloqueado.
