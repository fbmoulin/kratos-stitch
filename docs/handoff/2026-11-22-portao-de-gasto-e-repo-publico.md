# Handoff 2026-11-22 — repositório público, portão de gasto e fila sem ouvinte

Continua `docs/handoff/2026-11-21-uso-pratico-novo-projeto.md`.

## Estado medido (2026-11-22)

| Item | Medição |
|---|---|
| Branch | `correcoes-auditoria`; HEAD local = `kratos/correcoes-auditoria` (o SHA deste handoff está no `git log -1`) |
| Código | `ea778ee` |
| Testes | `python3 -m unittest discover -s tests` → 92 OK (eram 74) |
| `uvx ruff check ferramentas` | 21 (linha de base) |
| `oxlint` em `app/` | 9 (linha de base) |
| CI (`fbmoulin/kratos-stitch`) | `success` em `0c77e5a`, `4723564`, `d384d7a`, `ef7c79d`; o de `ea778ee` e o deste handoff: conferir com `gh run list` |
| Visibilidade | `fbmoulin/kratos-stitch` é **público** desde 2026-11-22; branch padrão `main` (o código original) |
| Servidor local | 127.0.0.1:8730, reiniciado com `ea778ee` |
| Produção | não há; o app é só local |
| Gasto de API acumulado | US$ 0,167 (nenhuma geração nesta sessão) |

## Decisões do dono nesta sessão

- O autor do Neo Stitch é professor de um curso da ASIMOV Academy que o dono faz, e liberou o uso do repositório como
  material do curso. O item "licença" está encerrado (nota em `docs/pesquisa/2026-11-15-itens-abertos.md`).
- O repositório passou a público. Antes: histórico varrido por chaves (OpenRouter, Anthropic, GitHub, AWS, Google), sem
  ocorrência; `.env`, `projects/` e `fila.jsonl` nunca foram commitados.
- Nada é enviado ao autor: push só para `kratos`, sem issue, PR ou branch em `origin`.
- O patch `rascunhos/correcoes-neo-stitch.patch` foi aposentado: não é mais regenerado.
- O "ok" para gastar é dado no chat, a cada geração.

## Commits

| SHA | O quê |
|---|---|
| `0c77e5a` | Pesquisa: a seção da licença está superada pela autorização do autor |
| `4723564` | Vídeo: o pedido volta como erro quando o catálogo do OpenRouter falha |
| `d384d7a` | Portão de gasto, aviso de fila sem ouvinte, cancelar envio, estimativa no rascunho de imagem |
| `ef7c79d` | Vídeo: dimensões de exibição quando o arquivo traz rotação |
| `ea778ee` | Portão: correções da revisão independente do `d384d7a` |

Spec e pre-mortem: `docs/specs/2026-11-22-fila-sem-ouvinte-e-portao-de-gasto.md` (rev2, veredito REFINE incorporado).

## Como ficou o fluxo de um pedido

1. Enviar no app grava o pedido como `enviado`. Sem ouvinte, a pílula do topo diz "Claude não está ouvindo" e o pedido
   mostra "fila · ninguém ouvindo", com um botão de cancelar (volta a rascunho).
2. O agente pega o pedido e roda o gerador. Com os tetos por pedido em zero, o gerador sai com código 3 e a estimativa,
   e o pedido volta para a fila como "aguarda seu ok · ≈ $X".
3. O agente pergunta no chat. Com o sim: `neo.py pegar` de novo e o gerador com `--confirmado`. Com o não:
   `neo.py erro <id> "Não autorizado"`.

## Processo

- Item 1: teste antes do conserto, revisão independente (aprovou; quatro mutações sobreviviam, teste endurecido).
- Itens 2 e 3: spec → pre-mortem (REFINE) → rev2 → implementação com testes → conferência no navegador → revisão
  independente do `d384d7a`, que achou três defeitos reais, corrigidos em `ea778ee` com teste e mutação.
- O conserto do `ea778ee` **não teve uma segunda revisão independente**; as nove mutações que rodei sobre ele morreram.
- A conferência no navegador foi feita antes do `ea778ee`. Depois dele não reabri o navegador (a mudança foi no servidor
  e nos geradores, coberta por teste).

## Em aberto

1. O dono ainda não confirmou que o "Novo projeto" funciona para ele.
2. Trocar o título da tela para "Kratos Stitch": sem resposta. São três linhas (`app/index.html:10`, `app/src/App.tsx:20`,
   `app/src/Home.tsx:63`) e um rebuild.
3. Ninguém ouve a fila por conta própria: o ouvinte só existe numa sessão do Claude Code aberta nesta pasta, depois de
   "ouça o canvas", e o Monitor cai em 30 minutos.
4. Limites conhecidos do portão, na spec: projeto antigo ou com tetos alterados por PATCH mantém os seus; `neo.py pegar`
   num pedido que está gerando; pedido `trabalhando` com gerador morto.
5. Achados da revisão do item 1 que ficaram fora: o mesmo travamento em três pontos adiante do gerador de vídeo
   (`plano` já foi coberto; restam `B.medidas` sem `sips` e `catalogo[...]['name']`), Ctrl-C ou SIGTERM durante a leitura
   do catálogo, e a chave do OpenRouter podendo aparecer em `pedido['erro']` se vier do ambiente com quebra de linha.
6. A barra do rascunho de imagem já transbordava o cartão antes desta sessão (313 px em 278); não corrigido.
7. Não consertados por decisão: `.mudo.mp4` órfão em SIGTERM e `entradas_antes` em pedido com erro.
8. O branch padrão do repositório público é `main`, o código original; as correções estão em `correcoes-auditoria`.
9. `fila.jsonl` tem duas linhas do `TES-010`, pedido de teste criado, enviado, cancelado e apagado nesta sessão.

## Regras que valem

- Push só para `kratos`. Nunca para `origin`.
- Geração paga só com ok explícito no chat, por pedido. Nunca imprimir nem ler chaves (`.env`).
- Mudança não trivial: spec → pre-mortem → teste → implementação → revisão independente, usando agentes e skills.

## Prompt de retomada

```
Leia docs/handoff/2026-11-22-portao-de-gasto-e-repo-publico.md em /Users/felipemoulin/Projetos/neo-stitch.
Meça de novo antes de confiar: git status, git log -3, gh run list -R fbmoulin/kratos-stitch --limit 3,
python3 -m unittest discover -s tests, gh repo view fbmoulin/kratos-stitch --json visibility, e se há servidor em 8730 (lsof).
O repositório é público; push só para o remoto kratos, nada para origin. Geração paga só com o meu ok no chat, por pedido.
Pendente: confirmar se o "Novo projeto" funciona para mim, decidir o título "Kratos Stitch", e os itens 4 a 6 do handoff.
```

---

# Atualização (mesma data) — uso real no projeto `brain` e três funcionalidades novas

## Estado medido

| Item | Medição |
|---|---|
| Código | `d24826f` em `kratos/correcoes-auditoria` |
| Testes | 103 OK; `ruff check ferramentas` 21; `oxlint` 9 |
| CI | `success` em `29b916d` e `a6c51ed`; o de `d24826f` e o deste handoff: conferir com `gh run list` |
| Servidor local | 127.0.0.1:8730, reiniciado com `d24826f` |
| Gasto de API | projeto `brain`: US$ 1,30 em 2026-11-22 (15 imagens e 1 vídeo); `teste-e2e`: US$ 0,167, sem mudança |

## O que o dono fez e o que foi atendido

- Criou o projeto `brain` e mandou pedidos sem ninguém ouvindo. O ouvinte (`ferramentas/ouvir.sh` pelo Monitor) foi ligado
  nesta sessão e re-armado a cada 30 minutos.
- Gerados com ok no chat: `BRA-005` (3 imagens), `BRA-006` (6), `BRA-017` (mix, 3), `BRA-021` (3), `BRA-031` (mix com a
  imagem e o vídeo dele, 3) e o vídeo `BRA-041` (Grok Imagine 1.5 Lite, 6 s, US$ 0,19).
- Recusados por ele e devolvidos com `neo.py erro`: `BRA-004`, `BRA-026`, `BRA-027`, `BRA-037` (enviados sem texto).
- Referências postas à mão no canvas a partir de `~/Downloads`: `BRA-028` (imagem dele), `BRA-029` e `BRA-030` (quadros do
  vídeo dele).

## Funcionalidades novas (ratificadas pelo dono; spec em `docs/specs/2026-11-22-comentario-pedido-e-video-de-referencia.md`)

| SHA | O quê |
|---|---|
| `29b916d` | Servidor: vídeo próprio como referência (capa, arquivo, um quadro por segundo até 16) e limite de 200 MB |
| `a6c51ed` | App: vídeo no canvas e no visualizador, comentário que vira pedido (`⌘↵`), anexo no comentário |
| `d24826f` | Correções da revisão independente do `a6c51ed` |

Processo: spec → pre-mortem (REFINE) → rev2 → testes e implementação → navegador → revisão independente (achou 2
bloqueantes: vídeo válido recusado e pedido duplicado) → correção com teste e mutação. **O `d24826f` não teve segunda
revisão independente.** No navegador foram conferidos: soltar um mp4, o player da referência, `⌘↵` com anexo, e três
`⌘↵` seguidos criando um pedido só. Não conferidos no navegador depois do `d24826f`: o upload de vídeo e o aviso de
arquivo não aceito.

## Em aberto (além da lista anterior)

1. Achados da revisão não corrigidos: `Transfer-Encoding: chunked` sem `Content-Length` (anterior a esta sessão); vários
   vídeos soltos de uma vez sobrepõem as grades de quadros; soltar um arquivo sobre o visualizador, fora da caixa de
   comentário, sobe pelo canvas por trás (anterior); vídeo de horas pode segurar a requisição por muitos minutos; `.mov`
   sem cache longo.
2. Mutações que a revisão viu sobreviver e ficaram sem teste: troca de largura e altura na rotação do vídeo enviado, e
   webm sem duração.
3. O número máximo de imagens de referência que o modelo aceita num pedido não foi medido; o teto de 16 quadros é escolha
   da spec.
4. O custo por imagem variou de US$ 0,03 a US$ 0,15 no mesmo modelo e resolução, sem causa identificada; a estimativa do
   portão (US$ 0,14 por imagem) superestimou em quase todos os casos.
5. No projeto `brain` ficaram rascunhos vazios (`BRA-016`, `BRA-025`, `BRA-035`, `BRA-036`) criados pelo dono.
6. Título "Kratos Stitch": ainda sem resposta.

## Prompt de retomada

```
Leia docs/handoff/2026-11-22-portao-de-gasto-e-repo-publico.md inteiro (inclusive a Atualização) em
/Users/felipemoulin/Projetos/neo-stitch. Meça antes de confiar: git status, git log -3,
gh run list -R fbmoulin/kratos-stitch --limit 3, python3 -m unittest discover -s tests, lsof na 8730.
Se eu for usar o canvas: suba o servidor (uv run ferramentas/servidor.py), ligue o ouvinte da fila pelo Monitor
(ferramentas/ouvir.sh, re-armar a cada 30 min) e rode neo.py pendentes. Geração paga só com o meu ok no chat, por
pedido, com a estimativa. Push só para o remoto kratos.
```
