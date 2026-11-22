# Prompt de retomada (2026-11-22)

```
Leia primeiro, na íntegra:
/Users/felipemoulin/Projetos/neo-stitch/docs/handoff/2026-11-22-portao-de-gasto-e-repo-publico.md

Projeto: Kratos Stitch, meu clone do Neo Stitch (canvas local: imagem → vídeo → HTML). Checkout:
/Users/felipemoulin/Projetos/neo-stitch
⚠️ O trabalho está no branch `correcoes-auditoria`, não no `main` (que é o código original do autor). O remoto para
enviar é `kratos` (fbmoulin/kratos-stitch, público); nunca envie nada para `origin`.

Estado em 2026-11-22: árvore limpa, 103 testes OK, código em b6673db. Todo número aqui é pista datada: meça antes de
confiar (git status, git log -3, gh run list -R fbmoulin/kratos-stitch --limit 3,
python3 -m unittest discover -s tests, lsof -nP -iTCP:8730 -sTCP:LISTEN).

Próxima ação:
1. Se eu disser que vou usar o canvas: suba o servidor em segundo plano (uv run ferramentas/servidor.py, porta 8730),
   ligue o ouvinte da fila com a ferramenta Monitor (comando
   /Users/felipemoulin/Projetos/neo-stitch/ferramentas/ouvir.sh, timeout_ms 1800000, re-armar a cada expiração) e rode
   uv run ferramentas/neo.py pendentes. Siga .claude/skills/neo-stitch/SKILL.md para cada evento.
2. Senão, pergunte o que eu quero atacar da seção "Em aberto" do handoff; o de maior valor é a segunda revisão
   independente do commit d24826f e reabrir no navegador o upload de vídeo.

Já decidido, NÃO reabra:
- Licença: o autor (professor de um curso da ASIMOV Academy que eu faço) liberou o uso do repositório.
- O repositório kratos-stitch é público por decisão minha; o histórico foi varrido por segredos antes.
- Nada é enviado ao autor; o patch em rascunhos/ foi aposentado e não é mais regenerado.
- Geração paga só com o meu ok no chat, por pedido, com a estimativa na mensagem. Os tetos por pedido são zero de
  propósito: o gerador para na saída 3 e o pedido volta à fila como "aguarda seu ok".
- Minhas respostas curtas ("prossiga", "sugestão", "ok") valem como ok para o que você acabou de apresentar com valor.
  Pedido que eu envio sem texto não é pedido de variações: pergunte o que eu quero.
- Vídeo meu como referência vira um nó `referencia` cujo arquivo é a capa, mais um nó por segundo de vídeo (até 16).
- Título da tela é "Kratos Stitch"; a skill, as chaves do localStorage e o crédito ao original seguem "Neo Stitch".
- Não consertar: `.mudo.mp4` órfão em SIGTERM e `entradas_antes` em pedido com erro.

Já tentado e descartado:
- Estimativa do rascunho de imagem dentro da barra do cartão: não cabe; fica numa linha abaixo.
- Extração de quadros "tudo ou nada": recusava vídeos reais; hoje o instante sem quadro é pulado.
- Claude in Chrome para conferir o app: a extensão desconectou; use o Playwright MCP.

Método para mudança não trivial: spec com evidência medida → pre-mortem por um agente → teste antes do código →
mutação → conferir no navegador → revisão independente. Eu ratifico a spec antes de você codar.
```
