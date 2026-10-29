import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { homeDoPerfil, useAuth } from '../auth.jsx'
import { Campo, Erro } from '../ui.jsx'

const DEMO = [['Admin', 'admin@barberiq.com', 'admin123'], ['Barbeiro', 'carlos@barberiq.com', 'barbeiro123'],
  ['Cliente', 'maria@email.com', 'cliente123']]

export default function Login() {
  const { usuario, entrar } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (usuario) return <Navigate to={homeDoPerfil(usuario.tipo)} replace />

  const enviar = async (e) => {
    e.preventDefault()
    setErro(''); setEnviando(true)
    try { nav(homeDoPerfil((await entrar(email, senha)).tipo), { replace: true }) }
    catch (err) { setErro(err.message) }
    finally { setEnviando(false) }
  }

  return (
    <div className="auth">
      <form className="card caixa" onSubmit={enviar}>
        <div className="marca">BarberIQ</div>
        <p className="sub">Agendamento inteligente para barbearias</p>
        <Erro msg={erro} />
        <Campo rotulo="E-mail"><input type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} /></Campo>
        <Campo rotulo="Senha"><input type="password" required value={senha} onChange={(e) => setSenha(e.target.value)} /></Campo>
        <button className="btn-primario" style={{ width: '100%' }} disabled={enviando}>{enviando ? 'Entrando…' : 'Entrar'}</button>
        <p className="sub" style={{ marginTop: 14 }}>Novo por aqui? <Link to="/registro">Criar conta de cliente</Link></p>
        <div className="demo">Contas de demonstração (dados do seed):<br />
          {DEMO.map(([n, e, s]) => <button type="button" key={n} onClick={() => { setEmail(e); setSenha(s) }}>{n}</button>)}
        </div>
      </form>
    </div>
  )
}
