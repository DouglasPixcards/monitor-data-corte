import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  abrirCompetencia, executarColeta, fetchAuditoria, fetchCiclos, fetchCompetencias,
  fmtDataISO, fmtMoney, informarDataCorte, patchCiclo, syncRemessas,
} from '../lib.js'
import { useUser } from '../auth.jsx'
import AdminPanel from './AdminPanel.jsx'

const STATUS_LABEL = { automatico: 'automático', pendente: 'pendente', enviado: 'enviado' }

// ── Botão copiar (cod_empr) ───────────────────────────────────────────────────
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
    <button className="copy-btn" onClick={copiar} title="Copiar código do empregador">
      {ok ? '✓' : '📋'}
    </button>
  )
}

// ── Células editáveis ─────────────────────────────────────────────────────────
// Padrão: exibe o valor; clique → input; Enter/blur salva (PATCH), Esc cancela.
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
  return (
    <span
      className={`cel ${podeEditar ? 'editavel' : ''} ${salvando ? 'salvando' : ''}`}
      onClick={abrir} title={podeEditar ? 'Clique para editar' : undefined}
    >
      {exibicao ?? placeholder}
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
          onClick={toggle}>
      {valor ? '✓' : '—'}
    </span>
  )
}

// Corte banksoft: sugestão fantasma (data_site − 7d) com aceite em 1 clique.
function BanksoftCell({ ciclo, podeEditar, salvarCampo }) {
  if (!ciclo.corte_banksoft && ciclo.sugestao_corte_banksoft && podeEditar) {
    return (
      <span className="cel banksoft-sugestao">
        <em>{fmtDataISO(ciclo.sugestao_corte_banksoft)}?</em>
        <button
          className="aceitar"
          title="Aceitar a sugestão (data site − 7 dias)"
          onClick={() => salvarCampo('corte_banksoft', ciclo.sugestao_corte_banksoft)}
        >aceitar</button>
      </span>
    )
  }
  return (
    <CellEdit
      valor={ciclo.corte_banksoft} exibicao={fmtDataISO(ciclo.corte_banksoft)} tipo="date"
      podeEditar={podeEditar} onSalvar={(v) => salvarCampo('corte_banksoft', v)}
    />
  )
}

// data_site: monitorado = leitura (com vermelho quando mudou); não-monitorado = input manual.
function DataSiteCell({ ciclo, role, salvarCampo, onReload, onErro }) {
  const [ocupado, setOcupado] = useState(false)
  const monitorado = !!ciclo.registro.monitor_key || role === 'operacoes'
  const podeCiente = role !== 'operacoes'
  const cls = ciclo.data_site_alterada ? 'alterada' : ''

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
            <button className="aceitar" onClick={informar} title="Vi a data no portal — informar manualmente">informar</button>
            <button className="aceitar" onClick={coletar} title="Rodar o scraper agora">coletar</button>
          </>
        )}
      </span>
    )
  }
  if (monitorado) {
    return (
      <span className={`cel ${cls}`}
            title={ciclo.data_site_alterada && ciclo.data_site_anterior
              ? `Mudou! Era ${fmtDataISO(ciclo.data_site_anterior)}` : undefined}>
        {fmtDataISO(ciclo.data_site) ?? '—'}
        {ciclo.data_site_alterada && podeCiente && (
          <button className="aceitar" title="Marcar como ciente da mudança"
                  onClick={() => salvarCampo('data_site_alterada', false)}>ciente</button>
        )}
      </span>
    )
  }
  return (
    <span className={cls} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
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

// ── Linha do grid ─────────────────────────────────────────────────────────────
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
  const produtos = ciclo.registro.produtos || {}

  if (role === 'operacoes') {
    return (
      <div className="rem-row oper">
        <span className="cod"><b>{ciclo.registro.cod_empr}</b><CopyButton valor={ciclo.registro.cod_empr} /></span>
        <span className="nome">{ciclo.registro.nome}</span>
        <span><DataSiteCell ciclo={ciclo} role={role} salvarCampo={salvarCampo} onReload={onReload} onErro={onErro} /></span>
        <span><BanksoftCell ciclo={ciclo} podeEditar={escreveOper} salvarCampo={salvarCampo} /></span>
      </div>
    )
  }

  const prodCell = (habilitado, valorCampo, qtdCampo) => (
    habilitado ? (
      <>
        <span className="num">
          <CellEdit valor={ciclo[valorCampo]} exibicao={fmtMoney(ciclo[valorCampo])} tipo="number"
                    podeEditar={escreveConc} onSalvar={(v) => salvarCampo(valorCampo, v)} />
        </span>
        <span className="num">
          <CellEdit valor={ciclo[qtdCampo]} exibicao={ciclo[qtdCampo]} tipo="number"
                    podeEditar={escreveConc} onSalvar={(v) => salvarCampo(qtdCampo, v == null ? null : Number(v))} />
        </span>
      </>
    ) : (<><span className="num na">·</span><span className="num na">·</span></>)
  )

  return (
    <div className="rem-row">
      <span className="cod"><b>{ciclo.registro.cod_empr}</b><CopyButton valor={ciclo.registro.cod_empr} /></span>
      <span className="nome" onClick={() => onAbrirAuditoria(ciclo)} title="Ver histórico de alterações">
        {ciclo.registro.nome}
      </span>
      <span><DataSiteCell ciclo={ciclo} role={role} salvarCampo={salvarCampo} onReload={onReload} onErro={onErro} /></span>
      <span>
        <CellEdit valor={ciclo.data_envio} exibicao={fmtDataISO(ciclo.data_envio)} tipo="date"
                  podeEditar={escreveConc} onSalvar={(v) => salvarCampo('data_envio', v)} />
      </span>
      <span className="num">
        <CellEdit valor={ciclo.valor_enviado} exibicao={fmtMoney(ciclo.valor_enviado)} tipo="number"
                  podeEditar={escreveConc} onSalvar={(v) => salvarCampo('valor_enviado', v)} />
        <DivergenciaIcone ativo={ciclo.divergencia?.valor}
                          titulo="Valor enviado ≠ soma dos produtos preenchidos" />
      </span>
      <span className="num">
        <CellEdit valor={ciclo.qtd_contratos} exibicao={ciclo.qtd_contratos} tipo="number"
                  podeEditar={escreveConc}
                  onSalvar={(v) => salvarCampo('qtd_contratos', v == null ? null : Number(v))} />
        <DivergenciaIcone ativo={ciclo.divergencia?.qtd}
                          titulo="Qtd de contratos ≠ soma das qtds dos produtos" />
      </span>
      <span><em className={`tag st-${ciclo.status}`}>{STATUS_LABEL[ciclo.status] || ciclo.status}</em></span>
      {prodCell(produtos.credito, 'credito_valor', 'credito_qtd')}
      {prodCell(produtos.beneficio, 'beneficio_valor', 'beneficio_qtd')}
      {prodCell(produtos.compras, 'compras_valor', 'compras_qtd')}
      <span><BanksoftCell ciclo={ciclo} podeEditar={role === 'admin'} salvarCampo={salvarCampo} /></span>
      <span><CellCheck valor={ciclo.validado} podeEditar={escreveConc}
                       onSalvar={(v) => salvarCampo('validado', v)} /></span>
      <span className="obs">
        <CellEdit valor={ciclo.observacao} exibicao={ciclo.observacao}
                  podeEditar={escreveConc} onSalvar={(v) => salvarCampo('observacao', v)}
                  placeholder="" />
      </span>
    </div>
  )
}

// ── Modal de auditoria ────────────────────────────────────────────────────────
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
export default function RemessasView() {
  const user = useUser()
  const role = user?.role
  const [competencia, setCompetencia] = useState(null)   // null = corrente (server decide)
  const [competencias, setCompetencias] = useState([])
  const [ciclos, setCiclos] = useState(null)
  const [busca, setBusca] = useState('')
  const [erro, setErro] = useState(null)
  const [auditoriaDe, setAuditoriaDe] = useState(null)
  const [mostrarAdmin, setMostrarAdmin] = useState(false)

  const carregar = useCallback(async (comp) => {
    setErro(null)
    try {
      const [cs, comps] = await Promise.all([fetchCiclos(comp), fetchCompetencias()])
      setCiclos(cs)
      setCompetencias(comps)
      if (!comp && cs.length) setCompetencia(cs[0].competencia)
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

  const abrirNova = async () => {
    const comp = prompt('Abrir competência (MM/YYYY):')
    if (!comp) return
    try {
      await abrirCompetencia(comp.trim())
      trocarCompetencia(comp.trim())
    } catch (e) { mostrarErro(e.message) }
  }

  const mostrarErro = (msg) => {
    setErro(msg)
    setTimeout(() => setErro(null), 6000)
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

  return (
    <div className="remessas">
      <div className="controls">
        <select className="filtro" value={compAtual}
                onChange={(e) => trocarCompetencia(e.target.value)} aria-label="Competência">
          {!competencias.some((c) => c.competencia === compAtual) && compAtual &&
            <option value={compAtual}>{compAtual}</option>}
          {competencias.map((c) => (
            <option key={c.competencia} value={c.competencia}>
              {c.competencia} · {c.enviados}/{c.total - c.automaticos} enviados
            </option>
          ))}
        </select>
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
        {role === 'admin' && (
          <>
            <button className="acao" onClick={abrirNova}>Abrir competência</button>
            <button className="acao" onClick={() => setMostrarAdmin(!mostrarAdmin)}>
              {mostrarAdmin ? 'Fechar cadastro' : 'Cadastro'}
            </button>
          </>
        )}
      </div>

      {erro && <div className="estado erro rem-erro">{erro}</div>}
      {mostrarAdmin && role === 'admin' && <AdminPanel onMudou={() => carregar(compAtual)} />}

      {!ciclos && !erro && <div className="estado">Carregando remessas...</div>}
      {ciclos && filtrados.length === 0 && <div className="vazio">Nenhum convênio nesta competência.</div>}
      {ciclos && filtrados.length > 0 && (
        <div className="rem-wrap">
          <div className={`rem-grid ${oper ? 'oper' : ''}`}>
            {oper ? (
              <div className="rem-head oper">
                <span>Cod</span><span>Convênio</span><span>Data site</span><span>Corte banksoft</span>
              </div>
            ) : (
              <div className="rem-head">
                <span>Cod</span><span>Convênio</span><span>Data site</span><span>Data envio</span>
                <span>Valor enviado</span><span>Qtd</span><span>Status</span>
                <span>Crédito R$</span><span>Qtd</span><span>Benefício R$</span><span>Qtd</span>
                <span>Compras R$</span><span>Qtd</span><span>Corte banksoft</span>
                <span>Val.</span><span>Observação</span>
              </div>
            )}
            {filtrados.map((c) => (
              <CicloRow key={c.id} ciclo={c} role={role} onPatch={onPatch}
                        onAbrirAuditoria={setAuditoriaDe} onErro={mostrarErro}
                        onReload={() => carregar(compAtual)} />
            ))}
          </div>
        </div>
      )}

      {auditoriaDe && <AuditoriaModal ciclo={auditoriaDe} onFechar={() => setAuditoriaDe(null)} />}
    </div>
  )
}
