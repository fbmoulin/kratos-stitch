# /// script
# requires-python = ">=3.11"
# ///
"""Gera vídeos a partir de uma imagem (image-to-video) em um ou vários modelos do OpenRouter, em paralelo.

    uv run ferramentas/gerar_video.py <PEDIDO> --prompt-arquivo <txt> [--confirmado]        (modo do app: pedido de vídeo)
    uv run ferramentas/gerar_video.py --imagem <png> --saida <pasta> --prompt-arquivo <txt> [--modelos a,b,c | --modelos todos]
        [--duracao 6] [--resolucao 720p] [--confirmado]                                       (modo pasta: comparação avulsa)

- API assíncrona: POST /api/v1/videos → polling em /api/v1/videos/{id} → download em /videos/{id}/content.
- Para cada modelo usa a duração/resolução suportada mais próxima da pedida; áudio sempre desligado quando o modelo deixa.
- Grava <saida>/<modelo>.mp4, <saida>/<modelo>.jpg (1º quadro, se o ffmpeg existir) e <saida>/resultados.json
  (status, custo, tempo, parâmetros e erro de cada modelo). Falhas não são cobradas pelo OpenRouter.
- Teto: se a estimativa passar de $5, sai com código 3 (rode de novo com --confirmado depois do usuário dizer sim).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import base as B  # noqa: E402
from openrouter import chave, data_url, pedir  # noqa: E402

# modelos que não fazem image-to-video a partir de uma tela (avatar, edição/upscale de vídeo)
FORA = {'heygen/heygen-video-1', 'heygen/avatar-iv', 'black-forest-labs/flux-video-edit', 'black-forest-labs/flux-video-upscale',
        'runway/aleph-2'}


IMAGEM = {'.png', '.jpg', '.jpeg', '.webp'}


def catalogo_api(key: str) -> dict:
    return {m['id']: m for m in pedir('GET', '/videos/models', key)['data']}


def mais_perto(valor, opcoes):
    if not opcoes:
        return None
    if valor in opcoes:
        return valor
    if isinstance(valor, (int, float)):
        return min(opcoes, key=lambda o: (abs(o - valor), -o))
    ordem = ['480p', '720p', '768p', '1080p', '2K', '4K']
    alvo = ordem.index(valor) if valor in ordem else 1
    return min(opcoes, key=lambda o: abs((ordem.index(o) if o in ordem else 9) - alvo))


def estimar(m: dict, dur: int, res: str) -> float:
    """Custo aproximado em US$ (sem áudio). Por token (Seedance): ~w·h·24·s/1024 tokens."""
    s = {k: float(v) for k, v in (m.get('pricing_skus') or {}).items()}
    for k in (f'duration_seconds_without_audio_{res}', 'duration_seconds_without_audio', f'duration_seconds_{res}',
              f'image_to_video_duration_seconds_{res}', 'duration_seconds'):
        if k in s:
            return s[k] * dur
    for k in (f'cents_per_video_output_second_{res}', f'cents_per_second_output_{res}'):
        if k in s:
            return s[k] / 100 * dur + s.get('cents_per_image_input', 0) / 100
    if 'video_tokens_without_audio' in s or 'video_tokens' in s:
        px = {'480p': 854 * 480, '720p': 1280 * 720, '1080p': 1920 * 1080}.get(res, 1280 * 720)
        return px * 24 * dur / 1024 * s.get('video_tokens_without_audio', s.get('video_tokens', 0))
    return 0.12 * dur


def plano(m: dict, duracao: int, resolucao: str) -> dict:
    dur = mais_perto(duracao, m.get('supported_durations') or [])
    res = mais_perto(resolucao, m.get('supported_resolutions') or [])
    return {'modelo': m['id'], 'duracao': dur, 'resolucao': res, 'estimativa': round(estimar(m, dur or duracao, res or resolucao), 3),
            'audio_controlavel': m.get('generate_audio') is not None}


def sondar(arq: Path) -> dict | None:
    """{largura, altura, audio} do arquivo, pelo ffprobe (a API não diz o tamanho do que gerou). None sem o ffprobe ou se
    o arquivo não for um vídeo."""
    if not shutil.which('ffprobe'):
        return None
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height:stream_disposition=attached_pic',
                        '-of', 'json', str(arq)], capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=60)
    try:
        faixas = json.loads(r.stdout).get('streams') or []
    except ValueError:
        return None
    # a capa embutida também é uma faixa "de vídeo" (mjpeg), às vezes de outro tamanho: não é ela
    video = next((f for f in faixas if f.get('codec_type') == 'video' and f.get('width') and f.get('height')
                  and not (f.get('disposition') or {}).get('attached_pic')), None)
    if not video:
        return None
    return {'largura': video['width'], 'altura': video['height'], 'audio': any(f.get('codec_type') == 'audio' for f in faixas)}


def tirar_audio(arq: Path) -> None:
    """Tira a trilha de áudio sem recodificar o vídeo. Alguns modelos mandam áudio mesmo sem ser pedido (o catálogo não
    diz se dá para desligar), e ninguém o pediu: o app toca mudo. Se o ffmpeg falhar, o arquivo fica como veio."""
    if not shutil.which('ffmpeg'):
        return
    tmp = arq.with_suffix('.mudo.mp4')
    try:
        r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(arq), '-an', '-c', 'copy', str(tmp)],
                           capture_output=True, check=False, timeout=120)
        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
            os.replace(tmp, arq)
    finally:
        tmp.unlink(missing_ok=True)


def gerar_um(p: dict, prompt: str, url_img: str, proporcao: str, key: str, destino: Path, capa: Path | None) -> dict:
    """Um vídeo: cria o job, acompanha até terminar, baixa o .mp4 (e a capa, um quadro do meio, se houver ffmpeg)."""
    corpo = {'model': p['modelo'], 'prompt': prompt, 'aspect_ratio': proporcao,
             'frame_images': [{'type': 'image_url', 'image_url': {'url': url_img}, 'frame_type': 'first_frame'}]}
    if p['duracao']:
        corpo['duration'] = p['duracao']
    if p['resolucao']:
        corpo['resolution'] = p['resolucao']
    if p['audio_controlavel']:
        corpo['generate_audio'] = False
    r = dict(p, status='erro')
    t0 = time.time()
    try:
        job = pedir('POST', '/videos', key, corpo)
        r['job'] = job.get('id')
        fim = time.time() + 25 * 60
        st: dict = {}
        while time.time() < fim:
            time.sleep(8)
            st = pedir('GET', f'/videos/{job["id"]}', key)
            if st.get('status') in ('completed', 'failed', 'cancelled', 'expired'):
                break
        r['status'] = st.get('status') or 'tempo esgotado'
        r['custo'] = (st.get('usage') or {}).get('cost')
        if st.get('status') != 'completed':
            r['erro'] = json.dumps(st.get('error') or st, ensure_ascii=False)[:500]
        else:
            destino.write_bytes(pedir('GET', f'/videos/{job["id"]}/content?index=0', key, bruto=True))
            r['arquivo'] = destino.name
            try:   # o vídeo já está no disco (e pago): medir e tirar o áudio não podem derrubá-lo
                if info := sondar(destino):
                    r['largura'], r['altura'] = info['largura'], info['altura']
                    if info['audio']:
                        tirar_audio(destino)
            except (OSError, subprocess.SubprocessError):
                pass
            if capa and shutil.which('ffmpeg'):
                meio = max(0.5, (p['duracao'] or 6) / 2)
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(meio), '-i', str(destino), '-frames:v', '1', '-vf', 'scale=640:-2',
                                '-q:v', '4', str(capa)])
                r['capa'] = capa.name
    except Exception as e:  # noqa: BLE001
        r['erro'] = str(e)[:500]
    r['segundos'] = round(time.time() - t0, 1)
    print(f"{p['modelo']:40s} {r['status']:10s} ${r.get('custo') or 0:.3f} {r['segundos']}s {r.get('erro', '')[:120]}", flush=True)
    return r


def por_pedido(codigo: str, prompt: str, confirmado: bool) -> None:
    """Modo do app: lê o pedido de vídeo (modelos, duração, resolução, imagem de entrada), cria os nós de vídeo
    (placeholders) e pendura os resultados na árvore. Saída 3 = teto de custo (pergunte e rode com --confirmado)."""
    slug, pid = B.resolver_codigo(codigo)
    pedido = B.ler_no(slug, pid)
    if pedido.get('tipo') != 'pedido' or pedido.get('midia') != 'video':
        sys.exit(f'ERRO: {pid} não é um pedido de vídeo.')
    pasta = B.pasta(slug)
    # a 1ª entrada com imagem no disco: um nó, ou uma página IMG/vN (pelo print dela)
    img = next((f for e in pedido.get('entradas', []) if (f := B.arquivo_entrada(slug, e)) and f.suffix.lower() in IMAGEM), None)
    if not img:   # o pedido não vai ser atendido: volta como erro em vez de ficar "enviado"/"trabalhando"
        B.devolver_pedido(slug, pid, 'O pedido de vídeo precisa de uma imagem de entrada (a que ele tinha não existe mais).')
        sys.exit('ERRO: o pedido de vídeo precisa de uma imagem de entrada.')
    try:
        key = chave()
    except SystemExit as e:
        B.devolver_pedido(slug, pid, str(e.code))
        raise
    catalogo = catalogo_api(key)
    planos = [plano(catalogo[m], pedido.get('duracao') or 6, pedido.get('resolucao') or '720p') for m in pedido.get('modelos', []) if m in catalogo]
    if not planos:
        B.devolver_pedido(slug, pid, 'Nenhum modelo de vídeo válido no pedido.')
        sys.exit('ERRO: nenhum modelo válido no pedido.')
    total = sum(p['estimativa'] for p in planos)
    tetos = {**B.TETOS, **B.ler_projeto(slug).get('tetos', {})}
    hoje = B.custos(slug)['hoje']
    print(f'{pid}: {len(planos)} vídeos · estimativa ${total:.2f}')
    if not confirmado and (total > tetos['video_por_pedido_usd'] or hoje + total > tetos['diario_usd']):
        print(f'BLOQUEADO: estimativa ${total:.2f} (teto por pedido ${tetos["video_por_pedido_usd"]:.2f}; hoje ${hoje:.2f} de '
              f'${tetos["diario_usd"]:.2f}). Pergunte ao usuário e rode com --confirmado.')
        sys.exit(3)
    url_img = data_url(img)
    largura, altura = B.medidas(img) or (1280, 720)
    nossos = B.modelos_video(todos=True)  # os nomes curtos ("Hailuo 3"); o catálogo da API traz "MiniMax: H3"
    with B.travado(slug):
        B._soltar_orfaos(slug)   # um gerador que morreu não segura o pedido
        pedido = B.ler_no(slug, pid)
        if any((B.ler_json(B.caminho_no(slug, i)) or {}).get('gerando') for i in pedido.get('saidas') or []):
            sys.exit(f'ERRO: {pid} já tem vídeos sendo gerados (outra execução do gerar_video.py). Se ela morreu, solte o '
                     f'pedido com `neo.py erro {pid} "motivo"` e rode de novo.')
        ids = []
        for p in planos:
            nome = (nossos.get(p['modelo']) or {}).get('nome') or catalogo[p['modelo']]['name'].split(': ', 1)[-1]
            v = B.novo_no(slug, 'video', pedido=pid, modelo=p['modelo'], nome=nome, prompt=prompt, duracao=p['duracao'], resolucao=p['resolucao'], largura=largura, altura=altura, gerando=True)
            ids.append(v['id'])
        pedido.update(status='trabalhando', saidas=pedido.get('saidas', []) + ids, variacoes=[{'nome': 'vídeo', 'prompt': prompt}],
                      iniciado_em=B.agora(), gerador={'pid': os.getpid(), 'desde': B.agora(), 'saidas': ids})
        pedido.pop('erro', None)
        B.gravar_no(slug, pedido)

    vazio = 'Nenhum vídeo foi gerado (veja o erro em cada nó).'
    fechando = threading.Event()

    def ao_terminar(*_):
        # SIGTERM: fecha o pedido já e sai, sem esperar os vídeos em voo (o `finally` esperaria os workers por minutos)
        if fechando.is_set():
            return
        with B.travado(slug):
            B.fechar_pedido(slug, pid, ids, vazio)
        os._exit(143)
    anterior = signal.signal(signal.SIGTERM, ao_terminar)

    def um(par):
        vid, p = par
        r = gerar_um(p, prompt, url_img, '16:9' if largura >= altura else '9:16', key, pasta / 'videos' / f'{vid}.mp4', pasta / 'thumbs' / f'{vid}.jpg')
        with B.travado(slug):
            v = B.ler_json(B.caminho_no(slug, vid))
            if v:   # o usuário pode ter apagado o placeholder no meio
                v.pop('gerando', None)
                if r['status'] == 'completed' and r.get('arquivo') and (pasta / 'videos' / f'{vid}.mp4').exists():
                    v.pop('erro', None)
                    v.update(arquivo=f'videos/{vid}.mp4', thumb=f'thumbs/{vid}.jpg' if r.get('capa') else None, custo=r.get('custo'), segundos=r['segundos'])
                    if r.get('largura') and r.get('altura'):   # as do arquivo; sem o ffprobe, ficam as da imagem de origem
                        v.update(largura=r['largura'], altura=r['altura'])
                else:
                    v.update(erro=r.get('erro') or r['status'], custo=r.get('custo'))
                B.gravar_no(slug, v)
        return r

    (pasta / 'videos').mkdir(exist_ok=True)
    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(um, zip(ids, planos)))
    finally:   # também quando a geração é interrompida: o pedido fecha pelo que ficou no disco e nada segue "gerando"
        fechando.set()
        with B.travado(slug):
            ok, custo = B.fechar_pedido(slug, pid, ids, vazio)
        signal.signal(signal.SIGTERM, anterior)
    print(f'{pid}: {ok}/{len(ids)} vídeos · ${custo:.2f} · {", ".join(ids)}')
    sys.exit(0 if ok else 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('pedido', nargs='?', help='código de um pedido de vídeo do app (modo por pedido)')
    ap.add_argument('--imagem')
    ap.add_argument('--saida')
    ap.add_argument('--prompt')
    ap.add_argument('--prompt-arquivo')
    ap.add_argument('--modelos', default='google/veo-3.1-lite')
    ap.add_argument('--duracao', type=int, default=6)
    ap.add_argument('--resolucao', default='720p')
    ap.add_argument('--proporcao', default='16:9')
    ap.add_argument('--confirmado', action='store_true')
    a = ap.parse_args()

    prompt = a.prompt or Path(a.prompt_arquivo).read_text(encoding='utf-8').strip()
    if a.pedido:
        return por_pedido(a.pedido, prompt, a.confirmado)
    key = chave()
    catalogo = catalogo_api(key)
    if a.modelos == 'todos':
        ids = [i for i, m in catalogo.items() if i not in FORA and 'first_frame' in (m.get('supported_frame_images') or [])]
    else:
        ids = [x.strip() for x in a.modelos.split(',') if x.strip()]

    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    img = Path(a.imagem)
    url_img = data_url(img)

    planos = [plano(catalogo[i], a.duracao, a.resolucao) for i in ids]
    total = sum(p['estimativa'] for p in planos)
    print(f'{len(planos)} modelos · estimativa ${total:.2f}')
    if total > 5 and not a.confirmado:
        print('BLOQUEADO: passa de $5. Pergunte ao usuário e rode com --confirmado.')
        sys.exit(3)

    def um(p: dict) -> dict:
        nome = p['modelo'].replace('/', '__')
        return gerar_um(p, prompt, url_img, a.proporcao, key, saida / f'{nome}.mp4', saida / f'{nome}.jpg')

    with ThreadPoolExecutor(max_workers=8) as ex:
        resultados = list(ex.map(um, planos))
    (saida / 'resultados.json').write_text(json.dumps({'prompt': prompt, 'imagem': str(img), 'resultados': resultados}, indent=1, ensure_ascii=False))
    ok = [r for r in resultados if r['status'] == 'completed']
    print(f'{len(ok)}/{len(resultados)} prontos · custo ${sum(r.get("custo") or 0 for r in resultados):.2f}')


if __name__ == '__main__':
    main()
