from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from . import models
from .db import get_db
from .settings import settings


def db_dep() -> Generator[Session, None, None]:
    yield from get_db()


def current_session(request: Request, db: Session = Depends(db_dep)) -> models.Session_:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    sess = db.get(models.Session_, token)
    if not sess:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    return sess


def current_user(sess: models.Session_ = Depends(current_session), db: Session = Depends(db_dep)) -> models.User:
    user = db.get(models.User, sess.user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    return user


def current_membership(
    sess: models.Session_ = Depends(current_session),
    user: models.User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> models.Membership:
    org_id = sess.active_org_id
    if not org_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="no_active_org")
    membership = (
        db.query(models.Membership)
        .filter(models.Membership.org_id == org_id, models.Membership.user_id == user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="not_a_member")
    return membership


def current_org(
    membership: models.Membership = Depends(current_membership),
    db: Session = Depends(db_dep),
) -> models.Organization:
    org = db.get(models.Organization, membership.org_id)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="org_not_found")
    return org


def require_admin(membership: models.Membership = Depends(current_membership)) -> models.Membership:
    if membership.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="admin_required")
    return membership
