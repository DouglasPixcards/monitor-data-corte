from app.services.coleta_service import resumir_lote


def _c(key, status):
    return {"convenio_key": key, "convenio_nome": key, "status": status, "records_count": 0, "erro": None}


def test_resumir_lote_todos_ok():
    lote = resumir_lote("p", [_c("a", "ok"), _c("b", "ok")], [{"convenio_key": "a"}])
    assert lote["status"] == "ok"
    assert lote["success_count"] == 2
    assert lote["error_count"] == 0
    assert lote["fora_janela_count"] == 0
    assert lote["records"] == [{"convenio_key": "a"}]


def test_resumir_lote_misto():
    lote = resumir_lote("p", [_c("a", "ok"), _c("b", "erro"), _c("c", "fora_janela")], [])
    assert lote["status"] == "partial_success"
    assert lote["success_count"] == 1
    assert lote["error_count"] == 1
    assert lote["fora_janela_count"] == 1


def test_resumir_lote_todos_fora_janela():
    lote = resumir_lote("p", [_c("a", "fora_janela"), _c("b", "fora_janela")], [])
    assert lote["status"] == "fora_janela"
    assert lote["success_count"] == 0
    assert lote["error_count"] == 0
    assert lote["fora_janela_count"] == 2
