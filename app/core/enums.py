from enum import Enum


class AuthType(str, Enum):
    CERTIFICATE = "certificate"
    LOGIN_PASSWORD = "login_password"


class CollectionStatus(str, Enum):
    OK = "ok"
    ERROR = "erro"
    PARTIAL_SUCCESS = "partial_success"


class EventoTipo(str, Enum):
    DATA_CORTE_ALTERADA = "data_corte_alterada"
    REGISTRO_NOVO = "registro_novo"
    REGISTRO_NAO_ENCONTRADO = "registro_nao_encontrado"
    ERRO_COLETA = "erro_coleta"