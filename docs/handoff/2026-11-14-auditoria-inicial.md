# Handoff 2026-11-14 — clone, instalação e auditoria inicial

## Estado medido

- Repo: `https://github.com/rtadewald/neo-stitch.git`, branch `main`, HEAD `d6d0c86`, clonado em `/Users/felipemoulin/Projetos/neo-stitch`.
- Nenhum commit feito, nada enviado. Único arquivo novo: este handoff (não rastreado). Sem CI no repo. Nada em produção (app local).
- Instalação: `npm --prefix app install` (0 vulnerabilidades) e `npm --prefix app run build` (ok, 1 chunk JS de 515 kB).
- Servidor real: `uv run ferramentas/servidor.py` → `GET /` 200, `GET /api/projetos` 200 `[]`.
- Chaves: `/api/config` devolve `origem: null` para `OPENROUTER_API_KEY` e `FAL_KEY` (nenhuma definida).
- Toolchain: Python 3.13.15, Node 26.8.1, uv, ffmpeg, sips e Google Chrome presentes.
- Lint: `oxlint` 9 avisos (nenhum é bug); `ruff check ferramentas` 21 avisos cosméticos.
- Não há testes, CI nem LICENSE no repo.

## Achados reproduzidos (cópia isolada, porta 8731, sem chave)

1. Projeto com nome de 1–2 letras ("IA", "X"): `POST /api/projetos` → 422 `código inválido: 'IA1-001'` e fica um projeto zumbi (projeto.json sem nós) na lista. Causa: `base.prefixo_livre` devolve prefixo com dígito, que `CODIGO` rejeita.
2. `gerar.py` sem chave: cria os placeholders e marca `trabalhando` (l.94–105) antes de `chave()` (l.107). O pedido fica preso: DELETE → 422 "espere o Claude terminar", reenviar → 422. `neo.py erro` solta o pedido, mas as imagens seguem `gerando: true`. Rodar `gerar.py` de novo no mesmo pedido acrescenta saídas (sem guarda de status).
3. Escritas vindas de outra origem: `POST …/enviar` com `Origin: https://evil.test` → 200 e linha na `fila.jsonl`; `POST …/nos` com `Content-Type: text/plain;x=json` → 200 (sem preflight). `GET /api/projetos` com `Host: evil.test` → 200. Só `/api/config*` checa Origin/Host.
4. Tipo `modelo` pela metade: `PATCH` de estado/desloc num modelo → 200 sem gravar nada (falta em `CAMPOS_APP`); `custos()` ignora o custo dele (0.66 em vez de 1.06 no teste); `galho()` não o liga ao pedido, então apagar o pedido 3D deixa o modelo órfão.
5. `galho()` (base.py) diverge de `arvore()` (layout.ts:64,73): não trata vídeo/página como pai de pedido.
6. `criar_no` descarta entradas que não são imagem/referência (página `IMG/vN`, vídeo); `PATCH entradas` aceita qualquer coisa (`["NAO-999","../../etc",42]`). `gerar_video.py` dá traceback com entrada `IMG/vN`.
7. Menores: corpo JSON que não é objeto → 500; `PATCH` em projeto inexistente cria `projects/<slug>/.lock`; `Range` além do arquivo → 206 com `Content-Range: bytes 999999-8/9`; `HEAD /.env` e `HEAD /ferramentas/base.py` → 200 (só cabeçalhos).

## Achados do frontend (lidos no código, não observados rodando)

- `Canvas.tsx:246-253`: cada carga recria todos os nós do React Flow sem `measured` (re-medição geral).
- `useProjeto.ts:66-70`: erro de PATCH é apagado pelo `carregar(true)` seguinte; `useProjeto.ts:18`: erro de rede não some enquanto `igual`.
- `useHistorico.ts:86-100`: ⌘Z diz "Desfeito" mesmo quando o servidor recusa.
- `Canvas.tsx:545-599`: atalhos agem com o visualizador ou um modal aberto.

## Desempenho medido

Projeto de 602 nós: GET completo 19 ms / 546 kB; poll `?rev=` 6 ms; Home 13 ms. O servidor não é gargalo.

## Itens abertos

- Nenhuma correção aplicada. Decidir quais corrigir e se vai como fork/PR para o autor.
- Drift de docs: README lista `F` "Favorita" (não existe mais); `impl.py:106` cita "seção 4" (é a 5); skill `video2html` citada e ausente do repo; Chrome não está nos requisitos.

## Prompt de retomada

```
Leia docs/handoff/2026-11-14-auditoria-inicial.md em /Users/felipemoulin/Projetos/neo-stitch e re-meça (git status, git log -1, curl localhost:8730/api/projetos). Depois corrija, com teste que reproduz cada um antes: (1) prefixo_livre com nomes curtos, (2) gerar.py pedindo a chave antes dos placeholders e com guarda de status, (3) checagem de Origin/Host em todas as rotas de escrita, (4) tipo modelo em CAMPOS_APP, custos() e galho().
```

---

# Atualização (mesma sessão) — correções 1 a 4 aplicadas

## Estado medido

- Branch local `correcoes-auditoria`, saída de `main` (`d6d0c86`). Nada enviado: `origin` é o repo do autor e as correções ficam só neste clone.
- Pre-mortem do plano: veredito REFINE (ajustes incorporados: testes isolados com `gerar.chave`/`gerar.pedir` trocados, guarda dentro da trava, checagem de origem depois de ler o corpo, `galho()` com round-trip apagar→restaurar).
- Testes: `tests/test_auditoria.py`, 18 testes. Antes das correções: 14 falhavam e 4 passavam (os de comportamento que não devia mudar). Depois: `uvx pytest tests -q` → `18 passed`.
- `ruff check ferramentas`: 21 avisos, igual à linha de base. `ruff format --check` reformataria 9 arquivos do autor: não apliquei (colide com a regra de mudanças cirúrgicas).
- Servidor real reiniciado com o código novo: `GET /` 200; `GET /api/projetos` 200; POST com `Origin: http://localhost:8730` passa; POST com `Origin: https://evil.test` → 403 "Só pelo app local."

## O que mudou

1. `base.py`: `prefixo_livre` sempre devolve 3 letras; `criar_projeto` valida o prefixo antes de criar a pasta.
2. `gerar.py`: chave e referências antes dos placeholders; recusa rodar se o pedido já tem saída `gerando`; fecha o pedido num `finally` pelo que ficou no disco. `gerar_video.py`: a mesma guarda. `neo.py erro`: limpa `gerando` das saídas.
3. `servidor.py`: `so_do_app` vale para toda rota `/api` (Host local sempre; Origin local quando presente).
4. `modelo` em `CAMPOS_APP`, `custos()` e `galho()`; `galho()` trata vídeo e página (`IMG/vN`) como pai de pedido.

## Limites conhecidos

- `GET /projects/*` (arquivos) segue sem checagem de Host.
- Um pedido que parte de uma página pende da imagem dela no servidor; no app pende da página. Apagar só o vídeo não leva esse pedido (direção segura: apaga de menos).
- `gerar_video.py` não ganhou o `finally`: interrompido, deixa vídeos `gerando` (saída: `neo.py erro`).
- A chave do OpenRouter continua sem definir neste clone.

## Itens abertos

- Itens 6 e 7 da auditoria (validação de `entradas`, erros menores do servidor) e todos os de frontend.
- Drift de docs.

## Prompt de retomada

```
Leia docs/handoff/2026-11-14-auditoria-inicial.md em /Users/felipemoulin/Projetos/neo-stitch e re-meça (git status, git log -3, uvx pytest tests -q, curl localhost:8730/api/projetos). Branch local correcoes-auditoria, sem push. Próximos: validação de entradas em criar_no/PATCH e gerar_video.py com IMG/vN; depois o frontend (Canvas.tsx:246-253, useProjeto.ts:18 e 66-70, useHistorico.ts:86-100), cada um com teste antes.
```
