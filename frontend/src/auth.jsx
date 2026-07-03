import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { fetchMe, login as apiLogin, logout as apiLogout } from './lib.js'

export const UserContext = createContext(null)
export const useUser = () => useContext(UserContext)

export const ROLE_LABEL = { admin: 'Admin', operacoes: 'Operações', conciliacao: 'Conciliação' }

// Sessão do painel: /auth/me no boot.
// - módulo desabilitado → { user:null, remessasEnabled:false } (painel aberto, modo monitor)
// - 401 → precisaLogin (renderiza <Login/>)
export function useSession() {
  const [estado, setEstado] = useState({ carregando: true })

  const carregar = useCallback(async () => {
    try {
      const me = await fetchMe()
      setEstado({ carregando: false, user: me.user, remessasEnabled: me.remessas_enabled })
    } catch (e) {
      if (e.status === 401) setEstado({ carregando: false, precisaLogin: true })
      else setEstado({ carregando: false, user: null, remessasEnabled: false, erro: e.message })
    }
  }, [])

  useEffect(() => { carregar() }, [carregar])

  const sair = useCallback(async () => {
    try { await apiLogout() } catch { /* cookie some de qualquer jeito */ }
    carregar()
  }, [carregar])

  return { ...estado, recarregar: carregar, sair }
}

export function Login({ onOk }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [erro, setErro] = useState(null)
  const [enviando, setEnviando] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      await apiLogin(username, password)
      onOk()
    } catch (err) {
      setErro(err.status === 401 ? 'Usuário ou senha inválidos.' : err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="titulo"><span className="ponto" /> MONITOR DE CORTES</div>
        <p className="login-sub">Entre com sua conta para acessar o painel.</p>
        <input
          className="busca" type="text" placeholder="Usuário" autoComplete="username"
          value={username} onChange={(e) => setUsername(e.target.value)} autoFocus
        />
        <input
          className="busca" type="password" placeholder="Senha" autoComplete="current-password"
          value={password} onChange={(e) => setPassword(e.target.value)}
        />
        {erro && <div className="login-erro">{erro}</div>}
        <button className="login-btn" type="submit" disabled={enviando || !username || !password}>
          {enviando ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}

export function UserChip({ user, onLogout }) {
  if (!user) return null
  return (
    <span className="user-chip">
      <b>{user.display_name}</b>
      <em className={`tag role-${user.role}`}>{ROLE_LABEL[user.role] || user.role}</em>
      <button className="sair" onClick={onLogout} title="Sair">sair</button>
    </span>
  )
}
