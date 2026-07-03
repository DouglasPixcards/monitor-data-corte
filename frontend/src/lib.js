import { useCallback, useEffect, useRef, useState } from 'react'

// Helper compartilhado: fetch same-origin com JSON + erros legíveis. Mutações levam o
// header X-Requested-With (exigido pelo backend como defesa anti-CSRF).
export async function api(path, { method = 'GET', body } = {}) {
  const opts = { method, headers: { Accept: 'application/json' } }
  if (method !== 'GET') opts.headers['X-Requested-With'] = 'fetch'
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(path, opts)
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const j = await res.json()
      if (j.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
      if (j.campos_negados) detail += ` (campos: ${j.campos_negados.join(', ')})`
    } catch { /* corpo não-JSON — mantém o HTTP status */ }
    const err = new Error(detail)
    err.status = res.status
    throw err
  }
  return res.status === 204 ? null : res.json()
}

// Sessão (módulo de remessas)
export const fetchMe = () => api('/auth/me')
export const login = (username, password) => api('/auth/login', { method: 'POST', body: { username, password } })
export const logout = () => api('/auth/logout', { method: 'POST' })

// Busca os dados de corte atuais na API do Monitor (mesma origem quando servido em /painel).
export async function fetchCortes() {
  const res = await fetch('/cortes/atuais', { headers: { Accept: 'application/json' } })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// Linha do tempo de data_corte de um convênio (mudanças + primeiro registro).
export async function fetchHistorico(convenioKey) {
  const res = await fetch(`/convenios/${encodeURIComponent(convenioKey)}/historico`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// Métricas de coleta: taxa de sucesso por processadora + convênios com falhas.
export async function fetchMetricas() {
  const res = await fetch('/metricas', { headers: { Accept: 'application/json' } })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// "DD/MM/YYYY" -> Date (ou null se não for esse formato).
export function parseBR(s) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec((s || '').trim())
  return m ? new Date(+m[3], +m[2] - 1, +m[1]) : null
}

// Agrupa os cortes por DIA do mês para (ano, mes). `mes` é o índice 0–11 (Date.getMonth()).
// Linhas sem data precisa (MM/YYYY, vazio, etc.) ficam de fora do calendário.
export function cortesPorDia(dados, ano, mes) {
  const porDia = new Map()
  for (const d of dados) {
    const data = parseBR(d.data_corte)
    if (!data || data.getFullYear() !== ano || data.getMonth() !== mes) continue
    const dia = data.getDate()
    const arr = porDia.get(dia) || []
    arr.push(d)
    porDia.set(dia, arr)
  }
  return porDia
}

// Dias entre hoje e a data de corte (negativo = já passou).
export function diasAte(s) {
  const d = parseBR(s)
  if (!d) return null
  const hoje = new Date()
  hoje.setHours(0, 0, 0, 0)
  return Math.round((d - hoje) / 86400000)
}

// Classifica a proximidade do corte para destaque visual (estilo painel).
export function statusCorte(s) {
  const dias = diasAte(s)
  if (dias === null) return { cls: 'neutro', label: '' }
  if (dias < 0) return { cls: 'passou', label: 'encerrado' }
  if (dias === 0) return { cls: 'hoje', label: 'hoje' }
  if (dias <= 3) return { cls: 'breve', label: `em ${dias}d` }
  return { cls: 'ok', label: `em ${dias}d` }
}

export function fmtAtualizado(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('pt-BR', {
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return '—'
  }
}

// Convênios cujas folhas são consolidadas numa única linha no painel.
// Pedido específico: agrupar SOMENTE Teresina. Os demais mostram folha a folha.
export const CONVENIOS_AGRUPADOS = new Set(['teresina'])

// Consolida numa linha só os convênios de CONVENIOS_AGRUPADOS; o restante passa
// inalterado. Junta as datas distintas (Teresina tem todas iguais) e mantém a
// coleta mais recente; a "folha" passa a indicar a quantidade de órgãos.
export function aplicarAgrupamento(dados) {
  const grupos = new Map()
  const resto = []
  for (const d of dados) {
    if (CONVENIOS_AGRUPADOS.has(d.convenio_key)) {
      const arr = grupos.get(d.convenio_key) || []
      arr.push(d)
      grupos.set(d.convenio_key, arr)
    } else {
      resto.push(d)
    }
  }
  const agregados = [...grupos.values()].map((grupo) => {
    const datas = [...new Set(grupo.map((d) => d.data_corte).filter(Boolean))]
    const coletado = grupo.map((d) => d.coletado_em).filter(Boolean).sort().pop() || null
    const g0 = grupo[0]
    return {
      convenio_key: g0.convenio_key,
      convenio_nome: g0.convenio_nome,
      processadora: g0.processadora,
      mes_atual: g0.mes_atual,
      coletado_em: coletado,
      folha: `${grupo.length} órgãos`,
      data_corte: datas.join(' / ') || null,
    }
  })
  return [...resto, ...agregados]
}

// Hook: busca os dados a cada `intervaloMs` e expõe estado de carregamento/erro.
export function usePolling(intervaloMs = 60000) {
  const [dados, setDados] = useState([])
  const [erro, setErro] = useState(null)
  const [loading, setLoading] = useState(true)
  const [updatedAt, setUpdatedAt] = useState(null)
  const timer = useRef(null)

  const carregar = useCallback(async () => {
    try {
      const d = await fetchCortes()
      setDados(Array.isArray(d) ? d : [])
      setErro(null)
      setUpdatedAt(new Date())
    } catch (e) {
      setErro(e.message || 'falha')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    carregar()
    timer.current = setInterval(carregar, intervaloMs)
    return () => clearInterval(timer.current)
  }, [carregar, intervaloMs])

  return { dados, erro, loading, updatedAt, recarregar: carregar }
}
