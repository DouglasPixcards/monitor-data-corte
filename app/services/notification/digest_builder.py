from __future__ import annotations

from html import escape as _esc

from app.core.models import Evento

_FOLHA_VIRADA = "virada_competencia"

_DISCLAIMER_VIRADA = (
    "Este dado é uma <strong>estimativa de virada de competência</strong> coletada via API SafeConsig, "
    "não uma data de corte oficial confirmada. "
    "Verifique com a processadora antes de tomar decisões operacionais."
)


class DigestBuilder:
    @staticmethod
    def build(processadora: str, mudancas: list[Evento]) -> tuple[str, str]:
        n = len(mudancas)
        plural = "alteração" if n == 1 else "alterações"

        is_virada = any(e.folha == _FOLHA_VIRADA for e in mudancas)

        if is_virada:
            assunto = f"[Alerta] Alteração na estimativa de competência — {processadora} ({n} {plural})"
            titulo = "Alteração na estimativa de competência detectada"
            disclaimer_html = (
                f'<p style="background:#fff8e1;border-left:4px solid #f9a825;'
                f'padding:10px 14px;margin:12px 0">'
                f'<em>{_DISCLAIMER_VIRADA}</em></p>'
            )
        else:
            assunto = f"[Alerta] Mudança de data de corte — {processadora} ({n} {plural})"
            titulo = "Mudança de data de corte detectada"
            disclaimer_html = ""

        linhas = "".join(
            f"""
            <tr>
                <td style="padding:6px 12px">{_esc(e.convenio_key or '')}</td>
                <td style="padding:6px 12px">{_esc(e.folha or '-')}</td>
                <td style="padding:6px 12px">{_esc(e.mes_atual or '-')}</td>
                <td style="padding:6px 12px">{_esc(e.data_corte_anterior or '-')}</td>
                <td style="padding:6px 12px"><strong>{_esc(e.data_corte_nova or '-')}</strong></td>
            </tr>"""
            for e in mudancas
        )

        corpo = f"""
        <html>
        <body style="font-family:sans-serif">
            <h2>{_esc(titulo)}</h2>
            <p><strong>Processadora:</strong> {_esc(processadora)}</p>
            {disclaimer_html}
            <table border="1" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
                <thead>
                    <tr style="background:#f0f0f0">
                        <th style="padding:6px 12px">Convênio</th>
                        <th style="padding:6px 12px">Folha</th>
                        <th style="padding:6px 12px">Mês</th>
                        <th style="padding:6px 12px">Antes</th>
                        <th style="padding:6px 12px">Depois</th>
                    </tr>
                </thead>
                <tbody>{linhas}</tbody>
            </table>
        </body>
        </html>
        """

        return assunto, corpo
