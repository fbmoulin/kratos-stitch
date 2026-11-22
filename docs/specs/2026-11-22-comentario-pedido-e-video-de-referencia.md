# Spec — comentário que vira pedido, vídeo de referência e anexo no comentário (2026-11-22)

Ratificado pelo dono em 2026-11-22: os três itens, nesta ordem, e "o máximo de quadros aplicável" por vídeo.

## Evidência (uso real de 2026-11-22, HEAD `48618a1`)

- O dono escreveu pedidos em comentários ("gere mais 3 opções…", `projects/brain/nodes/BRA-018.json`). Comentar não põe
  nada na fila: `comentar` (`ferramentas/servidor.py:506-516`) só grava o comentário; `B.enfileirar` só é chamado pelo
  enviar e pelo "Novo projeto" (`servidor.py:169,483`). O agente só os leu porque foi olhar os nós.
- Ele tentou anexar uma imagem e um vídeo a um comentário e só os nomes dos arquivos entraram no texto
  (`BRA-022`, comentário de 09:41:10). A caixa de comentário é um `textarea` sem colar/soltar arquivo
  (`app/src/Viewer.tsx:257-262`).
- O canvas só aceita imagem: `subir` filtra `image/` (`app/src/Canvas.tsx:472`), o seletor é `accept="image/*"`
  (`Canvas.tsx:1055`) e o servidor recusa o resto (`EXTENSOES`, `servidor.py:73,533-536`).
- Feito à mão nesta data, sem código novo: dois quadros do vídeo dele extraídos com ffmpeg e enviados como referências
  (`BRA-029`, `BRA-030`), usados como entrada do `BRA-031`.
- Cada referência ligada a um pedido custa: o `BRA-021` (2 entradas) saiu a US$ 0,15 por imagem e o `BRA-017` (2 entradas
  menores) a US$ 0,05. O número máximo de imagens de referência que o modelo aceita **não foi medido**.

## Mudanças (rev2, depois do pre-mortem: veredito REFINE)

### C1 — Comentário que vira pedido
No visualizador, a caixa de comentário ganha um segundo botão, "Enviar ao Claude como pedido", para imagem e referência
(não para o vídeo gerado, que o servidor descarta como entrada). `Enter` comenta, como hoje; `⌘↵` envia como pedido.
Ordem: cria o rascunho com `entradas: [o nó, …anexos]` e `intencao: o texto` → grava o comentário → envia. Usa
`api.criarNo` e `api.enviar` direto, sem o `novoPedido` do contexto, que recentra o canvas por trás do visualizador. Sem
rota nova; o pedido segue o portão de gasto.

### C2 — Vídeo próprio como referência
- **Limite de corpo, para toda rota:** 200 MB, conferido pelo `Content-Length` antes de ler; acima disso o servidor
  responde 413 e fecha a conexão (um corpo não lido seria atendido como outra requisição). O app confere `file.size` antes
  de mandar, para a mensagem chegar inteira.
- `POST …/refs` aceita `video/mp4`, `video/quicktime` e `video/webm`. Exige ffmpeg e ffprobe (sem eles, 422 dizendo o que
  falta). O que decide se é vídeo é o ffprobe: `format_name` tem de ser mp4/mov ou matroska/webm (uma imagem com
  `Content-Type` de vídeo é recusada), com faixa de vídeo e duração legível (webm sem duração: 422 pedindo mp4).
- O vídeo vira um nó `referencia` cujo `arquivo` é a capa (o quadro do meio, em jpg, como nos vídeos gerados) e que guarda
  `video` (`refs/<ID>.<ext>`), `duracao` e `quadros` (os códigos). Ligado a um pedido, entra como a capa.
- Quadros: `n = min(16, max(1, round(duração)))`, nos tempos `duração·i/(n+1)` (nunca o último instante, onde o ffmpeg
  não devolve quadro), um `-ss` por quadro. Cada um é um nó `referencia` comum, com `titulo` "<nome> · m:ss", `de` e `t`.
  Largura e altura vêm do ffprobe, com a rotação aplicada. Com posição (soltar, colar), os quadros ficam em grade de 4 por
  linha à direita do vídeo; sem posição, o canvas os empilha como faz com qualquer referência solta.
- **Tudo ou nada, fora da trava:** sondar e extrair num diretório temporário, sem a trava do projeto (a extração leva
  segundos e a trava seguraria toda escrita); só então travar, criar os nós, mover os arquivos e gravar. Se qualquer
  quadro faltar, nada é criado.
- Apagar o vídeo não apaga os quadros: são referências independentes, e o `de` que sobra é só um rótulo.
- App: `subir` e o seletor aceitam vídeo; o cartão mostra a marca de vídeo; o visualizador toca `no.video` quando o nó o
  tem. O teto de 16 é a escolha desta spec para "o máximo aplicável": extrair é grátis, ligar custa, e o limite do modelo
  não foi medido.

### C3 — Anexo no comentário
Colar ou soltar imagem ou vídeo na caixa de comentário sobe o arquivo como referência e mostra um chip com o código (o
soltar para na caixa, senão o canvas por trás subiria o arquivo outra vez). No "enviar como pedido" os anexos entram nas
`entradas`; **de um vídeo entra só a capa**, e os quadros o dono liga à mão (17 imagens num pedido seria um gasto que ele
não viu). No comentário simples, os códigos são acrescentados ao texto. Trocar de imagem no visualizador zera os chips.
Anexo de um comentário nunca enviado fica no canvas como referência solta.

## Fora do escopo

Ouvinte sem sessão do Claude Code; vídeo como entrada de pedido de vídeo; escolher os quadros pausando o player; recortar
ou converter o vídeo enviado; indicador de progresso do upload; mostrar `de` e `t` no `neo.py ver`; a guarda que falta
no soltar do canvas com o visualizador aberto (anterior a esta spec).

## Critérios de aceite

1. `POST …/refs` com um mp4 de 10 s: 200; nó de vídeo com `video`, `duracao`, `quadros` e `arquivo` jpg no disco; 10
   quadros com `de` e `t` crescentes, todos menores que a duração e com arquivo no disco. Com 2 s: 2 quadros. Com 40 s: 16.
2. PNG com `Content-Type: video/mp4`: 422, nenhum nó novo e nada deixado em `refs/`. Lixo com o mesmo tipo: idem.
3. Sem ffmpeg: 422 com a mensagem, nada criado. `Content-Length` acima do limite: 413, nada criado, e a conexão não
   atende um segundo pedido com o corpo que sobrou.
4. Imagem continua subindo como hoje (não havia teste de `subir_ref`: entra um).
5. No navegador: soltar um mp4 cria o vídeo e os quadros; o visualizador toca o vídeo; `⌘↵` num comentário cria um pedido
   `enviado` com o texto e a imagem; um arquivo colado no comentário vira chip e entra nas entradas.
6. Suíte verde; `ruff check ferramentas` em 21 e `oxlint` em 9.

## Mutações que os testes têm de matar

- C2: número de quadros fixo; quadros fora da duração; deixar o nó do vídeo quando a extração falha; aceitar qualquer
  `Content-Type`; ignorar o limite de tamanho.
