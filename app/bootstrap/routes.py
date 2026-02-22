from __future__ import annotations

from fastapi import FastAPI

from app.bootstrap.contracts import ProtectedDependencies
from app.routes import register_routes


def register_domain_routes(api: FastAPI, *, protected_dependencies: ProtectedDependencies) -> None:
    register_routes(api, dependencies=protected_dependencies)
