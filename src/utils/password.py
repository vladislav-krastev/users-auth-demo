from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pydantic_core import MultiHostHost, MultiHostUrl


__password_hash = PasswordHash((Argon2Hasher(),))


def hash_create(password: str) -> str:
    """ """
    return __password_hash.hash(password)


def hash_verify(plain: str, hashed: str) -> bool:
    """ """
    return __password_hash.verify(plain, hashed)


def get_obscured_password_db_url(url: MultiHostUrl, char="*", count=5) -> MultiHostUrl:
    """ """
    new_hosts: list[MultiHostHost] = []
    for host in url.hosts():
        host.update(password=char * count)
        new_hosts.append(host)
    return MultiHostUrl.build(scheme=url.scheme, hosts=new_hosts)
