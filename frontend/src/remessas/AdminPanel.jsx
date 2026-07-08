import { useCallback, useEffect, useState } from 'react'
import {
  criarRegistro, criarUsuario, fetchMonitorKeys, fetchRegistros, fetchUsuarios,
  patchRegistro, patchUsuario,
} from '../lib.js'
import { ROLE_LABEL, useUser } from '../auth.jsx'

const REGISTRO_VAZIO = {
  cod_empr: '', nome: '', link_portal: '', tipo_desconto: 'remessa',
  prod_credito: false, prod_beneficio: false, prod_compras: false, monitor_key: '',
}
const USUARIO_VAZIO = { username: '', display_name: '', password: '', role: 'conciliacao' }

export default function AdminPanel({ onMudou }) {
  const user = useUser()
  const ehAdmin = user?.role === 'admin'
  const [aba, setAba] = useState('registros')
  const [registros, setRegistros] = useState([])
  const [usuarios, setUsuarios] = useState([])
  const [monitorKeys, setMonitorKeys] = useState([])
  const [novoReg, setNovoReg] = useState(REGISTRO_VAZIO)
  const [novoUser, setNovoUser] = useState(USUARIO_VAZIO)
  const [erro, setErro] = useState(null)

  const carregar = useCallback(async () => {
    try {
      const [regs, users, keys] = await Promise.all(
        [fetchRegistros(), fetchUsuarios(), fetchMonitorKeys()])
      setRegistros(regs)
      setUsuarios(users)
      setMonitorKeys(keys)
    } catch (e) { setErro(e.message) }
  }, [])

  useEffect(() => { carregar() }, [carregar])

  const falha = (e) => { setErro(e.message); setTimeout(() => setErro(null), 6000) }

  const addRegistro = async (e) => {
    e.preventDefault()
    try {
      await criarRegistro({
        ...novoReg,
        cod_empr: Number(novoReg.cod_empr),
        link_portal: novoReg.link_portal || null,
        monitor_key: novoReg.monitor_key || null,
      })
      setNovoReg(REGISTRO_VAZIO)
      await carregar()
      onMudou?.()
    } catch (err) { falha(err) }
  }

  const toggleAtivoRegistro = async (r) => {
    try { await patchRegistro(r.id, { ativo: !r.ativo }); await carregar(); onMudou?.() }
    catch (err) { falha(err) }
  }

  const addUsuario = async (e) => {
    e.preventDefault()
    try {
      await criarUsuario(novoUser)
      setNovoUser(USUARIO_VAZIO)
      await carregar()
    } catch (err) { falha(err) }
  }

  const toggleAtivoUsuario = async (u) => {
    try { await patchUsuario(u.id, { ativo: !u.ativo }); await carregar() }
    catch (err) { falha(err) }
  }

  return (
    <div className="admin-panel">
      <div className="vista-toggle">
        <button className={aba === 'registros' ? 'ativo' : ''}
                onClick={() => setAba('registros')}>Convênios ({registros.length})</button>
        <button className={aba === 'usuarios' ? 'ativo' : ''}
                onClick={() => setAba('usuarios')}>Usuários ({usuarios.length})</button>
      </div>
      {erro && <div className="estado erro rem-erro">{erro}</div>}

      {aba === 'registros' && (
        <>
          <form className="admin-form" onSubmit={addRegistro}>
            <input className="busca" style={{ maxWidth: 90 }} type="number" placeholder="Cod"
                   value={novoReg.cod_empr} required
                   onChange={(e) => setNovoReg({ ...novoReg, cod_empr: e.target.value })} />
            <input className="busca" placeholder="Nome do convênio" value={novoReg.nome} required
                   onChange={(e) => setNovoReg({ ...novoReg, nome: e.target.value })} />
            <input className="busca" placeholder="Link do portal (opcional)" value={novoReg.link_portal}
                   onChange={(e) => setNovoReg({ ...novoReg, link_portal: e.target.value })} />
            <select className="filtro" value={novoReg.tipo_desconto}
                    onChange={(e) => setNovoReg({ ...novoReg, tipo_desconto: e.target.value })}>
              <option value="remessa">remessa</option>
              <option value="automatico">automático</option>
            </select>
            <select className="filtro" value={novoReg.monitor_key}
                    onChange={(e) => setNovoReg({ ...novoReg, monitor_key: e.target.value })}>
              <option value="">sem monitor (manual)</option>
              {monitorKeys.map((k) => (
                <option key={k.key} value={k.key}>{k.nome} ({k.processadora})</option>
              ))}
            </select>
            {['credito', 'beneficio', 'compras'].map((p) => (
              <label key={p} className="chk">
                <input type="checkbox" checked={novoReg[`prod_${p}`]}
                       onChange={(e) => setNovoReg({ ...novoReg, [`prod_${p}`]: e.target.checked })} />
                {p}
              </label>
            ))}
            <button className="acao" type="submit">Adicionar</button>
          </form>
          <div className="admin-lista">
            {registros.map((r) => (
              <div key={r.id} className={`admin-item ${r.ativo ? '' : 'inativo'}`}>
                <b>{r.cod_empr}</b>
                <span>{r.nome}</span>
                <em className="tag">{r.tipo_desconto}</em>
                {r.monitor_key
                  ? <em className="tag ok">monitor: {r.monitor_key}</em>
                  : <em className="tag estimativa">manual</em>}
                <span className="produtos">
                  {['credito', 'beneficio', 'compras'].filter((p) => r.produtos[p]).join(' · ') || '—'}
                </span>
                <button className="sair" onClick={() => toggleAtivoRegistro(r)}>
                  {r.ativo ? 'desativar' : 'reativar'}
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {aba === 'usuarios' && (
        <>
          <form className="admin-form" onSubmit={addUsuario}>
            <input className="busca" placeholder="usuário (login)" value={novoUser.username} required
                   onChange={(e) => setNovoUser({ ...novoUser, username: e.target.value })} />
            <input className="busca" placeholder="Nome de exibição" value={novoUser.display_name} required
                   onChange={(e) => setNovoUser({ ...novoUser, display_name: e.target.value })} />
            <input className="busca" type="password" placeholder="Senha (mín. 8)" value={novoUser.password}
                   required minLength={8}
                   onChange={(e) => setNovoUser({ ...novoUser, password: e.target.value })} />
            <select className="filtro" value={novoUser.role}
                    onChange={(e) => setNovoUser({ ...novoUser, role: e.target.value })}>
              <option value="conciliacao">Conciliação</option>
              <option value="operacoes">Operações</option>
              {ehAdmin && <option value="admin">Admin</option>}
            </select>
            <button className="acao" type="submit">Criar usuário</button>
          </form>
          <div className="admin-lista">
            {usuarios.map((u) => (
              <div key={u.id} className={`admin-item ${u.ativo ? '' : 'inativo'}`}>
                <b>{u.username}</b>
                <span>{u.display_name}</span>
                <em className={`tag role-${u.role}`}>{ROLE_LABEL[u.role] || u.role}</em>
                {(ehAdmin || u.role !== 'admin') && (
                  <button className="sair" onClick={() => toggleAtivoUsuario(u)}>
                    {u.ativo ? 'desativar' : 'reativar'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
