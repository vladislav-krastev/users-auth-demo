import pathlib
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from api_grpc.server import GrpcServer
from api_rest.routes import router_admins, router_auth, router_users
from config import AppConfig
from utils import lifespan_hooks, logging


log = logging.getLogger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # TODO: how to correctly terminate from within the logger context-manager?
    # TODO: how to terminate without the traceback from starlette and fastapi?
    with log.any_error(exit_code=1):
        await lifespan_hooks.setup_services()
        await lifespan_hooks.ensure_super_admin()

    # # TODO: help with the PR on uvicorn for passing the current event loop, instead of this:
    grpc_server = GrpcServer()
    await grpc_server.start()
    yield
    await grpc_server.stop()


app = FastAPI(
    lifespan=lifespan,
    # swagger_ui_init_oauth={"clientId": ""},  # TODO: how to supply multiple OAuths URLs to OpenAPI/Swagger?
    swagger_ui_oauth2_redirect_url=f"/auth{AppConfig.OAUTH2.REDIRECT_ROUTE_PATH}",
    swagger_ui_parameters={
        "persistAuthorization": True,
    },
)
app.include_router(router_auth)
app.include_router(router_admins)
app.include_router(router_users)


if __name__ == "__main__":
    # acts as if "python -m uvicorn 'main:app' ..." was executed in the shell:
    with log.with_prefix("cli args parser:"), log.any_error(exit_code=1):
        # use a COPY of sys.argv, because '.make_context()' empties its 'args' input,
        # but uvicorn needs the original sys.argv to spawn new processes, if needed (e.g. the reloader, workers):
        ctx = uvicorn.main.make_context(None, args=sys.argv[:])
    ctx.params["app"] = "main:app"
    if "--reload" in sys.argv and "--reload-dir" not in sys.argv:
        sys.argv.append(f"--reload-dir {pathlib.Path(__file__).parent.resolve()}")
    ctx.forward(uvicorn.main)
