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
