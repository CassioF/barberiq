import { useEffect, useState } from 'react'
import { api, DIAS } from '../../api.js'
import { Carregando, Erro, useToast } from '../../ui.jsx'

// Editor das janelas semanais de trabalho (usado pelo barbeiro e pelo admin).
export default function DisponibilidadeEditor({ barbeiroId, onSalvo }) {
  const avisar = useToast()
  const [dias, setDias] = useState(null) // { 0: [{ini, fim}], ... }
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    api.get(`/barbeiros/${barbeiroId}/disponibilidade`).then((lista) => {
      const d = Object.fromEntries(DIAS.map((_, i) => [i, []]))
      lista.forEach((j) => d[j.dia_semana].push({ ini: j.hora_inicio.slice(0, 5), fim: j.hora_fim.slice(0, 5) }))
      setDias(d)
    }).catch((e) => setErro(e.message))
  }, [barbeiroId])

  if (!dias) return <><Erro msg={erro} /><Carregando /></>

  const mudar = (dia, i, campo, valor) =>
    setDias({ ...dias, [dia]: dias[dia].map((f, k) => (k === i ? { ...f, [campo]: valor } : f)) })
  const add = (dia) => setDias({ ...dias, [dia]: [...dias[dia], { ini: '09:00', fim: '18:00' }] })
  const rem = (dia, i) => setDias({ ...dias, [dia]: dias[dia].filter((_, k) => k !== i) })

  const salvar = async () => {
    setErro(''); setSalvando(true)
    try {
      const corpo = DIAS.flatMap((_, d) => dias[d].map((f) => ({ dia_semana: d, hora_inicio: f.ini + ':00', hora_fim: f.fim + ':00' })))
      await api.put(`/barbeiros/${barbeiroId}/disponibilidade`, corpo)
      avisar('Horários de trabalho salvos.')
      onSalvo?.()
    } catch (e) { setErro(e.message) } finally { setSalvando(false) }
  }

  return (
    <div>
      <Erro msg={erro} />
      {DIAS.map((nome, d) => (
        <div className="janela" key={d}>
          <b>{nome}</b>
          <div>
            {dias[d].length === 0 && <span className="suave">Folga</span>}
            {dias[d].map((f, i) => (
              <div className="faixa" key={i}>
                <input type="time" step="1800" value={f.ini} onChange={(e) => mudar(d, i, 'ini', e.target.value)} aria-label={`${nome}: início`} />
                <span>às</span>
                <input type="time" step="1800" value={f.fim} onChange={(e) => mudar(d, i, 'fim', e.target.value)} aria-label={`${nome}: fim`} />
                <button className="btn-icone" onClick={() => rem(d, i)} aria-label="Remover janela">✕</button>
              </div>
            ))}
            <button className="btn-pequeno" onClick={() => add(d)}>+ Janela</button>
          </div>
        </div>
      ))}
      <div className="rodape-modal"><button className="btn-primario" onClick={salvar} disabled={salvando}>{salvando ? 'Salvando…' : 'Salvar horários'}</button></div>
    </div>
  )
}
