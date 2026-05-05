"""
Entrypoint alternativo para rodar a API diretamente:

    python -m app.main

Equivalente a:

    uvicorn app.api.main:app --reload
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)
