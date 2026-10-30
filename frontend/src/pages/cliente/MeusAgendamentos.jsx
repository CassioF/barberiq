import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, dinheiro, diaMes, diaSem, hora, isoDataHora } from '../../api.js'
import { Carregando, Erro, StatusBadge, Vazio, useToast } from '../../ui.jsx'

export default function MeusAgendamentos() {
  const avisar = useToast()
  const [ags, setAgs] = useState(null)
  const [erro, setErro] = useState('')

  const carregar = useCallback(() =>
    api.get('/agendamentos', { limit: 200 }).then(setAgs).catch((e) => setErro(e.message)), [])
  useEffect(() => { carregar() }, [carregar])
  // o assistente de chat avisa quando agenda ou cancela algo
  useEffect(() => {
    window.addEventListener('barberiq:agendamentos', carregar)
    return () => window.removeEventListener('barberiq:agendamentos', carregar)
  }, [carregar])

  const cancelar = async (a) => {
    if (!confirm(`Cancelar ${a.servico.nome} em ${diaMes(a.data_hora)} às ${hora(a.data_hora)}?`)) return
    try { await api.patch(`/agendamentos/${a.id}/cancelar`); avisar('Agendamento cancelado.'); carregar() }
    catch (e) { avisar(e.message, 'erro') }
  }

  if (!ags) return <><Erro msg={erro} /><Carregando /></>
  const agora = isoDataHora(new Date())
  const proximos = ags.filter((a) => a.status === 'confirmado' && a.data_hora >= agora)
  const historico = ags.filter((a) => !proximos.includes(a)).reverse()

  const Item = ({ a, pode }) => (
    <div className="ag">
      <div className="quando"><b>{hora(a.data_hora)}</b><small>{diaSem(a.data_hora)} {diaMes(a.data_hora)}</small></div>
      <div className="info"><b>{a.servico.nome}</b><small>com {a.barbeiro.nome} · {dinheiro(a.servico.preco)}</small></div>
      <div className="lado"><StatusBadge status={a.status} />
        {pode && <button className="btn-perigo btn-pequeno" onClick={() => cancelar(a)}>Cancelar</button>}</div>
    </div>
  )

  return (
    <>
      <div className="topo-pagina"><div><h1>Meus agendamentos</h1><p>Acompanhe seus próximos horários e o histórico.</p></div>
        <Link to="/agendar" className="btn btn-primario" style={{ textDecoration: 'none' }}>Novo agendamento</Link></div>
      <Erro msg={erro} />
      <h2>Próximos</h2>
      <div className="lista-ag">
        {proximos.length ? proximos.map((a) => <Item key={a.id} a={a} pode />) : <Vazio>Você não tem horários marcados.</Vazio>}
      </div>
      <h2 className="espaco">Histórico</h2>
      <div className="lista-ag">
        {historico.length ? historico.map((a) => <Item key={a.id} a={a} />) : <Vazio>Nada por aqui ainda.</Vazio>}
      </div>
    </>
  )
}
