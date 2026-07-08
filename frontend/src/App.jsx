import { useEffect, useMemo, useState } from 'react'
import { usePolling, statusCorte, fmtAtualizado, aplicarAgrupamento, fetchHistorico, cortesPorDia, fetchMetricas } from './lib.js'
import { Login, UserChip, UserContext, useSession } from './auth.jsx'
import RemessasView from './remessas/RemessasView.jsx'

const SEMANA = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb']

const REFRESH_MS = 60000

function Relogio() {
  const [agora, setAgora] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setAgora(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return <span className="relogio">{agora.toLocaleTimeString('pt-BR')}</span>
}

function Controls({ busca, setBusca, proc, setProc, processadoras, total, exibidos }) {
  return (
    <div className="controls">
      <input
        className="busca"
        type="search"
        placeholder="Buscar convênio..."
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        aria-label="Buscar convênio"
      />
      <select className="filtro" value={proc} onChange={(e) => setProc(e.target.value)} aria-label="Filtrar por processadora">
        <option value="">Todas as processadoras</option>
        {processadoras.map((p) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>
      <span className="contador">{exibidos} de {total} convênios</span>
    </div>
  )
}

function BoardRow({ r, onAbrir }) {
  const st = statusCorte(r.data_corte)
  return (
    <div className={`board-row ${st.cls} clicavel`} onClick={() => onAbrir(r)} title="Ver histórico de datas">
      <span className="conv">
        <b className="nome">{r.convenio_nome || r.convenio_key}</b>
        {r.folha && <em className="folha">{r.folha}</em>}
        {r.origem === 'api_estimativa' && <em className="tag estimativa">estimativa</em>}
        {r.confianca === 'instavel' && (
          <em className="tag instavel" title="Data de corte mudou várias vezes recentemente">instável</em>
        )}
      </span>
      <span className="proc">{r.processadora}</span>
      <span className="comp">{r.competencia || '—'}</span>
      <span className="corte">
        <b>{r.data_corte || '—'}</b>
        {st.label && <em className={`tag ${st.cls}`}>{st.label}</em>}
      </span>
      <span className="upd">{fmtAtualizado(r.coletado_em)}</span>
    </div>
  )
}

function Board({ linhas, onAbrir }) {
  if (!linhas.length) return <div className="vazio">Nenhum convênio encontrado.</div>
  return (
    <div className="board">
      <div className="board-head">
        <span>Convênio</span>
        <span>Processadora</span>
        <span>Competência</span>
        <span>Data de corte</span>
        <span>Atualizado</span>
      </div>
      {linhas.map((r, i) => (
        <BoardRow key={`${r.convenio_key || ''}-${r.folha || ''}-${i}`} r={r} onAbrir={onAbrir} />
      ))}
    </div>
  )
}


function HistoricoModal({ convenio, onFechar }) {
  const [eventos, setEventos] = useState(null)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    let vivo = true
    fetchHistorico(convenio.convenio_key)
      .then((evs) => { if (vivo) setEventos(evs) })
      .catch((e) => { if (vivo) setErro(e.message || 'falha') })
    return () => { vivo = false }
  }, [convenio.convenio_key])

  return (
    <div className="modal-overlay" onClick={onFechar}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <b>Histórico de datas — {convenio.convenio_nome || convenio.convenio_key}</b>
          <button className="fechar" onClick={onFechar} aria-label="Fechar">×</button>
        </header>
        {erro && <div className="estado erro">Falha ao carregar histórico ({erro}).</div>}
        {!eventos && !erro && <div className="estado">Carregando histórico...</div>}
        {eventos && eventos.length === 0 && <div className="vazio">Sem mudanças registradas para este convênio.</div>}
        {eventos && eventos.length > 0 && (
          <ul className="timeline">
            {eventos.map((e, i) => (
              <li key={i} className="tl-item">
                <span className="tl-data">{fmtAtualizado(e.detectado_em)}</span>
                <span className="tl-mud">
                  {e.tipo === 'data_corte_alterada'
                    ? <>{e.data_corte_anterior || '—'} → <b>{e.data_corte_nova || '—'}</b></>
                    : <>primeiro registro: <b>{e.data_corte_nova || '—'}</b></>}
                  {e.folha && <em className="folha"> · {e.folha}</em>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function Calendario({ dados }) {
  const [ref, setRef] = useState(() => {
    const d = new Date()
    return { ano: d.getFullYear(), mes: d.getMonth() }
  })
  const porDia = useMemo(() => cortesPorDia(dados, ref.ano, ref.mes), [dados, ref])

  const primeiroDiaSemana = new Date(ref.ano, ref.mes, 1).getDay()
  const diasNoMes = new Date(ref.ano, ref.mes + 1, 0).getDate()
  const hoje = new Date()
  const ehMesAtual = hoje.getFullYear() === ref.ano && hoje.getMonth() === ref.mes
  const rotuloMes = new Date(ref.ano, ref.mes, 1).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })

  const mudarMes = (delta) => setRef((r) => {
    const d = new Date(r.ano, r.mes + delta, 1)
    return { ano: d.getFullYear(), mes: d.getMonth() }
  })

  const celulas = []
  for (let i = 0; i < primeiroDiaSemana; i++) celulas.push(null)
  for (let dia = 1; dia <= diasNoMes; dia++) celulas.push(dia)

  return (
    <div className="calendario">
      <div className="cal-nav">
        <button onClick={() => mudarMes(-1)} aria-label="Mês anterior">‹</button>
        <b className="cal-mes">{rotuloMes}</b>
        <button onClick={() => mudarMes(1)} aria-label="Próximo mês">›</button>
      </div>
      <div className="cal-grade">
        {SEMANA.map((s) => <div key={s} className="cal-dow">{s}</div>)}
        {celulas.map((dia, i) => {
          if (dia === null) return <div key={`b${i}`} className="cal-cel vazia" />
          const cortes = porDia.get(dia) || []
          const ehHoje = ehMesAtual && hoje.getDate() === dia
          return (
            <div key={dia} className={`cal-cel ${cortes.length ? 'tem-corte' : ''} ${ehHoje ? 'hoje' : ''}`}>
              <span className="cal-dia">{dia}</span>
              {cortes.length > 0 && (
                <div className="cal-cortes">
                  <b className="cal-count">{cortes.length}</b>
                  <ul>
                    {cortes.slice(0, 4).map((c, j) => {
                      const nome = c.convenio_nome || c.convenio_key
                      const rotulo = c.competencia ? `${nome} · ${c.competencia}` : nome
                      const dica = nome + (c.folha ? ` · ${c.folha}` : '') + (c.competencia ? ` · comp ${c.competencia}` : '')
                      return <li key={j} title={dica}>{rotulo}</li>
                    })}
                    {cortes.length > 4 && <li className="mais">+{cortes.length - 4}</li>}
                  </ul>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}


const TEND = { melhorando: '▲', piorando: '▼', estavel: '', sem_dados: '' }
const fmtPct = (t) => (t == null ? '—' : `${Math.round(t * 100)}%`)
const classeTaxa = (t) => (t == null ? 'neutra' : t >= 0.9 ? 'alta' : t >= 0.7 ? 'media' : 'baixa')

function Metricas() {
  const [data, setData] = useState(null)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    let vivo = true
    fetchMetricas()
      .then((d) => { if (vivo) setData(d) })
      .catch((e) => { if (vivo) setErro(e.message || 'falha') })
    return () => { vivo = false }
  }, [])

  if (erro) return <div className="estado erro">Falha ao carregar métricas ({erro}).</div>
  if (!data) return <div className="estado">Carregando métricas...</div>

  return (
    <div className="metricas">
      <section className="met-bloco">
        <h3>Taxa de sucesso por processadora</h3>
        <div className="met-grid">
          {data.processadoras.map((p) => (
            <div key={p.processadora} className="met-card">
              <div className="met-head">
                <b>{p.processadora}</b>
                <span className={`met-tend ${p.tendencia}`}>{TEND[p.tendencia]}</span>
              </div>
              <div className="met-bar">
                <span className={classeTaxa(p.taxa_atual)} style={{ width: `${(p.taxa_atual || 0) * 100}%` }} />
              </div>
              <div className="met-num">
                <b>{fmtPct(p.taxa_atual)}</b> agora · {fmtPct(p.taxa_media)} média ({p.execucoes}x)
              </div>
            </div>
          ))}
        </div>
      </section>
      <section className="met-bloco">
        <h3>Convênios com falhas (últimos 30 dias)</h3>
        {data.convenios_com_falha.length === 0 ? (
          <div className="vazio">Nenhuma falha registrada. 🎉</div>
        ) : (
          <ul className="met-falhas">
            {data.convenios_com_falha.map((c) => (
              <li key={`${c.processadora}-${c.convenio_key}`}>
                <b>{c.convenio_key}</b>
                <span className="met-meta">{c.processadora} · {c.categoria || '—'}{c.subtipo ? ` · ${c.subtipo}` : ''}</span>
                <span className="met-falha-count">{c.falhas}×</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}


// Ordem fixa das abas; visibilidade por papel (Operações só vê Remessas;
// Conciliação não vê Métricas; sem login = vistas do monitor).
const VISTAS_LABEL = { board: 'Board', remessas: 'Remessas', calendario: 'Calendário', metricas: 'Métricas' }
const VISTAS_POR_PAPEL = {
  admin: ['board', 'remessas', 'calendario', 'metricas'],
  conciliacao: ['board', 'remessas', 'calendario', 'metricas'],  // paridade com admin (exceto banksoft)
  operacoes: ['remessas'],
}

function Painel({ user, remessasEnabled, onLogout }) {
  const vistas = useMemo(() => {
    if (!remessasEnabled || !user) return ['board', 'calendario', 'metricas']
    return VISTAS_POR_PAPEL[user.role] || ['board']
  }, [user, remessasEnabled])
  const usaMonitor = vistas.includes('board') || vistas.includes('calendario')
  const { dados, erro, loading, updatedAt } = usePolling(REFRESH_MS, usaMonitor)
  const [busca, setBusca] = useState('')
  const [proc, setProc] = useState('')
  const [selecionado, setSelecionado] = useState(null)
  const [vista, setVista] = useState(vistas[0])

  // Consolida SOMENTE Teresina numa linha; os demais ficam folha a folha.
  const base = useMemo(() => aplicarAgrupamento(dados), [dados])

  // Ordena por convênio e, dentro do convênio, por folha.
  const ordenados = useMemo(
    () => [...base].sort((a, b) => {
      const n = (a.convenio_nome || '').localeCompare(b.convenio_nome || '', 'pt')
      return n !== 0 ? n : (a.folha || '').localeCompare(b.folha || '', 'pt')
    }),
    [base],
  )

  const processadoras = useMemo(
    () => [...new Set(ordenados.map((d) => d.processadora).filter(Boolean))].sort(),
    [ordenados],
  )

  const linhas = useMemo(() => {
    const b = busca.trim().toLowerCase()
    return ordenados.filter((d) => {
      const txt = `${d.convenio_nome || d.convenio_key || ''} ${d.folha || ''}`.toLowerCase()
      const okBusca = !b || txt.includes(b)
      const okProc = !proc || d.processadora === proc
      return okBusca && okProc
    })
  }, [ordenados, busca, proc])

  // Calendário usa os dados SEM agrupamento (cada folha/órgão no seu dia), com o mesmo filtro.
  const dadosCalendario = useMemo(() => {
    const b = busca.trim().toLowerCase()
    return dados.filter((d) => {
      const txt = `${d.convenio_nome || d.convenio_key || ''} ${d.folha || ''}`.toLowerCase()
      return (!b || txt.includes(b)) && (!proc || d.processadora === proc)
    })
  }, [dados, busca, proc])

  return (
    <div className="app">
      <header className="topo">
        <div className="titulo">
          <span className="ponto" />
          <span className="marca">PixCard ·</span> Datas de Corte
        </div>
        <div className="meta">
          <Relogio />
          {usaMonitor && (
            <>
              <span className="sep">·</span>
              <span>atualizado {updatedAt ? updatedAt.toLocaleTimeString('pt-BR') : '—'}</span>
            </>
          )}
          <UserChip user={user} onLogout={onLogout} />
        </div>
      </header>

      {vista !== 'remessas' && (
        <Controls
          busca={busca}
          setBusca={setBusca}
          proc={proc}
          setProc={setProc}
          processadoras={processadoras}
          total={ordenados.length}
          exibidos={linhas.length}
        />
      )}

      {vistas.length > 1 && (
        <div className="vista-toggle">
          {vistas.map((v) => (
            <button key={v} className={vista === v ? 'ativo' : ''} onClick={() => setVista(v)}>
              {VISTAS_LABEL[v]}
            </button>
          ))}
        </div>
      )}

      {loading && vista !== 'metricas' && vista !== 'remessas' && <div className="estado">Carregando dados...</div>}
      {erro && !loading && vista !== 'metricas' && vista !== 'remessas' && (
        <div className="estado erro">Falha ao carregar ({erro}). Nova tentativa automática em instantes...</div>
      )}
      {!loading && !erro && vista === 'board' && <Board linhas={linhas} onAbrir={setSelecionado} />}
      {!loading && !erro && vista === 'calendario' && <Calendario dados={dadosCalendario} />}
      {vista === 'metricas' && <Metricas />}
      {vista === 'remessas' && <RemessasView />}

      {selecionado && <HistoricoModal convenio={selecionado} onFechar={() => setSelecionado(null)} />}

      <footer className="rodape">
        Atualização automática a cada {REFRESH_MS / 1000}s · Monitor de Datas de Corte
      </footer>
    </div>
  )
}


export default function App() {
  const sessao = useSession()
  if (sessao.carregando) {
    return <div className="app"><div className="estado">Carregando...</div></div>
  }
  if (sessao.precisaLogin) {
    return <Login onOk={sessao.recarregar} />
  }
  return (
    <UserContext.Provider value={sessao.user}>
      <Painel user={sessao.user} remessasEnabled={sessao.remessasEnabled} onLogout={sessao.sair} />
    </UserContext.Provider>
  )
}
