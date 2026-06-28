import { useEffect, useMemo, useState } from 'react'
import { usePolling, statusCorte, fmtAtualizado, aplicarAgrupamento } from './lib.js'

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

function BoardRow({ r }) {
  const st = statusCorte(r.data_corte)
  return (
    <div className={`board-row ${st.cls}`}>
      <span className="conv">
        <b className="nome">{r.convenio_nome || r.convenio_key}</b>
        {r.folha && <em className="folha">{r.folha}</em>}
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

function Board({ linhas }) {
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
        <BoardRow key={`${r.convenio_key || ''}-${r.folha || ''}-${i}`} r={r} />
      ))}
    </div>
  )
}

export default function App() {
  const { dados, erro, loading, updatedAt } = usePolling(REFRESH_MS)
  const [busca, setBusca] = useState('')
  const [proc, setProc] = useState('')

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
      {!loading && !erro && <Board linhas={linhas} />}

      <footer className="rodape">
        Atualização automática a cada {REFRESH_MS / 1000}s · Monitor de Datas de Corte
      </footer>
    </div>
  )
}
