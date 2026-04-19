"""
Routers Package
===============
FastAPI routers for xMixing API.
"""

from .router_auth import router as auth_router
from .router_users import router as users_router
from .router_ingredients import router as ingredients_router
from .router_skus import router as skus_router
from .router_production import router as production_router
from .router_plants import router as plants_router
from .router_monitoring import router as monitoring_router
from .router_views import router as views_router
from .router_warehouses import router as warehouses_router
from .router_translations import router as translations_router
from .router_stock_adjustments import router as stock_adjustments_router
from .router_reports import router as reports_router
from .router_db_sync import router as db_sync_router
from .router_server_station import router as server_station_router
from .router_remote_server import router as remote_server_router
from .router_plc import router as plc_router
from .router_edge import router as edge_router

__all__ = [
    "auth_router",
    "users_router", 
    "ingredients_router",
    "skus_router",
    "production_router",
    "plants_router",
    "monitoring_router",
    "views_router",
    "warehouses_router",
    "translations_router",
    "stock_adjustments_router",
    "reports_router",
    "db_sync_router",
    "server_station_router",
    "remote_server_router",
    "plc_router",
    "edge_router"
]
