# HANDOFF — Kratos Stitch (clone do Neo Stitch): repositório público, portão de gasto, vídeo de referência (2026-11-22)

> O contexto foi limpo. Este arquivo é a fonte e substitui os handoffs de 14, 15 e 21/11 (que ficam como histórico).
> Tudo abaixo foi medido em 2026-11-22, exceto onde marcado. Números são pistas datadas: confirme por `git` e pela suíte.

## Estado

- **Repo / branch:** `/Users/felipemoulin/Projetos/neo-stitch` @ `correcoes-auditoria`. ⚠️ O branch padrão do remoto é
  `main`, que é o código original do autor; todo o trabalho está em `correcoes-auditoria`.
- **Remotos:** `kratos` = `fbmoulin/kratos-stitch`, **público** desde 2026-11-22 (é para onde se envia); `origin` = o
  repositório do autor (nunca enviar).
- **HEAD do código:** `b6673db` (o commit deste handoff vem depois; veja `git log -1`). Working tree limpo, remoto em dia.
- **Testes:** `python3 -m unittest discover -s tests` → 103 OK. `uvx ruff check ferramentas` → 21 e `oxlint` em `app/` → 9
  (as duas são linhas de base do código do autor, não zero).
- **CI:** `success` até `b4bca59`; o de `b6673db` estava em andamento quando este arquivo foi escrito.
- **Produção:** não há. O app é local: `uv run ferramentas/servidor.py` → http://localhost:8730/. O servidor desta sessão
  morre com ela.
- **Gasto de API:** projeto `brain` US$ 1,30 (15 imagens e 1 vídeo, tudo em 22/11); `teste-e2e` US$ 0,167.
- **Fila:** `neo.py pendentes` → nada pendente.

## 🔒 Decisões fechadas — NÃO REABRIR

- **Licença está resolvida.** O autor é professor de um curso da ASIMOV Academy que o dono faz e liberou o uso do
  repositório como material do curso. Descartado: pedir licença por escrito (a recomendação antiga de
  `docs/pesquisa/2026-11-15-itens-abertos.md`, que agora traz a nota de superado).
- **O repositório é público por decisão do dono.** Antes de publicar, o histórico foi varrido por chaves (OpenRouter,
  Anthropic, GitHub, AWS, Google): nenhuma. Não voltar a privado sem ele pedir.
- **Nada é enviado ao autor.** Sem push para `origin`, sem issue, PR ou branch lá. Motivo do dono: o autor o segue no
  GitHub e o repositório é público. Descartado junto: o patch `rascunhos/correcoes-neo-stitch.patch`, **aposentado**, não
  é mais regenerado (os handoffs antigos mandam regenerar: ignore).
- **O "ok" para gastar é no chat, por pedido, com a estimativa.** Descartado: tratar o clique em Enviar como ok, e um
  trabalhador automático no servidor (um clique viraria cobrança). Por isso os tetos por pedido são **zero**
  (`base.TETOS`): todo gerador para na saída 3 e o pedido volta à fila como "aguarda seu ok".
- **Mensagens curtas do dono no chat ("prossiga", "sugestão", "ok para os pedidos pendentes") valem como o ok** para o
  que acabou de ser apresentado com valor. Pedido enviado **sem texto** não é pedido de variações: ele recusou os três
  que mandou assim (queria vídeo). Pergunte o que ele quer antes de estimar.
- **Cancelar envio volta a rascunho** (ou a `erro` se o pedido já tinha saídas) e grava `cancelado_em`, que faz o
  `neo.py pegar` recusar até um novo envio. Motivo: a linha antiga fica na `fila.jsonl` e um agente travaria o rascunho
  que ele está editando.
- **Vídeo de referência é um nó `referencia` cujo `arquivo` é a capa** (jpg), com o mp4 em `video`. Motivo: tudo que já
  lê referências segue lendo uma imagem. Descartado: tipo de nó novo, e expandir o vídeo em quadros dentro do gerador.
- **Quadros: um por segundo, de 1 a 16, cada um um nó de referência.** O dono pediu "o máximo aplicável"; 16 é escolha
  da spec porque extrair é grátis e ligar custa. Um vídeo anexado a um comentário entra no pedido só com a capa.
- **Não consertar:** `.mudo.mp4` órfão em SIGTERM (janela de menos de 1 s, sem leitor) e `entradas_antes` em pedido com
  erro (campo morto). Medidos e julgados sem valor.
- **Título da tela é "Kratos Stitch"** só na aba e na página inicial. A skill `neo-stitch`, as chaves `neo:*` do
  localStorage, o `X-Title` enviado ao OpenRouter e o crédito ao original ficam como estão.

## ❌ Tentado e descartado

- **Estimativa do rascunho de imagem dentro da barra do cartão** → a barra passa de 278 px e a estimativa quebra em duas
  linhas; ficou numa linha própria abaixo. Encolher os seletores deixava o modelo com 33 px.
- **Testar "imagem disfarçada de vídeo" com um PNG** → o PNG já cai na checagem de duração e o teste não exercita a de
  formato; o caso que a exercita é um GIF animado.
- **Extração de quadros "tudo ou nada"** → recusava vídeos reais (áudio mais longo que a imagem, 1 quadro por segundo).
  Hoje o instante sem quadro é pulado e só a falta total recusa.
- **`pop('aguarda_ok')` no enviar tirado como "inalcançável"** → era alcançável por `devolver_pedido`; voltou, com teste.
- **Claude in Chrome para conferir o app** → a extensão desconectou no meio da sessão. O Playwright MCP
  (`mcp__plugin_playwright_playwright__*`) funcionou; ele só grava arquivo dentro de `~`.

## ▶ Próxima ação concreta

1. Se o dono for usar o canvas: `uv run ferramentas/servidor.py` em segundo plano, ligar o ouvinte com a ferramenta
   Monitor (`/Users/felipemoulin/Projetos/neo-stitch/ferramentas/ouvir.sh`, `timeout_ms: 1800000`, re-armar a cada
   expiração) e rodar `uv run ferramentas/neo.py pendentes`. O roteiro de cada evento está em
   `.claude/skills/neo-stitch/SKILL.md`.
2. Senão, o item 1 de "Em aberto" é o de maior valor.

## ⚠️ Armadilhas ativas

- **A skill `neo-stitch` é de projeto:** só carrega numa sessão aberta em `/Users/felipemoulin/Projetos/neo-stitch`. Em
  outra pasta, leia o `SKILL.md` à mão.
- **O Monitor expira em 30 minutos** e `tail -n0` não relê linhas antigas: ao religar, rode `neo.py pendentes`.
- **O servidor não recarrega código Python:** depois de mexer em `ferramentas/`, mate o processo da 8730 e suba de novo.
  O app (`app/src`) precisa de `npm --prefix app run build`.
- **O dono escreve instruções em comentários das imagens.** Comentário simples não entra na fila; só o `⌘↵` (sufixo
  `[pedido <id>]`). Se ele disser "execute o meu prompt", leia os comentários dos nós do projeto.
- **Os testes rodam com tetos folgados** (`Isolado.setUp` troca `B.TETOS`); só `PortaoDeGasto` usa os zeros de verdade.
  Teste novo que gere sem `--confirmado` passa por isso.
- **O portão lê os tetos do `projeto.json`.** Projeto criado antes de 22/11 ou alterado por PATCH mantém os seus.
- **A estimativa do portão superestima:** US$ 0,14 por imagem na tabela contra US$ 0,03 a 0,15 cobrados; a causa da
  variação não foi identificada.
- **Mutação por script:** desfaça com o `replace` inverso, nunca com `git checkout`; apague `ferramentas/__pycache__`
  entre mutações.

## Em aberto (não bloqueia)

1. `d24826f` (correções do vídeo de referência e do comentário-pedido) **não teve segunda revisão independente**, e
   depois dele o upload de vídeo e o aviso de arquivo não aceito não foram reabertos no navegador.
2. Limites conhecidos do upload: `Transfer-Encoding: chunked` sem `Content-Length` (anterior); vários vídeos soltos de
   uma vez sobrepõem as grades; soltar um arquivo sobre o visualizador, fora da caixa de comentário, sobe pelo canvas
   por trás (anterior); vídeo de horas segura a requisição; sem indicador de progresso.
3. Mutações sem teste: troca de largura e altura na rotação do vídeo enviado; webm sem duração.
4. Gerador de vídeo: o pedido ainda pode ficar preso por `B.medidas` sem `sips`, por `catalogo[...]['name']` ausente e por
   Ctrl-C ou SIGTERM durante a leitura do catálogo. A chave do OpenRouter pode aparecer em `pedido['erro']` se vier do
   ambiente com quebra de linha.
5. A barra do rascunho de imagem transborda o cartão (313 px em 278), anterior a esta sessão.
6. O número máximo de imagens de referência que o modelo aceita num pedido não foi medido.
7. No projeto `brain` há rascunhos vazios criados pelo dono (`BRA-016`, `BRA-025`, `BRA-035`, `BRA-036`).
8. O vídeo `BRA-041` (Grok Imagine 1.5 Lite) borrou o texto miúdo dos cartões; foi oferecido repetir no Wan 3.0
   (US$ 0,51) ou no Seedance 2.5 (US$ 1,39), sem resposta.
9. `MEMORY.md` do usuário está em 17,5 KB, acima dos 17,1 KB que o harness pede; não foi compactado.

## Confiança

- **Medi e confirmei:** suíte 103 OK; lints nas linhas de base; visibilidade pública (`gh repo view`); HEAD local igual
  ao remoto; no navegador, antes do `d24826f`: soltar um mp4 cria vídeo e quadros, o visualizador toca a referência,
  `⌘↵` com anexo cria pedido enviado, cancelar volta a rascunho, a pílula e o pedido avisam que ninguém ouve; depois do
  `d24826f`: três `⌘↵` seguidos criam um pedido só; título "Kratos Stitch" servido pelo servidor.
- **Li o código mas não executei:** o player da referência-vídeo com pins de tempo; o aviso "Só imagens e vídeos…".
- **Vi dois quadros, não o vídeo:** `BRA-041` (interface parada, galáxia girou, texto miúdo borrado no fim).
- **Estou supondo:** que o CI de `b6673db` e o deste handoff fecham verdes (a mudança foi de três strings e de docs).

## Onde está o detalhe

- Specs com pre-mortem: `docs/specs/2026-11-22-fila-sem-ouvinte-e-portao-de-gasto.md` e
  `docs/specs/2026-11-22-comentario-pedido-e-video-de-referencia.md`.
- Prompt de retomada: `docs/handoff/2026-11-22-portao-de-gasto-e-repo-publico-prompt.md`.
