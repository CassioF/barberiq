// Cartão "Onde receber as confirmações": conecta o Telegram e mostra o canal atual.
import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { useToast } from './ui.jsx'

const NOME = { telegram: 'Telegram', whatsapp: 'WhatsApp', email: 'e-mail' }

export default function CanaisMensagem() {
  const avisar = useToast()
  const [c, setC] = useState(null)
  const [aguardando, setAguardando] = useState(false)

  const carregar = useCallback(() => api.get('/notificacoes/canais').then(setC).catch(() => {}), [])
  useEffect(() => { carregar() }, [carregar])

  // depois de abrir o bot, confere a cada 3s se o vínculo foi feito (por até 2 min)
  useEffect(() => {
    if (!aguardando) return
    let n = 0
    const t = setInterval(async () => {
      n += 1
      const r = await api.get('/notificacoes/canais').catch(() => null)
      if (r) setC(r)
      if (r?.telegram_vinculado) { setAguardando(false); avisar('Telegram conectado!') }
      else if (n >= 40) setAguardando(false)
    }, 3000)
    return () => clearInterval(t)
  }, [aguardando, avisar])

  if (!c) return null
  const acao = async (fn, msg) => {
    try { await fn(); avisar(msg); carregar() } catch (e) { avisar(e.message, 'erro') }
  }

  return (
    <div className="card espaco">
      <h2>Onde receber as confirmações</h2>
      <p className="suave">
        Suas confirmações e lembretes vão por <b>{NOME[c.canal_atual]}</b>
        {c.canal_atual === 'whatsapp' && c.telefone ? ` (${c.telefone})` : ''}.
      </p>
      <div className="linha">
        {c.telegram_ativo && !c.telegram_vinculado && c.telegram_link && (
          <a className="btn btn-primario" style={{ textDecoration: 'none' }} href={c.telegram_link}
             target="_blank" rel="noreferrer" onClick={() => setAguardando(true)}>
            {aguardando ? 'Aguardando o Telegram…' : 'Conectar Telegram'}</a>)}
        {c.telegram_vinculado && (
          <button className="btn-pequeno" onClick={() => acao(() => api.del('/notificacoes/telegram'), 'Telegram desconectado.')}>
            Desconectar Telegram</button>)}
        <button className="btn-pequeno" onClick={() => acao(() => api.post('/notificacoes/teste'), 'Mensagem de teste enviada.')}>
          Enviar mensagem de teste</button>
      </div>
      {aguardando && <small className="suave" style={{ display: 'block', marginTop: 8 }}>
        No Telegram, toque em <b>Iniciar</b> (Start) para concluir.</small>}
    </div>
  )
}
