# Dataset

---

## Español

Registro en SQLite (`dataset_samples`) para **revisión humana** y **entrenamiento ML**. Cada fila enlaza un mensaje con features, perfil, scores de reglas y una etiqueta.

Relacionado: [ML.md](ML.md) · [README.md](README.md)

### Cuándo se crea una muestra

Por cada **mensaje nuevo** procesado en un guild, el bot inserta una fila con:

- `message_features` — características del mensaje
- `user_features` — snapshot del perfil en ese momento
- `spam_score`, `automation_score`, clasificaciones y señales de detección (reglas)
- `label` — por defecto `unknown`

Los scores guardados son los de **reglas**, no los inflados por el modo híbrido ML.

### Etiquetas válidas

| Label | Uso |
|-------|-----|
| `unknown` | Sin revisar (default) |
| `normal` | Comportamiento legítimo |
| `spam` | Spam manual / no automatizado |
| `automated_spam` | Spam con patrón automatizado |
| `legitimate_bot` | Bot o automatización aceptable |

### Etiquetar

**CLI** (usa el ID real del mensaje en Discord):

```bash
python -m app.dataset.cli label 1553074113688641588 spam
```

**Dashboard:** `python -m app.dashboard` → **Investigación** → selector de etiqueta en la timeline del usuario.

### Exportar (JSONL)

Un objeto JSON por línea. Rutas relativas se escriben bajo `data/`.

```bash
python -m app.dataset.cli export -o dataset_export.jsonl
python -m app.dataset.cli export -o guild.jsonl --guild-id TU_GUILD_ID
```

Ejemplo de campos:

```json
{
  "message_id": "...",
  "guild_id": "...",
  "channel_id": "...",
  "user_id": "...",
  "timestamp": "2026-09-25T12:00:00+00:00",
  "message_features": {},
  "user_features": {},
  "spam_score": 90,
  "automation_score": 65,
  "spam_classification": "spam_likely",
  "automation_classification": "automation_suspicious",
  "detection_signals": { "spam": [], "automation": [] },
  "label": "unknown"
}
```

### Mensajes sin fila en `dataset_samples`

Si hay mensajes antiguos en SQLite pero no muestras de dataset, en el dashboard verás entradas MESSAGE/DETECTION sin DATASET.

**Backfill:**

```bash
python -m app.dataset.cli backfill
python -m app.dataset.cli backfill --guild-id GUILD_ID --user-id USER_ID
python -m app.dataset.cli backfill --limit 500
```

O en **Investigación** → **Generar filas dataset (backfill)**.

---

## English

SQLite table `dataset_samples` for **human review** and **ML training**. Each row ties a message to features, profile snapshot, rule-based scores, and a label.

See also: [ML.md](ML.md) · [README.md](README.md)

### When a sample is created

For each **new** guild message the bot processes, it inserts a row with:

- `message_features` — per-message features
- `user_features` — profile snapshot at that time
- `spam_score`, `automation_score`, classifications, and detection signals (rules)
- `label` — defaults to `unknown`

Stored scores are **rule-based**, not ML-hybrid inflated scores.

### Valid labels

| Label | Meaning |
|-------|---------|
| `unknown` | Not reviewed (default) |
| `normal` | Legitimate behavior |
| `spam` | Manual / non-automated spam |
| `automated_spam` | Automated spam pattern |
| `legitimate_bot` | Acceptable bot or automation |

### Labeling

**CLI** (use the real Discord message ID):

```bash
python -m app.dataset.cli label 1553074113688641588 spam
```

**Dashboard:** `python -m app.dashboard` → **Investigación** → label selector on the user timeline.

### Export (JSONL)

One JSON object per line. Relative paths are written under `data/`.

```bash
python -m app.dataset.cli export -o dataset_export.jsonl
python -m app.dataset.cli export -o guild.jsonl --guild-id YOUR_GUILD_ID
```

Example fields:

```json
{
  "message_id": "...",
  "guild_id": "...",
  "channel_id": "...",
  "user_id": "...",
  "timestamp": "2026-09-25T12:00:00+00:00",
  "message_features": {},
  "user_features": {},
  "spam_score": 90,
  "automation_score": 65,
  "spam_classification": "spam_likely",
  "automation_classification": "automation_suspicious",
  "detection_signals": { "spam": [], "automation": [] },
  "label": "unknown"
}
```

### Messages without a `dataset_samples` row

Older SQLite data may show MESSAGE/DETECTION events in the dashboard without DATASET rows.

**Backfill:**

```bash
python -m app.dataset.cli backfill
python -m app.dataset.cli backfill --guild-id GUILD_ID --user-id USER_ID
python -m app.dataset.cli backfill --limit 500
```

Or in **Investigación** → **Generar filas dataset (backfill)**.
