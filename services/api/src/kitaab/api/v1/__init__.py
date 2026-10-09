"""Version 1 of the REST API, mounted at /api/v1."""

from fastapi import APIRouter

from kitaab.api.v1 import (
    admin_config,
    admin_finance,
    admin_orders,
    admin_people,
    auth,
    catalog,
    me,
    notifications,
    orders,
    uploads,
    vendor,
    webhooks,
)
from kitaab.problems import PROBLEM_RESPONSES

router = APIRouter(prefix="/api/v1", responses=PROBLEM_RESPONSES)
for module in (
    auth,
    me,
    catalog,
    uploads,
    orders,
    notifications,
    webhooks,
    admin_orders,
    admin_people,
    admin_config,
    admin_finance,
    vendor,
):
    router.include_router(module.router)
