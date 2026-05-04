from __future__ import annotations

from html import escape as _esc

from app.core.models import Evento


class DigestBuilder:
    @staticmethod
    def build(processadora: str, mudancas: list[Evento]) -> tuple[str, str]:
        n = len(mudancas)
        plural = "alteração" if n == 1 else "alterações"
        assunto = f"[Alerta] Mudança de data de corte — {processadora} ({n} {plural})"

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
            <h2>Mudança de data de corte detectada</h2>
            <p><strong>Processadora:</strong> {processadora}</p>
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
