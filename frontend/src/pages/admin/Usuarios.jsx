import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api.js'
import { Campo, Carregando, Erro, Modal, Vazio, useToast } from '../../ui.jsx'
import DisponibilidadeEditor from '../barbeiro/DisponibilidadeEditor.jsx'

const LIMITE = 20

// CRUD de clientes e de barbeiros (mesma tela, rota diferente).
export default function Usuarios({ tipo, rotulo }) {
  const avisar = useToast()
  const [busca, setBusca] = useState('')
  const [pagina, setPagina] = useState(0)
  const [res, setRes] = useState(null)
  const [erro, setErro] = useState('')
  const [form, setForm] = useState(null)     // null | {} (novo) | usuário (edição)
  const [horarios, setHorarios] = useState(null)

  useEffect(() => { setPagina(0); setBusca('') }, [tipo])

  const carregar = useCallback(() => {
    setErro('')
    api.list(`/${tipo}`, { busca, skip: pagina * LIMITE, limit: LIMITE }).then(setRes).catch((e) => setErro(e.message))
  }, [tipo, busca, pagina])
  useEffect(() => { const t = setTimeout(carregar, 250); return () => clearTimeout(t) }, [carregar])

  const excluir = async (u) => {
    if (!confirm(`Excluir ${u.nome}?`)) return
    try { await api.del(`/${tipo}/${u.id}`); avisar(`${rotulo} excluído.`); carregar() }
    catch (e) { avisar(e.message, 'erro') }
  }
  const alternar = async (u) => {
    try { await api.put(`/${tipo}/${u.id}`, { ativo: !u.ativo }); carregar() } catch (e) { avisar(e.message, 'erro') }
  }
  const totalPaginas = res ? Math.max(1, Math.ceil(res.total / LIMITE)) : 1

  return (
    <>
      <div className="topo-pagina"><div><h1>{rotulo}s</h1><p>Cadastro, edição e controle de acesso.</p></div>
        <button className="btn-primario" onClick={() => setForm({})}>+ Novo {rotulo.toLowerCase()}</button></div>
      <div className="filtros"><Campo rotulo="Buscar por nome ou e-mail">
        <input value={busca} onChange={(e) => { setBusca(e.target.value); setPagina(0) }} placeholder="Digite para filtrar…" /></Campo></div>
      <Erro msg={erro} />
      {!res ? <Carregando /> : res.data.length === 0 ? <Vazio>Nenhum registro encontrado.</Vazio> : (
        <>
          <div className="tabela-wrap"><table>
            <thead><tr><th>Nome</th><th>E-mail</th><th>Telefone</th><th>Situação</th><th /></tr></thead>
            <tbody>{res.data.map((u) => (
              <tr key={u.id}>
                <td><b>{u.nome}</b></td><td>{u.email}</td><td>{u.telefone || '—'}</td>
                <td><span className={`badge ${u.ativo ? 'st-confirmado' : 'st-cancelado'}`}>{u.ativo ? 'Ativo' : 'Inativo'}</span></td>
                <td className="acoes">
                  {tipo === 'barbeiros' && <button className="btn-pequeno" onClick={() => setHorarios(u)}>Horários</button>}
                  <button className="btn-pequeno" onClick={() => setForm(u)}>Editar</button>
                  <button className="btn-pequeno" onClick={() => alternar(u)}>{u.ativo ? 'Desativar' : 'Ativar'}</button>
                  <button className="btn-perigo btn-pequeno" onClick={() => excluir(u)}>Excluir</button>
                </td>
              </tr>))}</tbody>
          </table></div>
          <div className="linha espaco" style={{ justifyContent: 'space-between' }}>
            <small>{res.total} registro(s)</small>
            <div className="linha">
              <button disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>←</button>
              <small>página {pagina + 1} de {totalPaginas}</small>
              <button disabled={pagina + 1 >= totalPaginas} onClick={() => setPagina(pagina + 1)}>→</button>
            </div>
          </div>
        </>
      )}
      {form && <FormUsuario tipo={tipo} rotulo={rotulo} inicial={form} onClose={() => setForm(null)} onSalvo={() => { setForm(null); carregar() }} />}
      {horarios && <Modal largo titulo={`Horários de ${horarios.nome}`} onClose={() => setHorarios(null)}><DisponibilidadeEditor barbeiroId={horarios.id} /></Modal>}
    </>
  )
}

function FormUsuario({ tipo, rotulo, inicial, onClose, onSalvo }) {
  const avisar = useToast()
  const edicao = !!inicial.id
  const [f, setF] = useState({ nome: inicial.nome || '', email: inicial.email || '', telefone: inicial.telefone || '', senha: '' })
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const enviar = async (e) => {
    e.preventDefault()
    setErro(''); setEnviando(true)
    const corpo = { nome: f.nome, email: f.email, telefone: f.telefone || null }
    if (f.senha) corpo.senha = f.senha
    try {
      if (edicao) await api.put(`/${tipo}/${inicial.id}`, corpo); else await api.post(`/${tipo}`, corpo)
      avisar(`${rotulo} salvo.`); onSalvo()
    } catch (err) { setErro(err.message) } finally { setEnviando(false) }
  }

  return (
    <Modal titulo={edicao ? `Editar ${rotulo.toLowerCase()}` : `Novo ${rotulo.toLowerCase()}`} onClose={onClose}>
      <form onSubmit={enviar}>
        <Erro msg={erro} />
        <Campo rotulo="Nome"><input required minLength={2} value={f.nome} onChange={set('nome')} autoFocus /></Campo>
        <Campo rotulo="E-mail"><input type="email" required value={f.email} onChange={set('email')} /></Campo>
        <Campo rotulo="Telefone"><input value={f.telefone} onChange={set('telefone')} /></Campo>
        <Campo rotulo={edicao ? 'Nova senha (deixe em branco para manter)' : 'Senha (mín. 6 caracteres)'}>
          <input type="password" minLength={6} required={!edicao} value={f.senha} onChange={set('senha')} /></Campo>
        <div className="rodape-modal"><button type="button" onClick={onClose}>Cancelar</button>
          <button className="btn-primario" disabled={enviando}>{enviando ? 'Salvando…' : 'Salvar'}</button></div>
      </form>
    </Modal>
  )
}
