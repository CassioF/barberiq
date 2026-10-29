import { useCallback, useEffect, useState } from 'react'
import { api, dinheiro, hora, isoData } from '../../api.js'
import { Carregando, Erro, RiscoBadge, StatusBadge, Vazio } from '../../ui.jsx'
import AcoesAgendamento from '../AcoesAgendamento.jsx'

export default function AgendaBarbeiro() {
  const [dia, setDia] = useState(isoData(new Date()))
  const [ags, setAgs] = useState(null)
  const [erro, setErro] = useState('')

  const carregar = useCallback(() => {
    setAgs(null)
    api.get('/agendamentos', { data_de: dia, data_ate: dia, limit: 200 })
      .then((l) => setAgs(l.filter((a) => a.status !== 'cancelado')))
      .catch((e) => setErro(e.message))
  }, [dia])
  useEffect(() => { carregar() }, [carregar])

  const mover = (n) => { const d = new Date(dia + 'T12:00'); d.setDate(d.getDate() + n); setDia(isoData(d)) }
  const titulo = new Date(dia + 'T12:00').toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' })
  const altos = (ags || []).filter((a) => a.status === 'confirmado' && a.nivel_risco === 'alto').length
  const total = (ags || []).filter((a) => a.status !== 'faltou').reduce((s, a) => s + Number(a.servico.preco), 0)

  return (
    <>
      <div className="topo-pagina"><div><h1>Minha agenda</h1><p>{titulo}</p></div>
        <div className="linha">
          <button onClick={() => mover(-1)} aria-label="Dia anterior">←</button>
          <input type="date" value={dia} onChange={(e) => e.target.value && setDia(e.target.value)} style={{ width: 160 }} />
          <button onClick={() => mover(1)} aria-label="Próximo dia">→</button>
          <button onClick={() => setDia(isoData(new Date()))}>Hoje</button>
        </div>
      </div>
      <Erro msg={erro} />
      {ags && <p className="suave">{ags.length} atendimento(s) · previsão {dinheiro(total)}
        {altos > 0 && <> · <b style={{ color: 'var(--perigo)' }}>{altos} com alto risco de falta</b> (a IA sugere confirmar presença)</>}</p>}
      {!ags ? <Carregando /> : ags.length === 0 ? <Vazio>Nenhum atendimento neste dia.</Vazio> : (
        <div className="lista-ag">
          {ags.map((a) => (
            <div className="ag" key={a.id}>
              <div className="quando"><b>{hora(a.data_hora)}</b><small>{a.servico.duracao_min} min</small></div>
              <div className="info"><b>{a.cliente.nome}</b><small>{a.servico.nome} · {dinheiro(a.servico.preco)}{a.cliente.telefone && ` · ${a.cliente.telefone}`}</small></div>
              <div className="lado">
                {a.status === 'confirmado' && <RiscoBadge nivel={a.nivel_risco} risco={a.risco_noshow} />}
                <StatusBadge status={a.status} />
                <AcoesAgendamento ag={a} aoMudar={carregar} />
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
