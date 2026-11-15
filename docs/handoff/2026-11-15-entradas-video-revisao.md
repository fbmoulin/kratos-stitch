# Handoff 2026-11-15 — entradas de rascunho, vídeo, revisão e artefato para o autor

Continua `docs/handoff/2026-11-14-auditoria-inicial.md` (Atualizações 1 a 8).

## Estado medido

- Repo `/Users/felipemoulin/Projetos/neo-stitch`, branch `correcoes-auditoria`. Remotes: `kratos` (https://github.com/fbmoulin/kratos-stitch, privado) e `origin` (o do autor; nada foi enviado para lá).
- `git status --short` → vazio. A pasta `rascunhos/` existe e é ignorada só neste clone (`.git/info/exclude`).
- `python3 -m unittest discover -s tests` → `Ran 63 tests … OK`.
- `uvx ruff check ferramentas` → 21 avisos (a linha de base do código do autor). `oxlint` → 9 (linha de base).
- Produção: não há. O app é local; o servidor em http://localhost:8730/ foi reiniciado com o código de `bd8256e`.

## Commits desta etapa (todos em `kratos/correcoes-auditoria`)

| SHA | O quê |
|---|---|
| `9bbc189` | Restaurar devolve aos rascunhos as entradas que o apagar tirou (1ª versão, com manifesto no lote) |
| `bc21b34` | Vídeo: dimensões reais (ffprobe) e sem a trilha de áudio; ffmpeg no CI |
| `ed3a2bf` | Handoff (Atualização 8) |
| `bd8256e` | Correções da revisão: `entradas_antes` no rascunho, `enviar` sem entrada viva, vídeo sem imagem |
| (este) | Correções ao documento de pesquisa e este handoff |

## CI

- `bc21b34`: sucesso, `Ran 58 tests … OK` em ubuntu, nenhum pulado.
- O run do push deste handoff: conferir com `gh run list -R fbmoulin/kratos-stitch --limit 2` (o resultado está na mensagem final da sessão).

## Processo

- Os itens 2, 3 e 4 foram implementados **sem** pre-mortem nem agentes, por eu ter lido "ausência agentes e skills" como "sem". O usuário corrigiu: era "use". A revisão (skill `code-review`) rodou depois e achou três defeitos reais, corrigidos em `bd8256e` com teste antes:
  1. lotes restaurados fora de ordem trocavam a ordem das entradas (muda o pai do pedido);
  2. o `enviar` aceitava pedido sem texto cujas entradas não existem mais;
  3. `gerar_video.py` sem imagem de entrada saía com erro e deixava o pedido preso.
- A revisão olhou o documento de pesquisa (o alvo que passei foi o commit de docs), não o diff de código. Os achados foram cruzados à mão com a implementação; **o diff de `9bbc189..bd8256e` não teve uma revisão independente própria**.

## Verificado com geração real (autorizada)

```
TES-007: 1 vídeos · estimativa $0.05
x-ai/grok-imagine-video-1.5-lite         completed  $0.050 31.3s
nó    : largura 736, altura 400   (antes: 1376×768, as da imagem)
faixas: ['h264,video']            (antes: h264 + aac)
```

Gasto total em APIs nas duas sessões: US$ 0,167 (uma imagem e dois vídeos). O vídeo antigo `TES-006` não foi alterado.

## Artefato para o autor

- `rascunhos/correcoes-neo-stitch.patch` (14 arquivos, +1413/−158) e `rascunhos/LEIAME.md`. Fora do git; nenhuma issue, PR ou branch foi criada.
- Conferido: `git apply --check` limpo sobre `d6d0c86` (o `main` do autor) num clone temporário, e `Ran 63 tests … OK` depois de aplicado.
- O patch é uma fotografia de `bd8256e`: se o código mudar, gerar de novo com `git diff main..HEAD -- ferramentas app/src tests`.

## Itens abertos

- Licença: decisão do usuário de manter privado por enquanto (`docs/pesquisa/2026-11-15-itens-abertos.md`, item 1 e a seção de correções).
- Revisão independente do diff `9bbc189..bd8256e`.
- O usuário vai usar o app e relatar o que encontrar.
- Regra do projeto para a próxima mudança não trivial: spec → pre-mortem (skill `premortem-code:premortem-code`) → implementação com teste → revisão (skill `code-review`), usando agentes.

## Prompt de retomada

```
Leia docs/handoff/2026-11-15-entradas-video-revisao.md em /Users/felipemoulin/Projetos/neo-stitch e re-meça (git status, git log -5, python3 -m unittest discover -s tests, gh run list -R fbmoulin/kratos-stitch --limit 2, curl localhost:8730/api/projetos). Branch correcoes-auditoria, remote kratos; nunca enviar para origin; geração real só com o meu ok. Use agentes e skills: rode a skill code-review sobre o diff 81e2da5..HEAD restrito a ferramentas/ e tests/, e para qualquer mudança nova siga spec → pre-mortem → teste → implementação → revisão. Trate o que eu relatar do uso do app.
```

---

# Atualização (mesma sessão) — revisão independente do código e correções

## Estado medido

- Branch `correcoes-auditoria`; código em `3040272`. `git status --short` → vazio.
- `python3 -m unittest discover -s tests` → `Ran 74 tests … OK`. `ruff check ferramentas` → 21 (linha de base). `npm --prefix app run build` ok; `oxlint` → 9 (linha de base).
- Servidor local reiniciado com `3040272`. Produção: não há.

## O que a revisão independente achou (agente, sobre `git diff 81e2da5..HEAD -- ferramentas tests`)

Oito defeitos, todos reproduzidos por ela ou por teste novo, todos corrigidos em `3040272` com o teste antes:

1. Um segundo apagar não era registrado no rascunho: o ⌘Z perdia a entrada.
2. Desfazer em pilha trocava a ordem e o pai do rascunho.
3. Com uma página (`IMG/vN`) nas entradas, a marca `entradas_antes` nunca saía.
4. Todo restaurar regravava todos os rascunhos com a marca, mesmo sem mudança (mexia no `rev` do projeto).
5. `sondar` pegava a primeira faixa de vídeo, que pode ser a capa embutida.
6. `test_video_sem_audio_nao_e_regravado` não conseguia falhar (o `self.fail` era engolido pelo `except`).
7. O app habilitava Enviar com entradas mortas, e o servidor aceitava pedido de vídeo sem imagem viva.
8. (anterior a esta etapa) Download que falha depois do job concluído deixava o nó com `arquivo` inexistente e o pedido `concluido`.

Mutações conferidas depois da correção (cada uma derruba ao menos um teste): tirar áudio sempre; regravar rascunho sem mudança; ignorar a vizinha seguinte ao reinserir; não tratar página como existente; aceitar vídeo sem entrada viva; não filtrar a capa embutida; aceitar vídeo "pronto" sem arquivo.

## Não corrigido (apontado como menor)

- Vídeo com rotação nos metadados fica com as dimensões codificadas, não as de exibição.
- SIGTERM no meio de `tirar_audio` pode deixar um `.mudo.mp4` temporário.
- `catalogo_api` falhando (rede) não devolve o pedido.
- `entradas_antes` fica em pedidos que deram erro (inofensivo).
- Não coberto pela revisão: o arquivo real do provedor com as funções novas depois desta correção (o `TES-008` foi gerado antes dela), `arvore()` do app além da regra do pai, e concorrência entre servidor e gerador durante um restaurar.

## Artefato

`rascunhos/correcoes-neo-stitch.patch` foi gerado de novo a partir de `3040272`; aplica limpo sobre `d6d0c86`, com `Ran 74 tests … OK` e o build do app passando num clone temporário.

## Prompt de retomada

```
Leia docs/handoff/2026-11-15-entradas-video-revisao.md (inclusive a Atualização) em /Users/felipemoulin/Projetos/neo-stitch e re-meça (git status, git log -5, python3 -m unittest discover -s tests, gh run list -R fbmoulin/kratos-stitch --limit 2, curl localhost:8730/api/projetos). Branch correcoes-auditoria, remote kratos; nunca enviar para origin; geração real só com o meu ok. Use agentes e skills: spec → pre-mortem (premortem-code) → teste → implementação → revisão independente do diff de código. Trate o que eu relatar do uso do app; se o código mudar, gere de novo rascunhos/correcoes-neo-stitch.patch.
```
