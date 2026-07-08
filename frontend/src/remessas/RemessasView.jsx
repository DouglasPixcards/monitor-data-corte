import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  abrirCompetencia, executarColeta, fetchAuditoria, fetchCiclos, fetchCompetencias,
  fetchRemessasMetricas, fmtDataISO, fmtMoney, informarDataCorte, patchCiclo, syncRemessas,
} from '../lib.js'
import { useUser } from '../auth.jsx'
import AdminPanel from './AdminPanel.jsx'

const STATUS_LABEL = { automatico: 'automático', pendente: 'pendente', enviado: 'enviado' }

// ── Botão copiar (SVG) ────────────────────────────────────────────────────────
const IconeCopiar = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="9" y="9" width="13" height="13" rx="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
)
const IconeOk = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M20 6 9 17l-5-5" />
  </svg>
)

export function CopyButton({ valor }) {
  const [ok, setOk] = useState(false)
  const copiar = async (e) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(String(valor))
    } catch {
      const ta = document.createElement('textarea')
      ta.value = String(valor)
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setOk(true)
    setTimeout(() => setOk(false), 1500)
  }
  return (
    <button className={`copy-btn ${ok ? 'ok' : ''}`} onClick={copiar}
            title={ok ? 'Copiado!' : 'Copiar código do empregador'}>
      {ok ? <IconeOk /> : <IconeCopiar />}
    </button>
  )
}

// ── Células editáveis ─────────────────────────────────────────────────────────
function CellEdit({ valor, exibicao, tipo = 'text', podeEditar, onSalvar, placeholder = '—' }) {
  const [editando, setEditando] = useState(false)
  const [rascunho, setRascunho] = useState('')
  const [salvando, setSalvando] = useState(false)
  const ref = useRef(null)

  useEffect(() => { if (editando && ref.current) ref.current.focus() }, [editando])

  const abrir = () => {
    if (!podeEditar || salvando) return
    setRascunho(valor ?? '')
    setEditando(true)
  }
  const salvar = async () => {
    setEditando(false)
    const novo = rascunho === '' ? null : rascunho
    if ((valor ?? null) === novo) return
    setSalvando(true)
    try { await onSalvar(novo) } finally { setSalvando(false) }
  }
  if (editando) {
    return (
      <input
        ref={ref} className="cel-input" type={tipo} value={rascunho}
        onChange={(e) => setRascunho(e.target.value)}
        onBlur={salvar}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.target.blur()
          if (e.key === 'Escape') setEditando(false)
        }}
      />
    )
  }
  const vazio = exibicao == null || exibicao === ''
  return (
    <span
      className={`cel ${podeEditar ? 'editavel' : ''} ${vazio ? 'vazia' : ''} ${salvando ? 'salvando' : ''}`}
      onClick={abrir} title={podeEditar ? 'Clique para editar' : undefined}
    >
      {vazio ? placeholder : exibicao}
    </span>
  )
}

function CellCheck({ valor, podeEditar, onSalvar }) {
  const [salvando, setSalvando] = useState(false)
  const toggle = async () => {
    if (!podeEditar || salvando) return
    setSalvando(true)
    try { await onSalvar(!valor) } finally { setSalvando(false) }
  }
  return (
    <span className={`cel-check ${valor ? 'sim' : ''} ${podeEditar ? 'editavel' : ''}`}
          onClick={toggle} title={podeEditar ? 'Marcar/desmarcar validado' : undefined}>
      {valor ? '✓' : '—'}
    </span>
  )
}

// Corte banksoft: SEMPRE editável pra quem pode escrever (digita a própria data);
// a sugestão (data_site − 7d) é um chip de aceite rápido AO LADO — nunca bloqueia.
function BanksoftCell({ ciclo, podeEditar, salvarCampo }) {
  return (
    <span className="banksoft">
      <CellEdit
        valor={ciclo.corte_banksoft} exibicao={fmtDataISO(ciclo.corte_banksoft)} tipo="date"
        podeEditar={podeEditar} onSalvar={(v) => salvarCampo('corte_banksoft', v)}
        placeholder={podeEditar ? 'definir' : '—'}
      />
      {!ciclo.corte_banksoft && ciclo.sugestao_corte_banksoft && podeEditar && (
        <button className="chip-acao"
                title="Aceitar a sugestão (data site − 7 dias)"
                onClick={() => salvarCampo('corte_banksoft', ciclo.sugestao_corte_banksoft)}>
          {fmtDataISO(ciclo.sugestao_corte_banksoft)} ✓
        </button>
      )}
    </span>
  )
}

// data_site: monitorado = leitura (vermelho quando mudou); não-monitorado = input manual.
function DataSiteCell({ ciclo, role, salvarCampo, onReload, onErro }) {
  const [ocupado, setOcupado] = useState(false)
  const monitorado = !!ciclo.registro.monitor_key || role === 'operacoes'
  const podeCiente = role !== 'operacoes'

  const informar = async () => {
    const dataBR = prompt('Data de corte vista no portal (DD/MM/AAAA):')
    if (!dataBR) return
    setOcupado(true)
    try {
      await informarDataCorte(ciclo.registro.monitor_key, dataBR.trim())
      await syncRemessas(ciclo.competencia)
      onReload()
    } catch (e) { onErro(e.message) } finally { setOcupado(false) }
  }
  const coletar = async () => {
    if (!confirm('Disparar a coleta agora? Pode levar alguns minutos.')) return
    setOcupado(true)
    try {
      await executarColeta(ciclo.registro.monitor_key)
      await syncRemessas(ciclo.competencia)
      onReload()
    } catch (e) { onErro(e.message) } finally { setOcupado(false) }
  }

  if (ciclo.a_coletar) {
    return (
      <span className="a-coletar-wrap">
        <em className="tag a-coletar" title="Ainda sem data coletada nesta competência">
          {ocupado ? 'coletando…' : 'A coletar'}
        </em>
        {role !== 'operacoes' && !ocupado && (
          <>
            <button className="chip-acao" onClick={informar} title="Vi a data no portal — informar manualmente">informar</button>
            <button className="chip-acao" onClick={coletar} title="Rodar o scraper agora">coletar</button>
          </>
        )}
      </span>
    )
  }
  if (monitorado) {
    return (
      <span className={ciclo.data_site_alterada ? 'alterada' : ''}
            title={ciclo.data_site_alterada && ciclo.data_site_anterior
              ? `Mudou! Era ${fmtDataISO(ciclo.data_site_anterior)}` : undefined}>
        {fmtDataISO(ciclo.data_site) ?? '—'}
        {ciclo.data_site_alterada && podeCiente && (
          <button className="chip-acao" title="Marcar como ciente da mudança"
                  onClick={() => salvarCampo('data_site_alterada', false)}>ciente</button>
        )}
      </span>
    )
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      {ciclo.registro.link_portal && (
        <a className="link-portal" href={ciclo.registro.link_portal} target="_blank"
           rel="noreferrer" title="Abrir o portal do convênio" onClick={(e) => e.stopPropagation()}>🔗</a>
      )}
      <CellEdit
        valor={ciclo.data_site} exibicao={fmtDataISO(ciclo.data_site)} tipo="date"
        podeEditar onSalvar={(v) => salvarCampo('data_site', v)} placeholder="informar"
      />
    </span>
  )
}

function DivergenciaIcone({ ativo, titulo }) {
  if (!ativo) return null
  return <em className="diverg" title={titulo}>⚠️</em>
}

// Observação: truncada na célula; clique abre um editor confortável (textarea).
function ObsCell({ valor, podeEditar, onSalvar }) {
  const [aberto, setAberto] = useState(false)
  const [rascunho, setRascunho] = useState('')
  const [salvando, setSalvando] = useState(false)

  const abrir = () => {
    if (!podeEditar) return
    setRascunho(valor ?? '')
    setAberto(true)
  }
  const salvar = async () => {
    setSalvando(true)
    try {
      await onSalvar(rascunho.trim() === '' ? null : rascunho.trim())
      setAberto(false)
    } finally { setSalvando(false) }
  }
  return (
    <>
      <span className={`cel ${podeEditar ? 'editavel' : ''} ${!valor ? 'vazia' : ''}`}
            onClick={abrir} title={valor || (podeEditar ? 'Clique para anotar' : undefined)}>
        {valor || (podeEditar ? 'anotar' : '—')}
      </span>
      {aberto && (
        <div className="modal-overlay" onClick={() => setAberto(false)}>
          <div className="modal obs-modal" onClick={(e) => e.stopPropagation()}>
            <header className="modal-head">
              <b>Observação</b>
              <button className="fechar" onClick={() => setAberto(false)} aria-label="Fechar">×</button>
            </header>
            <textarea autoFocus value={rascunho} maxLength={2000}
                      placeholder="Anotações sobre esta remessa..."
                      onChange={(e) => setRascunho(e.target.value)} />
            <div className="obs-acoes">
              <button className="acao" onClick={() => setAberto(false)}>Cancelar</button>
              <button className="btn-primario" onClick={salvar} disabled={salvando}>
                {salvando ? 'Salvando...' : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// ── Linhas da tabela ──────────────────────────────────────────────────────────
function CicloRow({ ciclo, role, onPatch, onAbrirAuditoria, onErro, onReload }) {
  const salvarCampo = useCallback(async (campo, valor) => {
    try {
      const atualizado = await patchCiclo(ciclo.id, { [campo]: valor })
      onPatch(atualizado)
    } catch (e) {
      onErro(`${ciclo.registro.nome}: ${e.message}`)
    }
  }, [ciclo.id, ciclo.registro.nome, onPatch, onErro])

  const escreveConc = role === 'conciliacao' || role === 'admin'
  const escreveOper = role === 'operacoes' || role === 'admin'
  const ehAdmin = role === 'admin'
  const produtos = ciclo.registro.produtos || {}

  const codCell = (
    <td>
      <span className="rem-cod">{ciclo.registro.cod_empr}<CopyButton valor={ciclo.registro.cod_empr} /></span>
    </td>
  )
  const nomeCell = (
    <td>
      <span className={`rem-nome ${ehAdmin ? 'clicavel' : ''}`}
            onClick={ehAdmin ? () => onAbrirAuditoria(ciclo) : undefined}
            title={ehAdmin ? 'Ver histórico de alterações (auditoria)' : undefined}>
        {ciclo.registro.nome}
      </span>
      {ciclo.atraso_mes_anterior && (
        <em className="tag alerta-atraso"
            title="No mês anterior a remessa foi enviada APÓS a data limite — atenção ao prazo deste ciclo">
          ⚠ atrasou mês passado
        </em>
      )}
    </td>
  )

  if (role === 'operacoes') {
    return (
      <tr>
        {codCell}
        {nomeCell}
        <td><DataSiteCell ciclo={ciclo} role={role} salvarCampo={salvarCampo} onReload={onReload} onErro={onErro} /></td>
        <td><BanksoftCell ciclo={ciclo} podeEditar={escreveOper} salvarCampo={salvarCampo} /></td>
      </tr>
    )
  }

  const prodCells = (habilitado, valorCampo, qtdCampo) => (
    habilitado ? (
      <>
        <td className="num">
          <CellEdit valor={ciclo[valorCampo]} exibicao={fmtMoney(ciclo[valorCampo])} tipo="number"
                    podeEditar={escreveConc} onSalvar={(v) => salvarCampo(valorCampo, v)} />
        </td>
        <td className="num">
          <CellEdit valor={ciclo[qtdCampo]} exibicao={ciclo[qtdCampo]} tipo="number"
                    podeEditar={escreveConc} onSalvar={(v) => salvarCampo(qtdCampo, v == null ? null : Number(v))} />
        </td>
      </>
    ) : (<><td className="na">·</td><td className="na">·</td></>)
  )

  return (
    <tr className={ciclo.envio_atrasado ? 'linha-atrasada' : ''}>
      {codCell}
      {nomeCell}
      <td><DataSiteCell ciclo={ciclo} role={role} salvarCampo={salvarCampo} onReload={onReload} onErro={onErro} /></td>
      <td className={ciclo.envio_atrasado ? 'envio-atrasado' : ''}
          title={ciclo.envio_atrasado ? 'Remessa enviada APÓS a data limite do site' : undefined}>
        <CellEdit valor={ciclo.data_envio} exibicao={fmtDataISO(ciclo.data_envio)} tipo="date"
                  podeEditar={escreveConc} onSalvar={(v) => salvarCampo('data_envio', v)} />
      </td>
      <td className="num">
        <CellEdit valor={ciclo.valor_enviado} exibicao={fmtMoney(ciclo.valor_enviado)} tipo="number"
                  podeEditar={escreveConc} onSalvar={(v) => salvarCampo('valor_enviado', v)} />
        <DivergenciaIcone ativo={ciclo.divergencia?.valor}
                          titulo="Valor enviado ≠ soma dos produtos preenchidos" />
      </td>
      <td className="num">
        <CellEdit valor={ciclo.qtd_contratos} exibicao={ciclo.qtd_contratos} tipo="number"
                  podeEditar={escreveConc}
                  onSalvar={(v) => salvarCampo('qtd_contratos', v == null ? null : Number(v))} />
        <DivergenciaIcone ativo={ciclo.divergencia?.qtd}
                          titulo="Qtd de contratos ≠ soma das qtds dos produtos" />
      </td>
      <td><em className={`tag st-${ciclo.status}`}>{STATUS_LABEL[ciclo.status] || ciclo.status}</em></td>
      {prodCells(produtos.credito, 'credito_valor', 'credito_qtd')}
      {prodCells(produtos.beneficio, 'beneficio_valor', 'beneficio_qtd')}
      {prodCells(produtos.compras, 'compras_valor', 'compras_qtd')}
      <td><BanksoftCell ciclo={ciclo} podeEditar={ehAdmin} salvarCampo={salvarCampo} /></td>
      <td><CellCheck valor={ciclo.validado} podeEditar={escreveConc}
                     onSalvar={(v) => salvarCampo('validado', v)} /></td>
      <td className="obs">
        <ObsCell valor={ciclo.observacao} podeEditar={escreveConc}
                 onSalvar={(v) => salvarCampo('observacao', v)} />
      </td>
    </tr>
  )
}

// ── Modal de auditoria (só admin chega aqui) ──────────────────────────────────
function AuditoriaModal({ ciclo, onFechar }) {
  const [linhas, setLinhas] = useState(null)
  useEffect(() => {
    let vivo = true
    fetchAuditoria(ciclo.id).then((l) => { if (vivo) setLinhas(l) }).catch(() => { if (vivo) setLinhas([]) })
    return () => { vivo = false }
  }, [ciclo.id])
  return (
    <div className="modal-overlay" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <b>Auditoria — {ciclo.registro.nome} · {ciclo.competencia}</b>
          <button className="fechar" onClick={onFechar} aria-label="Fechar">×</button>
        </header>
        {!linhas && <div className="estado">Carregando...</div>}
        {linhas && linhas.length === 0 && <div className="vazio">Sem alterações registradas.</div>}
        {linhas && linhas.length > 0 && (
          <ul className="timeline">
            {linhas.map((a, i) => (
              <li key={i} className="tl-item">
                <span className="tl-data">
                  {a.ocorrido_em ? new Date(a.ocorrido_em).toLocaleString('pt-BR',
                    { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'}
                </span>
                <span className="tl-mud">
                  <b>{a.usuario_nome}</b>{' '}
                  {a.acao === 'create' ? `criou (${a.valor_novo ?? ''})`
                    : a.acao === 'sync' ? `sync: ${a.valor_anterior ?? '—'} → ${a.valor_novo ?? '—'}`
                    : <>{a.campo}: {a.valor_anterior ?? '—'} → <b>{a.valor_novo ?? '—'}</b></>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

// ── Vista principal ───────────────────────────────────────────────────────────
const CABECALHO_FULL = [
  ['Cod'], ['Convênio'], ['Data site'], ['Data envio'],
  ['Valor enviado', 'num'], ['Qtd', 'num'], ['Status'],
  ['Crédito R$', 'num'], ['Qtd', 'num'], ['Benefício R$', 'num'], ['Qtd', 'num'],
  ['Compras R$', 'num'], ['Qtd', 'num'], ['Corte banksoft'], ['Val.'], ['Observação'],
]
const CABECALHO_OPER = [['Cod'], ['Convênio'], ['Data site'], ['Corte banksoft']]

export default function RemessasView() {
  const user = useUser()
  const role = user?.role
  const [competencia, setCompetencia] = useState(null)
  const [competencias, setCompetencias] = useState([])
  const [ciclos, setCiclos] = useState(null)
  const [busca, setBusca] = useState('')
  const [erro, setErro] = useState(null)
  const [auditoriaDe, setAuditoriaDe] = useState(null)
  const [mostrarAdmin, setMostrarAdmin] = useState(false)
  const [metricas, setMetricas] = useState(null)

  const carregar = useCallback(async (comp) => {
    setErro(null)
    try {
      const [cs, comps] = await Promise.all([fetchCiclos(comp), fetchCompetencias()])
      setCiclos(cs)
      setCompetencias(comps)
      if (!comp && cs.length) setCompetencia(cs[0].competencia)
      fetchRemessasMetricas(comp || (cs[0] && cs[0].competencia))
        .then(setMetricas).catch(() => setMetricas(null))
    } catch (e) {
      setErro(e.message)
      setCiclos([])
    }
  }, [])

  useEffect(() => { carregar(competencia) }, [])  // boot

  const trocarCompetencia = (comp) => {
    setCompetencia(comp)
    setCiclos(null)
    carregar(comp)
  }

  const mostrarErro = (msg) => {
    setErro(msg)
    setTimeout(() => setErro(null), 6000)
  }

  const abrirNova = async () => {
    const comp = prompt('Abrir competência (MM/YYYY):')
    if (!comp) return
    try {
      await abrirCompetencia(comp.trim())
      trocarCompetencia(comp.trim())
    } catch (e) { mostrarErro(e.message) }
  }

  const onPatch = useCallback((atualizado) => {
    setCiclos((atuais) => atuais.map((c) => (c.id === atualizado.id ? atualizado : c)))
  }, [])

  const filtrados = useMemo(() => {
    if (!ciclos) return null
    const b = busca.trim().toLowerCase()
    if (!b) return ciclos
    return ciclos.filter((c) =>
      c.registro.nome.toLowerCase().includes(b) || String(c.registro.cod_empr).includes(b))
  }, [ciclos, busca])

  const compAtual = competencia || (ciclos && ciclos[0]?.competencia) || ''
  const oper = role === 'operacoes'
  const cabecalho = oper ? CABECALHO_OPER : CABECALHO_FULL

  // Navegador de competência: setas ‹ › (a lista vem DESC do server) + dropdown por ano.
  const idxComp = competencias.findIndex((c) => c.competencia === compAtual)
  const irPara = (delta) => {
    const alvo = competencias[idxComp + delta]
    if (alvo) trocarCompetencia(alvo.competencia)
  }
  const porAno = useMemo(() => {
    const grupos = {}
    for (const c of competencias) {
      const ano = c.competencia.split('/')[1]
      ;(grupos[ano] = grupos[ano] || []).push(c)
    }
    return Object.entries(grupos).sort((a, b) => Number(b[0]) - Number(a[0]))
  }, [competencias])

  return (
    <div className="remessas">
      <div className="controls">
        <div className="comp-nav">
          <button className="seta" onClick={() => irPara(1)}
                  disabled={idxComp < 0 || idxComp >= competencias.length - 1}
                  title="Competência anterior">‹</button>
          <select className="filtro comp-select" value={compAtual}
                  onChange={(e) => trocarCompetencia(e.target.value)} aria-label="Competência">
            {!competencias.some((c) => c.competencia === compAtual) && compAtual &&
              <option value={compAtual}>{compAtual}</option>}
            {porAno.map(([ano, comps]) => (
              <optgroup key={ano} label={ano}>
                {comps.map((c) => (
                  <option key={c.competencia} value={c.competencia}>
                    {c.competencia} · {c.enviados}/{c.total - c.automaticos} enviados
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <button className="seta" onClick={() => irPara(-1)} disabled={idxComp <= 0}
                  title="Próxima competência">›</button>
        </div>
        <input className="busca" type="search" placeholder="Buscar convênio ou código..."
               value={busca} onChange={(e) => setBusca(e.target.value)} />
        {(role === 'admin' || role === 'conciliacao') && (
          <button className="acao" onClick={async () => {
            try {
              const r = await syncRemessas(compAtual)
              mostrarErro(`Sync: ${r.atualizados} atualizado(s), ${r.alterados} mudança(s)` +
                (r.conflitos.length ? `, ${r.conflitos.length} conflito(s)` : ''))
              carregar(compAtual)
            } catch (e) { mostrarErro(e.message) }
          }} title="Puxar as datas do monitor agora">↻ Sync</button>
        )}
        {(role === 'admin' || role === 'conciliacao') && compAtual && (
          <a className="acao" href={`/remessas/export?competencia=${encodeURIComponent(compAtual)}`}
             title="Baixar a planilha da competência">⬇ Excel</a>
        )}
        {role === 'admin' && (
          <>
            <button className="acao" onClick={abrirNova}>Abrir competência</button>
            <button className="acao" onClick={() => setMostrarAdmin(!mostrarAdmin)}>
              {mostrarAdmin ? 'Fechar cadastro' : 'Cadastro'}
            </button>
          </>
        )}
      </div>

      {metricas && !oper && (
        <div className="rem-metricas">
          <span><b>{metricas.por_status.enviado}</b> enviados</span>
          <span className="pend"><b>{metricas.por_status.pendente}</b> pendentes</span>
          <span><b>{metricas.por_status.automatico}</b> automáticos</span>
          <span><b>{metricas.validados}</b> validados</span>
          <span><b>{metricas.banksoft_pendentes}</b> sem corte banksoft</span>
          {metricas.lead_time_envio_medio_dias != null && (
            <span title="Média de dias entre o envio e a data limite do site">
              antecedência média <b>{metricas.lead_time_envio_medio_dias}d</b>
            </span>
          )}
          {metricas.envios_apos_data_site > 0 && (
            <span className="atraso"><b>{metricas.envios_apos_data_site}</b> enviados APÓS a data limite</span>
          )}
        </div>
      )}

      {erro && <div className="estado erro rem-erro">{erro}</div>}
      {mostrarAdmin && role === 'admin' && <AdminPanel onMudou={() => carregar(compAtual)} />}

      {!ciclos && !erro && <div className="estado">Carregando remessas...</div>}
      {ciclos && filtrados.length === 0 && <div className="vazio">Nenhum convênio nesta competência.</div>}
      {ciclos && filtrados.length > 0 && (
        <div className="rem-wrap">
          <table className="rem-table">
            <thead>
              <tr>
                {cabecalho.map(([rotulo, cls], i) => (
                  <th key={i} className={cls || ''}>{rotulo}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtrados.map((c) => (
                <CicloRow key={c.id} ciclo={c} role={role} onPatch={onPatch}
                          onAbrirAuditoria={setAuditoriaDe} onErro={mostrarErro}
                          onReload={() => carregar(compAtual)} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {auditoriaDe && <AuditoriaModal ciclo={auditoriaDe} onFechar={() => setAuditoriaDe(null)} />}
    </div>
  )
}
