from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from onebrain import services
from onebrain.db import init_db, make_engine
from onebrain.main import create_app
from onebrain.models import AuditLog, ContractModel, Project, Role, Stage, UnitType


@pytest.fixture
def s():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(f"sqlite:///{tmp_path / 't.db'}", seed=True))


def test_master_ids_are_sequential(s):
    co = services.get_or_create_company(s)
    c1 = services.create_client(s, co, name="أ", phone="010")
    c2 = services.create_client(s, co, name="ب")
    assert (c1.code, c2.code) == ("CL-0001", "CL-0002")
    p1 = services.create_project(s, co, name="م1", client_id=c1.id, unit_type=UnitType.villa,
                                 contract_model=ContractModel.cost_plus_fee, fee_percent=15,
                                 start_date=date(2026, 3, 1))
    p2 = services.create_project(s, co, name="م2", client_id=c2.id, unit_type=UnitType.apartment,
                                 contract_model=ContractModel.fixed_fee, fixed_fee_amount=50000,
                                 start_date=date(2026, 5, 1))
    p3 = services.create_project(s, co, name="م3", client_id=c2.id, unit_type=UnitType.apartment,
                                 contract_model=ContractModel.fixed_fee, fixed_fee_amount=1,
                                 start_date=date(2027, 1, 1))
    assert (p1.code, p2.code, p3.code) == ("ZAS-2026-001", "ZAS-2026-002", "ZAS-2027-001")
    e = services.create_person(s, co, name="م", role=Role.finance)
    assert e.code == "EMP-001"


def test_duplicate_phone_rejected(s):
    co = services.get_or_create_company(s)
    services.create_client(s, co, name="أ", phone="0100")
    with pytest.raises(services.ValidationError):
        services.create_client(s, co, name="ب", phone="0100")


@pytest.mark.parametrize("kwargs", [
    dict(contract_model=ContractModel.cost_plus_fee, fee_percent=None),
    dict(contract_model=ContractModel.cost_plus_fee, fee_percent=150),
    dict(contract_model=ContractModel.fixed_fee, fixed_fee_amount=0),
    dict(contract_model=ContractModel.cost_plus_fee, fee_percent=15, area_m2=-5),
])
def test_project_validation(s, kwargs):
    co = services.get_or_create_company(s)
    c = services.create_client(s, co, name="أ")
    with pytest.raises(services.ValidationError):
        services.create_project(s, co, name="م", client_id=c.id, unit_type=UnitType.villa, **kwargs)


def test_tenant_isolation(s):
    zas = services.get_or_create_company(s)
    other = services.get_or_create_company(s, code="OTH", name="Other Co")
    c_other = services.create_client(s, other, name="عميل شركة تانية")
    with pytest.raises(services.ValidationError):
        services.create_project(s, zas, name="م", client_id=c_other.id, unit_type=UnitType.villa,
                                contract_model=ContractModel.cost_plus_fee, fee_percent=10)


def test_audit_trail_records_stage_change(s):
    co = services.get_or_create_company(s)
    c = services.create_client(s, co, name="أ")
    p = services.create_project(s, co, name="م", client_id=c.id, unit_type=UnitType.villa,
                                contract_model=ContractModel.cost_plus_fee, fee_percent=15, actor="tester")
    services.change_stage(s, co, p.id, Stage.contract, actor="tester")
    actions = [a.action for a in s.exec(select(AuditLog).where(AuditLog.entity == "project")).all()]
    assert actions == ["create", "stage_change"]


def test_pages_render(client):
    for path in ["/", "/projects", "/clients", "/people", "/audit", "/projects/1"]:
        r = client.get(path)
        assert r.status_code == 200, path
    assert "ZAS-2026-001" in client.get("/projects").text


def test_create_project_via_form(client):
    r = client.post("/clients", data={"name": "عميل جديد", "phone": "01299999999"}, follow_redirects=False)
    assert r.status_code == 303
    page = client.get("/clients").text
    assert "CL-0004" in page
    r = client.post("/projects", data={"name": "شقة جديدة", "client_id": "4", "unit_type": "apartment",
                                       "contract_model": "cost_plus_fee", "fee_percent": "20",
                                       "start_date": "2026-12-01"}, follow_redirects=False)
    assert r.status_code == 303
    detail = client.get(r.headers["location"]).text
    assert "ZAS-2026-004" in detail
    r = client.post(r.headers["location"] + "/stage", data={"stage": "contract"}, follow_redirects=True)
    assert r.status_code == 200 and "contract" in r.text


def test_form_errors_shown_in_arabic(client):
    r = client.post("/projects", data={"name": "", "client_id": "1", "unit_type": "villa",
                                       "contract_model": "cost_plus_fee", "fee_percent": "15"})
    assert r.status_code == 400 and "مطلوبة" in r.text
    r = client.post("/projects", data={"name": "x", "client_id": "1", "unit_type": "villa",
                                       "contract_model": "cost_plus_fee", "fee_percent": "abc"})
    assert r.status_code == 400 and "مش رقم" in r.text
