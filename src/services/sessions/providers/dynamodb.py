import typing
import uuid
from datetime import datetime, timezone

# from boto3 import (
#     client as boto3_client,
#     resource as boto3_resource,
# )
# from boto3.dynamodb.conditions import Attr, Key
# import botocore.exceptions
import pydantic
from pynamodb.attributes import (
    BooleanAttribute,
    UnicodeAttribute,
)
from pynamodb.exceptions import (
    PutError as PynamoDBPutError,
)
from pynamodb.exceptions import (
    PynamoDBException,
)
from pynamodb.exceptions import (
    UpdateError as PynamoDBUpdateError,
)
from pynamodb.models import (
    MetaProtocol as DynamoDBMetaProtocol,
)
from pynamodb.models import (
    Model as DynamoDBModel,
)
from starlette.concurrency import run_in_threadpool

from config.sessions import DynamoDBProviderConfig
from utils import logging

from .abstract import BaseSessionsProvider, Session


log = logging.getLogger("TODO")


class _InnerModel(DynamoDBModel):
    """ """

    # so pynamodb.models.MetaModel can init it with default values:
    class Meta(DynamoDBMetaProtocol): ...

    user_id = UnicodeAttribute(hash_key=True)
    session_id = UnicodeAttribute(range_key=True)
    is_valid = BooleanAttribute()
    expires_at = UnicodeAttribute()


class SessionsProviderDynamoDB(BaseSessionsProvider):
    def __init__(self, config: DynamoDBProviderConfig):
        #####
        host = None
        region = "us-east-1"
        table = "text-share-user-sessions"
        #####

        _InnerModel.Meta.host = host
        _InnerModel.Meta.region = region
        _InnerModel.Meta.table_name = table
        _InnerModel.Meta.aws_access_key_id = config.AWS_ACCESS_KEY
        _InnerModel.Meta.aws_secret_access_key = config.AWS_SECRET_KEY

        self._conn = _InnerModel._get_connection()

        # self._client = boto3_client(
        #     "dynamodb",
        #     aws_access_key_id=aws_access_key_id,
        #     aws_secret_access_key=aws_secret_access_key,
        #     region_name='us-east-1',
        #     # endpoint_url=service_url,
        # )
        # self._table = boto3_resource(
        #     "dynamodb",
        #     aws_access_key_id=aws_access_key_id,
        #     aws_secret_access_key=aws_secret_access_key,
        #     region_name='us-east-1',
        #     # endpoint_url=service_url,
        # ).Table(self._table_name)

    @staticmethod
    def _dynamo_item_to_model(i: _InnerModel) -> Session | None:
        try:
            return Session(
                user_id=uuid.UUID(i.user_id),
                id=i.session_id,
                is_valid=i.is_valid,
                expires_at=datetime.fromtimestamp(int(i.expires_at), tz=timezone.utc),
            )
        except (TypeError, ValueError, pydantic.ValidationError) as err:
            log.error(err)

    @typing.override
    async def create(self, s: Session) -> bool:
        created = _InnerModel(
            hash_key=str(s.user_id),
            range_key=s.id,
            **s.model_dump(mode="json", exclude={"user_id", "session_id"}),
        )
        try:
            # TODO: limit on max sessions?
            res = await run_in_threadpool(created.save)
            return res["ResponseMetadata"]["HTTPStatusCode"] == 200
        except Exception as err:
            log.error(err)
            return False

    @typing.override
    async def get(self, u_id: str, s_id: str) -> Session | None:
        try:
            res = await run_in_threadpool(
                _InnerModel.query,
                hash_key=str(u_id),
                range_key_condition=_InnerModel.session_id == s_id,
            )
            ret = res.next()
        except StopIteration:
            return None
        except PynamoDBException as err:
            log.error(err)
            return None
        try:
            res.next()
            log.error(f"Too many items from DynamoDB for user_id=={u_id} AND session_id=={s_id}")
        except StopIteration:
            return self._dynamo_item_to_model(ret)

    @typing.override
    async def invalidate(self, u_id: str, s_id: str) -> bool:
        try:
            res = await run_in_threadpool(
                self._conn.update_item,
                hash_key=u_id,
                range_key=s_id,
                actions=[_InnerModel.is_valid.set(False)],
            )
            return res["ResponseMetadata"]["HTTPStatusCode"] == 200
        except Exception as err:
            log.error(err)
            if isinstance(err, PynamoDBUpdateError):
                raise err from None
        return False

    @typing.override
    async def invalidate_all(self, u_id: str) -> bool:
        try:
            # TODO: non super-hacky way of running batch.commit() in its ow thread?
            with _InnerModel.batch_write() as batch:
                for r in await run_in_threadpool(_InnerModel.scan, _InnerModel.user_id == u_id):
                    batch.delete(r)
            return True
        except Exception as err:
            log.error(err)
            if isinstance(err, PynamoDBPutError):
                raise err from None
        return False
