import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth, homeDoPerfil } from '../auth.jsx'
import { Campo, Erro, useToast } from '../ui.jsx'

export default function Registro() {
  const nav = useNavigate()
  const { entrar } = useAuth()
  const avisar = useToast()
  const [f, setF] = useState({ nome: '', email: '', telefone: '', senha: '' })
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const enviar = async (e) => {
    e.preventDefault()
    setErro(''); setEnviando(true)
    try {
      await api.post('/auth/registrar', { ...f, telefone: f.telefone || null })
      const u = await entrar(f.email, f.senha)
      avisar('Conta criada! Bem-vindo(a).')
      nav(homeDoPerfil(u.tipo), { replace: true })
    } catch (err) { setErro(err.message) } finally { setEnviando(false) }
  }

  return (
    <div className="auth">
      <form className="card caixa" onSubmit={enviar}>
        <div className="marca">BarberIQ</div>
        <p className="sub">Crie sua conta de cliente</p>
        <Erro msg={erro} />
        <Campo rotulo="Nome completo"><input required minLength={2} value={f.nome} onChange={set('nome')} /></Campo>
        <Campo rotulo="E-mail"><input type="email" required value={f.email} onChange={set('email')} /></Campo>
        <Campo rotulo="Telefone / WhatsApp" dica="Usado para lembretes do seu horário"><input value={f.telefone} onChange={set('telefone')} placeholder="34999990000" /></Campo>
        <Campo rotulo="Senha (mín. 6 caracteres)"><input type="password" required minLength={6} value={f.senha} onChange={set('senha')} /></Campo>
        <button className="btn-primario" style={{ width: '100%' }} disabled={enviando}>{enviando ? 'Criando…' : 'Criar conta'}</button>
        <p className="sub" style={{ marginTop: 14 }}>Já tem conta? <Link to="/login">Entrar</Link></p>
      </form>
    </div>
  )
}
