from enum import Enum


class AuthType(str, Enum):
    CERTIFICATE = "certificate"
    LOGIN_PASSWORD = "login_password"


class CollectionStatus(str, Enum):
    OK = "ok"
    ERROR = "error"