from __future__ import annotations

import random
import string
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import current_session, current_user, db_dep
from ..settings import settings
from ..time_utils import utcnow

router = APIRouter(prefix="/api/auth", tags=["auth"])

OTP_TTL_MINUTES = 10
MAX_OTP_ATTEMPTS = 5


class OtpStartIn(BaseModel):
    email: EmailStr


class OtpVerifyIn(BaseModel):
    email: EmailStr
    code: str


class SwitchOrgIn(BaseModel):
    org_id: str


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        secure=not settings.dev_mode,
        max_age=60 * 60 * 24 * 30,
    )


@router.post("/otp/start")
def otp_start(body: OtpStartIn, db: Session = Depends(db_dep)) -> dict:
    code = "".join(random.choices(string.digits, k=6))
    db.add(
        models.OtpCode(
            email=body.email.lower(),
            code=code,
            expires_at=utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
        )
    )
    db.commit()
    result: dict = {"ok": True}
    if settings.dev_mode:
        # No email provider wired up yet (see CONFIG.md) — dev mode hands
        # the code straight back so the OTP flow is testable end-to-end
        # without sending real email.
        result["dev_code"] = code
    return result


@router.post("/otp/verify")
def otp_verify(body: OtpVerifyIn, response: Response, db: Session = Depends(db_dep)) -> schemas.MeOut:
    email = body.email.lower()
    # Look up the latest *pending* code for this email regardless of what
    # was submitted (not filtered by code == body.code) — that's what lets
    # us count failed attempts against it and lock it out below. A 6-digit
    # code with unlimited guesses is brute-forceable within its TTL; this
    # caps it at MAX_OTP_ATTEMPTS tries per requested code.
    otp = (
        db.query(models.OtpCode)
        .filter(models.OtpCode.email == email, models.OtpCode.consumed.is_(False))
        .order_by(models.OtpCode.created_at.desc())
        .first()
    )
    if not otp or otp.expires_at < utcnow():
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="invalid_or_expired_code")
    if otp.attempts >= MAX_OTP_ATTEMPTS:
        otp.consumed = True
        db.commit()
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="too_many_attempts")
    if otp.code != body.code:
        otp.attempts += 1
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="invalid_or_expired_code")
    otp.consumed = True

    user = db.query(models.User).filter_by(email=email).first()
    if not user:
        user = models.User(email=email, name=email.split("@")[0])
        db.add(user)
        db.flush()

    membership = db.query(models.Membership).filter_by(user_id=user.id).first()
    session = models.Session_(user_id=user.id, active_org_id=membership.org_id if membership else None)
    db.add(session)
    db.commit()

    _set_session_cookie(response, session.token)
    return _me_payload(db, user, session)


@router.post("/logout")
def logout(response: Response, sess: models.Session_ = Depends(current_session), db: Session = Depends(db_dep)) -> dict:
    db.delete(sess)
    db.commit()
    response.delete_cookie(settings.session_cookie_name)
    return {"ok": True}


@router.get("/me")
def me(
    user: models.User = Depends(current_user),
    sess: models.Session_ = Depends(current_session),
    db: Session = Depends(db_dep),
) -> schemas.MeOut:
    return _me_payload(db, user, sess)


@router.post("/switch-org")
def switch_org(
    body: SwitchOrgIn,
    user: models.User = Depends(current_user),
    sess: models.Session_ = Depends(current_session),
    db: Session = Depends(db_dep),
) -> schemas.MeOut:
    membership = db.query(models.Membership).filter_by(user_id=user.id, org_id=body.org_id).first()
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="not_a_member")
    sess.active_org_id = body.org_id
    db.commit()
    return _me_payload(db, user, sess)


def _me_payload(db: Session, user: models.User, sess: models.Session_) -> schemas.MeOut:
    memberships = db.query(models.Membership).filter_by(user_id=user.id).all()
    orgs = [db.get(models.Organization, m.org_id) for m in memberships]
    active_org = db.get(models.Organization, sess.active_org_id) if sess.active_org_id else None
    active_membership = next((m for m in memberships if m.org_id == sess.active_org_id), None)
    return schemas.MeOut(
        user=schemas.UserOut.model_validate(user),
        active_org=schemas.OrganizationOut.model_validate(active_org) if active_org else None,
        role=active_membership.role if active_membership else None,
        organizations=[schemas.OrganizationOut.model_validate(o) for o in orgs if o],
    )
