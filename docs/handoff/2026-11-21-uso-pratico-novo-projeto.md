# Handoff 2026-11-21 — primeiro uso prático e aviso de nome no "Novo projeto"

> **Superado.** O estado e as decisões atuais estão em `docs/handoff/2026-11-22-portao-de-gasto-e-repo-publico.md`. Este arquivo é histórico: o repositório hoje é público, o patch em `rascunhos/` foi aposentado, e o prompt de retomada abaixo não vale mais.

Continua `docs/handoff/2026-11-15-entradas-video-revisao.md` (leia-o para o histórico das correções).

## Estado medido (2026-11-21)

| Item | Medição |
|---|---|
| Branch | `correcoes-auditoria`, `git status` limpo |
| HEAD local = `kratos/correcoes-auditoria` | `b76d56c` (antes deste handoff) |
| CI (`fbmoulin/kratos-stitch`) | `b76d56c completed success` |
| Testes | `python3 -m unittest discover -s tests` → 74 OK |
| `uvx ruff check ferramentas` | 21 avisos (linha de base do autor) |
| `oxlint` em `app/` | 9 avisos (linha de base) |
| Servidor local | PID 53379 em 127.0.0.1:8730, iniciado 15/11 03:23, serve o `app/dist` recompilado |
| Produção | não há; o app é só local |
| Gasto de API acumulado | US$ 0,167 (nenhuma geração nesta rodada) |

## O que aconteceu nesta rodada

- O usuário abriu http://localhost:8730/, descreveu um dashboard em "Novo projeto" e não conseguiu enviar.
- Causa provável (não vi a tela dele): o botão de criar fica desabilitado com o campo "Nome do projeto" vazio, e
  nada dizia isso. Evidência: nenhum projeto novo em `projects/`, `fila.jsonl` com as mesmas 3 linhas; reproduzido
  no navegador.
- Correção `b76d56c` (`app/src/Home.tsx`): com descrição e sem nome, aparece "Falta o nome do projeto, no campo de
  cima"; o `title` do botão explica. Conferido no navegador nos três estados.
- `rascunhos/correcoes-neo-stitch.patch` gerado de novo (15 arquivos, +1596/−163); `git apply --check` passa no `main`.

## Em aberto

1. O usuário ainda não confirmou que a causa era o nome vazio.
2. Pergunta sem resposta: trocar o título da tela de "Neo Stitch" para "Kratos Stitch" (e se isso fica fora do patch do autor).
3. Ninguém ouve a fila: enviar pelo app só grava em `fila.jsonl`. Gerar é pago e exige ok explícito do usuário a cada vez.
4. Itens menores não corrigidos, listados no handoff de 15/11 (rotação de vídeo, `.mudo.mp4` em SIGTERM,
   `catalogo_api` sem devolver o pedido, regra do botão Enviar do rascunho não conferida no navegador).
5. Licença do upstream: decisão do usuário; repositório segue privado.

## Regras que valem

- Push só para o remoto `kratos` (privado). Nunca para `origin` (repositório do autor). Sem issue/PR/branch para o autor.
- `rascunhos/` fica fora do git; se o código mudar, gerar o patch de novo com
  `git diff main..HEAD -- ferramentas app/src tests` e conferir que aplica no `main`.
- Geração paga só com ok explícito. Nunca imprimir nem ler chaves (`.env`).
- Mudança não trivial: spec → pre-mortem → teste → implementação → revisão independente, usando agentes e skills.

## Prompt de retomada

```
Leia docs/handoff/2026-11-21-uso-pratico-novo-projeto.md e o de 2026-11-15 em /Users/felipemoulin/Projetos/neo-stitch.
Meça de novo antes de confiar: git status, git log -3, gh run list --repo fbmoulin/kratos-stitch --limit 1,
python3 -m unittest discover -s tests, e se há servidor em 8730 (lsof). Estou usando o app na prática e vou
relatar o que encontrar; corrija só no meu clone (remoto kratos, privado), sem gerar nada pago sem o meu ok.
Pendente: confirmar se o "Novo projeto" agora funciona para mim e decidir o título da tela.
```
