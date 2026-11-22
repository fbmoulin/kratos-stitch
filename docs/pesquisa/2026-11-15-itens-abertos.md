# Pesquisa — itens em aberto (2026-11-15)

Quatro itens, cada um com o que foi medido, as fontes, as opções e a recomendação.

**Estado (2026-11-15):** os itens 2, 3 e 4 foram aprovados e implementados com a opção recomendada (testes
`EntradasDeRascunho` e `VideoBaixado`). O item 1 fica como está: repositório privado, com um rascunho de PR para o autor
guardado fora do git.
A parte jurídica não é aconselhamento: é leitura das fontes primárias, com os pontos onde um advogado faria diferença.

> **Atualização (2026-11-22): o item 1 está superado.** O autor do Neo Stitch é professor de um curso da ASIMOV
> Academy, do qual o dono deste clone é aluno, e informou aos alunos que o repositório pode ser usado livremente, como
> material disponibilizado no curso. A autorização que a seção 1 dizia faltar foi dada. Com isso o repositório
> `kratos-stitch` passou a ser público nesta data, e o rascunho de PR guardado fora do git foi aposentado. O texto da
> seção 1 fica abaixo como registro do que se sabia em 15/11; a recomendação dela não vale mais.

---

## 1. Licença do repositório de origem

> Superado em 2026-11-22: ver a atualização no topo deste documento.

### O que existe hoje (conferido em 2026-11-15)

- `https://api.github.com/repos/rtadewald/neo-stitch` → `license: null`, público, `allow_forking: true`, 44 forks.
- Sem arquivo LICENSE; `app/package.json` sem campo `license`; o README não tem frase de permissão, só as instruções
  de clonar e rodar e o crédito ao autor.

### O que as fontes dizem

- **GitHub, sem licença:** "without a license, the default copyright laws apply"; ninguém pode reproduzir, distribuir
  ou criar obra derivada.
  https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
  · https://choosealicense.com/no-permission/
- **Termos do GitHub, D.5:** quem publica um repositório público permite que outros usuários o vejam e o reproduzam
  "by forking", dentro do serviço e "as permitted by GitHub's functionality". O texto não fala em modificar nem em obra
  derivada. https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
- **Fork é sempre público:** "Public repository forks are public"; a visibilidade de um fork não muda sozinha.
  https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/about-permissions-and-visibility-of-forks
  O `kratos-stitch` é um clone enviado a um repositório privado separado, não um fork pela função do GitHub.
- **Lei 9.609/1998 (software):** proteção igual à das obras literárias e independente de registro (art. 2º, caput e
  §3º); o uso depende de contrato de licença (art. 9º); a derivação só gera direitos próprios se autorizada (art. 5º).
  As exceções do art. 6º são: cópia de salvaguarda, citação didática, semelhança funcional e integração tecnicamente
  indispensável para uso exclusivo de quem a fez. Nenhuma cobre modificação privada em geral.
  https://www.planalto.gov.br/ccivil_03/leis/l9609.htm
- **Lei 9.610/1998:** depende de autorização "prévia e expressa" a reprodução (art. 29, I), a adaptação e outras
  transformações (III) e a distribuição (VI); os negócios sobre direitos autorais interpretam-se restritivamente
  (art. 4º). https://www.planalto.gov.br/ccivil_03/leis/l9610.htm
- **Sanções:** Lei 9.609 art. 12 (em regra, ação mediante queixa do titular) e art. 14 (ação de abstenção);
  Lei 9.610 arts. 102–103.

### Opções

| # | Opção | O que permite | Risco | Esforço |
|---|---|---|---|---|
| 1 | Manter privado, uso pessoal | Continuar como está | Baixo na prática (sem distribuição); formalmente, as modificações não têm autorização expressa | Zero |
| 2 | Pedir licença ao autor | Tudo: modificar, publicar, compartilhar | Ele pode não responder ou negar | Uma mensagem |
| 3 | Fork de verdade + PRs | Devolver as correções ao projeto | O fork é público; um PR não licencia o código dele para você | Médio |
| 4 | Publicar o derivado sem permissão | — | Alto: reprodução, transformação e distribuição sem autorização; exposto a takedown e a ação | — |
| 5 | Reescrever do zero | Independência total | Quem já leu o código não é "clean room" | Muito alto |

### Recomendação

**2, e 1 enquanto espera.** Pedir ao autor que adicione uma licença (MIT é a mais simples: basta manter o aviso de
copyright e o texto da licença; Apache-2.0 acrescenta aviso de arquivos alterados e concessão de patente). Vale pedir
a autorização por escrito mesmo que ele não suba o arquivo, porque o art. 29 exige que seja "expressa". O projeto tem
44 forks e o README ensina a clonar e rodar, o que sugere boa vontade, mas não substitui a autorização.

Enquanto isso: não dar acesso ao repositório privado a terceiros e não tornar o `kratos-stitch` público.

A opção 3 combina bem com a 2: as correções deste clone (prefixo de nomes curtos, pedido preso, origem da API) são
úteis para ele, e oferecê-las num PR é um bom motivo para a conversa.

### Onde um advogado faria diferença

- Se as instruções de `git clone` + rodar no README configuram licença implícita de uso.
- O alcance do art. 6º, IV, da Lei 9.609.
- Qualquer plano de publicar ou de uso comercial.

---

## 2. Rascunhos perdem as entradas apagadas, e o desfazer não as devolve

### Evidência (servidor real, `projects/` temporário)

```
antes     : ['MOD-004', 'MOD-010']
DELETE    : 200
apagado   : ['MOD-004']
RESTAURAR : 200
restaurado: ['MOD-004'] | o asset voltou ao disco: True
```

O `apagar` (`ferramentas/servidor.py`) tira dos rascunhos que ficam as entradas que saíram; o `restaurar_da_lixeira`
(`ferramentas/base.py`) só move os arquivos de volta. Alcance: só rascunhos que usam o nó apagado como referência
**secundária**. Se o nó apagado é a imagem de origem do rascunho, o rascunho pertence ao galho e sai e volta com ele.

### Quem lê `entradas`, e o que acontece com um código que não existe

- `app/src/layout.ts:62` e `:472`, `app/src/nodes.tsx:213`: filtram o que não está no projeto. Tolerante.
- `ferramentas/gerar.py:87`, `ferramentas/gerar_video.py:131`: usam `arquivo_entrada`, que devolve `None`. Tolerante.
- `ferramentas/servidor.py:447` (`enviar`): aceita o pedido se há `entradas`, sem conferir se existem. Um rascunho
  só com entradas mortas e sem texto seria enviado vazio.

### Opções

| # | Opção | Prós | Contras |
|---|---|---|---|
| A | O lote da lixeira guarda `{rascunho: entradas de antes}`; o restaurar reaplica, sob a mesma trava | Atômico; serve ao app e à linha de comando; preserva a ordem (a 1ª entrada é o pai) | Um arquivo a mais no lote; precisa mesclar com o que o usuário mudou depois |
| B | Não tirar as entradas ao apagar | Remove código; o restaurar "funciona" sem fazer nada | Muda o significado de `entradas`; exige fechar o `enviar`; rascunhos ficam com códigos mortos para sempre se o lote não for restaurado |
| C | O app guarda as entradas de antes no passo de desfazer e reenvia depois do restaurar | Não mexe na lixeira | Duas chamadas, não atômico; não cobre quem restaura pela linha de comando |

### Recomendação

**A.** É a única que mantém a regra do projeto (toda escrita sob a trava) e funciona para qualquer cliente.
A mescla: para cada rascunho que ainda é rascunho, `[e de antes que voltou ou continua] + [o que o usuário
acrescentou depois]`, o que preserva a ordem original. Tamanho estimado: ~20 linhas e 2 testes.

---

## 3. Vídeo com trilha de áudio

### Evidência

- Teste real: `x-ai/grok-imagine-video-1.5-lite`, 2 s, 480p → o mp4 veio com trilha AAC (`ffprobe`).
- Catálogo público `https://openrouter.ai/api/v1/videos/models` (32 modelos): `generate_audio` é `true` em 18,
  `false` em 9 e `null` em 5. O Grok Lite é `null`; os outros quatro que o app oferece (Wan 3.0, Wan 3.0 Prime,
  Hailuo 3, Seedance 2.5) são `true`.
- `ferramentas/gerar_video.py` só manda `generate_audio: false` quando o campo do catálogo não é `null`. Para o Grok
  Lite, portanto, o pedido foi sem o parâmetro.
- A especificação diz que o padrão, sem o parâmetro, é "false if not set"; o guia diz que é `true` para modelos que
  suportam áudio. As duas fontes se contradizem, e o observado (veio áudio com o campo `null`) não bate com a
  especificação. https://openrouter.ai/openapi.json ·
  https://openrouter.ai/docs/guides/overview/multimodal/video-generation
- No app os dois `<video>` são `muted` (`app/src/nodes.tsx:596`, `app/src/Viewer.tsx:109`): o áudio só aparece se o
  arquivo for aberto ou exportado fora do app.

### Opções

| # | Opção | Prós | Contras |
|---|---|---|---|
| A | Mandar `generate_audio: false` sempre | 1 linha | Em modelo com `null` o efeito não é documentado: pode ser honrado, ignorado ou recusado (não testado; custaria uma geração) |
| B | Tirar a trilha depois do download: `ffmpeg -an -c copy` | Determinístico, sem recodificar, independe do provedor; o `ffmpeg` já é usado para a capa | Sem o `ffmpeg`, fica como está |
| C | Deixar | Zero esforço; no app já toca mudo | O arquivo exportado leva um áudio que ninguém pediu |

### Recomendação

**B.** Não depende de comportamento não documentado e resolve para qualquer modelo. A opção A pode ser somada depois,
se um teste pago mostrar que o parâmetro é aceito nos modelos `null` (economizaria o custo do áudio, se houver).

---

## 4. O cartão do vídeo guarda as dimensões da imagem de origem

### Evidência

- Teste real: o nó ficou com `largura: 1376, altura: 768` (da imagem); o arquivo tem 736×400 (`ffprobe`).
- A API não informa o tamanho do resultado: o `GET /videos/{id}` devolve `id`, `status`, `urls`, `usage`, `error` e
  pouco mais, sem largura, altura ou duração (https://openrouter.ai/openapi.json). A documentação não diz como "480p"
  vira pixels nem como uma entrada que não é 16:9 é tratada.
- Onde o valor é usado: `app/src/layout.ts:11` (só a proporção, para o tamanho do cartão) e `app/src/Viewer.tsx:198`,
  que mostra `{largura}×{altura}`.
- Efeito visível: o visualizador mostra "1376×768" para um arquivo de 736×400; no canvas, o cartão fica 720×402 em
  vez de 720×391, um corte lateral de cerca de 2,7% com `object-fit: cover`, sem distorção.
- O script manda sempre `16:9` ou `9:16`, pela orientação. Uma imagem 4:3 ou quadrada divergiria bem mais.

### Opções

| # | Opção | Prós | Contras |
|---|---|---|---|
| A | Medir o arquivo com `ffprobe` depois do download e gravar no nó | Única fonte real; `ffprobe` vem com o `ffmpeg` | Sem ele, mantém o valor de hoje |
| B | Deixar | Zero esforço | O rótulo do visualizador segue errado; piora com imagens que não são 16:9 |

### Recomendação

**A**, junto com o item 3: os dois mexem no mesmo ponto do `gerar_video.py`, logo depois do download.

---

## Não confirmado

- Se `generate_audio: false` é aceito e honrado em modelos com o campo `null`.
- Por que veio áudio com o campo `null`.
- A regra que transforma "480p" em pixels e o tratamento de entradas que não são 16:9.
- Se enviar um clone a um repositório privado cabe em "as permitted by GitHub's functionality".
- Licença implícita pelo README e o alcance do art. 6º, IV: não foi pesquisada jurisprudência.
- Os textos das leis foram lidos em resumo com citações curtas; conferir a redação literal antes de citar formalmente.

---

## Correções a este documento (revisão de código, 2026-11-15)

Uma revisão independente apontou afirmações erradas ou incompletas acima. O que foi implementado já leva isso em conta.

**Item 1.** A recomendação dizia para manter privado e, ao mesmo tempo, endossava a opção 3 (fork + PR). Um fork é
público: mandar as correções antes da autorização do autor é justamente o que a opção 4 classifica como risco alto.
A ordem certa é a opção 2 primeiro, e a 3 só depois da resposta dele. O que existe hoje é um patch local em
`rascunhos/`, fora do git.

**Item 2.**
- O alcance estava subestimado. Além da referência secundária, também ficavam entradas mortas em: pedidos com status
  `erro` (que podem ser reenviados), entradas de página (`IMG/vN`, nunca removidas quando a imagem sai) e rascunhos
  cuja única entrada é uma referência com posição própria.
- A lista de quem lê `entradas` estava incompleta. Leem a primeira entrada pela posição, sem filtrar:
  `ferramentas/base.py` (`avancos`, `p['entradas'][0]`) e `ferramentas/impl.py` (`cmd_iniciar`). Também leem:
  `ferramentas/neo.py` (`ver_no`), `ferramentas/base.py` (`capa_de`), `app/src/Viewer.tsx` e `app/src/Trilho.tsx`.
- `ferramentas/gerar_video.py` não era "tolerante": sem imagem de entrada ele saía com erro e deixava o pedido
  "enviado". Corrigido: devolve o pedido como erro. O `enviar` passou a recusar pedido sem texto cujas entradas não
  existem mais.
- A regra de mescla recomendada (manifesto no lote) trocava a ordem quando dois lotes eram restaurados fora de ordem,
  e perdia a entrada se o rascunho estivesse na lixeira na hora. A implementação final não usa manifesto: o rascunho
  guarda a lista original em `entradas_antes`, e o restaurar reconstrói a partir dela (testes
  `test_lotes_restaurados_fora_de_ordem_mantem_a_ordem_das_entradas` e
  `test_rascunho_apagado_no_meio_nao_quebra_o_restaurar`).

**Item 3.** Há um terceiro player: `ferramentas/pagina_videos.py` gera uma página de comparação com
`<video controls muted>`, onde o usuário pode ligar o som. A retirada do áudio foi feita em `gerar_um`, que serve
aos dois modos (pedido do app e pasta avulsa), então cobre essa página. O detalhe que faltava nas opções: o `ffmpeg`
não regrava o arquivo no lugar; a implementação escreve um temporário e só troca se deu certo.

**Item 4.** "O `ffprobe` vem com o `ffmpeg`" não vale para toda instalação. A implementação confere o `ffprobe` por
conta própria e, sem ele, mantém as dimensões da imagem.

**Conferido com geração real (autorizada):** pedido `TES-007` → vídeo `TES-008`, $0,05. O nó ficou com 736×400 (as do
arquivo) e o arquivo tem uma faixa só, `h264,video`.
