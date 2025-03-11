from datetime import datetime
from logging import getLogger
from typing import Any, cast, override
from uuid import uuid4, UUID

from pydantic import ValidationError as pydantic_ValidationError
from starlette.concurrency import run_in_threadpool

from pynamodb.attributes import (
    Attribute,
    BooleanAttribute,
    UnicodeAttribute,
)
from pynamodb.exceptions import PutError
from pynamodb.models import (
    MetaProtocol as DynamoDBMetaProtocol,
    Model as DynamoDBModel,
)

from config.users import DynamoDBProvider
from .abstract import BaseUsersProvider, BaseUser


_logger = getLogger('uvicorn.error')


class _InnerModel(DynamoDBModel):
    """ """
    # so pynamodb.models.MetaModel can init it with default values:
    class Meta(DynamoDBMetaProtocol): ...

    id = UnicodeAttribute(hash_key=True)
    email = UnicodeAttribute(null=True)
    username = UnicodeAttribute()
    password = UnicodeAttribute()
    is_admin = BooleanAttribute()
    created_at = UnicodeAttribute()


class UsersProviderDynamoDB(BaseUsersProvider):
    def __init__(self, config: DynamoDBProvider) -> None:
        #####
        host = None
        region = "us-east-1"
        table = "text-share-users"
        #####

        _InnerModel.Meta.host = host
        _InnerModel.Meta.region = region
        _InnerModel.Meta.table_name = table
        _InnerModel.Meta.aws_access_key_id = config.AWS_ACCESS_KEY
        _InnerModel.Meta.aws_secret_access_key = config.AWS_SECRET_KEY
        self._conn = _InnerModel._get_connection()

    @staticmethod
    def _dynamo_item_to_model(i: _InnerModel) -> BaseUser | None:
        try:
            return BaseUser(
                id=UUID(i.id),
                email=i.email,
                username=i.username,
                password=i.password,
                is_admin=i.is_admin,
                created_at=datetime.fromisoformat(i.created_at),
            )
        except (TypeError, ValueError, pydantic_ValidationError) as err:
            _logger.error(err)

    @override
    async def create(self, u: BaseUser) -> bool:
        created = _InnerModel(
            hash_key=str(u.id),
            **u.model_dump(mode="json", exclude={"id"}),
        )
        while True:
            try:
                res = await run_in_threadpool(created.save, _InnerModel.id.does_not_exist())
                return res["ResponseMetadata"]["HTTPStatusCode"] == 200
            except PutError:
                created.id = str(uuid4())
            except Exception as err:
                _logger.error(err)
                return False

    @override
    async def get_unique_by(self, f: str, v: Any) -> BaseUser | None:
        try:
            if f == _InnerModel._hash_keyname:
                res = await run_in_threadpool(_InnerModel.query, hash_key=str(v))
            else:
                res = await run_in_threadpool(_InnerModel.scan, filter_condition=getattr(_InnerModel, f) == v)
            ret = res.next()
        except StopIteration:
            return None
        except Exception as err:
            _logger.error(err)
            return None
        try:
            res.next()
            _logger.error(f"Too many items from DynamoDB for {f}=={v}")
        except StopIteration:
            return self._dynamo_item_to_model(ret)

    @override
    async def update(self, u_id: str, **kwargs) -> BaseUser | None:
        if len(kwargs) == 0:
            return None
        try:
            res = await run_in_threadpool(
                self._conn.update_item,
                u_id,
                actions=[
                    cast(Attribute[Any], getattr(_InnerModel, f)).set(v)
                    for f, v in kwargs.items()
                ],
                return_values="ALL_NEW",
            )
            if res["ResponseMetadata"]["HTTPStatusCode"] == 200:
                im = _InnerModel()
                im.from_dynamodb_dict(res["Attributes"])
                return self._dynamo_item_to_model(im)
        except Exception as err:
            _logger.error(err)

        # update_expression = []
        # expression_attribute_names = {}
        # expression_attribute_values = {}
        # for i, kvp in enumerate(kwargs.items()):
        #     update_expression.append(f"#field{i} = :field{i}")
        #     expression_attribute_names[f"#field{i}"] = kvp[0]
        #     expression_attribute_values[f":field{i}"] = kvp[1]
        # try:
        #     res = await get_event_loop().run_in_executor(
        #         None,
        #         lambda: self._table.update_item(
        #             Key={"id": u_id},
        #             UpdateExpression=f"SET {", ".join(update_expression)}",
        #             ExpressionAttributeNames=expression_attribute_names,
        #             ExpressionAttributeValues=expression_attribute_values,
        #             ReturnValues="ALL_NEW",
        #         )
        #     )
        #     if res["ResponseMetadata"]["HTTPStatusCode"] == 200:
        #         return self._user_item_to_model(res["Attributes"])
        # except botocore.exceptions.ClientError as err:
        #     _logger.error(err)
        # return None

    @override
    async def delete(self, u_id: str) -> bool:
        # try:
        #     res = (await get_event_loop().run_in_executor(
        #         None,
        #         lambda: self._table.delete_item(
        #             Key={"id": u_id},
        #         )
        #     ))
        #     if res["ResponseMetadata"]["HTTPStatusCode"] == 200:
        #         return True
        # except botocore.exceptions.ClientError as err:
        #     _logger.error(err)
        # return False
        raise NotImplementedError()
