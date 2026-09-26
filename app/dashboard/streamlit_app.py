from __future__ import annotations

import asyncio
from datetime import datetime

import streamlit as st

from app.dashboard.queries import (
    list_guild_ids,
    list_suspicious_users,
    list_user_ids_in_guild,
    overview_stats,
    recent_alerts,
    user_message_timeline,
    user_profile_snapshot,
)
from app.dataset.labels import VALID_DATASET_LABELS
from app.dataset.storage import apply_dataset_label, backfill_dataset_samples
from app.moderation.settings import ModerationSettings, format_moderation_summary
from app.moderation.store import (
    get_effective_moderation,
    reset_guild_moderation,
    save_guild_moderation,
)
from app.storage.database import init_db

PAGES = ["Resumen", "Usuarios sospechosos", "Investigación", "Config moderación"]


def _run_async(coro):
    return asyncio.run(coro)


@st.cache_resource
def _bootstrap_db() -> bool:
    _run_async(init_db())
    return True


def _init_session_state() -> None:
    defaults = {
        "nav_page": "Resumen",
        "inv_guild_id": "",
        "inv_user_id": "",
        "inv_only_relevant": True,
        "inv_page": 1,
        "inv_page_size": 12,
        "susp_guild": "(todos)",
        "susp_min_score": 1,
        "mod_guild_id": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _go_investigation(guild_id: str, user_id: str) -> None:
    st.session_state.inv_guild_id = guild_id
    st.session_state.inv_user_id = user_id
    st.session_state.nav_page = "Investigación"
    st.session_state.inv_page = 1
    st.rerun()


def _format_ts(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def _preview(text: str, max_len: int = 72) -> str:
    one_line = text.replace("\n", " ").strip()
    if len(one_line) <= max_len:
        return one_line or "(vacío)"
    return one_line[: max_len - 1] + "…"


def _classification_badge(spam_cls: str | None, auto_cls: str | None) -> str:
    parts: list[str] = []
    if spam_cls and spam_cls != "normal":
        parts.append(f"spam:{spam_cls}")
    if auto_cls and auto_cls != "normal":
        parts.append(f"auto:{auto_cls}")
    return " · ".join(parts) if parts else "normal"


def _render_signal_chips(signals: dict | None) -> None:
    if not signals:
        st.caption("Sin señales registradas.")
        return
    spam = signals.get("spam") or []
    auto = signals.get("automation") or []
    ml = signals.get("ml")
    hybrid = signals.get("hybrid")
    cols = st.columns(2)
    with cols[0]:
        if spam:
            st.markdown("**Spam:** " + ", ".join(f"`{s}`" for s in spam))
        if auto:
            st.markdown("**Automation:** " + ", ".join(f"`{s}`" for s in auto))
    with cols[1]:
        if isinstance(ml, dict):
            sp = ml.get("spam_probability")
            ap = ml.get("automation_probability")
            if sp is not None or ap is not None:
                st.markdown(f"**ML:** spam_p={sp} · auto_p={ap}")
        if isinstance(hybrid, dict):
            eff_s = hybrid.get("spam_score_effective")
            eff_a = hybrid.get("automation_score_effective")
            if eff_s is not None or eff_a is not None:
                st.markdown(f"**Híbrido:** spam={eff_s} · auto={eff_a}")


def _render_profile_summary(guild_id: str, user_id: str) -> None:
    profile = user_profile_snapshot(guild_id, user_id)
    if not profile:
        st.info("Sin snapshot en `user_features` para este usuario.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Mensajes", profile.get("total_messages", "—"))
    c2.metric("Spam (perfil)", profile.get("spam_score", "—"))
    c3.metric("Automation", profile.get("automation_score", "—"))
    c4.metric("Dup. ratio", f"{profile.get('duplicate_ratio', 0):.2f}")
    c5.metric("Msgs / 10s", profile.get("messages_last_10s", "—"))

    flags: list[str] = []
    if profile.get("burst_activity"):
        flags.append("ráfaga")
    if profile.get("cross_channel_repetition"):
        flags.append("cross-channel")
    if profile.get("repeated_domain"):
        flags.append("dominio repetido")
    if profile.get("high_similarity_content"):
        flags.append("contenido similar")
    if flags:
        st.caption("Señales de perfil: " + ", ".join(flags))

    with st.expander("Perfil completo (JSON)", expanded=False):
        st.json(profile)


def _page_overview() -> None:
    stats = overview_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mensajes", stats.messages)
    c2.metric("Detecciones", stats.detections)
    c3.metric("Alertas", stats.alerts)
    c4.metric("Usuarios (detecciones)", stats.users)
    st.caption(
        f"Dataset: {stats.dataset_samples} muestras ({stats.dataset_labeled} etiquetadas)"
    )

    st.subheader("Alertas recientes")
    alerts = recent_alerts(limit=20)
    if not alerts:
        st.info("No hay alertas todavía.")
        return

    for alert in alerts:
        cols = st.columns([2, 2, 2, 2, 1])
        cols[0].write(_format_ts(alert.timestamp))
        cols[1].write(f"user `{alert.user_id}`")
        cols[2].write(f"spam **{alert.spam_score}** · auto **{alert.automation_score}**")
        cols[3].write(f"guild `{alert.guild_id}`")
        if cols[4].button("Investigar", key=f"alert-inv-{alert.user_id}-{alert.timestamp}"):
            _go_investigation(alert.guild_id, alert.user_id)


def _page_suspicious() -> None:
    guilds = list_guild_ids()
    guild_options = ["(todos)"] + guilds
    idx = (
        guild_options.index(st.session_state.susp_guild)
        if st.session_state.susp_guild in guild_options
        else 0
    )
    guild_filter = st.selectbox(
        "Servidor (guild)",
        guild_options,
        index=idx,
        key="susp_guild_select",
    )
    st.session_state.susp_guild = guild_filter

    min_score = st.slider(
        "Puntuación mínima (spam o automation)",
        0,
        100,
        st.session_state.susp_min_score,
        key="susp_min_slider",
    )
    st.session_state.susp_min_score = min_score

    rows = list_suspicious_users(
        guild_id=None if guild_filter == "(todos)" else guild_filter,
        min_score=min_score,
        limit=80,
    )
    if not rows:
        st.info("Ningún usuario coincide con el filtro.")
        return

    st.caption(f"{len(rows)} usuario(s). Usa **Investigar** para abrir la timeline.")
    for row in rows:
        with st.container(border=True):
            cols = st.columns([2, 2, 2, 2, 1])
            cols[0].markdown(f"**Usuario** `{row.user_id}`")
            cols[1].markdown(f"Guild `{row.guild_id}`")
            cols[2].markdown(
                f"Spam **{row.max_spam_score}** · Auto **{row.max_automation_score}**"
            )
            cols[3].markdown(
                f"{row.flagged_events} eventos · {_format_ts(row.last_activity)}"
            )
            if cols[4].button("Investigar", key=f"susp-{row.guild_id}-{row.user_id}"):
                _go_investigation(row.guild_id, row.user_id)


def _investigation_selector() -> tuple[str, str] | None:
    guilds = list_guild_ids()
    if not guilds:
        st.warning("No hay guilds en la base de datos. Ejecuta el bot y genera tráfico.")
        return None

    saved_guild = st.session_state.inv_guild_id.strip()
    if saved_guild and saved_guild not in guilds:
        guilds = [saved_guild] + guilds

    guild_index = guilds.index(saved_guild) if saved_guild in guilds else 0

    st.markdown("#### Selección de usuario")
    c1, c2 = st.columns(2)
    with c1:
        guild_id = st.selectbox(
            "Servidor (guild)",
            guilds,
            index=guild_index,
            key="inv_guild_select",
        )
    st.session_state.inv_guild_id = guild_id

    users = list_user_ids_in_guild(guild_id)
    user_ids = [u for u, _ in users]
    saved_user = st.session_state.inv_user_id.strip()
    if saved_user and saved_user not in user_ids:
        user_ids = [saved_user] + user_ids

    user_index = user_ids.index(saved_user) if saved_user in user_ids else 0
    with c2:
        if user_ids:
            user_id = st.selectbox(
                "Usuario",
                user_ids,
                index=min(user_index, len(user_ids) - 1),
                key="inv_user_select",
                format_func=lambda uid: uid,
            )
        else:
            st.caption("Sin usuarios en este guild.")
            user_id = st.text_input("User ID (manual)", value=saved_user, key="inv_user_manual")
    st.session_state.inv_user_id = user_id.strip()

    with st.expander("Pegar IDs manualmente", expanded=not user_ids):
        manual_g = st.text_input("Guild ID", value=guild_id, key="inv_guild_manual")
        manual_u = st.text_input("User ID", value=user_id, key="inv_user_manual2")
        if st.button("Aplicar IDs", key="inv_apply_manual"):
            st.session_state.inv_guild_id = manual_g.strip()
            st.session_state.inv_user_id = manual_u.strip()
            st.session_state.inv_page = 1
            st.rerun()

    guild_id = st.session_state.inv_guild_id.strip()
    user_id = st.session_state.inv_user_id.strip()
    if not guild_id or not user_id:
        return None
    return guild_id, user_id


def _page_investigation() -> None:
    pair = _investigation_selector()
    if pair is None:
        return
    guild_id, user_id = pair

    st.markdown(f"### Investigación · `{user_id}` en `{guild_id}`")

    _render_profile_summary(guild_id, user_id)

    tool_cols = st.columns([2, 2, 2, 2])
    with tool_cols[0]:
        only_relevant = st.checkbox(
            "Solo mensajes relevantes",
            value=st.session_state.inv_only_relevant,
            help="Oculta mensajes normal sin señales ni alertas.",
            key="inv_only_relevant_cb",
        )
        st.session_state.inv_only_relevant = only_relevant
    with tool_cols[1]:
        page_size = st.selectbox(
            "Por página",
            [8, 12, 20, 40],
            index=[8, 12, 20, 40].index(st.session_state.inv_page_size)
            if st.session_state.inv_page_size in [8, 12, 20, 40]
            else 1,
            key="inv_page_size_select",
        )
        st.session_state.inv_page_size = page_size
    with tool_cols[2]:
        if st.button("Backfill dataset", help="Crea filas dataset_samples faltantes"):
            created, skipped = _run_async(
                backfill_dataset_samples(guild_id=guild_id, user_id=user_id)
            )
            st.success(f"Dataset: {created} creadas, {skipped} omitidas.")
            st.rerun()
    with tool_cols[3]:
        if st.button("Recargar timeline"):
            st.rerun()

    rows = user_message_timeline(
        guild_id,
        user_id,
        limit=120,
        only_relevant=only_relevant,
    )
    if not rows:
        st.warning("Sin mensajes para este par guild/user (o ninguno pasa el filtro).")
        return

    total_pages = max(1, (len(rows) + page_size - 1) // page_size)
    page = st.number_input(
        "Página",
        min_value=1,
        max_value=total_pages,
        value=min(st.session_state.inv_page, total_pages),
        key="inv_page_input",
    )
    st.session_state.inv_page = int(page)
    start = (int(page) - 1) * page_size
    chunk = rows[start : start + page_size]

    st.caption(
        f"Mostrando {len(chunk)} de {len(rows)} mensaje(s) · "
        f"ordenados del más reciente al más antiguo."
    )

    labels = sorted(VALID_DATASET_LABELS)
    for row in chunk:
        badge = _classification_badge(row.spam_classification, row.automation_classification)
        alert_mark = " 🔔" if row.triggered_alert else ""
        label_mark = f" · label=`{row.label}`" if row.label else ""
        header = (
            f"{_format_ts(row.timestamp)}{alert_mark} · "
            f"spam **{row.spam_score if row.spam_score is not None else '—'}** · "
            f"auto **{row.automation_score if row.automation_score is not None else '—'}** · "
            f"{badge}{label_mark}"
        )
        expanded = row.triggered_alert or badge != "normal"
        with st.expander(header, expanded=expanded):
            st.markdown(f"**Vista previa:** {_preview(row.content, 200)}")
            if row.content.strip():
                with st.expander("Contenido completo", expanded=False):
                    st.text(row.content)
            meta = st.columns(3)
            meta[0].code(row.message_id, language=None)
            meta[1].write(f"Canal `{row.channel_id}`")
            if row.urls:
                meta[2].write("URLs: " + ", ".join(str(u) for u in row.urls[:5]))

            _render_signal_chips(row.signals)

            current = row.label or "unknown"
            label_cols = st.columns([2, 1])
            choice = label_cols[0].selectbox(
                "Etiqueta dataset",
                labels,
                index=labels.index(current) if current in labels else 0,
                key=f"label-{row.message_id}",
            )
            if label_cols[1].button("Guardar", key=f"save-{row.message_id}"):
                ok = _run_async(apply_dataset_label(row.message_id, choice))
                if ok:
                    st.success(f"Etiqueta: {choice}")
                    st.rerun()
                else:
                    st.error("No se pudo guardar (mensaje no encontrado en SQLite).")

            with st.expander("Datos técnicos (JSON)", expanded=False):
                st.json(
                    {
                        "message_id": row.message_id,
                        "signals": row.signals,
                        "label": row.label,
                        "urls": row.urls,
                    }
                )


def _page_moderation_config() -> None:
    st.subheader("Configuración de moderación")
    st.caption(
        "Política por servidor en SQLite. El bot la aplica al instante. "
        "En Discord hace falta **Gestionar servidor** para `!mod`."
    )
    guilds = list_guild_ids()
    if not guilds:
        st.info("No hay guilds en la base de datos todavía.")
        return

    saved = st.session_state.mod_guild_id
    if saved and saved not in guilds:
        guilds = [saved] + guilds
    idx = guilds.index(saved) if saved in guilds else 0
    guild_id = st.selectbox("Servidor (guild)", guilds, index=idx, key="mod_guild_select")
    st.session_state.mod_guild_id = guild_id

    current = _run_async(get_effective_moderation(guild_id))

    with st.form("mod_config_form"):
        enabled = st.checkbox("Moderación activa", value=current.enabled)
        dry_run = st.checkbox("Dry-run (solo logs, sin timeout)", value=current.dry_run)
        c1, c2 = st.columns(2)
        with c1:
            penalize_spam = st.checkbox("Penalizar spam", value=current.penalize_spam)
            min_spam = st.number_input(
                "Score spam mínimo",
                min_value=0,
                max_value=100,
                value=current.min_effective_spam_score,
            )
            timeout_suspicious = st.number_input(
                "Timeout suspicious (s)",
                min_value=0,
                value=current.timeout_suspicious_seconds,
            )
            timeout_spam_likely = st.number_input(
                "Timeout spam_likely (s)",
                min_value=0,
                value=current.timeout_spam_likely_seconds,
            )
        with c2:
            penalize_auto = st.checkbox(
                "Penalizar automation", value=current.penalize_automation
            )
            min_auto = st.number_input(
                "Score automation mínimo",
                min_value=0,
                max_value=100,
                value=current.min_effective_automation_score,
            )
            timeout_auto_susp = st.number_input(
                "Timeout automation_suspicious (s)",
                min_value=0,
                value=current.timeout_automation_suspicious_seconds,
            )
            timeout_auto_likely = st.number_input(
                "Timeout automation_likely (s)",
                min_value=0,
                value=current.timeout_automation_likely_seconds,
            )
        cooldown = st.number_input(
            "Cooldown entre sanciones (s)",
            min_value=0,
            value=current.cooldown_seconds,
        )
        submitted = st.form_submit_button("Guardar configuración")

    if submitted:
        updated = ModerationSettings(
            enabled=enabled,
            dry_run=dry_run,
            cooldown_seconds=int(cooldown),
            penalize_spam=penalize_spam,
            penalize_automation=penalize_auto,
            min_effective_spam_score=int(min_spam),
            min_effective_automation_score=int(min_auto),
            timeout_spam_likely_seconds=int(timeout_spam_likely),
            timeout_suspicious_seconds=int(timeout_suspicious),
            timeout_automation_likely_seconds=int(timeout_auto_likely),
            timeout_automation_suspicious_seconds=int(timeout_auto_susp),
        )
        _run_async(save_guild_moderation(guild_id, updated))
        st.success("Guardado.")
        st.markdown(format_moderation_summary(updated))

    if st.button("Restaurar defaults (.env)", key="mod-reset"):
        _run_async(reset_guild_moderation(guild_id))
        st.success("Eliminada config del servidor; se usa .env.")
        st.rerun()

    st.divider()
    st.markdown(format_moderation_summary(current))


def main() -> None:
    st.set_page_config(
        page_title="Spam Detection Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _bootstrap_db()
    _init_session_state()

    st.sidebar.title("Navegación")
    page_index = (
        PAGES.index(st.session_state.nav_page)
        if st.session_state.nav_page in PAGES
        else 0
    )
    page = st.sidebar.radio("Vista", PAGES, index=page_index)
    st.session_state.nav_page = page

    if st.session_state.inv_guild_id and st.session_state.inv_user_id:
        st.sidebar.divider()
        st.sidebar.markdown("**Investigación activa**")
        st.sidebar.code(
            f"guild: {st.session_state.inv_guild_id}\nuser: {st.session_state.inv_user_id}",
            language=None,
        )
        if st.sidebar.button("Limpiar selección"):
            st.session_state.inv_guild_id = ""
            st.session_state.inv_user_id = ""
            st.rerun()

    st.title("Discord Spam Detection")
    st.caption("Investigación local sobre SQLite — sin autenticación.")

    if page == "Resumen":
        _page_overview()
    elif page == "Usuarios sospechosos":
        _page_suspicious()
    elif page == "Investigación":
        _page_investigation()
    else:
        _page_moderation_config()


if __name__ == "__main__":
    main()
