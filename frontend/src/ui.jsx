import { createContext, useCallback, useContext, useEffect, useState } from 'react'

// ---------- toasts ----------
const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }) {
  const [itens, setItens] = useState([])
  const avisar = useCallback((texto, tipo = 'ok') => {
    const id = Math.random()
    setItens((x) => [...x, { id, texto, tipo }])
    setTimeout(() => setItens((x) => x.filter((i) => i.id !== id)), 4500)
  }, [])
  return (
    <ToastCtx.Provider value={avisar}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {itens.map((i) => <div key={i.id} className={`toast ${i.tipo}`}>{i.texto}</div>)}
      </div>
    </ToastCtx.Provider>
  )
}

// ---------- modal ----------
export function Modal({ titulo, onClose, children, largo }) {
  useEffect(() => {
    const f = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', f)
    return () => window.removeEventListener('keydown', f)
  }, [onClose])
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${largo ? 'largo' : ''}`} role="dialog" aria-modal="true" aria-label={titulo}>
        <header>
          <h3>{titulo}</h3>
          <button className="btn-icone" onClick={onClose} aria-label="Fechar">✕</button>
        </header>
        {children}
      </div>
    </div>
  )
}

// ---------- pequenos componentes ----------
export const Campo = ({ rotulo, children, dica }) => (
  <label className="campo"><span>{rotulo}</span>{children}{dica && <small>{dica}</small>}</label>
)

export const Vazio = ({ children }) => <div className="vazio">{children}</div>
export const Carregando = () => <div className="vazio">Carregando…</div>
export const Erro = ({ msg }) => (msg ? <div className="erro" role="alert">{msg}</div> : null)

const ROTULO_STATUS = { confirmado: 'Confirmado', concluido: 'Concluído', cancelado: 'Cancelado', faltou: 'Faltou' }
export const StatusBadge = ({ status }) => <span className={`badge st-${status}`}>{ROTULO_STATUS[status] || status}</span>

const ROTULO_RISCO = { baixo: 'Risco baixo', medio: 'Risco médio', alto: 'Risco alto' }
export const RiscoBadge = ({ nivel, risco }) =>
  nivel ? <span className={`badge risco-${nivel}`} title="Probabilidade de falta (IA)">
    {ROTULO_RISCO[nivel]} · {Math.round(risco * 100)}%
  </span> : null

export function Kpi({ rotulo, valor, sub, destaque }) {
  return (
    <div className={`kpi ${destaque ? 'destaque' : ''}`}>
      <span>{rotulo}</span><strong>{valor}</strong>{sub && <small>{sub}</small>}
    </div>
  )
}

export function Barras({ dados, formato }) {
  // gráfico de barras simples em SVG (sem dependências)
  if (!dados.length) return <Vazio>Sem dados no período.</Vazio>
  const max = Math.max(...dados.map((d) => d.valor), 1)
  const W = 720, H = 190, base = H - 26
  const larg = W / dados.length
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="grafico" role="img" aria-label="Gráfico de faturamento por dia">
      {dados.map((d, i) => {
        const h = (d.valor / max) * (base - 18)
        const x = i * larg + larg * 0.15
        return (
          <g key={d.rotulo}>
            <rect x={x} y={base - h} width={larg * 0.7} height={h} rx="3" className="barra">
              <title>{d.rotulo}: {formato(d.valor)}</title>
            </rect>
            {(dados.length <= 16 || i % Math.ceil(dados.length / 12) === 0) && (
              <text x={x + larg * 0.35} y={H - 8} textAnchor="middle" className="eixo">{d.rotulo}</text>
            )}
          </g>
        )
      })}
      <line x1="0" x2={W} y1={base} y2={base} className="linha-base" />
      <text x="2" y="12" className="eixo">{formato(max)}</text>
    </svg>
  )
}

export function Progresso({ valor, rotulo }) {
  return (
    <div className="prog">
      <div className="prog-topo"><span>{rotulo}</span><b>{Math.round(valor * 100)}%</b></div>
      <div className="prog-trilho"><div className="prog-barra" style={{ width: `${Math.min(valor, 1) * 100}%` }} /></div>
    </div>
  )
}
