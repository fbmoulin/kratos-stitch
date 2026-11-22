# Neo Stitch

Canvas local para explorar interfaces: imagem → vídeo → HTML vivo. **Antes de qualquer trabalho no canvas, leia o
[AGENTS.md](AGENTS.md)** (as regras e os comandos, iguais para todo agente) e, para uma página HTML, o
[docs/AGENTES.md](docs/AGENTES.md). Como operar o canvas (fila, prompts, geração): skill `neo-stitch`
(`.claude/skills/neo-stitch/SKILL.md`). Decisões e escopo: [specs.md](specs.md).

## Estrutura

- `ferramentas/` — Python só com biblioteca padrão, rodado com `uv run`:
  `servidor.py` (API + arquivos + app compilado, porta 8730) · `neo.py` (o lado do Claude: fila, contexto, direções, estados, registro de design systems) ·
  `gerar.py` (OpenRouter /images, N em paralelo, várias referências) · `gerar_video.py` (OpenRouter /videos, um vídeo por
  modelo) · `openrouter.py` (cliente HTTP e a chave) · `pagina_videos.py` (página de comparação avulsa) · `ouvir.sh` (o Monitor
  da fila) · `importar_jarvis.py` (import do 20-jarvisOS) · `impl.py` (implementações vídeo → HTML por qualquer agente: reservar a vN,
  reportar etapas, registrar assets e modelos 3D, parar para aprovação com `aguardar`, terminar; spec em `docs/AGENTES.md`) · `base.py` (caminhos, trava, nós,
  códigos, custos, avanços, vistas).
- `app/` — Vite + React + React Flow (`@xyflow/react`). Dev: `npm run dev` (porta 5173, repassa /api e /projects para 8730).
  Produção: `npm run build` → `app/dist`, servido pelo `servidor.py` (que recompila ao iniciar se `app/src` for mais novo).
- `projects/<slug>/` — os dados (um JSON por nó, imagens, vídeos, modelos 3D em models/, thumbs, refs, impl/, design systems em ds/, brief.md, lixeira/). Não versionar.
- `docs/` — o que o README mostra (demo, evolução imagem → vídeo → HTML) e o guia de uso (`docs/USO.md`).
- `fila.jsonl` — fila append-only que o app escreve e o Claude ouve (`tail -F`).
- `tests/` — testes do servidor e dos scripts (só biblioteca padrão): `python3 -m unittest discover -s tests`. Rodam num
  `projects/` temporário e sem chamar o OpenRouter. Rode antes de commitar qualquer mudança em `ferramentas/`.

## Regras

- Nunca apague imagens nem nós com linhagem: descarte (estado) ou mova para `lixeira/`.
- Toda escrita em nó passa por `base.travado(slug)` + `gravar_json` (o app e os scripts escrevem ao mesmo tempo).
- O app é tema claro e minimalista: ícones com `title`, sem texto onde um componente se explica.
- A chave `OPENROUTER_API_KEY` vem de `~/.env` (ou `.env` aqui) — nunca imprima nem commite.
- O servidor é só local: toda rota `/api` e `/projects` passa por `so_do_app` (Host e Origin locais). Uma rota nova não
  pode escapar disso.
- Um tipo de nó novo entra em todos os lugares que listam tipos: `TIPOS_NO`, `custos()` e `galho()` (`base.py`),
  `CAMPOS_APP` (`servidor.py`) e `arvore()` (`app/src/layout.ts`). O `galho()` tem de seguir a `arvore()`.
- Quem gera (`gerar.py`, `gerar_video.py`) deixa `gerador: {pid, desde, saidas}` no pedido e o fecha com
  `base.fechar_pedido`; um gerador novo segue o mesmo contrato, senão um pedido morto fica preso.
- No app, mudar ou apagar vários nós é um `mudarVarios` / `apagarVarios` (um pedido ao servidor, um passo de desfazer),
  não um laço de `mudar`.

## Regras deste clone (Kratos Stitch, desde 2026-11-22)

- Geração paga (`gerar.py`, `gerar_video.py`) só com o ok do dono no chat, por pedido, com a estimativa na pergunta. Os
  tetos por pedido em `base.TETOS` são zero de propósito: o gerador sai com código 3 e `B.aguardar_ok` devolve o pedido à
  fila. `--confirmado` vale para o pedido que recebeu o sim, não para os seguintes.
- Os testes rodam com tetos folgados (`Isolado.setUp` troca `B.TETOS`); só `PortaoDeGasto` usa os zeros de verdade.
- Push só para o remoto `kratos` (`fbmoulin/kratos-stitch`, público), no branch `correcoes-auditoria`. Nada para
  `origin`, que é o repositório do autor: nem push, nem issue, nem PR.
- O limite de corpo (`LIMITE_CORPO`, 200 MB) é conferido em `Handler.api` antes de ler; quem responde sem ler o corpo
  fecha a conexão (`close_connection`), senão o que sobrou é atendido como outra requisição.
- Referência que é vídeo: o `arquivo` do nó é a capa (jpg) e o vídeo fica em `video`; quem lê `arquivo` de uma
  referência continua recebendo uma imagem. Não troque isso sem rever todos os leitores.
- O servidor não recarrega Python: depois de mexer em `ferramentas/`, reinicie o processo da 8730.
- Estado e decisões: o handoff mais novo em `docs/handoff/`.
