import asyncio

from config import AppConfig
from services.sessions import SessionsService
from services.users import AdminUser, UsersService
from utils import logging, password


async def setup_services() -> bool:
    """Finish initialising the `Sessions` and the `Users` services."""
    async with asyncio.TaskGroup() as tg:
        u = tg.create_task(UsersService.setup())
        s = tg.create_task(SessionsService.setup())
    return u.result() and s.result()


super_admin_log = logging.getLogger("super-admin")


async def ensure_super_admin() -> bool:
    """Ensure the super ADMIN `User` exists in the UsersProvider storage."""
    n, p = AppConfig.USERS.SUPER_ADMIN_USERNAME, AppConfig.USERS.SUPER_ADMIN_INITIAL_PASSWORD
    existing = await UsersService.get_many(AdminUser, limit=2, is_admin_super=True)
    if existing is None:
        super_admin_log.error("failed: internal error. Is there an active connection to the USERS storage provider?")
        return False
    if len(existing) > 1:
        super_admin_log.error("failed: found existing: too many already exist. Required: 0 or 1, found: > 1")
        return False
    if len(existing) == 1:
        if existing[0].username != n:
            super_admin_log.error(
                f"failed: found existing: invalid username. Required: '{n}', found: '{existing[0].username}'"
            )
            return False
        super_admin_log.info("skipping: already exists")
        return True
    super_admin_log.info("creating ...")
    created = await UsersService.create(AdminUser(username=n, password=password.hash_create(p), is_admin_super=True))
    if created is None:
        super_admin_log.error("failed: internal error. Is there an active connection to the USERS storage provider?")
        return False
    super_admin_log.info("created!")
    return True
