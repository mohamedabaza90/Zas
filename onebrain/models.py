"""Shared Data Layer — the master records every OneBrain module builds on.

Every table carries `company_id` so the same system can later serve several
companies (multi-tenant SaaS) with each company's data kept separate.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, Enum):
    ceo = "ceo"
    project_manager = "project_manager"
    tech_office = "tech_office"
    site_engineer = "site_engineer"
    finance = "finance"
    sales = "sales"
    procurement = "procurement"
    marketing = "marketing"
    hr = "hr"


ROLE_LABELS = {
    Role.ceo: "الإدارة التنفيذية",
    Role.project_manager: "مدير مشروعات",
    Role.tech_office: "المكتب الفني",
    Role.site_engineer: "مهندس موقع",
    Role.finance: "الحسابات",
    Role.sales: "المبيعات",
    Role.procurement: "المشتريات",
    Role.marketing: "التسويق",
    Role.hr: "الموارد البشرية",
}


class Stage(str, Enum):
    """The 10-step project journey from the OneBrain vision document."""

    lead = "lead"
    sales = "sales"
    design = "design"
    pricing = "pricing"
    contract = "contract"
    planning = "planning"
    execution = "execution"
    control = "control"
    handover = "handover"
    aftercare = "aftercare"


STAGE_LABELS = {
    Stage.lead: "جذب",
    Stage.sales: "بيع ومعاينة",
    Stage.design: "تصميم",
    Stage.pricing: "تسعير BOQ",
    Stage.contract: "تعاقد",
    Stage.planning: "تخطيط",
    Stage.execution: "تنفيذ",
    Stage.control: "متابعة",
    Stage.handover: "تسليم",
    Stage.aftercare: "خدمة وضمان",
}

STAGE_ORDER = list(Stage)
PRE_CONTRACT = {Stage.lead, Stage.sales, Stage.design, Stage.pricing}


class UnitType(str, Enum):
    apartment = "apartment"
    duplex = "duplex"
    villa = "villa"
    commercial = "commercial"


UNIT_LABELS = {
    UnitType.apartment: "شقة",
    UnitType.duplex: "دوبلكس",
    UnitType.villa: "فيلا",
    UnitType.commercial: "تجاري",
}


class ContractModel(str, Enum):
    cost_plus_fee = "cost_plus_fee"
    fixed_fee = "fixed_fee"


CONTRACT_LABELS = {
    ContractModel.cost_plus_fee: "نسبة إشراف (Cost-plus)",
    ContractModel.fixed_fee: "أتعاب ثابتة",
}


class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    created_at: datetime = Field(default_factory=utcnow)


class Person(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    code: str = Field(index=True)  # EMP-001
    name: str
    role: Role
    phone: Optional[str] = None
    active: bool = True
    is_demo: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Client(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    code: str = Field(index=True)  # CL-0001
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = None  # where the lead came from (Facebook, referral...)
    notes: Optional[str] = None
    is_demo: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    code: str = Field(index=True)  # ZAS-2026-001 — the one Project ID shared by all departments
    name: str
    client_id: int = Field(foreign_key="client.id", index=True)
    manager_id: Optional[int] = Field(default=None, foreign_key="person.id")
    unit_type: UnitType
    location: Optional[str] = None
    area_m2: Optional[float] = None
    stage: Stage = Stage.lead
    contract_model: ContractModel = ContractModel.cost_plus_fee
    fee_percent: Optional[float] = None  # used with cost_plus_fee
    fixed_fee_amount: Optional[float] = None  # EGP, used with fixed_fee
    start_date: Optional[date] = None
    is_demo: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class AuditLog(SQLModel, table=True):
    """Who changed what and when — required before any AI is allowed to act."""

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    at: datetime = Field(default_factory=utcnow, index=True)
    actor: str
    action: str  # create / update / stage_change
    entity: str  # client / project / person
    entity_id: int
    details: str = ""
