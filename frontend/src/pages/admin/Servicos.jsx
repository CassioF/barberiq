import { useCallback, useEffect, useState } from 'react'
import { api, dinheiro } from '../../api.js'
import { Campo, Carregando, Erro, Modal, Vazio, useToast } from '../../ui.jsx'

export default function Servicos() {
  const avisar = useToast()
  const [lista, setLista] = useState(null)
  const [erro, setErro] = useState('')
  const [form, setForm] = useState(null)

  const carregar = useCallback(() => api.get('/servicos', { todos: true }).then(setLista).catch((e) => setErro(e.message)), [])
  useEffect(() => { carregar() }, [carregar])

  const excluir = async (s) => {
    if (!confirm(`Excluir o serviço "${s.nome}"?`)) return
    try { await api.del(`/servicos/${s.id}`); avisar('Serviço excluído.'); carregar() } catch (e) { avisar(e.message, 'erro') }
  }
  const alternar = async (s) => {
    try { await api.put(`/servicos/${s.id}`, { ativo: !s.ativo }); carregar() } catch (e) { avisar(e.message, 'erro') }
  }

  return (
    <>
      <div className="topo-pagina"><div><h1>Serviços</h1><p>Catálogo com duração e preço (a duração define o tamanho do horário na agenda).</p></div>
        <button className="btn-primario" onClick={() => setForm({})}>+ Novo serviço</button></div>
      <Erro msg={erro} />
      {!lista ? <Carregando /> : lista.length === 0 ? <Vazio>Nenhum serviço cadastrado.</Vazio> : (
        <div className="tabela-wrap"><table>
          <thead><tr><th>Serviço</th><th>Descrição</th><th className="num">Duração</th><th className="num">Preço</th><th>Situação</th><th /></tr></thead>
          <tbody>{lista.map((s) => (
            <tr key={s.id}>
              <td><b>{s.nome}</b></td><td>{s.descricao || '—'}</td>
              <td className="num">{s.duracao_min} min</td><td className="num">{dinheiro(s.preco)}</td>
              <td><span className={`badge ${s.ativo ? 'st-confirmado' : 'st-cancelado'}`}>{s.ativo ? 'Ativo' : 'Inativo'}</span></td>
              <td className="acoes">
                <button className="btn-pequeno" onClick={() => setForm(s)}>Editar</button>
                <button className="btn-pequeno" onClick={() => alternar(s)}>{s.ativo ? 'Desativar' : 'Ativar'}</button>
                <button className="btn-perigo btn-pequeno" onClick={() => excluir(s)}>Excluir</button>
              </td>
            </tr>))}</tbody>
        </table></div>
      )}
      {form && <FormServico inicial={form} onClose={() => setForm(null)} onSalvo={() => { setForm(null); carregar() }} />}
    </>
  )
}

function FormServico({ inicial, onClose, onSalvo }) {
  const avisar = useToast()
  const edicao = !!inicial.id
  const [f, setF] = useState({ nome: inicial.nome || '', descricao: inicial.descricao || '', duracao_min: inicial.duracao_min || 30, preco: inicial.preco ?? '' })
  const [erro, setErro] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const enviar = async (e) => {
    e.preventDefault(); setErro('')
    const corpo = { nome: f.nome, descricao: f.descricao || null, duracao_min: Number(f.duracao_min), preco: String(f.preco).replace(',', '.') }
    try {
      if (edicao) await api.put(`/servicos/${inicial.id}`, corpo); else await api.post('/servicos', corpo)
      avisar('Serviço salvo.'); onSalvo()
    } catch (err) { setErro(err.message) }
  }

  return (
    <Modal titulo={edicao ? 'Editar serviço' : 'Novo serviço'} onClose={onClose}>
      <form onSubmit={enviar}>
        <Erro msg={erro} />
        <Campo rotulo="Nome"><input required minLength={2} value={f.nome} onChange={set('nome')} autoFocus /></Campo>
        <Campo rotulo="Descrição"><input value={f.descricao} onChange={set('descricao')} /></Campo>
        <div className="linha" style={{ alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}><Campo rotulo="Duração (min)"><input type="number" min="5" max="480" step="5" required value={f.duracao_min} onChange={set('duracao_min')} /></Campo></div>
          <div style={{ flex: 1 }}><Campo rotulo="Preço (R$)"><input type="number" min="0" step="0.01" required value={f.preco} onChange={set('preco')} /></Campo></div>
        </div>
        <div className="rodape-modal"><button type="button" onClick={onClose}>Cancelar</button><button className="btn-primario">Salvar</button></div>
      </form>
    </Modal>
  )
}
