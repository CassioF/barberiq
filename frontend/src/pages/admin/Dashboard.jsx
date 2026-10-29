import { useEffect, useState } from 'react'
import { api, diaMes, dinheiro, isoData, pct } from '../../api.js'
import { Barras, Carregando, Erro, Kpi, Progresso } from '../../ui.jsx'

const PERIODOS = [[7, '7 dias'], [30, '30 dias'], [90, '90 dias']]

export default function Dashboard() {
  const [dias, setDias] = useState(30)
  const [r, setR] = useState(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    setR(null)
    const ate = new Date(), de = new Date()
    de.setDate(de.getDate() - (dias - 1))
    api.get('/relatorios/resumo', { data_de: isoData(de), data_ate: isoData(ate) }).then(setR).catch((e) => setErro(e.message))
  }, [dias])

  return (
    <>
      <div className="topo-pagina"><div><h1>Painel administrativo</h1><p>Faturamento, ocupação e faltas.</p></div>
        <div className="linha">{PERIODOS.map(([n, t]) => (
          <button key={n} className={n === dias ? 'btn-primario' : ''} onClick={() => setDias(n)}>{t}</button>))}</div></div>
      <Erro msg={erro} />
      {!r ? <Carregando /> : (
        <>
          <div className="grade g4">
            <Kpi destaque rotulo="Faturamento" valor={dinheiro(r.faturamento_total)} sub={`ticket médio ${dinheiro(r.ticket_medio)}`} />
            <Kpi rotulo="Agendamentos" valor={r.agendamentos_total} sub={`${r.por_status.concluido} concluídos · ${r.por_status.confirmado} a realizar`} />
            <Kpi rotulo="Taxa de no-show" valor={pct(r.taxa_noshow)} sub={`${r.por_status.faltou} falta(s) · ${pct(r.taxa_cancelamento)} cancelados`} />
            <Kpi rotulo="Ocupação" valor={pct(r.ocupacao_geral)} sub={`${r.futuros_alto_risco} futuro(s) com alto risco de falta`} />
          </div>

          <div className="card espaco">
            <h2>Faturamento por dia</h2>
            <Barras dados={r.faturamento_por_dia.map((d) => ({ rotulo: diaMes(d.data), valor: d.valor }))} formato={dinheiro} />
          </div>

          <div className="grade g2 espaco">
            <div className="card"><h2>Ocupação por barbeiro</h2>
              {r.ocupacao_por_barbeiro.length ? r.ocupacao_por_barbeiro.map((o) => <Progresso key={o.barbeiro} valor={o.taxa} rotulo={o.barbeiro} />) : <p className="suave">Sem barbeiros ativos.</p>}
            </div>
            <div className="card"><h2>Por serviço</h2>
              <Tabela cab={['Serviço', 'Qtd.', 'Faturamento']} linhas={r.faturamento_por_servico.map((s) => [s.servico, s.atendimentos, dinheiro(s.faturamento)])} />
            </div>
          </div>
          <div className="card espaco"><h2>Por barbeiro</h2>
            <Tabela cab={['Barbeiro', 'Atendimentos', 'Faturamento']} linhas={r.faturamento_por_barbeiro.map((s) => [s.barbeiro, s.atendimentos, dinheiro(s.faturamento)])} />
          </div>
        </>
      )}
    </>
  )
}

function Tabela({ cab, linhas }) {
  if (!linhas.length) return <p className="suave">Sem atendimentos concluídos no período.</p>
  return (
    <div className="tabela-wrap"><table style={{ minWidth: 0 }}>
      <thead><tr>{cab.map((c, i) => <th key={c} className={i ? 'num' : ''}>{c}</th>)}</tr></thead>
      <tbody>{linhas.map((l, i) => <tr key={i}>{l.map((c, k) => <td key={k} className={k ? 'num' : ''}>{c}</td>)}</tr>)}</tbody>
    </table></div>
  )
}
