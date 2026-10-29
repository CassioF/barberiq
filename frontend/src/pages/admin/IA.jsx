import { useEffect, useState } from 'react'
import { api, DIAS, dataLonga } from '../../api.js'
import { Campo, Carregando, Erro, Kpi, useToast } from '../../ui.jsx'

const ROTULO_TIPO = { confirmacao: 'Confirmação', lembrete: 'Lembrete', lembrete_reforcado: 'Lembrete reforçado', cancelamento: 'Cancelamento' }

export default function IA() {
  const avisar = useToast()
  const [metricas, setMetricas] = useState(null)
  const [notifs, setNotifs] = useState(null)
  const [erro, setErro] = useState('')
  const [sim, setSim] = useState({ taxa_faltas: 0.1, dia_semana: 4, antecedencia_horas: 48 })
  const [previsao, setPrevisao] = useState(null)
  const [ocupado, setOcupado] = useState(false)

  const carregar = () => {
    api.get('/ia/noshow/metricas').then(setMetricas).catch((e) => setErro(e.message))
    api.get('/notificacoes', { limit: 30 }).then(setNotifs).catch((e) => setErro(e.message))
  }
  useEffect(carregar, [])

  // simulador em tempo real (debounce curto)
  useEffect(() => {
    const t = setTimeout(() => api.post('/ia/noshow/prever', sim).then(setPrevisao).catch(() => {}), 150)
    return () => clearTimeout(t)
  }, [sim])

  const acao = async (fn, msg) => {
    setOcupado(true)
    try { const r = await fn(); avisar(typeof msg === 'function' ? msg(r) : msg); carregar() }
    catch (e) { avisar(e.message, 'erro') } finally { setOcupado(false) }
  }

  return (
    <>
      <div className="topo-pagina"><div><h1>IA & Notificações</h1><p>Previsão de no-show com Regressão Logística (scikit-learn) e envio automático de lembretes.</p></div></div>
      <Erro msg={erro} />
      <div className="grade g2">
        <div className="card">
          <h2>Simulador de risco de falta</h2>
          <Campo rotulo={`Histórico de faltas do cliente: ${Math.round(sim.taxa_faltas * 100)}%`}>
            <input type="range" min="0" max="1" step="0.05" value={sim.taxa_faltas} onChange={(e) => setSim({ ...sim, taxa_faltas: Number(e.target.value) })} /></Campo>
          <Campo rotulo="Dia da semana"><select value={sim.dia_semana} onChange={(e) => setSim({ ...sim, dia_semana: Number(e.target.value) })}>
            {DIAS.map((d, i) => <option key={d} value={i}>{d}</option>)}</select></Campo>
          <Campo rotulo={`Antecedência do agendamento: ${sim.antecedencia_horas} h (${(sim.antecedencia_horas / 24).toFixed(1).replace('.', ',')} dias)`}>
            <input type="range" min="1" max="720" step="1" value={sim.antecedencia_horas} onChange={(e) => setSim({ ...sim, antecedencia_horas: Number(e.target.value) })} /></Campo>
          {previsao && (
            <div className={`gauge ${previsao.nivel}`} aria-live="polite">
              <strong>{Math.round(previsao.risco * 100)}%</strong>
              <span>probabilidade de falta · risco <b>{previsao.nivel}</b></span>
              {previsao.nivel === 'alto' && <p className="suave">Ação: lembrete reforçado 48h antes, pedindo confirmação.</p>}
            </div>)}
        </div>

        <div className="card">
          <h2>Modelo</h2>
          {!metricas ? <Carregando /> : (
            <>
              <p className="suave">{metricas.algoritmo} · treinado com {metricas.amostras_treino} {metricas.dados} (versão {metricas.versao}).</p>
              <div className="grade" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <Kpi rotulo="Acurácia" valor={`${(metricas.acuracia * 100).toFixed(1)}%`} />
                <Kpi rotulo="AUC-ROC" valor={metricas.auc_roc.toFixed(3)} />
                <Kpi rotulo="No-show na base" valor={`${(metricas.taxa_noshow_base * 100).toFixed(1)}%`} />
                <Kpi rotulo="Limite de alto risco" valor={`${Math.round(metricas.limite_alto_risco * 100)}%`} />
              </div>
              <div className="linha espaco">
                <button disabled={ocupado} onClick={() => acao(() => api.post('/ia/noshow/treinar'), 'Modelo retreinado.')}>Retreinar modelo</button>
                <button className="btn-primario" disabled={ocupado} onClick={() => acao(() => api.post('/notificacoes/disparar-lembretes'), (r) => `${r.enviados} lembrete(s) enviado(s).`)}>Disparar lembretes agora</button>
              </div>
              <small className="suave" style={{ display: 'block', marginTop: 10 }}>Os lembretes também são enviados automaticamente pela API. O envio por e-mail/WhatsApp está simulado (registrado no log).</small>
            </>
          )}
        </div>
      </div>

      <div className="card espaco">
        <h2>Últimas notificações</h2>
        {!notifs ? <Carregando /> : notifs.length === 0 ? <p className="suave">Nenhuma notificação ainda.</p> : (
          <div className="tabela-wrap"><table>
            <thead><tr><th>Quando</th><th>Tipo</th><th>Canal</th><th>Mensagem</th><th>Status</th></tr></thead>
            <tbody>{notifs.map((n) => (
              <tr key={n.id}><td>{dataLonga(n.criado_em)}</td><td>{ROTULO_TIPO[n.tipo]}</td><td>{n.canal}</td><td>{n.mensagem}</td>
                <td><span className={`badge ${n.status === 'enviado' ? 'st-confirmado' : 'st-cancelado'}`}>{n.status}</span></td></tr>))}</tbody>
          </table></div>
        )}
      </div>
    </>
  )
}
