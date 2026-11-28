# Plan: Vercel (Frontend + Storage + Métricas) + Render (Backend + Señales + Ejecución)

## Objetivo
Mover toda la lógica de métricas (PnL, win/loss ratio, historial de trades) a Vercel para que persistan a pesar de reinicios de Render. Render solo procesa señales y ejecuta trades hacia Deriv. Vercel lee de Deriv (fuente de verdad) y/o de Render (cuando hay operación) y muestra en el frontend.

## Arquitectura propuesta

### Render (Backend + Señales + Ejecución)
- FastAPI (main.py) + bot Python (bot_1hz50v.py)
- WebSocket a Deriv (public + trading)
- Procesa señales (HMA 150, flow, dirección)
- Ejecuta trades hacia Deriv (CALL/PUT)
- Endpoints mínimos:
  - /status → estado del bot (running, symbol, balance actual, última señal)
  - /signals → última señal generada (side, price, hma, timestamp)
  - /config GET/POST → configuración
  - /health → liveness check
- NO almacena trades ni PnL ni win/loss ratio
- NO sirve dashboard HTML (solo API)

### Vercel (Frontend + Storage + Métricas)
- Next.js app (ya existe en /app, /components, /hooks, /lib)
- Almacenamiento: Vercel KV (Redis) o Vercel Postgres para:
  - Historial de trades (solo resumen: id, symbol, side, entry, exit, pnl, resultado)
  - Métricas calculadas: PnL total, win rate, win/loss ratio, drawdown
  - Configuración del bot (symbol, stake, HMA period, etc.)
  - Cache de últimas señales
- API Routes de Next.js:
  - /api/trades → lee/guarda trades en KV
  - /api/metrics → calcula PnL, win rate, ratio desde KV
  - /api/config → lee/escribe config en KV
  - /api/bot-status → proxy a Render /status
  - /api/bot-signals → proxy a Render /signals
- Polling a Render cada 5-10s para detectar nuevas señales/trades
- Cuando Render reporta un trade nuevo, Vercel lo guarda en KV y recalcula métricas

## Flujo de datos

1. Render bot → Deriv WebSocket → genera señal → ejecuta trade
2. Render /signals → devuelve última señal (side, price, timestamp)
3. Vercel frontend → polling a /api/bot-signals → Render → Deriv (fuente de verdad)
4. Vercel → guarda trade en KV/Postgres cuando se detecta cierre
5. Vercel /api/metrics → calcula PnL, win rate, ratio desde KV
6. Frontend muestra métricas en tiempo real desde Vercel (sin depender de Render)

## Por qué esto resuelve el problema

- **Render se reinicia** → bot se reinicia, pero las métricas (PnL, win/loss) ya están en Vercel KV/Postgres
- **No se pierden datos** porque Deriv es fuente de verdad para trades, y Vercel persiste el resumen
- **Render solo ejecuta** → no necesita almacenar nada, solo señales y trades en tiempo real
- **Vercel calcula métricas** → PnL = balance actual - balance inicial (leído de Deriv vía Render /status)

## Pasos de implementación

### Fase 1: Preparar Vercel ✅ COMPLETA
- [x] Crear proyecto en Vercel vinculado al repo (`deriv-py-bot`)
- [x] Configurar variables de entorno:
  - `NEXT_PUBLIC_API_URL=https://deriv-py-bot.onrender.com`
- [x] Crear Vercel Blob store (`store_sGlIdqUxUYtVFBau`)
- [x] Configurar CORS en Render para aceptar origen de Vercel (`https://deriv-py-bot.vercel.app`)
- [x] Token `BLOB_READ_WRITE_TOKEN` guardado en Vercel env vars

### Fase 2: Adaptar frontend ✅ COMPLETA
- [x] Crear API routes en `/app/api/`:
  - `/api/bot-status` → proxy a Render `/status`
  - `/api/bot-signals` → proxy a Render `/signals`
  - `/api/trades` → lee/guarda trades en Vercel Blob
  - `/api/metrics` → calcula PnL, win rate, ratio desde Blob
  - `/api/config` → lee/escribe config en Blob
- [x] Crear hook `hooks/use-bot-status.ts` que lee desde API routes de Vercel
- [x] Crear componente `components/bot/metrics-panel.tsx` que lee desde `/api/metrics`
- [x] Actualizar `components/bot/trade-tab.tsx` para incluir `MetricsPanel`
- [x] Agregar página `app/bot-status/page.tsx` para ver estado sin login de Deriv

### Fase 3: Optimizar Render ✅ COMPLETA
- [x] Eliminar dashboard HTML de `main.py` (solo API)
- [x] Agregar endpoint `/trade-complete` (webhook opcional)
- [x] Configurar CORS para origen de Vercel
- [x] Eliminar almacenamiento local de trades (ya eliminado)
- [x] Mantener bot en background task (ya existe)
- [x] Hacer deploy manual en Render (autoDeploy: "yes" en render.yaml)
- [x] Uptime bot en sistema local (no en Vercel — Vercel Hobby solo permite crons diarios)

### Fase 4: Storage compartido ✅ COMPLETA
- [x] Vercel Blob para config (symbol, stake, HMA period, etc.)
- [x] Render lee config desde Blob (o sigue usando config.json local como fallback)
- [x] Frontend escribe config a Blob → Render la recoge en el siguiente ciclo
- [x] Vercel Blob para historial de trades (solo resumen, Deriv es fuente de verdad)

### Fase 5: Testing y deploy ⏳ PENDIENTE
- [ ] Verificar que Render desplegó correctamente (auto-deploy activado)
- [ ] Probar flujo completo: frontend Vercel → Render API → Deriv
- [ ] Verificar que métricas persisten tras reinicio de Render
- [ ] Verificar latencia y CORS
- [ ] Deploy a producción

## Consideraciones

- **Costo:** Vercel free tier + Render free tier = $0/mes (con limitaciones)
- **Latencia:** Vercel edge → baja latencia para UI. Render → 100-200ms para API
- **CORS:** Render debe permitir origen de Vercel (https://*.vercel.app)
- **Autenticación:** Token de Deriv solo en Render (nunca en frontend)
- **State:** Deriv es fuente de verdad para trades/balance. Vercel KV solo persiste resumen y métricas.
- **No duplicar datos:** No almacenar trades completos en Vercel, solo resumen (id, side, entry, exit, pnl, resultado)
- **Métricas recalculadas:** PnL total = suma de pnl de trades en KV. Win rate = wins/total. Ratio = wins/losses.

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| main.py | Eliminar dashboard HTML, agregar CORS, mantener solo API |
| app/api/ (nuevo) | API routes proxy en Next.js (bot-status, bot-signals, trades, metrics, config) |
| hooks/useBotWS.ts | Usar nuevas API routes de Vercel |
| components/bot/ | Actualizar para leer métricas desde /api/metrics |
| vercel.json (nuevo) | Configuración de Vercel |
| render.yaml | Agregar CORS origins, quitar dashboard |

## Riesgos

1. Render free tier se duerme → bot se detiene. Solución: uptime bot local o Render paid ($7/mes)
2. Latencia entre Vercel y Render → 100-200ms. Aceptable para dashboard
3. Vercel KV tiene límites en free tier (30k requests/día). Suficiente para dashboard con polling cada 10s
4. Complejidad adicional: dos plataformas para mantener
5. Sincronización: Vercel debe detectar trades nuevos de Render. Solución: polling a /signals cada 5s y comparar con último trade en KV

## Alternativa más simple

Mantener todo en Render (frontend + backend) como está ahora. Vercel solo si se necesita mejor UX o persistencia de métricas.