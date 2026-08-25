"""マスタ API。"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.conflict import conflict_json_response
from app.auth.dependencies import require_admin, require_any_authenticated
from app.auth.models import CurrentUser
from app.logging_config import log_event
from app.rag.index_service import RagIndexService
from app.repository.master import MasterRepository
from app.repository.optimistic import OptimisticLockError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/masters", tags=["masters"])
_repo = MasterRepository()
_rag = RagIndexService()


class VersionedBody(BaseModel):
    row_version: int


class IncidentTypeBody(BaseModel):
    type_name: str
    avg_detection_minutes: int
    severity_default: str
    detection_source: str
    description: str = ""
    frequency_weight: float = 1.0


class IncidentTypeCreate(IncidentTypeBody):
    pass


class IncidentTypeUpdate(IncidentTypeBody, VersionedBody):
    pass


class ServiceBody(BaseModel):
    service_name: str
    description: str = ""


class ServiceUpdate(ServiceBody, VersionedBody):
    pass


class CustomerBody(BaseModel):
    customer_name: str
    industry_segment: str = "ENTERPRISE"
    service_id: str = "SVC-001"


class CustomerUpdate(CustomerBody, VersionedBody):
    pass


class DepartmentBody(BaseModel):
    department_id: str
    department_name: str


class DepartmentUpdate(BaseModel):
    department_name: str
    row_version: int


class EmployeeCreateBody(BaseModel):
    employee_name: str
    department_id: str
    role_title: str = ""
    employee_id: str | None = None


class EmployeeUpdateBody(BaseModel):
    department_id: str
    employee_name: str | None = None
    role_title: str | None = None
    row_version: int


class LocationCreateBody(BaseModel):
    location_name: str = Field(min_length=1)


class LocationUpdateBody(BaseModel):
    location_name: str = Field(min_length=1)
    row_version: int


def _log_master_change(entity: str, entity_id: str, action: str, user: CurrentUser) -> None:
    log_event(
        logger,
        event="master_change",
        entity=entity,
        entity_id=entity_id,
        action=action,
        user_id=user.user_id,
        employee_id=user.employee_id,
    )


def _maybe_rebuild_summaries(old_name: str | None, new_name: str, background_tasks: BackgroundTasks) -> None:
    if old_name and old_name != new_name:
        background_tasks.add_task(_rag.rebuild_summaries_only)


@router.get("/incident-types")
def list_incident_types(
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> dict:
    return {"items": _repo.list_incident_types()}


@router.get("/incident-types/{type_id}")
def get_incident_type(
    type_id: str,
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> dict:
    item = _repo.get_incident_type(type_id)
    if not item:
        raise HTTPException(status_code=404, detail="種類が見つかりません")
    return item


@router.post("/incident-types", status_code=201)
def create_incident_type(
    body: IncidentTypeCreate,
    user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    item = _repo.create_incident_type(body.model_dump(), operator_id=user.employee_id)
    _log_master_change("incident_type", item["type_id"], "create", user)
    return item


@router.put("/incident-types/{type_id}")
def update_incident_type(
    type_id: str,
    body: IncidentTypeUpdate,
    user: Annotated[CurrentUser, Depends(require_admin())],
    background_tasks: BackgroundTasks,
) -> dict:
    old = _repo.get_incident_type(type_id)
    if not old:
        raise HTTPException(status_code=404, detail="種類が見つかりません")
    try:
        item = _repo.update_incident_type(
            type_id,
            body.model_dump(exclude={"row_version"}),
            row_version=body.row_version,
            operator_id=user.employee_id,
        )
    except OptimisticLockError as exc:
        return conflict_json_response(exc)
    _log_master_change("incident_type", type_id, "update", user)
    _maybe_rebuild_summaries(old.get("type_name"), item["type_name"], background_tasks)
    return item


@router.get("/services")
def list_services(_user: Annotated[CurrentUser, Depends(require_any_authenticated())]) -> dict:
    return {"items": _repo.list_services()}


@router.get("/services/{service_id}")
def get_service(
    service_id: str,
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> dict:
    item = _repo.get_service(service_id)
    if not item:
        raise HTTPException(status_code=404, detail="サービスが見つかりません")
    return item


@router.post("/services", status_code=201)
def create_service(
    body: ServiceBody,
    user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    item = _repo.create_service(body.model_dump(), operator_id=user.employee_id)
    _log_master_change("service", item["service_id"], "create", user)
    return item


@router.put("/services/{service_id}")
def update_service(
    service_id: str,
    body: ServiceUpdate,
    user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    try:
        item = _repo.update_service(
            service_id,
            body.model_dump(exclude={"row_version"}),
            row_version=body.row_version,
            operator_id=user.employee_id,
        )
    except OptimisticLockError as exc:
        return conflict_json_response(exc)
    _log_master_change("service", service_id, "update", user)
    return item


@router.get("/customers")
def list_customers(_user: Annotated[CurrentUser, Depends(require_any_authenticated())]) -> dict:
    return {"items": _repo.list_customers()}


@router.get("/customers/{customer_id}")
def get_customer(
    customer_id: str,
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> dict:
    item = _repo.get_customer(customer_id)
    if not item:
        raise HTTPException(status_code=404, detail="顧客が見つかりません")
    return item


@router.post("/customers", status_code=201)
def create_customer(
    body: CustomerBody,
    user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    item = _repo.create_customer(body.model_dump(), operator_id=user.employee_id)
    _log_master_change("customer", item["customer_id"], "create", user)
    return item


@router.put("/customers/{customer_id}")
def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    try:
        item = _repo.update_customer(
            customer_id,
            body.model_dump(exclude={"row_version"}),
            row_version=body.row_version,
            operator_id=user.employee_id,
        )
    except OptimisticLockError as exc:
        return conflict_json_response(exc)
    _log_master_change("customer", customer_id, "update", user)
    return item


@router.get("/employees")
def list_employees(_user: Annotated[CurrentUser, Depends(require_any_authenticated())]) -> dict:
    return {"items": _repo.list_employees()}


@router.get("/employees/{employee_id}")
def get_employee(
    employee_id: str,
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> dict:
    item = _repo.get_employee(employee_id)
    if not item:
        raise HTTPException(status_code=404, detail="従業員が見つかりません")
    return item


@router.post("/employees", status_code=201)
def create_employee(
    body: EmployeeCreateBody,
    user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    item = _repo.create_employee_history(body.model_dump(), operator_id=user.employee_id)
    _log_master_change("employee", item["employee_id"], "create", user)
    return item


@router.put("/employees/{employee_id}")
def update_employee(
    employee_id: str,
    body: EmployeeUpdateBody,
    user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    try:
        item = _repo.update_employee_current(
            employee_id,
            body.model_dump(exclude={"row_version"}),
            row_version=body.row_version,
            operator_id=user.employee_id,
        )
    except OptimisticLockError as exc:
        return conflict_json_response(exc)
    except ValueError:
        raise HTTPException(status_code=404, detail="従業員が見つかりません") from None
    _log_master_change("employee", employee_id, "update", user)
    return item


@router.get("/departments")
def list_departments(_user: Annotated[CurrentUser, Depends(require_any_authenticated())]) -> dict:
    return {"items": _repo.list_departments()}


@router.get("/departments/{department_id}")
def get_department(
    department_id: str,
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())],
) -> dict:
    item = _repo.get_department(department_id)
    if not item:
        raise HTTPException(status_code=404, detail="部署が見つかりません")
    return item


@router.post("/departments", status_code=201)
def create_department(
    body: DepartmentBody,
    user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    item = _repo.create_department(body.model_dump(), operator_id=user.employee_id)
    _log_master_change("department", item["department_id"], "create", user)
    return item


@router.put("/departments/{department_id}")
def update_department(
    department_id: str,
    body: DepartmentUpdate,
    user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    try:
        item = _repo.update_department(
            department_id,
            body.model_dump(exclude={"row_version"}),
            row_version=body.row_version,
            operator_id=user.employee_id,
        )
    except OptimisticLockError as exc:
        return conflict_json_response(exc)
    _log_master_change("department", department_id, "update", user)
    return item


@router.get("/incident-type-locations")
def list_incident_type_locations(
    type_id: str = Query(...),
    _user: Annotated[CurrentUser, Depends(require_any_authenticated())] = None,
) -> dict:
    return {"items": _repo.list_incident_type_locations(type_id)}


@router.post("/incident-type-locations", status_code=201)
def create_incident_type_location(
    body: LocationCreateBody,
    type_id: str = Query(...),
    user: Annotated[CurrentUser, Depends(require_admin())] = ...,
) -> dict:
    if not _repo.get_incident_type(type_id):
        raise HTTPException(status_code=404, detail="種類が見つかりません")
    item = _repo.create_incident_type_location(type_id, body.location_name, operator_id=user.employee_id)
    _log_master_change("incident_type_location", f"{type_id}/{body.location_name}", "create", user)
    return item


@router.put("/incident-type-locations/{type_id}/{location_name}")
def update_incident_type_location(
    type_id: str,
    location_name: str,
    body: LocationUpdateBody,
    user: Annotated[CurrentUser, Depends(require_admin())],
) -> dict:
    try:
        item = _repo.update_incident_type_location(
            type_id,
            location_name,
            body.location_name,
            row_version=body.row_version,
            operator_id=user.employee_id,
        )
    except OptimisticLockError as exc:
        return conflict_json_response(exc)
    _log_master_change("incident_type_location", f"{type_id}/{location_name}", "update", user)
    return item
