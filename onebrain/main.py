"""ZAS OneBrain — web app (Section 1: Foundation / Shared Data Layer)."""

from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, func, select

from . import services
from .db import init_db, make_engine
from .models import (
    CONTRACT_LABELS,
    PRE_CONTRACT,
    ROLE_LABELS,
    STAGE_LABELS,
    STAGE_ORDER,
    UNIT_LABELS,
    AuditLog,
    Client,
    ContractModel,
    Person,
    Project,
    Role,
    Stage,
    UnitType,
)
from .seed import seed_demo

BASE = Path(__file__).resolve().parent
ACTOR = "مستخدم النظام"  # replaced by real logged-in users in the permissions section


def _num(v: Optional[str]) -> Optional[float]:
    v = (v or "").strip().replace(",", "")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        raise services.ValidationError(f"«{v}» مش رقم صحيح")


def _int(v: Optional[str]) -> Optional[int]:
    n = _num(v)
    return int(n) if n is not None else None


def _date(v: Optional[str]) -> Optional[date]:
    v = (v or "").strip()
    return date.fromisoformat(v) if v else None


def create_app(db_url: str | None = None, seed: bool = True) -> FastAPI:
    engine = make_engine(db_url)
    init_db(engine)
    with Session(engine) as s:
        services.get_or_create_company(s)
        if seed:
            seed_demo(s)

    app = FastAPI(title="ZAS OneBrain")
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
    templates = Jinja2Templates(directory=BASE / "templates")
    templates.env.globals.update(
        STAGE_LABELS=STAGE_LABELS, STAGE_ORDER=STAGE_ORDER, ROLE_LABELS=ROLE_LABELS,
        UNIT_LABELS=UNIT_LABELS, CONTRACT_LABELS=CONTRACT_LABELS, Role=Role, UnitType=UnitType,
        ContractModel=ContractModel, PRE_CONTRACT=PRE_CONTRACT,
    )

    def get_session():
        with Session(engine) as s:
            yield s

    def company(s: Session):
        return services.get_or_create_company(s)

    def render(request: Request, name: str, **ctx):
        return templates.TemplateResponse(request, name, ctx)

    # ---------- Home / dashboard ----------
    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, s: Session = Depends(get_session)):
        co = company(s)
        by_stage = dict(s.exec(select(Project.stage, func.count()).where(Project.company_id == co.id)
                               .group_by(Project.stage)).all())
        counts = {
            "projects": sum(by_stage.values()),
            "clients": s.exec(select(func.count()).select_from(Client).where(Client.company_id == co.id)).one(),
            "people": s.exec(select(func.count()).select_from(Person).where(Person.company_id == co.id)).one(),
            "active": sum(v for k, v in by_stage.items() if k not in PRE_CONTRACT),
        }
        recent = s.exec(select(AuditLog).where(AuditLog.company_id == co.id)
                        .order_by(AuditLog.at.desc()).limit(8)).all()
        return render(request, "home.html", company=co, counts=counts, by_stage=by_stage, recent=recent)

    # ---------- Clients ----------
    @app.get("/clients", response_class=HTMLResponse)
    def clients(request: Request, s: Session = Depends(get_session), error: str = "", form: dict | None = None):
        co = company(s)
        rows = s.exec(select(Client).where(Client.company_id == co.id).order_by(Client.id.desc())).all()
        return render(request, "clients.html", rows=rows, error=error, form=form or {})

    @app.post("/clients")
    def add_client(request: Request, name: str = Form(""), phone: str = Form(""), email: str = Form(""),
                   source: str = Form(""), notes: str = Form(""), s: Session = Depends(get_session)):
        try:
            services.create_client(s, company(s), name=name, phone=phone, email=email, source=source,
                                   notes=notes, actor=ACTOR)
        except services.ValidationError as e:
            s.rollback()
            form = dict(name=name, phone=phone, email=email, source=source, notes=notes)
            resp = clients(request, s, error=str(e), form=form)
            resp.status_code = 400
            return resp
        return RedirectResponse("/clients", status_code=303)

    # ---------- People ----------
    @app.get("/people", response_class=HTMLResponse)
    def people(request: Request, s: Session = Depends(get_session), error: str = "", form: dict | None = None):
        co = company(s)
        rows = s.exec(select(Person).where(Person.company_id == co.id).order_by(Person.id)).all()
        return render(request, "people.html", rows=rows, error=error, form=form or {})

    @app.post("/people")
    def add_person(request: Request, name: str = Form(""), role: str = Form(""), phone: str = Form(""),
                   s: Session = Depends(get_session)):
        try:
            try:
                role_v = Role(role)
            except ValueError:
                raise services.ValidationError("اختار الوظيفة")
            services.create_person(s, company(s), name=name, role=role_v, phone=phone, actor=ACTOR)
        except services.ValidationError as e:
            s.rollback()
            resp = people(request, s, error=str(e), form=dict(name=name, role=role, phone=phone))
            resp.status_code = 400
            return resp
        return RedirectResponse("/people", status_code=303)

    # ---------- Projects ----------
    def _project_ctx(s: Session, co):
        clients_ = s.exec(select(Client).where(Client.company_id == co.id).order_by(Client.name)).all()
        managers = s.exec(select(Person).where(Person.company_id == co.id, Person.active == True)  # noqa: E712
                          .order_by(Person.name)).all()
        return {c.id: c for c in clients_}, {m.id: m for m in managers}

    @app.get("/projects", response_class=HTMLResponse)
    def projects(request: Request, s: Session = Depends(get_session), error: str = "", form: dict | None = None):
        co = company(s)
        rows = s.exec(select(Project).where(Project.company_id == co.id).order_by(Project.id.desc())).all()
        clients_by_id, people_by_id = _project_ctx(s, co)
        return render(request, "projects.html", rows=rows, clients=clients_by_id, people=people_by_id,
                      error=error, form=form or {})

    @app.post("/projects")
    def add_project(request: Request, name: str = Form(""), client_id: str = Form(""), unit_type: str = Form(""),
                    location: str = Form(""), area_m2: str = Form(""), manager_id: str = Form(""),
                    contract_model: str = Form("cost_plus_fee"), fee_percent: str = Form(""),
                    fixed_fee_amount: str = Form(""), start_date: str = Form(""),
                    s: Session = Depends(get_session)):
        form = dict(name=name, client_id=client_id, unit_type=unit_type, location=location, area_m2=area_m2,
                    manager_id=manager_id, contract_model=contract_model, fee_percent=fee_percent,
                    fixed_fee_amount=fixed_fee_amount, start_date=start_date)
        try:
            try:
                ut = UnitType(unit_type)
            except ValueError:
                raise services.ValidationError("اختار نوع الوحدة")
            try:
                cm = ContractModel(contract_model)
            except ValueError:
                raise services.ValidationError("اختار نوع التعاقد")
            cid = _int(client_id)
            if cid is None:
                raise services.ValidationError("لازم تختار عميل موجود")
            try:
                sd = _date(start_date)
            except ValueError:
                raise services.ValidationError("تاريخ البداية غير صحيح")
            p = services.create_project(s, company(s), name=name, client_id=cid, unit_type=ut,
                                        contract_model=cm, fee_percent=_num(fee_percent),
                                        fixed_fee_amount=_num(fixed_fee_amount), location=location,
                                        area_m2=_num(area_m2), manager_id=_int(manager_id), start_date=sd,
                                        actor=ACTOR)
        except services.ValidationError as e:
            s.rollback()
            resp = projects(request, s, error=str(e), form=form)
            resp.status_code = 400
            return resp
        return RedirectResponse(f"/projects/{p.id}", status_code=303)

    @app.get("/projects/{project_id}", response_class=HTMLResponse)
    def project_detail(project_id: int, request: Request, s: Session = Depends(get_session)):
        co = company(s)
        p = s.get(Project, project_id)
        if p is None or p.company_id != co.id:
            raise HTTPException(404, "المشروع غير موجود")
        history = s.exec(select(AuditLog).where(AuditLog.company_id == co.id, AuditLog.entity == "project",
                                                AuditLog.entity_id == p.id).order_by(AuditLog.at.desc())).all()
        return render(request, "project_detail.html", p=p, client=s.get(Client, p.client_id),
                      manager=s.get(Person, p.manager_id) if p.manager_id else None, history=history)

    @app.post("/projects/{project_id}/stage")
    def set_stage(project_id: int, stage: str = Form(...), s: Session = Depends(get_session)):
        try:
            services.change_stage(s, company(s), project_id, Stage(stage), actor=ACTOR)
        except (ValueError, services.ValidationError):
            raise HTTPException(400, "مرحلة غير صحيحة")
        return RedirectResponse(f"/projects/{project_id}", status_code=303)

    # ---------- Audit ----------
    @app.get("/audit", response_class=HTMLResponse)
    def audit(request: Request, s: Session = Depends(get_session)):
        co = company(s)
        rows = s.exec(select(AuditLog).where(AuditLog.company_id == co.id)
                      .order_by(AuditLog.at.desc()).limit(200)).all()
        return render(request, "audit.html", rows=rows)

    return app

