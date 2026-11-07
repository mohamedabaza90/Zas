"""Demo data so the screens are not empty. Every record is flagged is_demo=True
and shown as «تجريبي» — none of it is real ZAS data."""

from datetime import date

from sqlmodel import Session, select

from .models import ContractModel, Project, Role, Stage, UnitType
from .services import create_client, create_person, create_project, get_or_create_company


def seed_demo(s: Session) -> bool:
    company = get_or_create_company(s)
    if s.exec(select(Project).where(Project.company_id == company.id)).first():
        return False  # already has data

    actor = "demo-seed"
    mk = lambda name, role: create_person(s, company, name=name, role=role, actor=actor, is_demo=True)  # noqa: E731
    mk("المدير التنفيذي (تجريبي)", Role.ceo)
    pm = mk("مدير مشروعات (تجريبي)", Role.project_manager)
    mk("مهندس مكتب فني (تجريبي)", Role.tech_office)
    mk("مهندس موقع 1 (تجريبي)", Role.site_engineer)
    mk("محاسب (تجريبي)", Role.finance)
    mk("مسؤول مبيعات (تجريبي)", Role.sales)

    c1 = create_client(s, company, name="عميل تجريبي — فيلا التجمع", phone="01000000001", source="Facebook",
                       actor=actor, is_demo=True)
    c2 = create_client(s, company, name="عميل تجريبي — شقة الشيخ زايد", phone="01000000002", source="ترشيح عميل",
                       actor=actor, is_demo=True)
    c3 = create_client(s, company, name="عميل تجريبي — دوبلكس أكتوبر", phone="01000000003", source="الموقع الإلكتروني",
                       actor=actor, is_demo=True)

    create_project(s, company, name="تشطيب فيلا — التجمع الخامس", client_id=c1.id, unit_type=UnitType.villa,
                   contract_model=ContractModel.cost_plus_fee, fee_percent=15, location="التجمع الخامس",
                   area_m2=420, manager_id=pm.id, start_date=date(2026, 9, 1), stage=Stage.execution,
                   actor=actor, is_demo=True)
    create_project(s, company, name="تشطيب شقة — الشيخ زايد", client_id=c2.id, unit_type=UnitType.apartment,
                   contract_model=ContractModel.fixed_fee, fixed_fee_amount=120000, location="الشيخ زايد",
                   area_m2=165, start_date=date(2026, 11, 1), stage=Stage.pricing, actor=actor, is_demo=True)
    create_project(s, company, name="دوبلكس — 6 أكتوبر", client_id=c3.id, unit_type=UnitType.duplex,
                   contract_model=ContractModel.cost_plus_fee, fee_percent=18, location="6 أكتوبر",
                   area_m2=280, stage=Stage.sales, actor=actor, is_demo=True)
    return True
