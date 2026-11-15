import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type EstadoProjeto, type No, type Pos } from './api'

/**
 * O estado do projeto, sincronizado com o disco: busca a cada 2 s (o servidor responde "igual" quando nada mudou),
 * e cada mudança local é aplicada na hora (otimista) e confirmada pela próxima leitura.
 */
export function useProjeto(slug: string) {
  const [estado, setEstado] = useState<EstadoProjeto | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const rev = useRef<string | undefined>(undefined)
  // o erro que a própria leitura mostrou (rede fora do ar): só esse some sozinho, na próxima leitura que der certo;
  // o de uma ação (o servidor recusou) fica até o clique no toast
  const erroLeitura = useRef<string | null>(null)
  const locais = useRef(new Map<string, { campos: Partial<No>; ate: number }>())

  const carregar = useCallback(
    async (forcar = false) => {
      try {
        const r = await api.estado(slug, forcar ? undefined : rev.current)
        const m = erroLeitura.current
        if (m !== null) { erroLeitura.current = null; setErro((e) => (e === m ? null : e)) }
        if (r.igual) return
        rev.current = r.rev
        const agora = Date.now()
        for (const [id, l] of locais.current) if (l.ate < agora) locais.current.delete(id)
        r.nos = r.nos.map((n) => {
          const l = locais.current.get(n.id)
          return l ? { ...n, ...l.campos } : n
        })
        for (const [id, l] of locais.current) if (id.includes('/') && 'desloc' in l.campos) r.avancos = comDesloc(r.avancos, id, l.campos.desloc ?? null)
        setEstado(r)
      } catch (e) {
        erroLeitura.current = (e as Error).message
        setErro(erroLeitura.current)
      }
    },
    [slug],
  )

  useEffect(() => {
    rev.current = undefined
    setEstado(null)
    carregar(true)
    const t = setInterval(() => document.visibilityState === 'visible' && carregar(), 2000)
    return () => clearInterval(t)
  }, [carregar])

  /** Muda um nó localmente agora e no servidor em seguida. Devolve se o servidor aceitou. */
  const mudar = useCallback(
    async (id: string, campos: Partial<No>) => {
      locais.current.set(id, { campos: { ...(locais.current.get(id)?.campos || {}), ...campos }, ate: Date.now() + 4000 })
      // uma versão de HTML (<IMG>/<vN>) não é um arquivo de nó: só o desloc dela vale, e vai para o impl.json
      const [img, versao] = id.split('/')
      if (versao) {
        if (!('desloc' in campos)) return true
        const d = campos.desloc ?? null
        setEstado((e) => (e ? { ...e, avancos: comDesloc(e.avancos, id, d) } : e))
        let ok = true
        try {
          await api.deslocImpl(slug, img, versao, d)
        } catch (e) {
          locais.current.delete(id)
          setErro((e as Error).message)
          ok = false
        }
        carregar(true)
        return ok
      }
      setEstado((e) => (e ? { ...e, nos: e.nos.map((n) => (n.id === id ? { ...n, ...campos } : n)) } : e))
      let ok = true
      try {
        await api.mudarNo(slug, id, campos)
      } catch (e) {
        locais.current.delete(id)
        setErro((e as Error).message)
        ok = false
      }
      carregar(true)
      return ok
    },
    [slug, carregar],
  )

  /** Muda vários nós de uma vez: um pedido ao servidor (tudo ou nada) e uma recarga. Devolve se o servidor aceitou.
   * Os cartões de página (<IMG>/<vN>) não são nós: vão um a um, pelo impl.json. */
  const mudarVarios = useCallback(
    async (mapa: Record<string, Partial<No>>) => {
      const paginas = Object.entries(mapa).filter(([id]) => id.includes('/'))
      const nos = Object.fromEntries(Object.entries(mapa).filter(([id]) => !id.includes('/')))
      const dasPaginas = Promise.all(paginas.map(([id, campos]) => mudar(id, campos)))
      if (!Object.keys(nos).length) return (await dasPaginas).every(Boolean)
      for (const [id, campos] of Object.entries(nos))
        locais.current.set(id, { campos: { ...(locais.current.get(id)?.campos || {}), ...campos }, ate: Date.now() + 4000 })
      setEstado((e) => (e ? { ...e, nos: e.nos.map((n) => (nos[n.id] ? { ...n, ...nos[n.id] } : n)) } : e))
      let ok = true
      try {
        await api.mudarNos(slug, nos)
      } catch (e) {
        for (const id of Object.keys(nos)) locais.current.delete(id)
        setErro((e as Error).message)
        ok = false
      }
      carregar(true)
      return (await dasPaginas).every(Boolean) && ok
    },
    [slug, carregar, mudar],
  )

  const posicoes = useCallback(
    async (mapa: Record<string, { x: number; y: number }>) => {
      if (!Object.keys(mapa).length) return true
      for (const [id, pos] of Object.entries(mapa))
        locais.current.set(id, { campos: { ...(locais.current.get(id)?.campos || {}), pos }, ate: Date.now() + 4000 })
      setEstado((e) => (e ? { ...e, nos: e.nos.map((n) => (mapa[n.id] ? { ...n, pos: mapa[n.id] } : n)) } : e))
      return api.posicoes(slug, mapa).then(() => true).catch((e) => {
        // o servidor não gravou: as posições otimistas saem e a tela volta ao que está no disco
        for (const id of Object.keys(mapa)) locais.current.delete(id)
        setErro(e.message)
        carregar(true)
        return false
      })
    },
    [slug, carregar],
  )

  /** Roda uma ação no servidor, mostra o erro se houver e recarrega. */
  const acao = useCallback(
    async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
      try {
        const r = await fn()
        await carregar(true)
        return r
      } catch (e) {
        setErro((e as Error).message)
      }
    },
    [carregar],
  )

  return { estado, erro, setErro, carregar, mudar, mudarVarios, posicoes, acao }
}

/** Os avanços com o desloc de uma versão de HTML (<IMG>/<vN>) trocado. */
function comDesloc(avancos: EstadoProjeto['avancos'], id: string, desloc: Pos | null): EstadoProjeto['avancos'] {
  const [img, versao] = id.split('/')
  const av = avancos?.[img]
  const t = av?.trabalhos?.[versao]
  if (!av || !t) return avancos
  return { ...avancos, [img]: { ...av, trabalhos: { ...av.trabalhos, [versao]: { ...t, desloc } } } }
}
