from app.services.collector_service import executar_coleta


def run() -> None:
    processadora = "consigfacil"
    executar_coleta(processadora)


if __name__ == "__main__":
    run()