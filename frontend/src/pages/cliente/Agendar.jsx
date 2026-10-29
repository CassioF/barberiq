import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, dinheiro, hora, isoData, isoDataHora, paraData } from '../../api.js'
import { Erro, useToast } from '../../ui.jsx'

const SEM = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb']

export default function Agendar() {
  const nav = useNavigate()
  const avisar = useToast()
  const [servicos, setServicos] = useState([])
  const [barbeiros, setBarbeiros] = useState([])
  const [servico, setServico] = useState(null)
  const [barbeiro, setBarbeiro] = useState(null)
  const [dia, setDia] = useState(isoData(new Date()))
  const [horarios, setHorarios] = useState([])
  const [carregandoH, setCarregandoH] = useState(false)
  const [escolhido, setEscolhido] = useState(null)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    Promise.all([api.get('/servicos'), api.get('/barbeiros', { somente_ativos: true, limit: 100 })])
      .then(([s, b]) => { setServicos(s); setBarbeiros(b) })
      .catch((e) => setErro(e.message))
  }, [])

  const proximosDias = useMemo(() => Array.from({ length: 14 }, (_, i) => {
    const d = new Date(); d.setDate(d.getDate() + i); return d
  }), [])

  useEffect(() => {
    setEscolhido(null); setHorarios([])
    if (!servico || !barbeiro) return
    let ativo = true
    setCarregandoH(true)
    api.get('/agendamentos/horarios-livres', { barbeiro_id: barbeiro.id, servico_id: servico.id, data: dia })
      .then((r) => ativo && setHorarios(r.horarios))
      .catch((e) => ativo && setErro(e.message))
      .finally(() => ativo && setCarregandoH(false))
    return () => { ativo = false }
  }, [servico, barbeiro, dia])

  const confirmar = async () => {
    setErro(''); setEnviando(true)
    try {
      await api.post('/agendamentos', { barbeiro_id: barbeiro.id, servico_id: servico.id, data_hora: escolhido })
      avisar('Agendamento confirmado! Você receberá um lembrete.')
      nav('/meus-agendamentos')
    } catch (e) {
      setErro(e.message)
      // atualiza a grade: o horário pode ter sido ocupado por outra pessoa
      api.get('/agendamentos/horarios-livres', { barbeiro_id: barbeiro.id, servico_id: servico.id, data: dia })
        .then((r) => { setHorarios(r.horarios); setEscolhido(null) }).catch(() => {})
    } finally { setEnviando(false) }
  }

  return (
    <>
      <div className="topo-pagina"><div><h1>Agendar horário</h1><p>Escolha o serviço, o profissional e o melhor horário.</p></div></div>
      <Erro msg={erro} />

      <section className="passo card">
        <h3><i>1</i> Serviço</h3>
        <div className="opcoes">
          {servicos.map((s) => (
            <button key={s.id} className={`opcao ${servico?.id === s.id ? 'sel' : ''}`} onClick={() => setServico(s)}>
              <b>{s.nome}</b><small>{s.duracao_min} min · {dinheiro(s.preco)}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="passo card">
        <h3><i>2</i> Profissional</h3>
        <div className="opcoes">
          {barbeiros.map((b) => (
            <button key={b.id} className={`opcao ${barbeiro?.id === b.id ? 'sel' : ''}`} onClick={() => setBarbeiro(b)}>
              <b>{b.nome}</b><small>Barbeiro</small>
            </button>
          ))}
        </div>
      </section>

      <section className="passo card">
        <h3><i>3</i> Data e horário</h3>
        <div className="dias" role="group" aria-label="Escolha o dia">
          {proximosDias.map((d) => {
            const iso = isoData(d)
            return (
              <button key={iso} className={`dia ${dia === iso ? 'sel' : ''}`} onClick={() => setDia(iso)}>
                <small>{SEM[d.getDay()]}</small><b>{d.getDate()}</b>
              </button>
            )
          })}
        </div>
        <div className="espaco">
          {!servico || !barbeiro ? <p className="suave">Escolha o serviço e o profissional para ver os horários.</p>
            : carregandoH ? <p className="suave">Buscando horários…</p>
            : horarios.length === 0 ? <p className="suave">Sem horários livres neste dia. Tente outra data.</p>
            : <div className="horarios">
                {horarios.map((h) => (
                  <button key={h} className={`horario ${escolhido === h ? 'sel' : ''}`} onClick={() => setEscolhido(h)}>{hora(h)}</button>
                ))}
              </div>}
        </div>
      </section>

      {escolhido && (
        <div className="card">
          <h3>Resumo</h3>
          <p>{servico.nome} com <b>{barbeiro.nome}</b> em{' '}
            <b>{paraData(escolhido).toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' })}</b> às <b>{hora(escolhido)}</b> — {dinheiro(servico.preco)}</p>
          <button className="btn-primario" onClick={confirmar} disabled={enviando}>{enviando ? 'Confirmando…' : 'Confirmar agendamento'}</button>
        </div>
      )}
    </>
  )
}
