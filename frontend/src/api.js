// Cliente HTTP da API FastAPI. O token JWT fica no localStorage.
const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')
const KEY = 'barberiq_token'

export const getToken = () => {
  try { return localStorage.getItem(KEY) } catch { return null }
}
export const setToken = (t) => {
  try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY) } catch { /* ignora */ }
}

let aoExpirar = () => {}
export const onSessaoExpirada = (fn) => { aoExpirar = fn }

function mensagemErro(corpo, status) {
  const d = corpo?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((e) => `${(e.loc || []).slice(1).join('.')}: ${e.msg}`).join('; ')
  return `Erro ${status}`
}

async function request(path, { method = 'GET', body, form, params } = {}) {
  const url = new URL(BASE + path)
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
  })
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let corpo
  if (form) { corpo = new URLSearchParams(form) }
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; corpo = JSON.stringify(body) }

  let res
  try {
    res = await fetch(url, { method, headers, body: corpo })
  } catch {
    throw new Error('Não foi possível conectar à API. Verifique se o servidor está no ar.')
  }
  if (res.status === 204) return { data: null, total: 0 }
  const json = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && token && !path.startsWith('/auth/login')) aoExpirar()
    throw new Error(mensagemErro(json, res.status))
  }
  return { data: json, total: Number(res.headers.get('X-Total-Count') ?? 0) }
}

const d = async (p) => (await p).data
export const api = {
  get: (path, params) => d(request(path, { params })),
  list: (path, params) => request(path, { params }), // { data, total }
  post: (path, body) => d(request(path, { method: 'POST', body })),
  put: (path, body) => d(request(path, { method: 'PUT', body })),
  patch: (path, body) => d(request(path, { method: 'PATCH', body })),
  del: (path) => d(request(path, { method: 'DELETE' })),
  login: (email, senha) => d(request('/auth/login', { method: 'POST', form: { username: email, password: senha } })),
}

// ---- datas (a API usa horário local sem fuso) ----
const p2 = (n) => String(n).padStart(2, '0')
export const isoData = (dt) => `${dt.getFullYear()}-${p2(dt.getMonth() + 1)}-${p2(dt.getDate())}`
export const isoDataHora = (dt) => `${isoData(dt)}T${p2(dt.getHours())}:${p2(dt.getMinutes())}:00`
export const paraData = (s) => new Date(s) // "2026-10-20T14:00:00" => horário local
export const hora = (s) => { const x = paraData(s); return `${p2(x.getHours())}:${p2(x.getMinutes())}` }
export const diaMes = (s) => { const x = paraData(s); return `${p2(x.getDate())}/${p2(x.getMonth() + 1)}` }
const SEM = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb']
export const diaSem = (s) => SEM[paraData(s).getDay()]
export const dataLonga = (s) => `${diaSem(s)}, ${diaMes(s)} às ${hora(s)}`
export const dinheiro = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
export const pct = (v) => `${(Number(v || 0) * 100).toFixed(1).replace('.', ',')}%`
export const DIAS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
