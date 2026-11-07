"""Business rules for the foundation: master IDs, validation, audit trail."""

from datetime import date
from typing import Optional

from sqlmodel import Session, func, select

from .models import (
    AuditLog,
    Client,
    Company,
    ContractModel,
    Person,
    Project,
    Role,
    Stage,
    UnitType,
)

DEFAULT_COMPANY_CODE = "ZAS"
DEFAULT_COMPANY_NAME = "ZAS Innovation"


class ValidationError(ValueError):
    """Raised with an Arabic message the screen can show directly."""


def get_or_create_company(s: Session, code: str = DEFAULT_COMPANY_CODE, name: str = DEFAULT_COMPANY_NAME) -> Company:
    company = s.exec(select(Company).where(Company.code == code)).first()
    if company is None:
        company = Company(code=code, name=name)
        s.add(company)
        s.commit()
        s.refresh(company)
    return company


def _count(s: Session, model, company_id: int, *extra) -> int:
    q = select(func.count()).select_from(model).where(model.company_id == company_id, *extra)
    return s.exec(q).one()


def next_person_code(s: Session, company_id: int) -> str:
    return f"EMP-{_count(s, Person, company_id) + 1:03d}"


def next_client_code(s: Session, company_id: int) -> str:
    return f"CL-{_count(s, Client, company_id) + 1:04d}"


def next_project_code(s: Session, company: Company, year: int) -> str:
    prefix = f"{company.code}-{year}-"
    n = _count(s, Project, company.id, Project.code.startswith(prefix))
    return f"{prefix}{n + 1:03d}"


def log(s: Session, company_id: int, actor: str, action: str, entity: str, entity_id: int, details: str = "") -> None:
    s.add(AuditLog(company_id=company_id, actor=actor, action=action, entity=entity, entity_id=entity_id, details=details))


def _required(value: Optional[str], label: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValidationError(f"خانة «{label}» مطلوبة")
    return value


def create_person(s: Session, company: Company, *, name: str, role: Role, phone: str | None = None,
                  actor: str = "system", is_demo: bool = False) -> Person:
    p = Person(company_id=company.id, code=next_person_code(s, company.id), name=_required(name, "الاسم"),
               role=role, phone=(phone or "").strip() or None, is_demo=is_demo)
    s.add(p)
    s.flush()
    log(s, company.id, actor, "create", "person", p.id, f"{p.code} {p.name}")
    s.commit()
    s.refresh(p)
    return p


def create_client(s: Session, company: Company, *, name: str, phone: str | None = None, email: str | None = None,
                  source: str | None = None, notes: str | None = None, actor: str = "system",
                  is_demo: bool = False) -> Client:
    name = _required(name, "اسم العميل")
    phone = (phone or "").strip() or None
    if phone:
        dup = s.exec(select(Client).where(Client.company_id == company.id, Client.phone == phone)).first()
        if dup:
            raise ValidationError(f"العميل ده متسجل قبل كده بنفس الموبايل ({dup.code} — {dup.name})")
    c = Client(company_id=company.id, code=next_client_code(s, company.id), name=name, phone=phone,
               email=(email or "").strip() or None, source=(source or "").strip() or None,
               notes=(notes or "").strip() or None, is_demo=is_demo)
    s.add(c)
    s.flush()
    log(s, company.id, actor, "create", "client", c.id, f"{c.code} {c.name}")
    s.commit()
    s.refresh(c)
    return c


def create_project(s: Session, company: Company, *, name: str, client_id: int, unit_type: UnitType,
                   contract_model: ContractModel, fee_percent: float | None = None,
                   fixed_fee_amount: float | None = None, location: str | None = None,
                   area_m2: float | None = None, manager_id: int | None = None,
                   start_date: date | None = None, stage: Stage = Stage.lead, actor: str = "system",
                   is_demo: bool = False) -> Project:
    name = _required(name, "اسم المشروع")
    client = s.get(Client, client_id)
    if client is None or client.company_id != company.id:
        raise ValidationError("لازم تختار عميل موجود")
    if manager_id is not None:
        mgr = s.get(Person, manager_id)
        if mgr is None or mgr.company_id != company.id:
            raise ValidationError("مدير المشروع غير موجود")
    if area_m2 is not None and area_m2 <= 0:
        raise ValidationError("المساحة لازم تكون أكبر من صفر")
    if contract_model == ContractModel.cost_plus_fee:
        if fee_percent is None or not (0 < fee_percent <= 100):
            raise ValidationError("نسبة الإشراف لازم تكون رقم بين 0 و 100")
        fixed_fee_amount = None
    else:
        if fixed_fee_amount is None or fixed_fee_amount <= 0:
            raise ValidationError("قيمة الأتعاب الثابتة لازم تكون أكبر من صفر")
        fee_percent = None

    year = (start_date or date.today()).year
    p = Project(company_id=company.id, code=next_project_code(s, company, year), name=name, client_id=client.id,
                manager_id=manager_id, unit_type=unit_type, location=(location or "").strip() or None,
                area_m2=area_m2, stage=stage, contract_model=contract_model, fee_percent=fee_percent,
                fixed_fee_amount=fixed_fee_amount, start_date=start_date, is_demo=is_demo)
    s.add(p)
    s.flush()
    log(s, company.id, actor, "create", "project", p.id, f"{p.code} {p.name} — عميل {client.code}")
    s.commit()
    s.refresh(p)
    return p


def change_stage(s: Session, company: Company, project_id: int, new_stage: Stage, actor: str = "system") -> Project:
    p = s.get(Project, project_id)
    if p is None or p.company_id != company.id:
        raise ValidationError("المشروع غير موجود")
    old = p.stage
    if old == new_stage:
        return p
    p.stage = new_stage
    s.add(p)
    log(s, company.id, actor, "stage_change", "project", p.id, f"{p.code}: {old.value} → {new_stage.value}")
    s.commit()
    s.refresh(p)
    return p
