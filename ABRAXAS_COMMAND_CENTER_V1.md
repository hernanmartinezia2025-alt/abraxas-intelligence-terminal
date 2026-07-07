# ABRAXAS Command Center V1

## Decision central

ABRAXAS no es una pagina estetica, no es un simulador y no es solo un radar de precios.

ABRAXAS debe evolucionar como un centro operativo para traders:

```text
mercado en vivo -> estadistica -> estrategia -> backtest -> bots -> reportes -> control operativo
```

La prioridad ya no es agregar pantallas sueltas. La prioridad es ordenar el producto para que cada modulo tenga un proposito real, medible y escalable.

## Proyecto vivo

El proyecto activo es:

```text
C:\Users\marti\OneDrive\Escritorio\PROGRAMACION\New folder\abraxas-intelligence-terminal
```

Carpetas viejas como `agent-framework` o `abraxas_extracted` solo pueden usarse como referencia historica. No son la base de trabajo.

## Principios no negociables

- No reintroducir Streamlit.
- Mantener React/Vite como frontend principal.
- Mantener FastAPI como backend principal.
- Mantener SQLite como base local inicial.
- No ejecutar ordenes reales hasta tener paper trading, auditoria, permisos, kill switch y limites de riesgo.
- No meter claves privadas en frontend.
- No construir un monolito nuevo.
- No copiar repos externos completos.
- No depender de APIs pagas para el core.
- No vender prediccion financiera: ABRAXAS observa, calcula, compara, audita y explica.

## Vision de producto

ABRAXAS debe funcionar como una terminal operativa compuesta por estos nucleos:

```text
1. Command Center
2. Market Intelligence
3. Statistical Intelligence
4. Charting Desk
5. Strategy Lab
6. Bot Forge
7. World Intelligence
8. User / Super User Center
9. AI Task Router
10. Data API Center
```

Cada nucleo debe poder crecer sin romper los demas.

## 1. Command Center

Funcion:

Mostrar el estado operativo completo del usuario.

Debe incluir:

- mercado general
- alertas activas
- bots activos o en paper mode
- riesgo global
- balance consolidado cuando existan exchanges conectados
- salud de fuentes de datos
- eventos relevantes del mundo
- resumen ABRAXAS en lenguaje simple

No debe ser decorativo. Debe responder rapido: que esta pasando, que exige atencion y que esta degradado.

## 2. Market Intelligence

Funcion:

Leer el mercado en vivo y organizar activos.

Debe incluir:

- crypto principales
- top movers
- watchlists
- volumen 24h
- cambio 24h
- volatilidad
- volumen relativo
- Fear & Greed
- tabla de mercado filtrable
- asset universe por categorias

Categorias futuras:

- crypto
- indices
- commodities
- forex
- acciones sensibles a narrativa
- ETFs
- sectores

## 3. Statistical Intelligence

Funcion:

Calcular estadistica real con pandas y modelos matematicos comprensibles.

Debe incluir:

- retornos
- volatilidad
- drawdown
- z-score
- correlaciones
- distribucion de retornos
- percentiles historicos
- campana de Gauss
- desviacion estandar
- intervalos de confianza
- Value at Risk basico
- Monte Carlo
- escenarios optimista / base / estres

La salida debe tener dos niveles:

```text
calculo matematico -> explicacion humana simple
```

Ejemplos de lectura:

- "El activo esta 1.8 desviaciones sobre su media reciente."
- "El movimiento actual esta en el percentil 92 de volatilidad."
- "Monte Carlo muestra un rango probable, no una prediccion."
- "La cola de riesgo esta mas pesada que lo normal."

## 4. Charting Desk

Funcion:

Dar una experiencia de chart seria, flexible y util.

Debe incluir:

- candles reales
- timeframes
- volumen
- indicadores basicos
- EMA
- RSI
- ATR
- volumen relativo
- overlays de eventos si aplica
- comparacion entre activos
- exportador Pine

TradingView:

No asumir que existe una API gratuita completa para operar como backend. La ruta prudente es:

- `lightweight-charts` para charts propios.
- Widget/embed solo si sirve para visualizacion.
- Exportador Pine para llevar estrategias a TradingView.
- Datos propios desde fuentes gratuitas cuando sea posible.

## 5. Strategy Lab

Funcion:

Crear, probar y explicar estrategias antes de convertirlas en bots.

Debe incluir:

- builder de reglas
- indicadores reutilizables
- condiciones de entrada
- condiciones de salida
- reglas de riesgo
- backtest
- reporte
- comparacion contra benchmark
- auditoria de sesgos

Pipeline:

```text
datos -> indicadores -> reglas -> backtest -> reporte -> bot blueprint
```

## 6. Bot Forge

Funcion:

Ser el universo principal de creacion, simulacion, versionado y control de bots.

No debe ser una pestaña menor.

Cada bot debe tener:

- nombre
- descripcion
- estado
- estrategia asociada
- activos operables
- timeframe
- capital simulado
- comisiones
- slippage
- reglas de entrada
- reglas de salida
- reglas de riesgo
- ROI acumulado
- drawdown
- win rate
- profit factor
- Sharpe / Sortino basico
- historial de operaciones
- logs
- versiones
- auditoria

Estados posibles:

```text
draft -> backtested -> paper -> paused -> live-ready
```

La ejecucion real queda fuera de V1. Antes deben existir:

- paper trading solido
- permisos por usuario
- claves cifradas
- limites de riesgo
- kill switch
- logs auditables
- separacion entre usuario y super usuario

## 7. World Intelligence

Funcion:

Relacionar eventos del mundo con mercados.

Debe incluir:

- mapa vivo
- eventos geolocalizados
- terremotos
- alertas globales
- noticias relevantes
- severidad
- frescura
- activos relacionados
- impacto estimado por narrativa

Direccion visual:

El mapa 2D actual es una base, no el destino final. El objetivo es una experiencia mas cercana a centro operativo, eventualmente semi-3D o globo interactivo, sin copiar codigo AGPL ni depender de repos externos de forma peligrosa.

## 8. User / Super User Center

Funcion:

Separar operaciones normales de administracion.

Usuario normal:

- portfolio propio
- exchanges conectados propios
- balance consolidado
- bots propios
- backtests propios
- paper trading propio
- reportes propios
- IA sobre sus datos

Super usuario:

- usuarios
- permisos
- health global
- fuentes de datos
- bots globales
- limites de riesgo
- modelos IA disponibles
- logs
- auditoria
- configuracion de modulos

## 9. AI Task Router

Funcion:

Usar IA de forma modular y eficiente, no como un chat gigante que quema tokens.

La IA debe dividir tareas:

- resumir eventos
- explicar estadisticas
- clasificar riesgo
- auditar estrategia
- comparar bots
- generar reportes
- detectar anomalias
- traducir datos complejos a lenguaje simple

Modelo mental:

```text
tarea pequeña -> modelo barato/rapido
tarea compleja -> modelo razonador
tarea critica -> auditoria + trazabilidad
```

Gemini u otros modelos pueden integrarse mas adelante mediante un router, no directamente en componentes de frontend.

## 10. Data API Center

Funcion:

Ser la base confiable de APIs, datos, cache, datasets analiticos, salud y trazabilidad.

Debe incluir:

- fuentes
- jobs de actualizacion
- cache local
- normalizacion
- datasets exportables
- tablas listas para PowerBI
- feature store para bots
- source health
- latencia
- ultima actualizacion
- errores
- SQLite como base local inicial

Fuentes iniciales:

- Binance
- Alternative.me
- USGS
- GDACS
- GDELT

Fuentes futuras posibles:

- Yahoo/Stooq para macro y acciones
- CoinGecko/CoinPaprika si se necesita universo crypto mayor
- fuentes RSS publicas
- fuentes on-chain gratuitas si aportan valor

Regla:

```text
APIs externas -> normalizacion -> SQLite/cache -> datasets analiticos -> frontend/bots/PowerBI
```

El frontend visualiza. El backend y la base de datos sostienen el peso del calculo y la verdad de los datos.

## Responsive como requisito base

ABRAXAS debe adaptarse dinamicamente a cualquier pantalla.

Reglas:

- no usar layouts fijos como base
- charts con resize real
- grids fluidos
- tablas con modo compacto
- cards que no se pisan
- sidebar colapsable
- navegacion adaptable
- cero overflow accidental
- mapas y charts deben recalcular tamaño

Estados esperados:

```text
desktop grande -> command center multicolumna
laptop -> layout denso pero legible
tablet -> paneles apilados
mobile -> cards compactas y tablas convertidas en listas
```

## Actualizacion automatica

ABRAXAS no debe depender de botones manuales para mantenerse fresco.

Regla:

```text
auto-refresh silencioso -> cache/local state -> render sin parpadeo -> usuario ve datos frescos
```

El boton manual debe quedar como accion de fuerza, no como mecanismo principal.

Principios:

- actualizar de fondo
- evitar loaders grandes para refresh automatico
- conservar ultimo dato valido si una fuente falla
- mostrar ultima actualizacion
- mostrar health por fuente
- no bloquear charts ni paneles durante una consulta
- preferir cache local antes que pantalla vacia

El objetivo no es prometer latencia cero. El objetivo es continuidad operativa imperceptible para el ojo humano.

## Orden de construccion recomendado

### Fase 0 - Congelar vision

Objetivo:

Evitar seguir agregando piezas desordenadas.

Entregables:

- este documento
- matriz de recuperacion actualizada
- lista de modulos vivos
- lista de modulos perdidos

### Fase 1 - Data Layer estable

Objetivo:

Que ABRAXAS tenga datos confiables antes de mas UI.

Entregables:

- registry de fuentes
- health por fuente
- cache local
- actualizaciones controladas
- errores visibles

### Fase 2 - Statistical Intelligence

Objetivo:

Construir el motor matematico real.

Entregables:

- endpoint de estadisticas
- endpoint de Monte Carlo
- endpoint de distribucion de retornos
- explicacion humana de resultados
- graficos estadisticos en frontend

### Fase 3 - Charting Desk

Objetivo:

Convertir Trade en una mesa de trabajo seria.

Entregables:

- chart responsive
- indicadores basicos
- comparacion de activos
- watchlist seria
- panel de lectura tecnica

### Fase 4 - Strategy Lab

Objetivo:

Crear estrategias probables y auditables.

Entregables:

- reglas
- indicadores
- backtest
- benchmark
- reporte

### Fase 5 - Bot Forge

Objetivo:

Crear bots completos en entorno controlado.

Entregables:

- saved bots
- versionado
- ROI profile
- risk profile
- backtest por bot
- paper mode inicial
- logs

### Fase 6 - User / Super User Center

Objetivo:

Preparar la plataforma para usuarios reales.

Entregables:

- usuarios
- roles
- permisos
- perfiles
- balances
- auditoria

### Fase 7 - AI Task Router

Objetivo:

Usar IA como capa de tareas, no como decoracion.

Entregables:

- router de tareas
- integracion Gemini opcional
- resumenes
- explicaciones
- auditorias

### Fase 8 - World Intelligence avanzado

Objetivo:

Elevar el mapa a una experiencia operativa.

Entregables:

- mapa/globo mas avanzado
- capas
- alertas
- impacto en activos
- conexion con Command Center

## Proximo paso inmediato

No tocar mas estetica suelta.

El siguiente paso tecnico recomendado es Fase 2:

```text
Statistical Intelligence v1
```

Porque desbloquea:

- analisis serio
- calculadora probabilistica
- Monte Carlo
- graficos estadisticos
- explicaciones ABRAXAS
- mejores bots en el futuro

Si la base estadistica es debil, Bot Forge tambien sera debil.

## Definicion de exito de V1

ABRAXAS V1 empieza a estar bien cuando puede responder:

- Que esta pasando en el mercado?
- Que tan raro es este movimiento?
- Que riesgo estadistico hay?
- Que eventos del mundo lo pueden estar afectando?
- Que estrategia puedo probar?
- Como se comporto esa estrategia antes?
- Que bot representa esa estrategia?
- Que ROI y drawdown tuvo?
- Que usuario/bot/fuente requiere atencion?

Cuando esas preguntas tengan respuesta en la app, ABRAXAS deja de ser maqueta y empieza a ser producto.
