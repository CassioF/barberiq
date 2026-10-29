import { useCallback, useEffect, useState } from 'react'
import { api, dinheiro, diaMes, diaSem, hora, isoData } from '../../api.js'
import { Campo, Carregando, Erro, RiscoBadge, StatusBadge, Vazio } from '../../ui.jsx'
import AcoesAgendamento from '../AcoesAgendamento.jsx'

const LIMITE = 50

export default function AgendaAdmin() {
  const hoje = isoData(new Date())
  const [f, setF] = useState({ data_de: hoje, data_ate: hoje, status: '', barbeiro_id: '' })
  const [barbeiros, setBarbeiros] = useState([])
  const [res, setRes] = useState(null)
  const [pagina, setPagina] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => { api.get('/barbeiros', { limit: 100 }).then(setBarbeiros).catch(() => {}) }, [])
  useEffect(() => { setPagina(0) }, [f])

  const carregar = useCallback(() => {
    setRes(null)
    api.list('/agendamentos', { ...f, skip: pagina * LIMITE, limit: LIMITE }).then(setRes).catch((e) => setErro(e.message))
  }, [f, pagina])
  useEffect(() => { carregar() }, [carregar])

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const totalPaginas = res ? Math.max(1, Math.ceil(res.total / LIMITE)) : 1

  return (
    <>
      <div className="topo-pagina"><div><h1>Agendamentos</h1><p>Todos os horários, com o risco de falta calculado pela IA.</p></div></div>
      <div className="filtros">
        <Campo rotulo="De"><input type="date" value={f.data_de} onChange={set('data_de')} /></Campo>
        <Campo rotulo="Até"><input type="date" value={f.data_ate} onChange={set('data_ate')} /></Campo>
        <Campo rotulo="Status"><select value={f.status} onChange={set('status')}>
          <option value="">Todos</option><option value="confirmado">Confirmado</option><option value="concluido">Concluído</option>
          <option value="faltou">Faltou</option><option value="cancelado">Cancelado</option></select></Campo>
        <Campo rotulo="Barbeiro"><select value={f.barbeiro_id} onChange={set('barbeiro_id')}>
          <option value="">Todos</option>{barbeiros.map((b) => <option key={b.id} value={b.id}>{b.nome}</option>)}</select></Campo>
      </div>
      <Erro msg={erro} />
      {!res ? <Carregando /> : res.data.length === 0 ? <Vazio>Nenhum agendamento para o filtro.</Vazio> : (
        <>
          <div className="tabela-wrap"><table>
            <thead><tr><th>Quando</th><th>Cliente</th><th>Serviço</th><th>Barbeiro</th><th>Risco (IA)</th><th>Status</th><th /></tr></thead>
            <tbody>{res.data.map((a) => (
              <tr key={a.id}>
                <td><b>{diaSem(a.data_hora)} {diaMes(a.data_hora)}</b> {hora(a.data_hora)}</td>
                <td>{a.cliente.nome}</td>
                <td>{a.servico.nome} <small>{dinheiro(a.servico.preco)}</small></td>
                <td>{a.barbeiro.nome}</td>
                <td>{a.status === 'confirmado' ? <RiscoBadge nivel={a.nivel_risco} risco={a.risco_noshow} /> : <small>—</small>}</td>
                <td><StatusBadge status={a.status} /></td>
                <td className="acoes"><AcoesAgendamento ag={a} aoMudar={carregar} compacto /></td>
              </tr>))}</tbody>
          </table></div>
          <div className="linha espaco" style={{ justifyContent: 'space-between' }}>
            <small>{res.total} registro(s)</small>
            <div className="linha">
              <button disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>←</button>
              <small>página {pagina + 1} de {totalPaginas}</small>
              <button disabled={pagina + 1 >= totalPaginas} onClick={() => setPagina(pagina + 1)}>→</button>
            </div>
          </div>
        </>
      )}
    </>
  )
}
