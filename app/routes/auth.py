from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.services.auth_service import (
    create_user, login, get_user_by_token, logout,
    create_project, get_projects, add_report_to_project, get_project_report_ids,
)

router = APIRouter()


def _tok(authorization: Optional[str]) -> str:
    return (authorization or "").replace("Bearer ", "").strip()


def _require_user(authorization: Optional[str]) -> dict:
    user = get_user_by_token(_tok(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


class SignupReq(BaseModel):
    username: str
    email: str
    password: str
    full_name: str = ""


class LoginReq(BaseModel):
    username: str
    password: str


class ProjectReq(BaseModel):
    name: str
    description: str = ""


@router.post("/signup")
def signup(req: SignupReq):
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    try:
        user = create_user(req.username, req.email, req.password, req.full_name)
        return {"success": True, "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
def do_login(req: LoginReq):
    try:
        result = login(req.username, req.password)
        user = result["user"]
        user.pop("password_hash", None)
        return {"success": True, "token": result["token"], "user": user}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me")
def get_me(authorization: Optional[str] = Header(None)):
    user = _require_user(authorization)
    user.pop("password_hash", None)
    return {"user": user}


@router.post("/logout")
def do_logout(authorization: Optional[str] = Header(None)):
    logout(_tok(authorization))
    return {"success": True}


@router.post("/projects")
def create_proj(req: ProjectReq, authorization: Optional[str] = Header(None)):
    user = _require_user(authorization)
    return create_project(req.name, req.description, user["id"])


@router.get("/projects")
def list_projects(authorization: Optional[str] = Header(None)):
    user = _require_user(authorization)
    return {"projects": get_projects(user["id"])}


@router.post("/projects/{project_id}/reports/{report_id}")
def attach_report(project_id: str, report_id: str, authorization: Optional[str] = Header(None)):
    _require_user(authorization)
    add_report_to_project(project_id, report_id)
    return {"success": True}


@router.get("/projects/{project_id}/reports")
def project_reports(project_id: str, authorization: Optional[str] = Header(None)):
    _require_user(authorization)
    return {"report_ids": get_project_report_ids(project_id)}
