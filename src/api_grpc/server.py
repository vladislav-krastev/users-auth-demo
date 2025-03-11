import asyncio

import grpc

from config import AppConfig
from protos.v_1_0_0 import users_pb2_grpc
from utils import logging

from .routes import UsersServicer


# grpcurl -import-path ./users/protos/v_1_0_0/users.proto -d '{"token": "some test token"}' -plaintext localhost:50051 Users/IsValidToken


log = logging.getLogger("grpc")


class GrpcServer:
    __slots__ = ("__port", "__server", "__task")

    def __init__(self, port: int = AppConfig.GRPC.PORT):
        self.__port = port
        self.__task: asyncio.Task | None = None
        self.__server = grpc.aio.server()
        users_pb2_grpc.add_UsersServicer_to_server(
            UsersServicer(),
            self.__server,
        )
        self.__server.add_insecure_port(f"[::]:{self.__port}")

    async def start(self) -> None:
        """Start the `gRPC` server.

        Is idempotent.
        """
        if self.__task is None:
            log.info(f"starting server on port '{self.__port}'...")
            await self.__server.start()
            self.__task = asyncio.create_task(self.__server.wait_for_termination())
        log.info(f"server listening on port '{self.__port}'")

    async def stop(self, grace_seconds: int = 5) -> None:
        """Stop the `gRPC` server.

        Is idempotent.
        """
        if self.__task is not None:
            log.info("stopping server...")
            await self.__server.stop(grace_seconds)
            await asyncio.gather(self.__task)
        log.info("server stopped.")
