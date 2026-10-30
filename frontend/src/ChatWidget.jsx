// Assistente de agendamento do cliente: balão flutuante no canto da tela.
// - Modo IA (quando a API tem ANTHROPIC_API_KEY): texto livre, a IA consulta horários e agenda.
// - Modo guiado (sem chave): botões passo a passo usando as rotas que já existem.
import { useEffect, useRef, useState } from 'react'
import { api, dataLonga, dinheiro, diaMes, hora, isoData } from './api.js'
import { useAuth } from './auth.jsx'

const SEMANA = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
const avisarAgenda = () => window.dispatchEvent(new Event('barberiq:agendamentos'))

function proximosDias(n = 7) {
  const hoje = new Date()
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() + i)
    const rotulo = i === 0 ? 'Hoje' : i === 1 ? 'Amanhã' : `${SEMANA[d.getDay()]} ${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`
    return { valor: isoData(d), rotulo }
  })
}

export default function ChatWidget() {
  const { usuario } = useAuth()
  const primeiroNome = usuario.nome.split(' ')[0]
  const [aberto, setAberto] = useState(false)
  const [ia, setIa] = useState(null) // null = verificando
  const [msgs, setMsgs] = useState([])
  const [opcoes, setOpcoes] = useState([]) // botões do modo guiado
  const [texto, setTexto] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const fim = useRef(null)
  const escolha = useRef({})

  useEffect(() => { fim.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, opcoes, ocupado])

  // ao abrir pela 1ª vez: descobre o modo e cumprimenta
  useEffect(() => {
    if (!aberto || ia !== null) return
    api.get('/chat/status').then((s) => s.ia).catch(() => false).then((temIa) => {
      setIa(temIa)
      if (temIa) {
        bot(`Olá, ${primeiroNome}! Sou o assistente da barbearia. Diga o que precisa, por exemplo: "quero cortar o cabelo sábado de manhã".`)
      } else {
        bot(`Olá, ${primeiroNome}! Como posso ajudar?`)
        menu()
      }
    })
  }, [aberto]) // eslint-disable-line react-hooks/exhaustive-deps

  const bot = (t) => setMsgs((m) => [...m, { papel: 'assistant', texto: t }])
  const eu = (t) => setMsgs((m) => [...m, { papel: 'user', texto: t }])

  // ------------------------------------------------------------ modo IA ---
  const enviar = async (e) => {
    e?.preventDefault()
    const t = texto.trim()
    if (!t || ocupado) return
    const historico = [...msgs, { papel: 'user', texto: t }].slice(-30)
    setMsgs(historico)
    setTexto('')
    setOcupado(true)
    try {
      const r = await api.post('/chat', { mensagens: historico })
      bot(r.resposta)
      if (r.atualizou) avisarAgenda()
    } catch (err) {
      bot(`⚠️ ${err.message}`)
    } finally {
      setOcupado(false)
    }
  }

  // ------------------------------------------------------- modo guiado ---
  const passo = async (fn) => {
    setOpcoes([])
    setOcupado(true)
    try { await fn() } catch (err) { bot(`⚠️ ${err.message}`); menu() } finally { setOcupado(false) }
  }

  function menu() {
    setOpcoes([
      { rotulo: 'Agendar um horário', acao: () => { eu('Agendar um horário'); passo(escolherServico) } },
      { rotulo: 'Meus agendamentos', acao: () => { eu('Meus agendamentos'); passo(listarMeus) } },
      { rotulo: 'Serviços e preços', acao: () => { eu('Serviços e preços'); passo(listarPrecos) } },
    ])
  }

  async function listarPrecos() {
    const s = await api.get('/servicos')
    bot(s.map((x) => `• ${x.nome}: ${dinheiro(x.preco)} (${x.duracao_min} min)`).join('\n'))
    menu()
  }

  async function escolherServico() {
    escolha.current = {}
    const s = await api.get('/servicos')
    bot('Qual serviço?')
    setOpcoes(s.map((x) => ({
      rotulo: `${x.nome} · ${dinheiro(x.preco)}`,
      acao: () => { eu(x.nome); escolha.current.servico = x; passo(escolherBarbeiro) },
    })))
  }

  async function escolherBarbeiro() {
    const b = await api.get('/barbeiros', { somente_ativos: true, limit: 100 })
    bot('Com qual barbeiro?')
    setOpcoes(b.map((x) => ({
      rotulo: x.nome,
      acao: () => { eu(x.nome); escolha.current.barbeiro = x; passo(escolherDia) },
    })))
  }

  async function escolherDia() {
    bot('Para qual dia?')
    setOpcoes(proximosDias().map((d) => ({
      rotulo: d.rotulo,
      acao: () => { eu(d.rotulo); escolha.current.dia = d.valor; passo(escolherHorario) },
    })))
  }

  async function escolherHorario() {
    const { servico, barbeiro, dia } = escolha.current
    const r = await api.get('/agendamentos/horarios-livres', { barbeiro_id: barbeiro.id, servico_id: servico.id, data: dia })
    if (!r.horarios.length) {
      bot(`${barbeiro.nome} não tem horário livre nesse dia. Escolha outro dia:`)
      return setOpcoes(proximosDias().map((d) => ({
        rotulo: d.rotulo,
        acao: () => { eu(d.rotulo); escolha.current.dia = d.valor; passo(escolherHorario) },
      })))
    }
    bot('Horários livres:')
    setOpcoes(r.horarios.map((h) => ({
      rotulo: hora(h),
      acao: () => { eu(hora(h)); escolha.current.data_hora = h; passo(confirmar) },
    })))
  }

  async function confirmar() {
    const { servico, barbeiro, data_hora } = escolha.current
    bot(`Confirma ${servico.nome} com ${barbeiro.nome}, ${dataLonga(data_hora)}, por ${dinheiro(servico.preco)}?`)
    setOpcoes([
      { rotulo: '✓ Confirmar', acao: () => { eu('Confirmar'); passo(agendar) } },
      { rotulo: 'Cancelar', acao: () => { eu('Cancelar'); bot('Tudo bem, nada foi agendado.'); menu() } },
    ])
  }

  async function agendar() {
    const { servico, barbeiro, data_hora } = escolha.current
    await api.post('/agendamentos', { barbeiro_id: barbeiro.id, servico_id: servico.id, data_hora })
    bot(`Pronto! ${servico.nome} marcado para ${dataLonga(data_hora)}. Você vai receber a confirmação.`)
    avisarAgenda()
    menu()
  }

  async function listarMeus() {
    const ags = await api.get('/agendamentos', { status: 'confirmado', data_de: isoData(new Date()), limit: 20 })
    const futuros = ags.filter((a) => new Date(a.data_hora) > new Date())
    if (!futuros.length) {
      bot('Você não tem agendamentos futuros.')
      return menu()
    }
    bot(futuros.map((a) => `• ${a.servico.nome} com ${a.barbeiro.nome}, ${dataLonga(a.data_hora)}`).join('\n'))
    setOpcoes([
      ...futuros.map((a) => ({
        rotulo: `Cancelar ${diaMes(a.data_hora)} ${hora(a.data_hora)}`,
        acao: () => { eu(`Cancelar ${diaMes(a.data_hora)} às ${hora(a.data_hora)}`); passo(() => confirmarCancelamento(a)) },
      })),
      { rotulo: 'Voltar', acao: () => { eu('Voltar'); menu() } },
    ])
  }

  async function confirmarCancelamento(a) {
    bot(`Tem certeza que quer cancelar ${a.servico.nome} ${dataLonga(a.data_hora)}?`)
    setOpcoes([
      { rotulo: 'Sim, cancelar', acao: () => { eu('Sim'); passo(async () => {
        await api.patch(`/agendamentos/${a.id}/cancelar`)
        bot('Agendamento cancelado.')
        avisarAgenda()
        menu()
      }) } },
      { rotulo: 'Não', acao: () => { eu('Não'); bot('Ok, mantive o agendamento.'); menu() } },
    ])
  }

  // -------------------------------------------------------------- tela ---
  return (
    <div className="chat">
      {aberto && (
        <section className="chat-janela" role="dialog" aria-label="Assistente de agendamento">
          <header>
            <div><b>Assistente</b><small>{ia ? 'com IA' : 'agendamento rápido'}</small></div>
            <button className="btn-icone" onClick={() => setAberto(false)} aria-label="Fechar assistente">✕</button>
          </header>
          <div className="chat-msgs" aria-live="polite">
            {msgs.map((m, i) => <p key={i} className={`chat-msg ${m.papel === 'user' ? 'eu' : 'bot'}`}>{m.texto}</p>)}
            {ocupado && <p className="chat-msg bot digitando">digitando…</p>}
            {!ia && opcoes.length > 0 && (
              <div className="chat-opcoes">
                {opcoes.map((o) => <button key={o.rotulo} onClick={o.acao} disabled={ocupado}>{o.rotulo}</button>)}
              </div>
            )}
            <div ref={fim} />
          </div>
          {ia && (
            <form className="chat-entrada" onSubmit={enviar}>
              <input value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={1000}
                placeholder="Escreva sua mensagem…" aria-label="Mensagem" autoFocus />
              <button className="btn-primario" disabled={ocupado || !texto.trim()}>Enviar</button>
            </form>
          )}
        </section>
      )}
      <button className="chat-botao" onClick={() => setAberto((a) => !a)} aria-expanded={aberto}
        aria-label={aberto ? 'Fechar assistente' : 'Abrir assistente de agendamento'}>
        {aberto ? '✕' : '💬'}
      </button>
    </div>
  )
}
