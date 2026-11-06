// Cartão "Confirmações pelo WhatsApp": mostra/edita o número e envia um teste.
import { useEffect, useState } from 'react'
import { api } from './api.js'
import { useToast } from './ui.jsx'

export default function CanaisMensagem() {
  const avisar = useToast()
  const [c, setC] = useState(null)
  const [tel, setTel] = useState('')
  const [editando, setEditando] = useState(false)

  useEffect(() => {
    api.get('/notificacoes/canais').then((r) => { setC(r); setTel(r.telefone || '') }).catch(() => {})
  }, [])
  if (!c) return null

  const salvar = async (e) => {
    e.preventDefault()
    try {
      const r = await api.put('/notificacoes/whatsapp', { telefone: tel || null })
      setC(r); setEditando(false); avisar('Número salvo.')
    } catch (err) { avisar(err.message, 'erro') }
  }
  const testar = async () => {
    try {
      const n = await api.post('/notificacoes/teste')
      avisar(n.status === 'enviado' ? 'Mensagem de teste enviada.' : 'Não foi possível enviar.', n.status === 'enviado' ? 'ok' : 'erro')
    } catch (err) { avisar(err.message, 'erro') }
  }

  return (
    <div className="card espaco">
      <h2>Confirmações pelo WhatsApp</h2>
      {editando || !c.telefone ? (
        <form className="linha" onSubmit={salvar}>
          <input value={tel} onChange={(e) => setTel(e.target.value)} placeholder="34999990000" inputMode="tel" aria-label="WhatsApp com DDD" />
          <button className="btn-primario btn-pequeno" type="submit">Salvar</button>
          {c.telefone && <button className="btn-pequeno" type="button" onClick={() => { setTel(c.telefone); setEditando(false) }}>Cancelar</button>}
        </form>
      ) : (
        <>
          <p className="suave">Confirmações e lembretes vão para o WhatsApp <b>{c.telefone}</b>.</p>
          <div className="linha">
            <button className="btn-pequeno" onClick={() => setEditando(true)}>Trocar número</button>
            <button className="btn-pequeno" onClick={testar}>Enviar mensagem de teste</button>
          </div>
        </>
      )}
      {!c.telefone && !editando && <small className="suave" style={{ display: 'block', marginTop: 8 }}>
        Sem número, você recebe só por e-mail.</small>}
    </div>
  )
}
