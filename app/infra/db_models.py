from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lang: Mapped[str] = mapped_column(String(2), nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text)
    tz: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str | None] = mapped_column(Text)
    employment_types: Mapped[list[str] | None] = mapped_column(JSON)
    skills: Mapped[list[str] | None] = mapped_column(JSON)
    locations: Mapped[list[str] | None] = mapped_column(JSON)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    formats: Mapped[list[str] | None] = mapped_column(JSON)
    experience_yrs: Mapped[int | None] = mapped_column(Integer)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    redirect_url: Mapped[str] = mapped_column(Text, primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BlacklistCompany(Base):
    __tablename__ = "blacklist_companies"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company: Mapped[str] = mapped_column(Text, primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    schedule_cron: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Applied(Base):
    __tablename__ = "applied"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    redirect_url: Mapped[str] = mapped_column(Text, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ShownCache(Base):
    __tablename__ = "shown_cache"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vacancy_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Complaint(Base):
    __tablename__ = "complaints"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    redirect_url: Mapped[str] = mapped_column(Text, primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)


class UiSession(Base):
    __tablename__ = "ui_sessions"
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    anchor_message_id: Mapped[int | None] = mapped_column(BigInteger)
    screen_state: Mapped[str] = mapped_column(String(64), nullable=False, default="welcome")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default={})
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
