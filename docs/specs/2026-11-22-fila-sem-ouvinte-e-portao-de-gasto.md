# Spec — fila sem ouvinte e portão de gasto (2026-11-22, rev2)

Ratificado pelo dono em 2026-11-22: aviso visível, cancelar envio, estimativa no rascunho de imagem, e tetos em zero
como portão; o "ok" para gastar é dado no chat, a cada geração. A rev2 incorpora o pre-mortem (veredito REFINE): os
quatro itens são os mesmos, mudou o detalhe de como cada um é feito.

## Evidência (medida em 2026-11-22, HEAD `4723564`)

- Enviar pelo app só grava o nó como `enviado` e acrescenta uma linha em `fila.jsonl` (`ferramentas/servidor.py:474-480`).
  Quem atende é um agente com o `ferramentas/ouvir.sh` ligado; sem ele, nada acontece.
- O único sinal é o ponto cinza "Claude" no topo, com a explicação só no `title` (`app/src/Canvas.tsx:870-872`). O pedido
  enviado mostra "fila" pulsando, sem dizer que ninguém ouve (`app/src/nodes.tsx:464`).
- Pedido `enviado` não é editado (`servidor.py:366-367`), reenviado (`servidor.py:460-461`) nem apagado com o galho
  (`servidor.py:436-437`). Só `neo.py erro <id>` o solta; o app não tem cancelar.
- Abaixo dos tetos o gerador gasta sem perguntar: `gerar.py:75-83`, `gerar_video.py:196`. Padrões em `base.py:54`; projeto
  novo os copia (`base.py:238`). O modo avulso de vídeo usa um limite fixo de US$ 5, fora dos tetos (`gerar_video.py:293`).
- A skill manda `neo.py pegar` antes do gerador (`.claude/skills/neo-stitch/SKILL.md:33`): o pedido fica `trabalhando`
  sem `gerador`, e é assim que ele ficaria depois de uma saída 3 (o varredor de órfãos exige `gerador`, `base.py:354`).
- O rascunho de vídeo mostra `≈ $` (`nodes.tsx:328`); o de imagem não (`nodes.tsx:346`).

## Mudanças

### M1 — Tetos em zero por padrão, e o pedido bloqueado volta para a fila
- `base.TETOS` passa a `imagens_por_pedido: 0` e `video_por_pedido_usd: 0.0`; `diario_usd` fica em 20. Todo pedido pago
  sai com código 3 e a estimativa. O `teste-e2e` (dado, fora do git) recebe os mesmos zeros por PATCH.
- Ao sair com 3, o gerador devolve o pedido à fila: se ele está `enviado` ou `trabalhando` sem `gerador` registrado, fica
  `enviado` com `aguarda_ok: <estimativa>`. Assim ele não gira como se estivesse gerando e pode ser cancelado (M3). O
  campo sai quando a geração começa, no cancelar e no reenviar.
- A mensagem de bloqueio de imagem passa a trazer o gasto do dia (com teto zero a checagem diária não é mais alcançada
  sem `--confirmado`).
- O modo avulso de vídeo usa `B.TETOS['video_por_pedido_usd']` em vez do US$ 5 fixo.
- Skill, AGENTS.md, README.md, specs.md e a docstring de `gerar_video.py` passam a dizer que neste clone toda geração
  para na saída 3, que `--confirmado` vale para um pedido depois do sim dado a ele, e que o "não" vira `neo.py erro`.

O que o portão cobre: imagem (`gerar.py`) e vídeo (`gerar_video.py`, por pedido e avulso). Não cobre assets e modelos 3D,
que o agente gera fora do repo e só registra depois (`docs/AGENTES.md`). `--confirmado` continua sendo um argumento que o
agente passa: o portão é uma parada obrigatória com estimativa, não uma trava contra um agente que ignore a regra.

### M2 — Aviso visível de que ninguém ouve
- A pílula do topo mostra "Claude não está ouvindo" quando `ouvinte` é falso.
- `StatusPedido` (`nodes.tsx:463`) passa a ler o `estado`: pedido `enviado` com `aguarda_ok` mostra "aguarda seu ok no
  chat" e a estimativa; `enviado` sem ouvinte mostra "fila · ninguém ouvindo".
- O brief usa outro componente (`status-claude`, `nodes.tsx:159`): com o brief ocupado e sem ouvinte, o mesmo aviso.

### M3 — Cancelar envio
Rota `POST /api/projetos/<slug>/nos/<id>/cancelar`, sob a trava, só para pedido `enviado`:
- sem `saidas`: volta a `rascunho` (editável), sem `enviado_em` e sem `aguarda_ok`;
- com `saidas` (um pedido que já gerou e foi reenviado): vai para `erro` com "Envio cancelado", que é o estado que esse
  pedido já podia ter; ele pode ser reenviado, não editado.

Qualquer outro estado ou tipo devolve 422 sem mudar o nó. No app, um botão ao lado do selo da fila.

A linha antiga continua na `fila.jsonl`. Para um agente que já a recebeu não pegar o pedido e travar de novo o rascunho
que o dono está editando, o cancelar grava `cancelado_em`, o `neo.py pegar` recusa o pedido que tem o campo, e o enviar o
tira (entrou depois da revisão do código). Ficam fora: cancelar o brief e cancelar pedido `trabalhando`.

## Limites conhecidos (revisão independente do `d384d7a`)

- O portão lê os tetos do `projeto.json`. Um projeto criado antes desta mudança, ou com tetos alterados por PATCH,
  mantém os seus; só o `teste-e2e` existia e foi zerado.
- `neo.py pegar` num pedido que está gerando apaga o `gerador`, e a saída 3 seguinte o devolve à fila com placeholders
  ainda girando. Anterior a esta mudança no que toca ao `pegar`.
- Pedido `trabalhando` com gerador morto não volta à fila na saída 3: fica para o varredor de órfãos.

### M4 — Estimativa no rascunho de imagem
`≈ $ preço do modelo × quantidade`, no lugar e formato da estimativa do vídeo; modelo fora da tabela usa 0,15, como o
gerador (`base.py:430`). O `title` diz que o valor final vem na confirmação: o gerador conta as variações que o agente
escreveu e corrige o preço pelo histórico, então os dois números podem diferir.

## Critérios de aceite

1. Projeto novo, pedido de imagem pego (`trabalhando`), `gerar.py` sem `--confirmado`: código 3, saída com a estimativa e
   o gasto do dia, nenhum POST, pedido `enviado` com `aguarda_ok`. Com `--confirmado`: gera e o campo some. O mesmo para
   `gerar_video.por_pedido` (ali o GET do catálogo acontece antes, é dele que sai a estimativa).
2. Um gerador vivo no pedido não é atropelado: a saída 3 não muda um pedido com gerador vivo.
3. `cancelar` em pedido `enviado` sem saídas: 200 e `rascunho`; com saídas: 200 e `erro`. Em `rascunho`, `trabalhando`,
   `concluido`, `erro` e em nó que não é pedido: 422 e nó intacto.
4. No navegador, sem ouvinte: a pílula traz o texto; o pedido enviado traz "ninguém ouvindo" e o cancelar; cancelado, o
   rascunho volta editável. O rascunho de imagem mostra a estimativa, ela muda com modelo e quantidade, e a barra não
   quebra na largura do cartão.
5. Suíte inteira verde, com os testes antigos rodando nos tetos antigos (`Isolado.setUp`) e os do portão em zero; `ruff`
   em 21 e `oxlint` em 9.

## Mutações que os testes têm de matar

- M1: voltar um teto ao valor antigo; não devolver o pedido à fila na saída 3; devolver mesmo com gerador vivo; não
  limpar `aguarda_ok` ao gerar.
- M3: aceitar `cancelar` em `trabalhando`; não gravar o nó; mandar para `rascunho` um pedido com saídas.
