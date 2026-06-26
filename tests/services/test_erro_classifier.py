from app.services.erro_classifier import classificar_erro


def test_timeout():
    assert classificar_erro("Timeout 30000ms exceeded. waiting for locator") == "timeout"


def test_auth_mensagem_do_portal():
    assert classificar_erro("[ConsigNet] Autenticação falhou — ainda em /auth/login") == "auth_falhou"


def test_auth_credencial_ausente():
    assert classificar_erro("Variável de ambiente ausente ou vazia: CONSIGNET_X_USERNAME") == "auth_falhou"


def test_rede_vence_auth_quando_falha_de_rede_ao_autenticar():
    # Mesmo contendo "autenticar", uma falha de REDE é técnica (transitória),
    # não credencial — senão o retry seria pulado indevidamente.
    assert classificar_erro("Falha de rede ao autenticar") == "rede"


def test_rede_connection_refused():
    assert classificar_erro("net::ERR_CONNECTION_REFUSED") == "rede"


def test_rede_conexao_recusada():
    assert classificar_erro("Erro de conexão com o portal: conexão recusada") == "rede"


def test_rede_dns():
    assert classificar_erro("getaddrinfo ENOTFOUND / name not resolved") == "rede"


def test_auth_sem_rede_continua_credencial():
    # Guarda de regressão: erro de credencial puro (sem termo de rede) segue auth.
    assert classificar_erro("[ConsigNet] senha inválida") == "auth_falhou"


def test_sem_dado():
    assert classificar_erro("[ConsigNet] Não foi possível extrair Cut-off Date") == "sem_dado"


def test_portal_mudou():
    assert classificar_erro("locator not found: .context-item") == "portal_mudou"


def test_outro():
    assert classificar_erro("erro inesperado xpto") == "outro"


def test_none_vira_outro():
    assert classificar_erro(None) == "outro"
