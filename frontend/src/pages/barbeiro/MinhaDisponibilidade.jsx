import { useAuth } from '../../auth.jsx'
import DisponibilidadeEditor from './DisponibilidadeEditor.jsx'

export default function MinhaDisponibilidade() {
  const { usuario } = useAuth()
  return (
    <>
      <div className="topo-pagina"><div><h1>Meus horários de trabalho</h1>
        <p>Defina quando você atende. Os clientes só conseguem marcar dentro dessas janelas (use duas janelas para o intervalo de almoço).</p></div></div>
      <div className="card"><DisponibilidadeEditor barbeiroId={usuario.id} /></div>
    </>
  )
}
