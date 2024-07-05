import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import CollectorRegistry, make_asgi_app

from asu import __version__
from asu.config import settings
from asu.metrics import BuildCollector
from asu.routers import api
from asu.util import get_redis_client

logging.basicConfig(encoding="utf-8", level=settings.log_level)

base_path = Path(__file__).resolve().parent


app = FastAPI()
app.include_router(api.router, prefix="/api/v1")

(settings.public_path / "json").mkdir(parents=True, exist_ok=True)

app.mount("/json", StaticFiles(directory=settings.public_path / "json"), name="json")
app.mount("/store", StaticFiles(directory=settings.public_path), name="store")
app.mount("/static", StaticFiles(directory=base_path / "static"), name="static")


registry = CollectorRegistry()
registry.register(BuildCollector())
metrics_app = make_asgi_app(registry)
app.mount("/metrics", metrics_app)

templates = Jinja2Templates(directory=base_path / "templates")

redis_client = get_redis_client()

branches = dict(
    map(
        lambda b: (
            b,
            {
                "versions": list(redis_client.smembers(f"versions:{b}")),
            },
        ),
        redis_client.smembers("branches"),
    )
)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="overview.html",
        context=dict(
            branches=branches,
            defaults=settings.allow_defaults,
            version=__version__,
            server_stats=settings.server_stats,
        ),
    )
