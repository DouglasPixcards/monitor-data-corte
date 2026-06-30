"""_estimar_data_corte aponta a PRÓXIMA virada (pra frente), não a última que já passou."""
from datetime import date, timedelta

from app.integrations.processors.safeconsig.collector import _estimar_data_corte


class _FakeClient:
    """Simula a API: competência atual até a virada, próxima a partir dela (inclusive)."""

    def __init__(self, virada: date, atual="07/2026", proxima="08/2026"):
        self.virada = virada
        self.atual = atual
        self.proxima = proxima
        self.chamadas = 0

    def consultar_mes_primeiro_desconto(self, data_hora):
        self.chamadas += 1
        d = date.fromisoformat(data_hora.split(" ")[0])
        return {"competencia": self.atual if d < self.virada else self.proxima}


def test_estima_a_proxima_virada_e_nao_a_passada():
    virada = date.today() + timedelta(days=15)
    client = _FakeClient(virada)
    # data_corte = dia ANTERIOR à próxima virada (= último dia da competência atual)
    assert _estimar_data_corte(client, "07/2026") == (virada - timedelta(days=1)).strftime("%d/%m/%Y")


def test_virada_logo_a_frente():
    virada = date.today() + timedelta(days=2)
    client = _FakeClient(virada)
    assert _estimar_data_corte(client, "07/2026") == (virada - timedelta(days=1)).strftime("%d/%m/%Y")


def test_virada_amanha_corte_e_hoje():
    virada = date.today() + timedelta(days=1)
    client = _FakeClient(virada)
    assert _estimar_data_corte(client, "07/2026") == date.today().strftime("%d/%m/%Y")


def test_virada_exatamente_no_horizonte_ainda_estima():
    # borda do horizonte (hoje+40): a virada está DENTRO → estima, não cai no fallback
    virada = date.today() + timedelta(days=40)
    client = _FakeClient(virada)
    assert _estimar_data_corte(client, "07/2026") == (virada - timedelta(days=1)).strftime("%d/%m/%Y")


def test_busca_binaria_e_logaritmica():
    client = _FakeClient(date.today() + timedelta(days=30))
    _estimar_data_corte(client, "07/2026")
    assert client.chamadas <= 8  # ~1 + ceil(log2(40)), não 40


def test_fallback_quando_proxima_virada_alem_do_horizonte():
    # virada além de 40 dias → no fim do horizonte ainda é a competência atual → None
    client = _FakeClient(date.today() + timedelta(days=60))
    assert _estimar_data_corte(client, "07/2026") is None
