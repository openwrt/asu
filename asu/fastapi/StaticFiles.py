import os

from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles as FastApiStaticFiles

from starlette.staticfiles import PathLike
from starlette.types import Scope

class StaticFiles(FastApiStaticFiles):
    def __init__(
        self,
        *,
        directory: PathLike | None = None,
        packages: list[str | tuple[str, str]] | None = None,
        html: bool = False,
        check_dir: bool = True,
        follow_symlink: bool = False,
    ) -> None:
        super().__init__(
            directory=directory, 
            packages=packages, 
            html=html, 
            check_dir=check_dir, 
            follow_symlink=follow_symlink
        )
    
    def file_response(
        self,
        full_path: PathLike,
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(
            full_path, 
            stat_result, 
            scope, 
            status_code)
        if isinstance(response, FileResponse):
            response.headers["Content-Type"] = "application/octet-stream"
        return response;
