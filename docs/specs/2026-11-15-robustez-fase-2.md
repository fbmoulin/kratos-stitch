# Spec — robustez, fase 2 (2026-11-15)

Branch `correcoes-auditoria`, a partir de `95e78ff`. Cinco itens, na ordem de implementação. Toda premissa abaixo foi
medida nesta máquina; o comando está junto do resultado.

## Fora do escopo (medido, não vale a pena)

- Dividir o contexto / `memo` dos nós: projeto de 542 nós no Chrome, no máximo 38 nós montados, pior quadro 14 ms e zero
  tarefas acima de 50 ms em poll com mudança, `D`, ⌘1 (30 PATCHes) e ⌘Z.
- Dividir o bundle de 515 kB: app servido de `localhost`, carga em 299 ms.

---

## 1. Pedido preso se cura sozinho

### Evidência

`gerar.py` real com o OpenRouter trocado por uma espera, morto 2 s depois de criar os placeholders:

```
SIGTERM em LOJ-003 -> exit 143
   [('LOJ-003', 'trabalhando'), ('LOJ-005', 'gerando'), ('LOJ-006', 'gerando')]
SIGKILL em LOJ-004 -> exit 137
   [('LOJ-004', 'trabalhando'), ('LOJ-007', 'gerando'), ('LOJ-008', 'gerando')]
-- rodar de novo:  ERRO: LOJ-003 já tem imagens sendo geradas (outra execução do gerar.py). Se ela morreu, solte o pedido com `neo.py erro …
```

O `finally` de `gerar.py` não roda com SIGTERM (o Python morre no sinal) nem com SIGKILL. O pedido fica `trabalhando`,
o app recusa apagar e reenviar, e a guarda recusa rodar de novo até um `neo.py erro` manual.

### Mudança

- `base.py`
  - `gerador_vivo(pedido) -> bool`: `pedido['gerador']['pid']` existe e o processo responde a `os.kill(pid, 0)`
    (`PermissionError` conta como vivo; `ProcessLookupError` como morto).
  - `soltar_orfaos(slug) -> list[str]`: com a trava do projeto, para cada pedido `trabalhando` que **tem** `gerador` e
    cujo processo morreu: tira `gerando` das saídas e põe `erro: 'A geração foi interrompida.'`; fecha o pedido como
    `concluido` se alguma saída tem `arquivo`, senão `erro`; soma o custo das saídas; remove `gerador`. Devolve os
    pedidos soltos.
  - `fechar_pedido(slug, pid, saidas, vazio)`: o fechamento que hoje está duplicado nos `finally` de `gerar.py` e
    `gerar_video.py` passa a ser esta função, usada pelos dois e por `soltar_orfaos`.
- `gerar.py`, `gerar_video.py`
  - ao criar os placeholders (dentro da trava): `pedido['gerador'] = {'pid': os.getpid(), 'desde': agora()}`.
  - a guarda de execução dupla chama `soltar_orfaos` antes de decidir: gerador morto não bloqueia.
  - `signal.signal(SIGTERM, …)` levanta `SystemExit(143)` na thread principal, e o `finally` existente roda.
- `servidor.py`: a thread `varredor` (que já passa por todos os projetos a cada 60 s) chama `soltar_orfaos`. O `GET`
  do polling não muda (continua barato: `rev()` só faz `stat`).

### Não muda

- Pedido `trabalhando` **sem** `gerador` (o `neo.py pegar` foi feito e o Claude ainda escreve os prompts, ou o pedido é
  de antes desta mudança) não é tocado: não há como saber se alguém está vivo. A saída segue sendo `neo.py erro`.
- `neo.py erro` continua funcionando como hoje.

### Critérios

1. Gerador morto com SIGKILL → `soltar_orfaos` fecha o pedido como `erro`, nenhuma saída `gerando`, `gerador` removido.
2. Gerador morto com uma imagem já no disco → pedido `concluido`, custo somado, a outra saída com `erro`.
3. Gerador vivo (o PID do próprio teste) → nada muda.
4. Pedido `trabalhando` sem `gerador` → nada muda.
5. `gerar.py` num pedido cujo gerador morreu → roda (não sai com "já tem imagens sendo geradas").
6. SIGTERM num `gerar.py` de verdade (subprocesso, OpenRouter trocado) → pedido fechado, nada `gerando`.
7. Os 31 testes atuais continuam passando.

### Riscos

- PID reaproveitado por outro processo: o pedido órfão parece vivo e não é solto. Falha para o lado seguro (volta ao
  comportamento de hoje, `neo.py erro`).
- O varredor só corre com o servidor ligado; sem ele, a cura acontece na próxima execução do gerador (critério 5).

---

## 2. Estimativa de custo pelo histórico

### Evidência

- Tabela `MODELOS` (`base.py:39`): `flash` a $0,04. Cobrança real medida: `TES-004 ok 0.0672185` (1376×768).
- `curl https://openrouter.ai/api/v1/models` → `google/gemini-3.1-flash-image`: `"image_output": "0.00006"` por token.
  O preço é por token de saída, então varia com a resolução; 4 dos 7 modelos da tabela nem aparecem nesse catálogo.
- O teto usa a tabela: `gerar.py:68-70`, `estimativa = preco * len(variacoes)`. O app não mostra estimativa de imagem
  (`grep '\.preco' app/src/*.tsx` → só o `preco_s` de vídeo).

### Mudança

- `base.py`: `preco_estimado(slug, modelo, resolucao) -> float`: a mediana do `custo` das imagens do projeto com o
  mesmo `modelo` e a mesma `resolucao` (sem `asset`, sem `erro`, custo > 0) quando há 3 ou mais; senão o `preco` da
  tabela; senão 0,15 (o padrão de hoje).
- `gerar.py:68`: usa `preco_estimado`.
- `MODELOS['google/gemini-3.1-flash-image']['preco']`: 0,04 → 0,07.

### Critérios

1. Sem histórico → o valor da tabela (comportamento de hoje, com o `flash` corrigido).
2. Com 3 imagens a $0,20 do modelo → estimativa 0,20 por imagem, e o teto diário bloqueia (saída 3) onde antes passava.
3. Imagens de outro modelo, de outra resolução, com erro ou `asset` não entram na mediana.

---

## 3. Colar com o visualizador aberto

### Evidência

`Canvas.tsx`, handler `colar` (~l. 462-482): registrado em `window` sem olhar `coberto`; a revisão do frontend apontou
que ⌘V com o visualizador aberto cria uma referência no canvas por trás. Os outros atalhos já usam `coberto`.

### Mudança

`colar` não faz nada quando `coberto` (visualizador ou modal aberto). Campos de texto já são excluídos.

### Critério

No navegador (cópia isolada): com o visualizador aberto, um evento `paste` com imagem não cria nó; fechado, cria.

---

## 4. CI no kratos-stitch

### Evidência

```
gh api repos/fbmoulin/kratos-stitch/actions/workflows --jq .total_count  → 0
PATH sem o sips: Ran 31 tests … FAILED (failures=2, errors=1)
   test_entrada_de_pagina_usa_o_print, test_gera_e_fecha_o_pedido, test_placeholder_apagado_no_meio_nao_prende_o_pedido
```

Só 3 dos 31 testes dependem do `sips` (macOS). Minuto de runner macOS em repositório privado custa 10× o de Linux.

### Mudança

- `tests/test_auditoria.py`: os testes que precisam do `sips` ganham `skipUnless(shutil.which('sips'))`.
- `.github/workflows/ci.yml`, em `push` e `pull_request`, runner `ubuntu-latest`:
  - Python 3.13: `python -m unittest discover -s tests`
  - Node 22: `npm --prefix app ci`, `npm --prefix app run build`, `npm --prefix app run lint`

### Critérios

1. Local, com o `sips`: todos os testes rodam. Sem o `sips` no PATH: 0 falhas, os dependentes pulados.
2. `gh run list` mostra o run do push concluído com sucesso.

### Risco

O lint do `oxlint` hoje dá 9 avisos e sai com 0; se o runner tratar aviso como erro, o passo de lint cai. Conferir no
primeiro run.

---

## 5. Mudar e apagar em lote

### Evidência

- `useHistorico.ts:35-50`: `lote.current` é global enquanto a função espera o servidor. Dois usos esperam em série:
  `Canvas.tsx:144` (apagar vários) e `Canvas.tsx:668` (distribuir).
- ⌘1 num projeto de 542 nós: `recolhidos` foi de 0 a 30 → 30 `PATCH`, cada um seguido de um `GET` completo (546 kB
  num projeto de 600 nós).
- Um lote que falha no meio fica meio desfeito (limite registrado no handoff).

### Mudança

- `servidor.py`
  - `PATCH /api/projetos/<slug>/nos` com `{id: campos, …}`: valida todos com `limpar_campos` e as regras de
    `mudar_no`; se algum falha, nada é gravado (tudo ou nada). Devolve os nós.
  - `POST /api/projetos/<slug>/nos/apagar` com `{ids: […]}`: um lote só na lixeira (`para_lixeira` já aceita `junto`),
    com as mesmas recusas de `apagar_no`. `…/nos/<id>/restaurar` do primeiro id traz o lote inteiro (já é assim).
- `app/src`
  - `useProjeto.mudarVarios(mapa)`: otimista, um `PATCH`, uma recarga; devolve se o servidor aceitou.
  - `useHistorico`: `mudarVarios` e `apagarVarios` registram **um** passo cada. Os usos de `emLote` que só juntam
    `mudar` (`Canvas.tsx:492, 511, 532, 684, 904`) e os dois que esperam em série (`144`, `668`) passam a usá-los.
  - `emLote` fica só para o que mistura tipos de passo (`Canvas.tsx:376`).

### Critérios

1. `PATCH` em lote com um item inválido → 422 e nenhum nó muda.
2. Apagar dois galhos numa chamada → um lote na lixeira; restaurar traz os dois.
3. Navegador: ⌘1 num projeto com 30 galhos → 1 `PATCH` e 1 recarga (hoje: 30 e 30); ⌘Z desfaz tudo num passo.
4. Navegador: apagar seleção múltipla e ⌘Z restaura tudo.

### Risco

É o item maior e mexe no caminho de desfazer. Fica por último e só entra depois de 1 a 4 commitados.

---

---

## Revisão depois do pre-mortem (2026-11-15)

Pre-mortem em `.premortems/PREMORTEM-2026-11-15T01-30-00.md`: **REFINE** (2 `high` locais, 3 `medium`). O que muda nesta
spec; onde houver conflito com o texto acima, vale o que está aqui.

**Ordem:** 4 → 1 → 2 → 3 → 5. O CI entra primeiro para verificar os outros.

**§1**
- `gerador` passa a ser `{'pid', 'desde', 'saidas': [ids desta execução]}`. `fechar_pedido` e `soltar_orfaos` só mexem
  nesses ids, e o custo somado é só o deles (as `saidas` do pedido acumulam execuções antigas).
- `gerador` sai do pedido em todo fechamento e também em `neo.py pegar`, `neo.py erro` e no `enviar` do servidor: um PID
  velho nunca fica num pedido reaberto.
- Duas funções: `soltar_orfaos(slug)` pega a trava (para o varredor) e `_soltar_orfaos(slug)` é chamada por quem já a
  tem (a guarda do gerador). `flock` não é reentrante.
- SIGTERM: o handler é instalado depois de criar os placeholders; fecha o pedido e sai com `os._exit(143)`, sem esperar
  os workers. Se o `finally` já está fechando, o handler não faz nada. As imagens em voo se perdem (o processo foi
  mandado morrer).
- Critério 6 passa a ser: SIGTERM num subprocesso com workers de 60 s → pedido fechado e processo morto em até 3 s.
- Critério novo 8: pedido solto com `neo.py erro` e pego de novo com `neo.py pegar` → `soltar_orfaos` não o toca.

**§2**
- `preco_estimado` = `max(preço da tabela, mediana do histórico)`: o histórico só sobe a estimativa. `legado` não entra.
- Critério novo 4: histórico mais barato que a tabela → vale a tabela.

**§4**
- Em vez de pular testes: sem o `sips`, a classe base dos testes troca `B.miniatura` e `B.medidas` por versões que não
  dependem dele. Critério 1 vira: sem o `sips` no PATH, os 31 testes rodam e passam, nenhum pulado.
- `timeout-minutes: 10` no job. Critério 2: `gh run list -R fbmoulin/kratos-stitch`.

**§5**
- Os cartões de página (`IMG/vN`) não vão para a rota em lote: `mudarVarios` os separa no cliente e os manda por
  `deslocImpl`, como hoje.
- `Canvas.tsx:668` (distribuir) continua dentro de `emLote`, envolvendo o `passo` do modo compacto e um `mudarVarios`.
- Critério 4 reescrito: apagar seleção múltipla e ⌘Z traz os nós de volta. As `entradas` que os rascunhos de fora
  perderam não voltam (já é assim hoje; fica registrado, não entra neste item).
- Critério novo 5: "Realinhar" num projeto com um cartão de página movido funciona.

## Verificação geral

`python3 -m unittest discover -s tests` · `uvx ruff check ferramentas` (linha de base: 21 avisos) ·
`npm --prefix app run build` · `npm --prefix app run lint` (linha de base: 9 avisos) · CI verde depois do item 4.
Nenhuma geração paga é necessária.
