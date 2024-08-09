import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.coder import PickleCoder
from fastapi_cache.decorator import cache

from asu import __version__
from asu.config import settings
from asu.routers import api
from asu.util import get_redis_client, parse_feeds_conf, parse_packages_file

logging.basicConfig(encoding="utf-8", level=settings.log_level)

base_path = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("ASU server starting up")
    FastAPICache.init(InMemoryBackend())
    yield
    # Any shutdown tasks here...
    logging.info("ASU server shutting down")


app = FastAPI(lifespan=lifespan)
app.include_router(api.router, prefix="/api/v1")

(settings.public_path / "json").mkdir(parents=True, exist_ok=True)
(settings.public_path / "store").mkdir(parents=True, exist_ok=True)

app.mount("/store", StaticFiles(directory=settings.public_path / "store"), name="store")
app.mount("/static", StaticFiles(directory=base_path / "static"), name="static")

templates = Jinja2Templates(directory=base_path / "templates")


@app.get("/", response_class=HTMLResponse)
@cache(expire=600, coder=PickleCoder)
def index(request: Request):
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


@app.get("/json/v1/{path:path}/index.json")
@cache(expire=600)
def json_v1_target_index(path: str):
    return parse_packages_file((f"{settings.upstream_url}/{path}/packages"))


@app.get("/json/v1/{path:path}/{arch:path}-index.json")
@cache(expire=600)
def json_v1_arch_index(path: str, arch: str):
    feeds = parse_feeds_conf(f"{settings.upstream_url}/{path}/{arch}")
    packages = {}
    for feed in feeds:
        packages.update(
            parse_packages_file(f"{settings.upstream_url}/{path}/{arch}/{feed}")[
                "packages"
            ]
        )

    return packages


app.mount(
    "/json",
    StaticFiles(directory=settings.public_path / "json"),
    name="json",
)


@app.get("//{path:path}")
def api_double_slash(path: str):
    print(f"Redirecting double slash to single slash: {path}")
    return RedirectResponse(f"/{path}", status_code=301)


# very legacy
@app.get("/overview")
def api_overview():
    return RedirectResponse("/json/v1/overview.json", status_code=301)
