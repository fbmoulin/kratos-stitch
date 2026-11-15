import { useCallback, useMemo, useRef } from 'react'
import { api, type No, type Pos } from './api'

// um passo que resolve `false` falhou (o servidor recusou): fica onde estava na pilha
type Passo = { desfazer: () => Promise<unknown>; refazer: () => Promise<unknown> }

// o valor "vazio" de cada campo, para desfazer uma mudança num nó que ainda não tinha o campo
const VAZIO: Partial<Record<keyof No, unknown>> = { estado: 'neutra', recolhido: false, escondidos: [], desloc: null, entradas: [], direcoes: [], literal: false }
// texto digitado tem o desfazer do próprio campo (⌘Z dentro do textarea)
const FORA = new Set<keyof No>(['intencao'])

/**
 * ⌘Z / ⌘⇧Z do canvas. Cada mudança feita por aqui guarda o "antes" e o "depois"; `emLote` junta várias mudanças
 * (arrastar uma seleção, marcar várias imagens, expandir tudo) num passo só.
 */
export function useHistorico(opts: {
  slug: string
  porId: () => Map<string, No>
  mudar: (id: string, campos: Partial<No>) => Promise<boolean>
  posicoes: (mapa: Record<string, Pos>) => Promise<boolean>
  acao: <T>(fn: () => Promise<T>) => Promise<T | undefined>
}) {
  const { slug, porId, mudar, posicoes, acao } = opts
  const pilhas = useRef<{ desfazer: Passo[]; refazer: Passo[] }>({ desfazer: [], refazer: [] })
  const lote = useRef<Passo[] | null>(null)
  const fila = useRef<Promise<unknown>>(Promise.resolve())  // desfazer/refazer rodam um de cada vez

  const registrar = useCallback((p: Passo) => {
    if (lote.current) { lote.current.push(p); return }
    pilhas.current.desfazer.push(p)
    if (pilhas.current.desfazer.length > 100) pilhas.current.desfazer.shift()
    pilhas.current.refazer = []
  }, [])

  const emLote = useCallback(async (fn: () => unknown) => {
    const anterior = lote.current
    lote.current = []
    try {
      await fn()
    } finally {
      const passos = lote.current || []
      lote.current = anterior
      // `feitos`: quantos passos do lote estão aplicados; se um falha no meio, a próxima tentativa continua dali
      let feitos = passos.length
      if (passos.length) registrar({
        desfazer: async () => { for (; feitos > 0; feitos--) if ((await passos[feitos - 1].desfazer()) === false) return false },
        refazer: async () => { for (; feitos < passos.length; feitos++) if ((await passos[feitos].refazer()) === false) return false },
      })
    }
  }, [registrar])

  const mudarH = useCallback((id: string, campos: Partial<No>) => {
    const no = porId().get(id)
    const chaves = (Object.keys(campos) as (keyof No)[]).filter((k) => !FORA.has(k))
    if (no && chaves.length) {
      const antes = Object.fromEntries(chaves.map((k) => [k, no[k] ?? VAZIO[k] ?? null])) as Partial<No>
      const depois = Object.fromEntries(chaves.map((k) => [k, campos[k]])) as Partial<No>
      registrar({ desfazer: () => mudar(id, antes), refazer: () => mudar(id, depois) })
    }
    return mudar(id, campos)
  }, [porId, mudar, registrar])

  const posicoesH = useCallback((mapa: Record<string, Pos>) => {
    const antes: Record<string, Pos> = {}
    for (const id of Object.keys(mapa)) {
      const p = porId().get(id)?.pos
      if (p) antes[id] = p
    }
    if (Object.keys(antes).length) registrar({ desfazer: () => posicoes(antes), refazer: () => posicoes(mapa) })
    return posicoes(mapa)
  }, [porId, posicoes, registrar])

  /** Apagar (rascunho, referência) vai para a lixeira do projeto; desfazer traz de volta. */
  const apagarH = useCallback(async (id: string) => {
    const r = await acao(() => api.apagarNo(slug, id))
    if (r) registrar({
      desfazer: async () => (await acao(() => api.restaurarNo(slug, id))) !== undefined,
      refazer: async () => (await acao(() => api.apagarNo(slug, id))) !== undefined,
    })
  }, [slug, acao, registrar])

  /** Um nó recém-criado: desfazer o apaga (vai para a lixeira), refazer o restaura. */
  const criado = useCallback((id: string) => {
    registrar({
      desfazer: async () => (await acao(() => api.apagarNo(slug, id))) !== undefined,
      refazer: async () => (await acao(() => api.restaurarNo(slug, id))) !== undefined,
    })
  }, [slug, acao, registrar])

  /** Roda o passo do topo de uma pilha: `null` = nada a fazer, `false` = falhou (o passo fica onde estava), `true` = feito. */
  const andar = useCallback((de: 'desfazer' | 'refazer') => {
    const r = fila.current.then(async () => {
      const p = pilhas.current[de].at(-1)
      if (!p) return null
      if ((await p[de]().catch(() => false)) === false) return false
      const i = pilhas.current[de].lastIndexOf(p)
      if (i >= 0) pilhas.current[de].splice(i, 1)
      pilhas.current[de === 'desfazer' ? 'refazer' : 'desfazer'].push(p)
      return true
    })
    fila.current = r
    return r
  }, [])

  const desfazer = useCallback(() => andar('desfazer'), [andar])
  const refazer = useCallback(() => andar('refazer'), [andar])

  return useMemo(
    () => ({ mudar: mudarH, posicoes: posicoesH, apagar: apagarH, criado, passo: registrar, emLote, desfazer, refazer }),
    [mudarH, posicoesH, apagarH, criado, registrar, emLote, desfazer, refazer],
  )
}
