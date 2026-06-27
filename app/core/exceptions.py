class ConfigurationError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class CollectionError(Exception):
    """Erro de coleta com categoria conhecida (tipada) — evita a heurística de string."""
    def __init__(self, mensagem: str, categoria: str | None = None) -> None:
        super().__init__(mensagem)
        self.categoria = categoria