import { useEffect, useMemo, useState } from 'react'
import { usePolling, statusCorte, fmtAtualizado, aplicarAgrupamento, fetchHistorico } from './lib.js'

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
      </span>
      <span className="proc">{r.processadora}</span>
      <span className="comp">{r.mes_atual || '—'}</span>
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

export default function App() {
  const { dados, erro, loading, updatedAt } = usePolling(REFRESH_MS)
  const [busca, setBusca] = useState('')
  const [proc, setProc] = useState('')
  const [selecionado, setSelecionado] = useState(null)

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

  return (
    <div className="app">
      <header className="topo">
        <div className="titulo">
          <span className="ponto" /> PAINEL DE DATAS DE CORTE
        </div>
        <div className="meta">
          <Relogio />
          <span className="sep">·</span>
          <span>atualizado {updatedAt ? updatedAt.toLocaleTimeString('pt-BR') : '—'}</span>
        </div>
      </header>

      <Controls
        busca={busca}
        setBusca={setBusca}
        proc={proc}
        setProc={setProc}
        processadoras={processadoras}
        total={ordenados.length}
        exibidos={linhas.length}
      />

      {loading && <div className="estado">Carregando dados...</div>}
      {erro && !loading && (
        <div className="estado erro">Falha ao carregar ({erro}). Nova tentativa automática em instantes...</div>
      )}
      {!loading && !erro && <Board linhas={linhas} onAbrir={setSelecionado} />}

      {selecionado && <HistoricoModal convenio={selecionado} onFechar={() => setSelecionado(null)} />}

      <footer className="rodape">
        Atualização automática a cada {REFRESH_MS / 1000}s · Monitor de Datas de Corte
      </footer>
    </div>
  )
}
