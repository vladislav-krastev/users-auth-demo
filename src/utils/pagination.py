import asyncio
import re
from collections.abc import Awaitable, Callable

from fastapi import Request


async def get_in_memory_all[T](
    getter: (Callable[[int, int], Awaitable[list[T] | None]]),
    *,
    page_count=5,  # TODO: this is an arbitary chosen default
    page_size=100,  # TODO: this is an arbitary chosen default
) -> list[T]:
    """Provide GET-ALL functionality for storage backends that don't support it natively.

    Contiously makes batched paginated calls to `getter`, untill the first call with res==*None* or len(res) < `page_size`.
    ***I think*** any of those two events ***should*** signal that there are no more valid pages to get from `getter`.

    :param getter:
        A coroutine, that produces pages of instances of type `T`.
    :param int page_count:
        Count calls to `getter` per batch.
    :param int page_size:
        The `limit` sent to `getter` on each call.
    """

    async def wrapper(offset: int, limit: int) -> list[T] | None:
        return await getter(offset, limit)

    tasks: list[asyncio.Task[list[T] | None]]
    res: list[T] = []
    more_data = True
    while more_data:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(wrapper(offset=p * page_size, limit=page_size)) for p in range(page_count)]
        for t in tasks:
            tr = t.result()
            if tr is None:  # treat the first failed fetch as the end of the batches. TODO: logging
                more_data = False
                break
            res.extend(tr)
            more_data = len(tr) == page_size
    return res


async def get_in_memory_filtered[T](
    offset: int,
    limit: int,
    *,
    getter: (Callable[[int], Awaitable[list[T] | None]]),
    filter: (Callable[[list[T]], Awaitable[list[T]]]),
) -> tuple[list[T], int] | tuple[None, None]:
    """Get an in-memory filtered page of instances of type `T`.

    :param int offset:
        The offset from which to start reading pages from `getter`.
    :param int limit:
        The desired count of instances in the ***final*** result (i.e. the total count of all results from `filter`).
        Note, that even after all of the pages from `getter` (starting from `offset`) were processed,
        the `filter` calls might result in a total count of results < `limit`
        (obviously depending on what `getter` is returning and on how much of it `filter` is filtering out).
    :param getter:
        A coroutine producing pages of instances of type `T`.
    :param filter:
        A coroutine producing a filtered page of instances of type `T` from the result of `getter`.

    :return tuple[2]:
    - the first element is the final resulting page.
    - the second element is the "offset" of the last instance in the result, including the provided `offset`.
    This should be passed as the new `offset` arg on next call to this func to produce the next logical page.
    """
    res = await getter(offset)
    if res is None:
        return None, None
    res = await filter(res)

    page_count, last_page = 1, []
    while len(res) < limit:
        page = await getter(offset + page_count * limit)
        if page is None:
            return None, None
        page_count += 1
        last_page = page
        res.extend(await filter(page))
        # no more potential pages (semi- or full-), if even the current unfiltered page is not a full-page:
        if len(page) < limit:
            break

    new_offset = offset + page_count * limit
    if len(res) > limit:
        # count records from the final internal page, that will be dropped
        # from the actual response to conform to the provided `limit` param:
        for i in range(len(last_page) - 1, 0, -1):
            if last_page[i] in res:
                new_offset -= len(last_page) - i
                break
        res = res[:limit]

    return res, new_offset


async def get_in_sqljoin_filtered():
    """
    TODO: the storage providers of the SessionsService and the UsersService are too decoupled, don't see any obvious,
        non-dumb way of JOINing SELECTs from each, in the edge-case where both providers are (the same) RDBMS (server).
    TODO: Same issue when both providers are on DynamoDB.
    """


def http_offset_limit_next_link(
    req: Request,
    /,
    current_count: int,
    explicit_offset: int | None = None,
) -> str | None:
    """Generate a 'next-link' for an offset-limit paginated Response.

    :param fastapi.Request req:
        The request that produced the Response.
    :param int current_count:
        The count of items that will be returned in the Response.
    :param int | None explicit_offset:
        If provided, is strictly used as the value for the 'offset' query-param in the return value,
        regardles of the contents of `req.url.components.query` and the provided value of `current_count`.
        Useful for links for pagination using custom logic for what the next 'offset' query-param should be.

    :return str:
        A ready-to-use 'next-page' link.
    """
    limit_param = int(req.query_params.get("limit", 0))
    if limit_param == 0 or current_count < limit_param:
        return None
    offset_param = req.query_params.get("offset", None)
    if offset_param is None:
        return (
            req.url.components.path
            + "?"
            + req.url.components.query
            + f"&offset={explicit_offset if explicit_offset else limit_param}"
        )
    return (
        req.url.components.path
        + "?"
        + re.sub(
            r"(?<=offset=)\d*",
            str(explicit_offset if explicit_offset else int(offset_param) + limit_param),
            req.url.components.query,
        )
    )
