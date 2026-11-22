# Handoff 2026-11-14 — clone, instalação e auditoria inicial

> **Superado.** O estado e as decisões atuais estão em `docs/handoff/2026-11-22-portao-de-gasto-e-repo-publico.md`. Este arquivo é histórico: o repositório hoje é público, o patch em `rascunhos/` foi aposentado, e o prompt de retomada abaixo não vale mais.

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

---

# Atualização 2 (mesma sessão) — entradas, erros do servidor, frontend e revisão de código

## Estado medido

- Branch `correcoes-auditoria`, enviada para o remote `kratos` (https://github.com/fbmoulin/kratos-stitch, privado). `origin` (o repo do autor) não recebeu nada. Sem CI no repositório.
- `python3 -m unittest discover -s tests` → 31 testes, OK. `ruff check ferramentas` → 21 avisos (linha de base). `npm --prefix app run build` ok; `oxlint` 9 avisos (linha de base).
- Chaves: `/api/config` mostra `OPENROUTER_API_KEY` e `FAL_KEY` com origem `.env` (valores não lidos). Nenhuma geração paga foi feita nesta sessão.
- Servidor real reiniciado com o código novo em http://localhost:8730/.

## O que entrou

- Backend: criar/mudar pedido validam `entradas` (imagem, referência, página com print; o que o pedido já tinha fica); corpo JSON não-objeto → 422; faixa fora do arquivo → 416; HEAD → 405; `travado()` não cria pasta de projeto inexistente; `gerar_video.py` aceita página como entrada.
- Frontend (`app/src`): erro de ação fica até o clique; erro de rede some na leitura seguinte; ⌘Z recusado não diz "Desfeito"; atalhos travados com visualizador/modal aberto; nós do React Flow reaproveitados; rascunho de comentário e erro da Home.
- Da revisão de código (10 achados, 9 corrigidos): sem chave o pedido pego volta como `erro`; placeholder apagado no meio não prende o pedido; imagem que chega depois de marcada como interrompida perde o `erro`; `gerar_video.py` ganhou o mesmo `finally`; PATCH de `entradas` mantém o que já existia; posições recusadas voltam ao disco; passo de desfazer recusado duas vezes sai da pilha; prefixo explícito repetido é recusado; `/projects/*` também recusa Host/Origin de fora; `galho()` voltou a NÃO contar página como pai (um pedido de design system não sai junto com a imagem).

## Verificado no navegador (cópia isolada, porta 8731)

- Mudança vinda do servidor: 10 nós montados antes e depois, os mesmos elementos, nenhum escondido.
- PATCH recusado: o toast continua depois de 5 s e some no clique.
- ⌘Z com o servidor recusando: sem "Desfeito"; na 2ª recusa o passo sai e o ⌘Z seguinte desfaz o passo anterior.
- Com Config ou o visualizador aberto: `D`, `1`, `2`, ⌘A, ⌘1 e ⌘Z não mudam nada.
- Não medi o antes/depois de desempenho; o ganho de re-medição vem da leitura do código do xyflow.

## Limites conhecidos

- SIGTERM em `gerar.py`/`gerar_video.py` pula o `finally` (saída: `neo.py erro <pedido>`).
- Um lote de desfazer que falha no meio fica meio desfeito.
- Nó fora da tela cujo conteúdo mudou só é re-medido quando volta à vista.
- Colar imagem com o visualizador aberto ainda cria referência.

## Itens abertos

- Drift de docs (README `F`/Favorita, `impl.py:106` "seção 4", skill `video2html` ausente, Chrome nos requisitos).
- Divisão do contexto/memo dos nós; `emLote` capturando ações alheias; bundle único de 515 kB.
- Teste de ponta a ponta com geração real (gasta dinheiro: só com o seu ok).

## Prompt de retomada

```
Leia docs/handoff/2026-11-14-auditoria-inicial.md em /Users/felipemoulin/Projetos/neo-stitch e re-meça (git status, git log -5, python3 -m unittest discover -s tests, curl localhost:8730/api/projetos, git ls-remote kratos). Branch correcoes-auditoria, remote kratos (privado); nunca enviar para origin. Próximos: drift de docs e, com o meu ok, um teste de ponta a ponta com uma geração real barata.
```

---

# Atualização 3 (mesma sessão) — teste real de ponta a ponta e docs

## Teste real (autorizado pelo usuário)

- Projeto `teste-e2e` (prefixo TES) criado pela API do servidor real; pedido TES-003 criado e enviado pela API (linha na `fila.jsonl`), `neo.py pegar`, `gerar.py --prompt …` com o modelo `flash` (`google/gemini-3.1-flash-image`).
- Saída: `TES-004 ok 0.0672185` · `TES-003: 1/1 imagens · $0.067`, exit 0. Pedido `concluido`; imagem 1376×768 com arquivo, thumb, custo e 10,5 s; `/projects/teste-e2e/images/TES-004.png` → 200 `image/png` 827 kB; custos do projeto `{total: 0.0672, hoje: 0.0672}`.
- Custo total da sessão em APIs: US$ 0,067. O projeto `teste-e2e` ficou em `projects/` (fora do git).
- A tabela `MODELOS` em `base.py` estima o `flash` em $0,04; a cobrança real foi $0,067. Não alterei a tabela (um ponto de dado só).
- Não testado com geração real: vídeo (`gerar_video.py`), várias referências, modelos 3D.

## Docs atualizados

- `README.md`: requisito do Chrome; atalhos reais (`D`, `⌫`, `⌘A` = pinados; sai `F`/`A`); skills `img2html`/`video2html` não vêm no repo; como soltar pedido preso; seções "Só local" e "Testes"; `tests/` na estrutura.
- `AGENTS.md`, `CLAUDE.md`, `.claude/skills/neo-stitch/SKILL.md`: guarda de execução dupla e `neo.py erro`; rodar os testes; regra de `so_do_app` e de tipo de nó novo.
- `specs.md`: nota datada da auditoria. `ferramentas/impl.py:106`: "seção 4" → "seção 5".

## Itens abertos

- Divisão do contexto/memo dos nós; `emLote` capturando ações alheias; bundle único de 515 kB.
- SIGTERM nos geradores pula o `finally`.
- Conferir o preço do `flash` na tabela `MODELOS`.

## Prompt de retomada

```
Leia docs/handoff/2026-11-14-auditoria-inicial.md em /Users/felipemoulin/Projetos/neo-stitch e re-meça (git status, git log -6, python3 -m unittest discover -s tests, curl localhost:8730/api/projetos, git ls-remote kratos). Branch correcoes-auditoria, remote kratos (privado); nunca enviar para origin. Geração real só com o meu ok. Próximos: desempenho do canvas (contexto/memo dos nós) e o preço do flash em MODELOS.
```

---

# Atualização 4 (2026-11-15) — nome no README, análise do que está em aberto e plano

## Feito

- `README.md`: o projeto passa a se chamar Kratos Stitch, com o clone apontando para `fbmoulin/kratos-stitch` e o rodapé creditando o Neo Stitch de Rodrigo Tadewald. Nomes de arquivos e da skill (`neo.py`, `.claude/skills/neo-stitch`) não mudaram.

## Medido

- Canvas com 542 nós (cópia isolada, Chrome): no máximo 38 nós montados (o React Flow só desenha o visível); pior quadro 14 ms e nenhuma tarefa longa (>50 ms) em: poll com mudança, `D` num nó, ⌘1 (30 PATCHes) e ⌘Z. Carga da página: 299 ms.
- Preço das imagens no OpenRouter é por token de saída (`google/gemini-3.1-flash-image`: $0,00006/token), não por imagem: a cobrança de $0,067 bate com ~1.120 tokens. A tabela fixa `MODELOS` é só aproximação.
- `emLote`: 8 usos; só 2 esperam o servidor em série (apagar vários, `Canvas.tsx:144`; distribuir, `Canvas.tsx:668`) e podem capturar ações alheias.

## Plano (nada implementado)

1. Pedido preso que se cura sozinho: o gerador grava o PID no pedido; guarda e servidor tratam `trabalhando` com PID morto como interrompido. Mais um handler de SIGTERM. Cobre SIGKILL e queda da máquina.
2. Estimativa de custo pelo histórico: mediana do custo real do modelo no projeto, com a tabela como reserva; corrigir o `flash`.
3. Colar com o visualizador aberto: usar a mesma trava `coberto`.
4. CI no `kratos-stitch`: testes, build e lint a cada push.
5. Rotas em lote (apagar vários, mudar vários): um passo de desfazer, uma recarga; resolve o `emLote` e o lote meio desfeito.
6. Teste real de vídeo (precisa de ok: ~$0,19 com o modelo mais barato).

Descartados com evidência: dividir o contexto/memo dos nós e dividir o bundle (sem ganho medido).
Decisão do usuário: o repo de origem não tem licença.

## Prompt de retomada

```
Leia docs/handoff/2026-11-14-auditoria-inicial.md (Atualização 4) em /Users/felipemoulin/Projetos/neo-stitch e re-meça (git status, git log -3, python3 -m unittest discover -s tests, git ls-remote kratos). Branch correcoes-auditoria, remote kratos; nunca enviar para origin. Implemente o plano na ordem 1, 2, 3, com teste antes de cada um; geração real só com o meu ok.
```

---

# Atualização 5 (2026-11-15) — teste real de vídeo (item 6 do plano, autorizado)

- Pedido de vídeo TES-005 criado e enviado pela API do servidor real, saindo da imagem TES-004; modelo `x-ai/grok-imagine-video-1.5-lite`, 2 s, 480p; `neo.py pegar` e `gerar_video.py`.
- Saída: `estimativa $0.05` · `completed $0.050 30.8s` · `TES-005: 1/1 vídeos · $0.05 · TES-006`, exit 0.
- Conferido: pedido `concluido`; nó de vídeo com arquivo, capa, custo; `avancos` liga TES-004 → TES-006; `/projects/teste-e2e/videos/TES-006.mp4` → 200 `video/mp4` 348 kB; `Range: bytes=0-99` → 206 `bytes 0-99/347708`; ffprobe: h264 736×400, 2,04 s. Quadros 0 e 40: layout e textos intactos, o segundo checkbox marcado como pedido.
- Estimativa ($0,05) igual à cobrança ($0,050). Gasto total da sessão em APIs: US$ 0,117.
- Observações (não corrigidas): o nó guarda `largura`/`altura` da imagem de origem (1376×768), não do vídeo (736×400); o arquivo veio com trilha de áudio.
- Plano restante: itens 1 a 5 da Atualização 4.

---

# Atualização 6 (2026-11-15) — spec, pre-mortem e a fase 2 de robustez

## Estado medido

- Spec: `docs/specs/2026-11-15-robustez-fase-2.md` (com a revisão pós pre-mortem e a tabela de resultado). Pre-mortem: `.premortems/PREMORTEM-2026-11-15T01-30-00.md`, veredito REFINE (2 `high` locais, 3 `medium`), todos incorporados antes de implementar.
- Os cinco itens estão implementados e enviados para `kratos/correcoes-auditoria`: CI (`0744be2`), pedido preso que se cura + estimativa de custo + colar (`9d745fc`), mudar e apagar em lote (`cd44af7`).
- `python3 -m unittest discover -s tests` → 46 testes, OK (com e sem o `sips`). `ruff check ferramentas` → 21 (linha de base). `oxlint` → 9 (linha de base). Build ok.
- CI: workflow `CI` em `ubuntu-latest`; o status de cada push está em `gh run list -R fbmoulin/kratos-stitch`.
- Nenhuma geração paga nesta etapa. Gasto da sessão em APIs: US$ 0,117.

## Verificado no navegador (cópia isolada)

- Colar com o visualizador aberto: 0 referências criadas; fechado: 1.
- ⌘1 com 6 galhos: 1 `PATCH /nos` + 1 recarga; ⌘Z e ⌘⇧Z idem.
- Realinhar com um cartão de página movido: zera nós e página; ⌘Z devolve os dois.
- Apagar + ⌘Z pela rota nova: só com um nó (o ⌘+clique por script não soma à seleção).

## Não verificado

- Apagar vários nós pelo app (coberto só no servidor).
- `gerar_video.py` com SIGTERM; o varredor chamando `soltar_orfaos` a cada 60 s.

## Itens abertos

- Rascunhos perdem as `entradas` apagadas e o desfazer não as devolve (bug anterior, registrado no pre-mortem).
- O cartão do vídeo guarda as dimensões da imagem de origem; o vídeo vem com trilha de áudio.
- Licença do repositório de origem (decisão do usuário).

## Prompt de retomada

```
Leia docs/handoff/2026-11-14-auditoria-inicial.md (Atualização 6) e docs/specs/2026-11-15-robustez-fase-2.md em /Users/felipemoulin/Projetos/neo-stitch e re-meça (git status, git log -5, python3 -m unittest discover -s tests, gh run list -R fbmoulin/kratos-stitch --limit 3, curl localhost:8730/api/projetos). Branch correcoes-auditoria, remote kratos; nunca enviar para origin; geração real só com o meu ok. Próximos: testar no app apagar vários nós com ⌘Z; devolver as entradas dos rascunhos ao restaurar.
```

---

# Atualização 7 (2026-11-15) — pendências verificadas e pesquisa dos itens em aberto

- Verificado: apagar vários nós pelo app (2 cartões, `POST /nos/apagar` único, ⌘Z/⌘⇧Z/⌘Z corretos); `gerar_video.py` com SIGTERM (teste novo); o varredor soltando órfãos (teste novo, com mutação). `python3 -m unittest discover -s tests` → 48, OK.
- Pesquisa com fontes e opções: `docs/pesquisa/2026-11-15-itens-abertos.md`. Recomendações: licença → pedir ao autor e manter privado enquanto isso; entradas de rascunho → manifesto no lote da lixeira; áudio → `ffmpeg -an -c copy` depois do download; dimensões → `ffprobe` depois do download.
- Nada da pesquisa foi implementado. O usuário vai testar o app na prática.

## Prompt de retomada

```
Leia docs/handoff/2026-11-14-auditoria-inicial.md (Atualização 7) e docs/pesquisa/2026-11-15-itens-abertos.md em /Users/felipemoulin/Projetos/neo-stitch e re-meça (git status, git log -3, python3 -m unittest discover -s tests, gh run list -R fbmoulin/kratos-stitch --limit 2). Branch correcoes-auditoria, remote kratos; nunca enviar para origin; geração real só com o meu ok. Implemente o que eu aprovar da pesquisa (itens 2, 3 e 4), com teste antes, e trate o que eu relatar do uso do app.
```

---

# Atualização 8 (2026-11-15) — itens 2, 3 e 4 da pesquisa implementados; rascunho de PR

- Entradas de rascunho: o lote da lixeira guarda `rascunhos.json` e o restaurar reaplica na ordem (`9bbc189`, testes `EntradasDeRascunho`).
- Vídeo: `sondar()` (ffprobe) grava as dimensões reais no nó e `tirar_audio()` remove a trilha sem recodificar (`bc21b34`, testes `VideoBaixado`). Conferido numa cópia do arquivo real do OpenRouter: 736×400 com áudio → 736×400 sem áudio, duração 2,04 s igual, 347 708 → 286 845 bytes.
- `python3 -m unittest discover -s tests` → 58, OK. `ruff check ferramentas` → 21 (linha de base). CI `bc21b34`: sucesso, 58 testes rodados no Linux (o ffmpeg é instalado no job).
- Não verificado com geração real: um vídeo novo saindo já sem áudio e com as dimensões certas (o `TES-006` existente não foi alterado).
- Licença: decisão do usuário de manter privado. Rascunho de issue e de 4 PRs para o autor em `rascunhos/PR-para-o-autor.md`, fora do git (`.git/info/exclude`); nada foi enviado ao repositório dele e nenhuma branch foi criada.
- Feito sem agentes nem skills, a pedido.

## Prompt de retomada

```
Leia docs/handoff/2026-11-14-auditoria-inicial.md (Atualização 8) em /Users/felipemoulin/Projetos/neo-stitch e re-meça (git status, git log -3, python3 -m unittest discover -s tests, gh run list -R fbmoulin/kratos-stitch --limit 2, curl localhost:8730/api/projetos). Branch correcoes-auditoria, remote kratos; nunca enviar para origin; geração real só com o meu ok. O rascunho do PR está em rascunhos/PR-para-o-autor.md (fora do git). Trate o que eu relatar do uso do app.
```
