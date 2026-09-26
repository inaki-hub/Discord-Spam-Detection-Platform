# Moderación configurable

---

## Español

Sanciones por **timeout** de Discord, **desactivadas por defecto**. Configuración por servidor sin editar código: comandos `!mod` o pestaña **Config moderación** del dashboard.

No aplica timeouts a bots ni administradores. Respeta un **cooldown** por usuario para evitar sanciones en cada mensaje de una ráfaga.

### Requisitos en Discord

- Bot: permiso **Moderar miembros** y rol por encima del miembro sancionado
- Quien configura: permiso **Gestionar servidor**

### Defaults desde `.env`

Si no hay fila en `guild_moderation` para un servidor, se usan `MODERATION_*` de `.env` (plantilla en `.env.example`).

| Variable (ejemplo) | Rol |
|--------------------|-----|
| `MODERATION_ENABLED` | Activar ejecución real (`false` por defecto) |
| `MODERATION_DRY_RUN` | Simular sin timeout (`true` por defecto) |
| `MODERATION_COOLDOWN_SECONDS` | Segundos entre sanciones al mismo usuario |
| `MODERATION_PENALIZE_SPAM` / `MODERATION_PENALIZE_AUTOMATION` | Qué ejes pueden sancionar |
| `MODERATION_MIN_SPAM_SCORE` / `MODERATION_MIN_AUTOMATION_SCORE` | Umbral mínimo de score efectivo (híbrido incluido) |
| `MODERATION_TIMEOUT_*` | Duración en segundos por clasificación (`0` = off) |

La config por guild se guarda en SQLite (`guild_moderation`). `!mod reset` o **Restaurar defaults (.env)** en el dashboard elimina la fila del servidor.

### Canal de comandos (opcional)

```env
MOD_CONFIG_CHANNEL_ID=1234567890123456789
```

Solo ese canal acepta `!mod`. Si está vacío, cualquier canal del guild (con Gestionar servidor).

### Comandos Discord (`!mod`)

Prefijo del bot: `!` (ver `app/bot.py`).

| Comando | Ejemplo |
|---------|---------|
| Ayuda | `!mod help` |
| Resumen | `!mod status` |
| Activar moderación | `!mod enable on` · `!mod enable off` |
| Dry-run | `!mod dryrun on` · `!mod dryrun off` |
| Timeout spam (segundos, `0`=off) | `!mod timeout suspicious 600` · `!mod timeout spam_likely 3600` |
| Timeout automation | `!mod timeout automation_suspicious 300` · `!mod timeout automation_likely 600` |
| Penalizar por tipo | `!mod penalize spam on` · `!mod penalize automation off` |
| Score mínimo | `!mod minscore spam 40` · `!mod minscore automation 40` |
| Cooldown | `!mod cooldown 300` |
| Volver a `.env` | `!mod reset` |

Clasificaciones que pueden disparar timeout (según política en `app/moderation/policy.py`): `suspicious`, `spam_likely`, `automation_suspicious`, `automation_likely`, con scores efectivos tras reglas + híbrido ML.

### Dashboard

```powershell
python -m app.dashboard
```

Sidebar → **Config moderación** → elige guild → formulario → **Guardar**.

### Buenas prácticas

1. Probar con `!mod dryrun on` o dry-run activado en la web.
2. Activar `!mod enable on` solo cuando la política sea la deseada.
3. Revisar alertas en `ALERT_CHANNELS` antes de sancionar automáticamente.

---

## English

**Discord timeouts**, **off by default**. Per-guild setup without code changes: `!mod` commands or the dashboard **Config moderación** page.

Does not timeout bots or administrators. Uses a per-user **cooldown** to avoid punishing every message in a burst.

### Discord requirements

- Bot: **Moderate Members** permission and a role above the target member
- Configurers: **Manage Server** permission

### Defaults from `.env`

If there is no `guild_moderation` row for a guild, `MODERATION_*` from `.env` applies (see `.env.example`).

| Variable (examples) | Purpose |
|---------------------|---------|
| `MODERATION_ENABLED` | Enable real enforcement (`false` by default) |
| `MODERATION_DRY_RUN` | Log/simulate without timeout (`true` by default) |
| `MODERATION_COOLDOWN_SECONDS` | Minimum seconds between sanctions for the same user |
| `MODERATION_PENALIZE_SPAM` / `MODERATION_PENALIZE_AUTOMATION` | Which axes can sanction |
| `MODERATION_MIN_SPAM_SCORE` / `MODERATION_MIN_AUTOMATION_SCORE` | Minimum effective score (includes hybrid ML) |
| `MODERATION_TIMEOUT_*` | Duration in seconds per classification (`0` = off) |

Per-guild settings live in SQLite (`guild_moderation`). `!mod reset` or **Restaurar defaults (.env)** in the dashboard clears the guild row.

### Command channel (optional)

```env
MOD_CONFIG_CHANNEL_ID=1234567890123456789
```

Only that channel accepts `!mod`. If empty, any guild channel works (with Manage Server).

### Discord commands (`!mod`)

Bot prefix: `!` (see `app/bot.py`).

| Command | Example |
|---------|---------|
| Help | `!mod help` |
| Summary | `!mod status` |
| Enable moderation | `!mod enable on` · `!mod enable off` |
| Dry-run | `!mod dryrun on` · `!mod dryrun off` |
| Spam timeouts (seconds, `0`=off) | `!mod timeout suspicious 600` · `!mod timeout spam_likely 3600` |
| Automation timeouts | `!mod timeout automation_suspicious 300` · `!mod timeout automation_likely 600` |
| Penalize by axis | `!mod penalize spam on` · `!mod penalize automation off` |
| Minimum score | `!mod minscore spam 40` · `!mod minscore automation 40` |
| Cooldown | `!mod cooldown 300` |
| Revert to `.env` | `!mod reset` |

Classifications that may trigger a timeout (see `app/moderation/policy.py`): `suspicious`, `spam_likely`, `automation_suspicious`, `automation_likely`, using effective scores after rules + optional ML hybrid.

### Dashboard

```powershell
python -m app.dashboard
```

Sidebar → **Config moderación** → select guild → form → **Guardar**.

### Recommended rollout

1. Start with `!mod dryrun on` or dry-run enabled in the web UI.
2. Enable `!mod enable on` only when policy matches your intent.
3. Review `ALERT_CHANNELS` alerts before relying on automatic timeouts.
