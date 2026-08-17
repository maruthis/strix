from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .time_utils import utcnow


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return utcnow()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# --------------------------------------------------------------------------
# Org / auth
# --------------------------------------------------------------------------


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    subscription: Mapped["Subscription | None"] = relationship(back_populates="organization", uselist=False, cascade="all, delete-orphan")
    pr_review_settings: Mapped["PRReviewSettings | None"] = relationship(back_populates="organization", uselist=False, cascade="all, delete-orphan")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, default="")
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String, default="admin")  # admin | member

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Session_(TimestampMixin, Base):
    """Server-side session token backing the auth cookie."""

    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    active_org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)


class OtpCode(TimestampMixin, Base):
    __tablename__ = "otp_codes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String, index=True)
    code: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class Invitation(TimestampMixin, Base):
    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="member")
    token: Mapped[str] = mapped_column(String, default=lambda: uuid.uuid4().hex)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------
# Assets: repositories & domains
# --------------------------------------------------------------------------


class Repository(TimestampMixin, Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    provider: Mapped[str] = mapped_column(String, default="github")
    full_name: Mapped[str] = mapped_column(String)  # e.g. "maruthis/anything-llm"
    default_branch: Mapped[str] = mapped_column(String, default="main")
    auto_review_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    installation_id: Mapped[str | None] = mapped_column(String, nullable=True)


class Domain(TimestampMixin, Base):
    __tablename__ = "domains"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    hostname: Mapped[str] = mapped_column(String)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_method: Mapped[str] = mapped_column(String, default="dns_txt")  # dns_txt | file
    verification_token: Mapped[str] = mapped_column(String, default=lambda: f"strix-verify={uuid.uuid4().hex}")
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------
# Pentests
# --------------------------------------------------------------------------


class PentestSchedule(TimestampMixin, Base):
    __tablename__ = "pentest_schedules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    target_type: Mapped[str] = mapped_column(String)  # repository | domain
    target_id: Mapped[str] = mapped_column(String)
    scan_mode: Mapped[str] = mapped_column(String, default="deep")
    cron_expr: Mapped[str] = mapped_column(String, default="0 0 * * 0")  # weekly default
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Pentest(TimestampMixin, Base):
    __tablename__ = "pentests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    target_type: Mapped[str] = mapped_column(String)  # repository | domain
    target_id: Mapped[str] = mapped_column(String)
    target_label: Mapped[str] = mapped_column(String, default="")
    scan_mode: Mapped[str] = mapped_column(String, default="deep")
    status: Mapped[str] = mapped_column(String, default="queued")  # queued|running|completed|failed|stopped
    schedule_id: Mapped[str | None] = mapped_column(ForeignKey("pentest_schedules.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    severity_counts: Mapped[dict] = mapped_column(JSON, default=dict)


# --------------------------------------------------------------------------
# Issues
# --------------------------------------------------------------------------


class Issue(TimestampMixin, Base):
    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    pentest_id: Mapped[str | None] = mapped_column(ForeignKey("pentests.id"), nullable=True)
    pr_review_id: Mapped[str | None] = mapped_column(ForeignKey("pr_reviews.id"), nullable=True)
    repository_id: Mapped[str | None] = mapped_column(ForeignKey("repositories.id"), nullable=True)
    domain_id: Mapped[str | None] = mapped_column(ForeignKey("domains.id"), nullable=True)

    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String)  # critical|high|medium|low
    status: Mapped[str] = mapped_column(String, default="open")  # open|in_progress|snoozed|fixed|ignored
    cvss: Mapped[float | None] = mapped_column(Float, nullable=True)
    cvss_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    technical_analysis: Mapped[str] = mapped_column(Text, default="")
    remediation_steps: Mapped[str] = mapped_column(Text, default="")
    poc_description: Mapped[str] = mapped_column(Text, default="")
    poc_script_code: Mapped[str] = mapped_column(Text, default="")
    code_before: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_after: Mapped[str | None] = mapped_column(Text, nullable=True)
    target: Mapped[str] = mapped_column(String, default="")
    endpoint: Mapped[str] = mapped_column(String, default="")
    fix_effort: Mapped[str] = mapped_column(String, default="medium")  # low|medium|high
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


# --------------------------------------------------------------------------
# PR reviews
# --------------------------------------------------------------------------


class PRReview(TimestampMixin, Base):
    __tablename__ = "pr_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"), index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String, default="")
    author: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="awaiting_merge")
    # awaiting_merge | needs_attention | merged_with_open_findings | passed
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class PRReviewSettings(Base):
    __tablename__ = "pr_review_settings"

    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    rereview_on_push: Mapped[bool] = mapped_column(Boolean, default=False)
    target_branches: Mapped[list] = mapped_column(JSON, default=list)
    approve_clean_prs: Mapped[bool] = mapped_column(Boolean, default=False)
    block_prs_on_findings: Mapped[bool] = mapped_column(Boolean, default=True)
    blocking_severities: Mapped[list] = mapped_column(JSON, default=lambda: ["critical", "high"])
    exclude_bot_accounts: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded_usernames: Mapped[list] = mapped_column(JSON, default=list)
    allow_overage_reviews: Mapped[bool] = mapped_column(Boolean, default=True)
    review_cap_per_dev: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_cap_period: Mapped[str] = mapped_column(String, default="month")

    organization: Mapped[Organization] = relationship(back_populates="pr_review_settings")


# --------------------------------------------------------------------------
# Knowledge
# --------------------------------------------------------------------------


class KnowledgeEntry(TimestampMixin, Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    type: Mapped[str] = mapped_column(String, default="business_logic")
    description: Mapped[str] = mapped_column(Text)
    scope_type: Mapped[str] = mapped_column(String, default="global")  # global|repository|domain
    scope_id: Mapped[str | None] = mapped_column(String, nullable=True)


# --------------------------------------------------------------------------
# Chat
# --------------------------------------------------------------------------


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String, default="New chat")
    category: Mapped[str] = mapped_column(String, default="web")

    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String)  # user | assistant
    content: Mapped[str] = mapped_column(Text)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


# --------------------------------------------------------------------------
# API access: tokens & webhooks
# --------------------------------------------------------------------------


class ApiToken(TimestampMixin, Base):
    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    token_type: Mapped[str] = mapped_column(String, default="personal")  # personal | service
    scopes: Mapped[list] = mapped_column(JSON, default=lambda: ["read"])
    token_hash: Mapped[str] = mapped_column(String)
    token_prefix: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")  # active | revoked
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Webhook(TimestampMixin, Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    url: Mapped[str] = mapped_column(String)
    events: Mapped[list] = mapped_column(JSON, default=list)
    secret: Mapped[str] = mapped_column(String, default=lambda: uuid.uuid4().hex)
    status: Mapped[str] = mapped_column(String, default="active")


# --------------------------------------------------------------------------
# Audit & billing
# --------------------------------------------------------------------------


class AuditLogEntry(TimestampMixin, Base):
    __tablename__ = "audit_log_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String, default="")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Subscription(Base):
    __tablename__ = "subscriptions"

    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    plan: Mapped[str] = mapped_column(String, default="pro_trial")
    status: Mapped[str] = mapped_column(String, default="trialing")  # trialing|active|canceled
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    card_added: Mapped[bool] = mapped_column(Boolean, default=False)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="subscription")
