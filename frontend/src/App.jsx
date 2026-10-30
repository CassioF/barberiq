import { Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom'
import { homeDoPerfil, useAuth } from './auth.jsx'
import { Carregando } from './ui.jsx'
import Login from './pages/Login.jsx'
import Registro from './pages/Registro.jsx'
import Agendar from './pages/cliente/Agendar.jsx'
import MeusAgendamentos from './pages/cliente/MeusAgendamentos.jsx'
import AgendaBarbeiro from './pages/barbeiro/AgendaBarbeiro.jsx'
import MinhaDisponibilidade from './pages/barbeiro/MinhaDisponibilidade.jsx'
import Dashboard from './pages/admin/Dashboard.jsx'
import AgendaAdmin from './pages/admin/AgendaAdmin.jsx'
import Usuarios from './pages/admin/Usuarios.jsx'
import Servicos from './pages/admin/Servicos.jsx'
import IA from './pages/admin/IA.jsx'
import ChatWidget from './ChatWidget.jsx'

const MENUS = {
  cliente: [['/agendar', 'Agendar'], ['/meus-agendamentos', 'Meus agendamentos']],
  barbeiro: [['/barbeiro', 'Minha agenda'], ['/barbeiro/disponibilidade', 'Meus horários']],
  admin: [
    ['/admin', 'Painel'], ['/admin/agenda', 'Agendamentos'], ['/admin/clientes', 'Clientes'],
    ['/admin/barbeiros', 'Barbeiros'], ['/admin/servicos', 'Serviços'], ['/admin/ia', 'IA & Notificações'],
  ],
}

function Layout() {
  const { usuario, sair } = useAuth()
  return (
    <div className="app">
      <nav className="menu" aria-label="Menu principal">
        <div className="marca">BarberIQ<small>AI Barbershop</small></div>
        {MENUS[usuario.tipo].map(([to, nome]) => (
          <NavLink key={to} to={to} end className={({ isActive }) => `item ${isActive ? 'ativo' : ''}`}>{nome}</NavLink>
        ))}
        <div className="rodape">
          <div className="nome"><b>{usuario.nome}</b><br /><small>{usuario.tipo}</small></div>
          <button className="btn-pequeno" onClick={sair}>Sair</button>
        </div>
      </nav>
      <main className="conteudo"><Outlet /></main>
      {usuario.tipo === 'cliente' && <ChatWidget />}
    </div>
  )
}

function Protegida({ tipos }) {
  const { usuario, carregando } = useAuth()
  if (carregando) return <Carregando />
  if (!usuario) return <Navigate to="/login" replace />
  if (!tipos.includes(usuario.tipo)) return <Navigate to={homeDoPerfil(usuario.tipo)} replace />
  return <Layout />
}

function Inicio() {
  const { usuario, carregando } = useAuth()
  if (carregando) return <Carregando />
  return <Navigate to={usuario ? homeDoPerfil(usuario.tipo) : '/login'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Inicio />} />
      <Route path="/login" element={<Login />} />
      <Route path="/registro" element={<Registro />} />

      <Route element={<Protegida tipos={['cliente']} />}>
        <Route path="/agendar" element={<Agendar />} />
        <Route path="/meus-agendamentos" element={<MeusAgendamentos />} />
      </Route>
      <Route element={<Protegida tipos={['barbeiro']} />}>
        <Route path="/barbeiro" element={<AgendaBarbeiro />} />
        <Route path="/barbeiro/disponibilidade" element={<MinhaDisponibilidade />} />
      </Route>
      <Route element={<Protegida tipos={['admin']} />}>
        <Route path="/admin" element={<Dashboard />} />
        <Route path="/admin/agenda" element={<AgendaAdmin />} />
        <Route path="/admin/clientes" element={<Usuarios tipo="clientes" rotulo="Cliente" />} />
        <Route path="/admin/barbeiros" element={<Usuarios tipo="barbeiros" rotulo="Barbeiro" />} />
        <Route path="/admin/servicos" element={<Servicos />} />
        <Route path="/admin/ia" element={<IA />} />
      </Route>
      <Route path="*" element={<Inicio />} />
    </Routes>
  )
}
