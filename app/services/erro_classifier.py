"""Classifica a causa de uma falha de coleta a partir da string de erro.

A categoria é derivada SOMENTE do texto de erro que o BaseScraper/collector já
captura (``scraper.run()['erro']``). Não inventa dado: quando não dá para
classificar, devolve ``"outro"`` e o chamador mantém a mensagem crua no Evento.
``falha_conhecida`` e ``nao_executou`` NÃO saem daqui — são decididos pelo
chamador (que tem o flag known_failure e o caso de gap).
"""
from __future__ import annotations

CATEGORIAS = (
    "auth_falhou",
    "rede",
    "fora_janela",
    "sem_dado",
    "timeout",
    "portal_mudou",
    "nao_executou",
    "falha_conhecida",
    "outro",
)

# Frase em português por categoria — camada humana do e-mail.
CATEGORIA_FRASE = {
    "auth_falhou": "falha de autenticação (login recusado)",
    "rede": "falha de rede/conexão durante a coleta",
    "fora_janela": "fora da janela de acesso do portal — coleta adiada",
    "sem_dado": "coletou mas não retornou data de corte",
    "timeout": "tempo esgotado durante a coleta",
    "portal_mudou": "página ou seletor mudou no portal",
    "nao_executou": "não foi coletada nesta rodada",
    "falha_conhecida": "falha conhecida (já mapeada)",
    "outro": "falha não classificada",
}

# Ordem importa: timeout antes de portal_mudou (um TimeoutError aguardando um
# seletor casa os dois; queremos "timeout").
_TIMEOUT = ("timeout", "timed out", "tempo esgotado", "deadline")
# Rede/conexão é checada ANTES de auth: uma falha de rede que menciona
# "autenticar"/"login" é transitória (técnica), não credencial — do contrário o
# retry de lote seria pulado indevidamente.
_REDE = (
    "rede", "conexão", "conexao", "connection", "network",
    "econnrefused", "econnreset", "econnaborted", "enetunreach", "ehostunreach",
    "enotfound", "net::err", "dns", "name not resolved", "name_not_resolved",
    "name resolution", "unreachable", "socket hang up",
    "ssl handshake", "tls handshake", "proxy",
)
_AUTH = (
    "autentic", "login", "senha", "credenc", "credential", "username",
    "password", "variável de ambiente", "variavel de ambiente",
    "unauthorized", "forbidden", "401", "403",
)
_SEM_DADO = (
    "sem dado", "sem registro", "nenhum registro", "no data", "vazio",
    "empty", "não foi possível extrair", "nao foi possivel extrair",
)
_PORTAL = (
    "não encontr", "nao encontr", "not found", "selector", "seletor",
    "locator", "element", "no node", "waiting for selector", "strict mode",
)


def classificar_erro(erro: str | None) -> str:
    """Mapeia a string de erro para uma categoria de `CATEGORIAS`."""
    if not erro:
        return "outro"
    e = str(erro).lower()
    if any(t in e for t in _TIMEOUT):
        return "timeout"
    if any(t in e for t in _REDE):
        return "rede"
    if any(t in e for t in _AUTH):
        return "auth_falhou"
    if any(t in e for t in _SEM_DADO):
        return "sem_dado"
    if any(t in e for t in _PORTAL):
        return "portal_mudou"
    return "outro"
