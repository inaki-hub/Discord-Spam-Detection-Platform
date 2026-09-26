from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class SchemaMigrationRecord(Base):
    """Migraciones de esquema aplicadas."""

    __tablename__ = "schema_migrations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MessageRecord(Base):
    """Mensaje de guild capturado por el collector (sin DMs)."""

    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("message_id", name="uq_messages_message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    channel_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    urls: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    attachments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    mentions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class MessageFeatureRecord(Base):
    """Características extraídas por mensaje."""

    __tablename__ = "message_features"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_message_features_message_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    features: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class UserRecord(Base):
    """Usuario observado en un servidor."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_users_guild_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserFeatureRecord(Base):
    """Snapshot del perfil comportamental por usuario y servidor."""

    __tablename__ = "user_features"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_user_features_guild_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DetectionRecord(Base):
    """Resultado de detección por mensaje/usuario."""

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    spam_score: Mapped[int | None] = mapped_column()
    automation_score: Mapped[int | None] = mapped_column()
    spam_classification: Mapped[str | None] = mapped_column(String(64))
    automation_classification: Mapped[str | None] = mapped_column(String(64))
    signals: Mapped[list | None] = mapped_column(JSON)


class DatasetSampleRecord(Base):
    """Muestra para entrenamiento / revisión humana."""

    __tablename__ = "dataset_samples"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_dataset_samples_message_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    channel_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message_features: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    user_features: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    spam_score: Mapped[int] = mapped_column(nullable=False, default=0)
    automation_score: Mapped[int] = mapped_column(nullable=False, default=0)
    spam_classification: Mapped[str] = mapped_column(String(64), nullable=False, default="normal")
    automation_classification: Mapped[str] = mapped_column(
        String(64), nullable=False, default="normal"
    )
    detection_signals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    label: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GuildModerationRecord(Base):
    """Configuración de moderación por servidor (UI Discord / dashboard)."""

    __tablename__ = "guild_moderation"

    guild_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AlertRecord(Base):
    """Alerta generada por el sistema."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    channel_id: Mapped[str | None] = mapped_column(String(32))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    spam_score: Mapped[int | None] = mapped_column()
    automation_score: Mapped[int | None] = mapped_column()
    signals: Mapped[list | None] = mapped_column(JSON)
    payload: Mapped[dict | None] = mapped_column(JSON)
