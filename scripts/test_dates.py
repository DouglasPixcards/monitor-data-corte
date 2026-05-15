import sys
sys.path.insert(0, ".")

from app.utils.dates import normalizar_data_corte

casos = [
    ("13/05/2026", "Maio de 2026",  "2026-05-15T18:00:00+00:00", "ConsigFacil - data completa"),
    ("15",         None,            "2026-05-15T18:00:00+00:00", "ConsigUp - so dia, sem mes_atual (fallback coletado_em)"),
    ("15",         "Maio de 2026", "2026-05-15T18:00:00+00:00", "ConSIGI/Konexia - so dia, mes por extenso"),
    ("15",         "04/05/2026",   "2026-05-15T18:00:00+00:00", "ConsigUp - so dia, mes_atual = data do aviso"),
    ("08",         "Maio de 2026", "2026-05-15T18:00:00+00:00", "dia com zero padding"),
    ("15/05/26",   None,           "2026-05-15T18:00:00+00:00", "ano com 2 digitos"),
    (None,         "Maio de 2026", "2026-05-15T18:00:00+00:00", "data_corte None"),
    ("15",         None,           None,                         "sem nenhuma referencia"),
]

for data_corte, mes_atual, coletado_em, desc in casos:
    resultado = normalizar_data_corte(data_corte, mes_atual, coletado_em)
    status = "OK" if resultado and len(resultado) == 10 and resultado[2] == "/" and resultado[5] == "/" else ("None" if resultado is None else "?")
    print(f"[{status}] {desc}")
    print(f"       entrada : {repr(data_corte)}")
    print(f"       mes_atual: {repr(mes_atual)}")
    print(f"       saida   : {repr(resultado)}")
    print()
