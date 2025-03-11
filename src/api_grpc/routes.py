from protos.v_1_0_0 import users_pb2, users_pb2_grpc
from services.auth import AuthNormalUserService
from utils import exceptions, logging


log = logging.getLogger("grpc")


class UsersServicer(users_pb2_grpc.UsersServicer):
    async def IsValidToken(self, request: users_pb2.AuthTokenRequest, context) -> users_pb2.AuthTokenIsValid:
        log_prefix = f"/{self.__class__.__name__}/IsValidToken"
        log.info(f"GET {log_prefix}")
        with log.any_error(), log.with_prefix(log_prefix):
            try:
                await AuthNormalUserService.authenticate(request.token)
                return users_pb2.AuthTokenIsValid(is_valid=True)
            except exceptions.InvalidTokenError:
                return users_pb2.AuthTokenIsValid(is_valid=False)
        return users_pb2.AuthTokenIsValid(is_valid=False)
