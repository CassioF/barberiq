import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api, getToken, setToken, onSessaoExpirada } from './api.js'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null)
  const [carregando, setCarregando] = useState(!!getToken())

  const sair = useCallback(() => { setToken(null); setUsuario(null) }, [])

  useEffect(() => {
    onSessaoExpirada(sair)
    if (getToken()) {
      api.get('/auth/me').then(setUsuario).catch(sair).finally(() => setCarregando(false))
    }
  }, [sair])

  const entrar = async (email, senha) => {
    const r = await api.login(email, senha)
    setToken(r.access_token)
    setUsuario(r.usuario)
    return r.usuario
  }

  return <Ctx.Provider value={{ usuario, carregando, entrar, sair }}>{children}</Ctx.Provider>
}

export const homeDoPerfil = (tipo) =>
  tipo === 'admin' ? '/admin' : tipo === 'barbeiro' ? '/barbeiro' : '/agendar'
