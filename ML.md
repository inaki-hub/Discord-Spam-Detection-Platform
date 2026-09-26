# Machine Learning

---

## Español

Capa **supervisada opcional** (`SpamDetector` / `AutomationDetector` siguen siendo la base). **No** aplica moderación por sí sola.

### Requisitos

- Filas en `dataset_samples` con `label != unknown`
- Mínimo por tarea al entrenar: **20 muestras** (spam y automation por separado; configurable con `--min-samples`)

### Etiquetas → objetivos de entrenamiento

| Tarea | Clase positiva (1) | Clase negativa (0) |
|-------|--------------------|--------------------|
| **Spam** | `spam`, `automated_spam` | `normal`, `legitimate_bot` |
| **Automation** | `automated_spam`, `legitimate_bot` | `normal`, `spam` |

**Features del modelo:** `message_features`, `user_features`, scores de reglas y presencia de señales.

### Entrenar y comprobar

```bash
python -m app.ml.cli train --min-samples 20
python -m app.ml.cli train --guild-id GUILD_ID -o data/models/ml_bundle.joblib
python -m app.ml.cli status
```

Salida por defecto: `data/models/ml_bundle.joblib` (bundle joblib con pipelines sklearn para spam y automation).

### Inferencia en el bot

```env
ML_ENABLED=true
# ML_MODEL_PATH=data/models/ml_bundle.joblib
```

Si el modelo existe y carga correctamente, el bot registra `[ML] spam_p=… auto_p=…` y guarda probabilidades en `detections.signals.ml`.

Si `ML_ENABLED=true` pero no hay modelo válido, verás un warning al arrancar.

### Modo híbrido (`ML_HYBRID_ENABLED`, default `true`)

Solo aplica cuando hay predicción ML (`ML_ENABLED=true` y modelo cargado):

1. **Boost acotado:** score efectivo = score de reglas + `ML_SCORE_BOOST_MAX × probabilidad` (tope 100).
2. **Alerta con contexto:** si las reglas están en `normal` pero la probabilidad supera el umbral **y** el perfil cumple contexto (duplicados, ráfaga, etc.), puede alertarse con señales como `ml_high_spam_probability` o `ml_high_automation_probability`.
3. Los embeds de alerta pueden mostrar score efectivo, reglas base y probabilidades ML.

Variables relevantes (ver `.env.example`): `ML_SCORE_BOOST_MAX`, `ML_ALERT_SPAM_THRESHOLD`, `ML_ALERT_AUTOMATION_THRESHOLD`, `ML_HYBRID_MIN_DUPLICATE_RATIO`.

El **dataset** y el perfil persistido siguen usando **solo scores de reglas** para no sesgar el entrenamiento.

### Enfoque

```text
REGLAS (scores + señales)  +  ML (probabilidades)  →  revisión humana / alertas
```

---

## English

Optional **supervised** layer (`SpamDetector` / `AutomationDetector` remain the foundation). ML **does not** trigger moderation by itself.

### Requirements

- Rows in `dataset_samples` with `label != unknown`
- Minimum per task when training: **20 samples** (spam and automation separately; override with `--min-samples`)

### Labels → training targets

| Task | Positive (1) | Negative (0) |
|------|--------------|--------------|
| **Spam** | `spam`, `automated_spam` | `normal`, `legitimate_bot` |
| **Automation** | `automated_spam`, `legitimate_bot` | `normal`, `spam` |

**Model features:** `message_features`, `user_features`, rule scores, and signal flags.

### Train and inspect

```bash
python -m app.ml.cli train --min-samples 20
python -m app.ml.cli train --guild-id GUILD_ID -o data/models/ml_bundle.joblib
python -m app.ml.cli status
```

Default output: `data/models/ml_bundle.joblib` (joblib bundle with sklearn pipelines for spam and automation).

### Bot inference

```env
ML_ENABLED=true
# ML_MODEL_PATH=data/models/ml_bundle.joblib
```

When the model loads, the bot logs `[ML] spam_p=… auto_p=…` and stores probabilities in `detections.signals.ml`.

If `ML_ENABLED=true` but no valid model exists, startup logs a warning.

### Hybrid mode (`ML_HYBRID_ENABLED`, default `true`)

Applies only when ML predictions are available (`ML_ENABLED=true` and model loaded):

1. **Bounded boost:** effective score = rule score + `ML_SCORE_BOOST_MAX × probability` (capped at 100).
2. **Contextual ML alert:** if rules are `normal` but probability exceeds the threshold **and** the profile matches context (duplicates, burst, etc.), an alert may fire with signals such as `ml_high_spam_probability` or `ml_high_automation_probability`.
3. Discord alert embeds may show effective score, rule baseline, and ML probabilities.

See `.env.example` for `ML_SCORE_BOOST_MAX`, `ML_ALERT_SPAM_THRESHOLD`, `ML_ALERT_AUTOMATION_THRESHOLD`, `ML_HYBRID_MIN_DUPLICATE_RATIO`.

The **dataset** and stored profile scores remain **rule-only** to avoid training bias.

### Approach

```text
RULES (scores + signals)  +  ML (probabilities)  →  human review / alerts
```
