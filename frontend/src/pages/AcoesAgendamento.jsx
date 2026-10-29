import { api, isoDataHora } from '../api.js'
import { useToast } from '../ui.jsx'

// Botões de ação de um agendamento para barbeiro/admin: concluir, marcar falta, cancelar.
export default function AcoesAgendamento({ ag, aoMudar, compacto }) {
  const avisar = useToast()
  const passou = ag.data_hora <= isoDataHora(new Date())

  const mudar = async (status, msg) => {
    if (status === 'cancelado' && !confirm('Cancelar este agendamento?')) return
    try { await api.patch(`/agendamentos/${ag.id}/status`, { status }); avisar(msg); aoMudar() }
    catch (e) { avisar(e.message, 'erro') }
  }
  if (ag.status !== 'confirmado') return null
  return (
    <span className="linha" style={{ gap: 6 }}>
      {passou && <>
        <button className="btn-pequeno" onClick={() => mudar('concluido', 'Atendimento concluído.')}>{compacto ? '✓' : 'Concluir'}</button>
        <button className="btn-pequeno" onClick={() => mudar('faltou', 'Falta registrada.')}>{compacto ? 'Faltou' : 'Não compareceu'}</button>
      </>}
      <button className="btn-perigo btn-pequeno" onClick={() => mudar('cancelado', 'Agendamento cancelado.')}>Cancelar</button>
    </span>
  )
}
