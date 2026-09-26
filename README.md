# Discord Spam Detection Platform

---

## Español

### Qué hace este proyecto

Bot de Discord que **observa mensajes en servidores** (no DMs), extrae señales comportamentales, calcula scores de spam y automatización, guarda todo en **SQLite** y puede **alertar** a un canal de moderación. Incluye un **dashboard Streamlit** local, un **dataset etiquetable** para revisión humana y **ML supervisado opcional**.

Las decisiones se basan en reglas explicables; el ML, si se activa, complementa alertas y scores efectivos sin sustituir las reglas base en el dataset.

**Documentación adicional:** [DATASET.md](DATASET.md) · [ML.md](ML.md) · [MODERATION.md](MODERATION.md)

### Requisitos

- Python **3.12+**
- Bot en el [Developer Portal](https://discord.com/developers/applications) con el intent **Message Content** activado
- Permisos del bot en el servidor: leer/enviar mensajes en los canales que quieras monitorizar; para alertas y timeouts, ver secciones correspondientes

### Instalación

```bash
cd "Discord Spam Detection Platform"
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` y define al menos `DISCORD_TOKEN`.

En Windows, si `python` no está en el PATH, usa `.\.venv\Scripts\python.exe` en lugar de `python`.

### Configuración principal (`.env`)

| Variable | Descripción |
|----------|-------------|
| `DISCORD_TOKEN` | Token del bot (obligatorio) |
| `DATABASE_URL` | SQLite async (por defecto `sqlite+aiosqlite:///./data/spam_detector.db`) |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DATA_RETENTION_DAYS` | Purga de datos antiguos al abrir la BD (`0` = desactivado) |
| `ALERT_CHANNELS` | Canal(es) para embeds de alerta (ver abajo) |
| `ML_*` | Inferencia y modo híbrido ([ML.md](ML.md)) |
| `MODERATION_*` | Defaults de timeouts ([MODERATION.md](MODERATION.md)) |
| `MOD_CONFIG_CHANNEL_ID` | Canal único para comandos `!mod` (opcional) |

Plantilla completa: [.env.example](.env.example).

### Ejecutar el bot

Desde la raíz del proyecto (con el venv activado):

```bash
python -m app.bot
```

Salida esperada: `Discord bot started`.

Por cada mensaje nuevo en un guild verás una línea `[MESSAGE]` con guild, canal, usuario y timestamp.

**Flujo de procesamiento:**

```text
Mensaje Discord
  → MessageCollector / MessageEvent
  → extract_message_features + UserProfileStore
  → SpamDetector + AutomationDetector
  → (opcional) MlAdvisor
  → evaluate_hybrid (alertas / scores efectivos)
  → SQLite: messages, message_features, user_features, detections, dataset_samples
  → AlertManager + (opcional) embed en ALERT_CHANNELS
  → (opcional) timeouts si moderación activada
```

Con `LOG_LEVEL=DEBUG`: `[FEATURES]`, `[PROFILE]`. En INFO, señales como `burst_activity`, `duplicate_content`, `similar_content`, `cross_channel_repetition`, `repeated_domain`. Si hay alerta: bloque `[ALERT]` (WARNING) y fila en `alerts`.

### Alertas en Discord (opcional)

```env
# Recomendado: guild_id:channel_id (varios separados por coma)
ALERT_CHANNELS=GUILD_ID:CHANNEL_ID

# Atajo: solo channel_id (un servidor / un canal)
ALERT_CHANNELS=CHANNEL_ID
```

El bot necesita **ver y enviar mensajes** en ese canal. **Un embed por usuario**: alertas nuevas del mismo usuario **editan** el mensaje existente.

### Retención de datos (opcional)

```env
DATA_RETENTION_DAYS=90
```

Se ejecuta al inicializar la base de datos (bot, dashboard o CLIs que llaman a `init_db`). Afecta mensajes, features, detecciones, alertas y perfiles inactivos. Las muestras del dataset con etiqueta distinta de `unknown` **no** se borran.

### Dashboard local

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.dashboard
```

URL: `http://127.0.0.1:8501`. **Sin autenticación** — solo uso local.

Vistas: **Resumen**, **Usuarios sospechosos**, **Investigación** (timeline, señales, etiquetado), **Config moderación**.

Alternativa:

```powershell
$env:PYTHONPATH = (Get-Location).Path
streamlit run app/dashboard/streamlit_app.py --server.address=127.0.0.1
```

No uses `app/dashboard/app.py`: el nombre `app.py` entra en conflicto con el paquete `app`.

### Dataset y ML

- Etiquetado y exportación: [DATASET.md](DATASET.md)
- Entrenamiento e inferencia: [ML.md](ML.md)

Resumen rápido:

```bash
python -m app.dataset.cli label MESSAGE_ID spam
python -m app.ml.cli train --min-samples 20
```

```env
ML_ENABLED=true
```

### Moderación (opt-in)

Los **timeouts** no están activos por defecto (`MODERATION_ENABLED=false`). Configuración por servidor vía `!mod` o dashboard. Detalle: [MODERATION.md](MODERATION.md).

### Tests

```bash
pytest
```

### Estructura del repositorio

```text
app/
  bot.py              # Entrada del bot
  config.py           # Variables de entorno
  collector/          # Eventos de mensaje
  storage/            # SQLAlchemy + SQLite + retención
  features/           # Señales y perfiles de usuario
  detection/          # Motores de reglas + híbrido ML
  ml/                 # Entrenamiento e inferencia opcional
  alerts/             # AlertManager + notificaciones Discord
  dashboard/          # Streamlit
  dataset/            # Muestras, export, etiquetas
  moderation/         # Política, timeouts, comandos !mod
tests/
data/                 # SQLite y modelos (gitignored)
```

### Privacidad

- Solo mensajes en **guilds** (no DMs).
- Se almacenan IDs, contenido, URLs, adjuntos y menciones necesarios para el análisis.
- Timeouts automáticos solo si activas moderación y desactivas dry-run.

### Problemas habituales

| Síntoma | Qué comprobar |
|---------|----------------|
| `DISCORD_TOKEN no configurado` | Copiar `.env.example` → `.env` y rellenar el token |
| `python` no reconocido (Windows) | Usar `.\.venv\Scripts\python.exe` o activar el venv |
| No llegan embeds | `ALERT_CHANNELS`, permisos del bot, formato `guild:channel` o solo `channel_id` |
| `ML_ENABLED=true` pero warning de modelo | Entrenar con `python -m app.ml.cli train` y revisar `ML_MODEL_PATH` |
| `label` falla | Usar el ID numérico del mensaje (17–20 dígitos), no el texto `MESSAGE_ID` |
| Dashboard sin filas DATASET | `python -m app.dataset.cli backfill` o botón en **Investigación** |

### Licencia

Ver [LICENSE](LICENSE).

---

## English

### What this project does

A Discord bot that **monitors guild messages** (not DMs), extracts behavioral signals, computes spam and automation scores, persists data in **SQLite**, and can **notify** a moderation channel. It includes a local **Streamlit dashboard**, a **labelable dataset** for human review, and **optional supervised ML**.

Decisions are driven by explainable rules. When enabled, ML complements alerts and effective scores without replacing rule-based scores stored in the dataset.

**Further docs:** [DATASET.md](DATASET.md) · [ML.md](ML.md) · [MODERATION.md](MODERATION.md)

### Requirements

- Python **3.12+**
- A bot in the [Developer Portal](https://discord.com/developers/applications) with **Message Content** intent enabled
- Bot permissions: read/send in channels you monitor; for alerts and timeouts see the relevant sections

### Installation

```bash
cd "Discord Spam Detection Platform"
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set at least `DISCORD_TOKEN`.

On Windows, if `python` is not on PATH, use `.\.venv\Scripts\python.exe` instead of `python`.

### Main configuration (`.env`)

| Variable | Description |
|----------|-------------|
| `DISCORD_TOKEN` | Bot token (required) |
| `DATABASE_URL` | Async SQLite (default `sqlite+aiosqlite:///./data/spam_detector.db`) |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DATA_RETENTION_DAYS` | Purge old rows on DB init (`0` = disabled) |
| `ALERT_CHANNELS` | Channel(s) for alert embeds (see below) |
| `ML_*` | Inference and hybrid mode ([ML.md](ML.md)) |
| `MODERATION_*` | Default timeout settings ([MODERATION.md](MODERATION.md)) |
| `MOD_CONFIG_CHANNEL_ID` | Single channel for `!mod` commands (optional) |

Full template: [.env.example](.env.example).

### Run the bot

From the project root (venv activated):

```bash
python -m app.bot
```

Expected log line: `Discord bot started`.

Each new guild message logs `[MESSAGE]` with guild, channel, user, and timestamp.

**Processing pipeline:**

```text
Discord message
  → MessageCollector / MessageEvent
  → extract_message_features + UserProfileStore
  → SpamDetector + AutomationDetector
  → (optional) MlAdvisor
  → evaluate_hybrid (alerts / effective scores)
  → SQLite: messages, message_features, user_features, detections, dataset_samples
  → AlertManager + (optional) embed to ALERT_CHANNELS
  → (optional) timeouts when moderation is enabled
```

With `LOG_LEVEL=DEBUG`: `[FEATURES]`, `[PROFILE]`. At INFO, signals such as `burst_activity`, `duplicate_content`, `similar_content`, `cross_channel_repetition`, `repeated_domain`. Alerts log `[ALERT]` (WARNING) and a row in `alerts`.

### Discord alerts (optional)

```env
# Recommended: guild_id:channel_id (comma-separated for multiple)
ALERT_CHANNELS=GUILD_ID:CHANNEL_ID

# Shortcut: channel_id only (single guild / channel)
ALERT_CHANNELS=CHANNEL_ID
```

The bot must **view and send messages** in that channel. **One embed per user**: new alerts for the same user **edit** the existing message.

### Data retention (optional)

```env
DATA_RETENTION_DAYS=90
```

Runs when the database is initialized (bot, dashboard, or CLIs that call `init_db`). Affects messages, features, detections, alerts, and inactive profiles. Dataset samples labeled other than `unknown` are **not** deleted.

### Local dashboard

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.dashboard
```

URL: `http://127.0.0.1:8501`. **No authentication** — local use only.

Pages: **Resumen** (Overview metrics), **Usuarios sospechosos**, **Investigación** (timeline, signals, labeling), **Config moderación**.

Alternative:

```powershell
$env:PYTHONPATH = (Get-Location).Path
streamlit run app/dashboard/streamlit_app.py --server.address=127.0.0.1
```

Do not use `app/dashboard/app.py`: the filename conflicts with the `app` package.

### Dataset and ML

- Labeling and export: [DATASET.md](DATASET.md)
- Training and inference: [ML.md](ML.md)

Quick start:

```bash
python -m app.dataset.cli label MESSAGE_ID spam
python -m app.ml.cli train --min-samples 20
```

```env
ML_ENABLED=true
```

### Moderation (opt-in)

**Timeouts are off by default** (`MODERATION_ENABLED=false`). Per-guild setup via `!mod` or the dashboard. Details: [MODERATION.md](MODERATION.md).

### Tests

```bash
pytest
```

### Repository layout

```text
app/
  bot.py              # Bot entrypoint
  config.py           # Environment settings
  collector/          # Message events
  storage/            # SQLAlchemy + SQLite + retention
  features/           # Signals and user profiles
  detection/          # Rule engines + ML hybrid
  ml/                 # Optional training/inference
  alerts/             # AlertManager + Discord notifications
  dashboard/          # Streamlit
  dataset/            # Samples, export, labels
  moderation/         # Policy, timeouts, !mod commands
tests/
data/                 # SQLite and models (gitignored)
```

### Privacy

- **Guild** messages only (no DMs).
- Stores IDs, content, URLs, attachments, and mentions needed for analysis.
- Automatic timeouts only if moderation is enabled and dry-run is off.

### Troubleshooting

| Symptom | What to check |
|---------|----------------|
| `DISCORD_TOKEN no configurado` | Copy `.env.example` → `.env` and set the token |
| `python` not found (Windows) | Use `.\.venv\Scripts\python.exe` or activate the venv |
| No alert embeds | `ALERT_CHANNELS`, bot permissions, `guild:channel` or `channel_id` format |
| `ML_ENABLED=true` but model warning | Run `python -m app.ml.cli train` and check `ML_MODEL_PATH` |
| `label` command fails | Use the numeric message ID (17–20 digits), not the literal `MESSAGE_ID` |
| No DATASET rows in dashboard | `python -m app.dataset.cli backfill` or the button under **Investigación** |

### License

See [LICENSE](LICENSE).
