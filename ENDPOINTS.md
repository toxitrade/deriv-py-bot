# Deriv Bot - API Endpoints Reference

## Base URL
`https://TU-SERVICE-ON-RENDER.render.com` (o localmente `http://localhost:8000`)

---

## Endpoints Publicados

### Health & Status

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Health check para la plataforma. Retorna `{"status":"ok","running":true/false,"mode":"binary"|"multiplier"}` |
| `GET` | `/status` | Estado detallado del bot. Incluye posición abierta, trades hoy, ticks recibidos, PnL, y modo-specific fields (martingale_step o multiplier) |
| `GET` | `/api-root` | Información raíz de la API. Retorna app name, running status, mode, trade_mode y dashboard_url |

### Configuration

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/config` | Devuelve la configuración actual **sin secretos** (mode, symbol, stake, hma_period, flow_period, flow_smooth, flow_threshold, duration, duration_unit, multiplier, tp_pct, sl_pct, log_level, log_file, token_configured) |
| `POST` | `/config` | Guarda configuración desde el sitio. Campos permitidos: mode, symbol, stake, hma_period, flow_period, flow_smooth, flow_threshold, duration, duration_unit, martingale_multiplier, max_martingale_steps, multiplier, tp_pct, sl_pct. Actualiza `config.json` y recarga el modo del bot si cambió |

### Control

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/start` | Inicia el bot en background. Retorna `{"status":"started","mode":"binary"|"multiplier","trade_mode":"DEMO"}`. Si ya está corriendo, retorna `{"status":"already_running"}`. |
| `POST` | `/stop` | Detiene el bot. Retorna `{"status":"stopped","mode":"binary"|"multiplier"}`. Si no estaba corriendo, retorna `{"status":"not_running"}`. |

### Signals

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/signals` | Última señal generada. Retorna `{"side":"call"|"put","entry_price":float,"entry_time":iso_timestamp,"position":int,"mode":"binary"|"multiplier"}`. Si no hay trades, retorna `{"signal":null,"message":"Sin trades aún"}` |

### Logs

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/logs?lines=50` | Devuelve las últimas N líneas del archivo de log del bot. Retorna `{log_file, lines, logs}`. Por defecto 50 líneas. |

### Environment (Development Only)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/printenv` | Imprime en el log del servidor las variables de entorno relevantes con valores secretos enmascarados (DERIV_TOKEN muestra los últimos 2 chars reemplazados por "xx"). **Solo para desarrollo** — no usar en producción. Retorna `{env_count, env: {DERIV_...}, note}` |

---

## Endpoints Heredados (Legacy — Backend Routes)

Estos vienen del backend legacy en `legacy/backend/` y aún pueden estar referenciados:

| Método | Ruta | Módulo |
|---|---|---|
| `GET` | `/` | `legacy/backend/routes/status.js` — estado básico |
| `GET` | `/:symbol` | `legacy/backend/routes/symbols.js` — configuración de símbolo |
| `GET` | `/` | `legacy/backend/routes/config.js` — configuración |
| `GET` | `/state` | `legacy/backend/routes/strategies.js` — estado de la estrategia |
| `GET` | `/state/history` | `legacy/backend/routes/strategies.js` — historial de señales |
| `POST` | `/state/reset` | `legacy/backend/routes/strategies.js` — reset de estado |
| `GET` | `/:name` | `legacy/backend/routes/strategies.js` — estrategia por nombre |
| `POST` | `/:name/activate` | `legacy/backend/routes/strategies.js` — activar estrategia |
| `POST` | `/:name/deactivate` | `legacy/backend/routes/strategies.js` — desactivar estrategia |
| `POST` | `/:name/params` | `legacy/backend/routes/strategies.js` — params de estrategia |
| `POST` | `/:name/deactivate` | `legacy/backend/routes/strategies.js` — desactivar |

---

## Respuesta de Errores Comunes

| Código | Significado | Solución |
|---|---|---|
| `404` | Ruta no encontrada | Verificar ortografía de la URL; los endpoints son *case-sensitive* |
| `422` | Validación de cuerpo JSON falló (POST /config) | Asegurar que el cuerpo sea `{"key": value, ...}` con tipos correctos |
| `500` | Error interno del bot | Revisar logs en `/logs` o el dashboard de Render; revisar `DERIV_TOKEN` y credenciales |

---

## Ejemplos de Curl

```bash
# Health check
curl http://localhost:8000/health

# Estado detallado
curl http://localhost:8000/status

# Configuración actual
curl http://localhost:8000/config

# Iniciar bot
curl -X POST http://localhost:8000/start

# Detener bot
curl -X POST http://localhost:8000/stop

# Última señal
curl http://localhost:8000/signals

# Logs (últimas 20 líneas)
curl "http://localhost:8000/logs?lines=20"

# Printenv (desarrollo)
curl http://localhost:8000/printenv
```