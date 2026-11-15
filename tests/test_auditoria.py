"""Testes das correções da auditoria de 2026-11-14 (só biblioteca padrão).

    python3 -m unittest discover -s tests -v      (ou: uvx pytest tests)

Todo teste roda num projects/ temporário, e os de geração trocam `gerar.chave` e `gerar.pedir`: nada aqui fala com o
OpenRouter nem toca nos projetos de verdade.
"""
from __future__ import annotations

import base64
import contextlib
import http.client
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ferramentas'))
import base as B  # noqa: E402
import gerar  # noqa: E402
import neo  # noqa: E402
import servidor  # noqa: E402

PNG = base64.b64encode(base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')).decode()


class Isolado(unittest.TestCase):
    """Aponta B.PROJETOS e B.FILA para uma pasta temporária."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)
        for nome, valor in (('RAIZ', self.raiz), ('PROJETOS', self.raiz / 'projects'), ('FILA', self.raiz / 'fila.jsonl')):
            p = mock.patch.object(B, nome, valor)
            p.start()
            self.addCleanup(p.stop)
        B.PROJETOS.mkdir()
        if not shutil.which('sips'):   # fora do macOS (o CI roda em Linux): miniatura e medidas sem o sips
            def miniatura(origem, destino, lado=640):
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origem, destino)
            for nome, valor in (('miniatura', miniatura), ('medidas', lambda arquivo: (1, 1))):
                p = mock.patch.object(B, nome, valor)
                p.start()
                self.addCleanup(p.stop)


class Prefixo(Isolado):
    def test_nomes_curtos_viram_projeto_completo(self):
        for nome in ('IA', 'X', 'Oi', '42'):
            p = B.criar_projeto(nome)
            self.assertRegex(p['prefixo'], r'^[A-Z]{3}$', nome)
            self.assertEqual([n['tipo'] for n in B.nos(p['slug'])], ['brief', 'tela'], nome)

    def test_prefixos_nao_se_repetem(self):
        prefixos = [B.criar_projeto('IA')['prefixo'] for _ in range(40)]
        self.assertEqual(len(set(prefixos)), 40)
        for p in prefixos:
            self.assertRegex(p, r'^[A-Z]{3}$')

    def test_prefixo_invalido_nao_deixa_projeto_pela_metade(self):
        with self.assertRaises(ValueError):
            B.criar_projeto('Loja', prefixo='ab1')
        self.assertEqual(list(B.PROJETOS.iterdir()), [])

    def test_prefixo_de_outro_projeto_e_recusado(self):
        B.criar_projeto('JarvisOS', prefixo='JAR')
        with self.assertRaises(ValueError):
            B.criar_projeto('Jarvis 2', prefixo='jar')
        self.assertEqual(B.projetos(), ['jarvisos'])

    def test_nome_normal_nao_mudou(self):
        self.assertEqual(B.criar_projeto('Loja')['prefixo'], 'LOJ')
        self.assertEqual(B.criar_projeto('JarvisOS', prefixo='JAR')['prefixo'], 'JAR')


def arvore_3d(slug: str) -> dict:
    """tela → pedido → IMAGEM → {pedido 3D → MODELO; pedido de vídeo → VÍDEO → pedido de assets → ASSET}."""
    tela = next(n['id'] for n in B.nos(slug) if n['tipo'] == 'tela')
    with B.travado(slug):
        def par(tipo, custo, **pedido):
            ped = B.novo_no(slug, 'pedido', tela=tela, status='concluido', **pedido)
            no = B.novo_no(slug, tipo, pedido=ped['id'], nome=tipo, custo=custo)
            ped['saidas'] = [no['id']]
            B.gravar_no(slug, ped)
            return ped['id'], no['id']
        p_img, img = par('imagem', 0.14)
        p_3d, mod = par('modelo', 0.40, entradas=[img], midia='3d')
        p_vid, vid = par('video', 0.50, entradas=[img], midia='video')
        p_ast, ast = par('imagem', 0.02, entradas=[vid])
        p_pag, da_pagina = par('imagem', 0.14, entradas=[f'{img}/v1'])   # pedido que parte do print de uma página
    return dict(tela=tela, p_img=p_img, img=img, p_3d=p_3d, mod=mod, p_vid=p_vid, vid=vid, p_ast=p_ast, ast=ast,
                p_pag=p_pag, da_pagina=da_pagina)


class Modelo3D(Isolado):
    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Modelos')['slug']
        self.a = arvore_3d(self.slug)

    def test_custo_do_modelo_entra_no_total(self):
        self.assertEqual(B.custos(self.slug)['total'], 1.20)

    def test_galho_segue_a_arvore_do_app(self):
        a, todos = self.a, B.nos(self.slug)
        self.assertEqual(B.galho(todos, a['p_3d']), [a['mod']])
        self.assertEqual(set(B.galho(todos, a['vid'])), {a['p_ast'], a['ast']})
        # o pedido que parte de uma página (p_pag) pende da tela: não sai junto com a imagem
        self.assertEqual(set(B.galho(todos, a['img'])), {a['p_3d'], a['mod'], a['p_vid'], a['vid'], a['p_ast'], a['ast']})
        self.assertIn(a['p_pag'], B.galho(todos, a['tela']))

    def test_galho_de_tela_e_de_referencia_nao_mudou(self):
        slug = B.criar_projeto('Refs')['slug']
        tela = next(n['id'] for n in B.nos(slug) if n['tipo'] == 'tela')
        with B.travado(slug):
            ref = B.novo_no(slug, 'referencia', tela=tela)                       # sem posição: abre o galho
            solta = B.novo_no(slug, 'referencia', tela=tela, pos={'x': 1, 'y': 1})  # com posição: fica solta
            p_ref = B.novo_no(slug, 'pedido', tela=tela, entradas=[ref['id']])
            p_tela = B.novo_no(slug, 'pedido', tela=tela, entradas=[solta['id']])
            img = B.novo_no(slug, 'imagem', pedido=p_tela['id'])
        todos = B.nos(slug)
        self.assertEqual(set(B.galho(todos, tela)), {ref['id'], p_ref['id'], p_tela['id'], img['id'], solta['id']})
        self.assertEqual(B.galho(todos, ref['id']), [p_ref['id']])
        self.assertEqual(set(B.galho(todos, p_tela['id'])), {img['id'], solta['id']})


class Api(Isolado):
    """O servidor de verdade, numa porta livre, sobre o projects/ temporário."""

    def setUp(self):
        super().setUp()
        self.srv = servidor.Servidor(('127.0.0.1', 0), servidor.Handler)
        self.porta = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        silencio = mock.patch.object(servidor.Handler, 'log_message', lambda *a, **k: None)
        silencio.start()
        self.addCleanup(silencio.stop)

    def pedir(self, metodo, caminho, corpo=None, **cabecalhos):
        c = http.client.HTTPConnection('127.0.0.1', self.porta, timeout=10)
        cab = {'Content-Type': 'application/json', **cabecalhos} if corpo is not None else cabecalhos
        c.request(metodo, caminho, body=json.dumps(corpo) if corpo is not None else None, headers=cab)
        r = c.getresponse()
        dados = json.loads(r.read() or b'{}')
        c.close()
        return r.status, dados


class Origem(Api):
    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Loja')['slug']
        self.nos_url = f'/api/projetos/{self.slug}/nos'
        self.pedido = {'tipo': 'pedido', 'tela': 'LOJ-002', 'intencao': 'teste'}

    def test_outro_site_nao_escreve(self):
        antes = len(B.nos(self.slug))
        self.assertEqual(self.pedir('POST', self.nos_url, self.pedido, Origin='https://evil.test')[0], 403)
        # sem preflight: o navegador manda text/plain direto, e o servidor lia o corpo como JSON
        self.assertEqual(self.pedir('POST', self.nos_url, self.pedido, Origin='https://evil.test',
                                    **{'Content-Type': 'text/plain;x=json'})[0], 403)
        status, _ = self.pedir('POST', self.nos_url, self.pedido)
        self.assertEqual(status, 200)
        pid = B.nos(self.slug)[-1]['id']
        self.assertEqual(self.pedir('POST', f'{self.nos_url}/{pid}/enviar', Origin='https://evil.test')[0], 403)
        self.assertEqual(len(B.nos(self.slug)), antes + 1)
        self.assertFalse(B.FILA.exists())

    def test_host_forjado_nao_le(self):
        self.assertEqual(self.pedir('GET', '/api/projetos', Host='evil.test')[0], 403)

    def test_arquivos_dos_projetos_tambem_recusam_host_forjado(self):
        arq = f'/projects/{self.slug}/projeto.json'
        self.assertEqual(self.pedir('GET', arq, Host='evil.test')[0], 403)
        self.assertEqual(self.pedir('GET', arq)[0], 200)

    def test_o_app_e_o_curl_continuam_passando(self):
        for origem in (f'http://localhost:{self.porta}', 'http://localhost:5173', 'http://127.0.0.1:5173', None):
            cab = {'Origin': origem} if origem else {}
            self.assertEqual(self.pedir('POST', self.nos_url, self.pedido, **cab)[0], 200, origem)
        self.assertEqual(self.pedir('GET', '/api/projetos')[0], 200)
        self.assertEqual(self.pedir('GET', '/api/projetos', Host=f'localhost:{self.porta}')[0], 200)

    def test_conexao_segue_valida_depois_do_403(self):
        c = http.client.HTTPConnection('127.0.0.1', self.porta, timeout=10)
        corpo = json.dumps(self.pedido)
        c.request('POST', self.nos_url, body=corpo, headers={'Content-Type': 'application/json', 'Origin': 'https://evil.test'})
        r = c.getresponse()
        r.read()
        self.assertEqual(r.status, 403)
        c.request('GET', '/api/projetos')
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        r.read()
        c.close()


class Modelo3DPeloApp(Api):
    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Modelos')['slug']
        self.a = arvore_3d(self.slug)
        self.url = f'/api/projetos/{self.slug}/nos'

    def test_descartar_e_mover_o_modelo_grava(self):
        status, _ = self.pedir('PATCH', f'{self.url}/{self.a["mod"]}', {'estado': 'descartada', 'desloc': {'x': 50, 'y': 60}})
        self.assertEqual(status, 200)
        no = B.ler_no(self.slug, self.a['mod'])
        self.assertEqual((no['estado'], no['desloc']), ('descartada', {'x': 50, 'y': 60}))

    def test_apagar_o_pedido_3d_leva_o_modelo_e_o_desfazer_traz_de_volta(self):
        a = self.a
        antes = sorted(n['id'] for n in B.nos(self.slug))
        status, dados = self.pedir('DELETE', f'{self.url}/{a["p_3d"]}')
        self.assertEqual((status, sorted(dados['apagados'])), (200, sorted([a['p_3d'], a['mod']])))
        self.assertEqual(sorted(n['id'] for n in B.nos(self.slug)), sorted(set(antes) - {a['p_3d'], a['mod']}))
        self.assertEqual(self.pedir('POST', f'{self.url}/{a["p_3d"]}/restaurar')[0], 200)
        self.assertEqual(sorted(n['id'] for n in B.nos(self.slug)), antes)


def pagina_com_print(slug: str, img: str, versao: str = 'v1') -> str:
    d = B.pasta(slug) / 'impl' / img / versao
    d.mkdir(parents=True)
    (d / 'captura.png').write_bytes(base64.b64decode(PNG))
    return f'{img}/{versao}'


class Entradas(Api):
    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Modelos')['slug']
        self.a = arvore_3d(self.slug)
        with B.travado(self.slug):
            self.ref = B.novo_no(self.slug, 'referencia', tela=self.a['tela'], pos={'x': 0, 'y': 0})['id']
        self.pagina = pagina_com_print(self.slug, self.a['img'])
        self.url = f'/api/projetos/{self.slug}/nos'
        self.validas = [self.a['img'], self.ref, self.pagina]
        self.ruins = ['NAO-999', '../../etc', 42, self.a['mod'], f'{self.a["img"]}/v9', self.a['tela']]

    def test_criar_aceita_imagem_referencia_e_pagina_com_print(self):
        status, no = self.pedir('POST', self.url, {'tipo': 'pedido', 'entradas': [*self.ruins, *self.validas]})
        self.assertEqual((status, no['entradas'], no['tela']), (200, self.validas, self.a['tela']))

    def test_pedido_so_da_pagina_herda_a_tela_da_imagem(self):
        status, no = self.pedir('POST', self.url, {'tipo': 'pedido', 'entradas': [self.pagina]})
        self.assertEqual((status, no['entradas'], no['tela']), (200, [self.pagina], self.a['tela']))

    def test_mudar_valida_como_criar(self):
        _, no = self.pedir('POST', self.url, {'tipo': 'pedido', 'tela': self.a['tela']})
        status, no = self.pedir('PATCH', f'{self.url}/{no["id"]}', {'entradas': [*self.ruins, *self.validas, self.ref]})
        self.assertEqual((status, no['entradas']), (200, self.validas))
        self.assertEqual(B.ler_no(self.slug, no['id'])['entradas'], self.validas)


    def test_mudar_mantem_o_que_o_pedido_ja_tinha(self):
        with B.travado(self.slug):   # como o `neo.py pedido --entradas IMG,VIDEO`
            pid = B.novo_no(self.slug, 'pedido', tela=self.a['tela'], entradas=[self.a['img'], self.a['vid']])['id']
        status, no = self.pedir('PATCH', f'{self.url}/{pid}', {'entradas': [self.a['vid'], self.a['mod']]})   # tirou a imagem
        self.assertEqual((status, no['entradas']), (200, [self.a['vid']]))


class ErrosDoServidor(Api):
    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Loja')['slug']

    def test_corpo_que_nao_e_objeto(self):
        self.assertEqual(self.pedir('POST', '/api/projetos', [1])[0], 422)

    def test_projeto_inexistente_nao_ganha_pasta(self):
        self.assertEqual(self.pedir('PATCH', '/api/projetos/fantasma', {'nome': 'x'})[0], 404)
        self.assertEqual(self.pedir('PUT', '/api/projetos/fantasma/brief', {'texto': 'x'})[0], 404)
        self.assertFalse((B.PROJETOS / 'fantasma').exists())

    def cru(self, metodo, caminho, **cabecalhos):
        c = http.client.HTTPConnection('127.0.0.1', self.porta, timeout=10)
        c.request(metodo, caminho, headers=cabecalhos)
        r = c.getresponse()
        corpo = r.read()
        c.close()
        return r, corpo

    def test_range(self):
        arq = f'/projects/{self.slug}/brief.md'
        tamanho = (B.pasta(self.slug) / 'brief.md').stat().st_size
        r, corpo = self.cru('GET', arq, Range='bytes=2-4')
        self.assertEqual((r.status, len(corpo), r.getheader('Content-Range')), (206, 3, f'bytes 2-4/{tamanho}'))
        r, _ = self.cru('GET', arq, Range='bytes=999999-')
        self.assertEqual((r.status, r.getheader('Content-Range')), (416, f'bytes */{tamanho}'))
        r, corpo = self.cru('GET', arq)
        self.assertEqual((r.status, len(corpo)), (200, tamanho))

    def test_head_nao_serve_a_raiz_do_repositorio(self):
        for caminho in ('/ferramentas/base.py', '/README.md', '/.env'):
            self.assertEqual(self.cru('HEAD', caminho)[0].status, 405, caminho)


class Video(Isolado):
    def test_entrada_de_pagina_usa_o_print(self):
        import gerar_video
        slug = B.criar_projeto('Modelos')['slug']
        a = arvore_3d(slug)
        pagina = pagina_com_print(slug, a['img'])
        with B.travado(slug):
            lixo = B.novo_no(slug, 'imagem', pedido=a['p_img'], arquivo='images/sumiu.png')['id']   # arquivo que não existe mais
            pid = B.novo_no(slug, 'pedido', tela=a['tela'], entradas=[lixo, pagina], midia='video', modelos=['m/x'])['id']
        visto = {}

        def gerar_um(p, prompt, url_img, *resto):
            visto['url'] = url_img
            return dict(p, status='failed', erro='teste', segundos=0)
        catalogo = {'m/x': {'id': 'm/x', 'name': 'M: X', 'supported_durations': [4], 'supported_resolutions': ['720p']}}
        with mock.patch.object(gerar_video, 'chave', lambda: 'chave-de-teste'), \
                mock.patch.object(gerar_video, 'catalogo_api', lambda key: catalogo), \
                mock.patch.object(gerar_video, 'gerar_um', gerar_um), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            gerar_video.por_pedido(pid, 'prompt', confirmado=False)
        self.assertTrue(visto['url'].startswith('data:image/png;base64,'))
        self.assertEqual(B.ler_no(slug, pid)['status'], 'erro')   # fechou (o vídeo de teste "falhou"), não ficou preso


class Gerar(Isolado):
    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Loja')['slug']
        with B.travado(self.slug):
            self.pid = B.novo_no(self.slug, 'pedido', tela='LOJ-002', intencao='teste')['id']
        self.chamadas = []

    def rodar(self, *args, chave=None, pedir=None):
        def pedir_ok(*a, **k):
            self.chamadas.append(a)
            return {'data': [{'b64_json': PNG}], 'usage': {'cost': 0.14}}
        saida = io.StringIO()
        with mock.patch.object(gerar, 'chave', chave or (lambda: 'chave-de-teste')), \
                mock.patch.object(gerar, 'pedir', pedir or pedir_ok), \
                mock.patch.object(sys, 'argv', ['gerar.py', self.pid, *args]), \
                contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            try:
                gerar.main()
            except SystemExit as e:
                return e.code, saida.getvalue()
        return 0, saida.getvalue()

    def estado(self):
        return {n['id']: n for n in B.nos(self.slug)}

    def test_sem_chave_nada_e_criado(self):
        def sem_chave():
            sys.exit('ERRO: defina OPENROUTER_API_KEY')
        codigo, _ = self.rodar('--prompt', 'a', '--prompt', 'b', chave=sem_chave)
        self.assertTrue(codigo)
        nos = self.estado()
        self.assertEqual([n['tipo'] for n in nos.values()], ['brief', 'tela', 'pedido'])
        self.assertEqual((nos[self.pid]['status'], nos[self.pid]['saidas']), ('rascunho', []))
        self.assertEqual(self.chamadas, [])

    def test_sem_chave_o_pedido_pego_volta_como_erro(self):
        def sem_chave():
            sys.exit('ERRO: defina OPENROUTER_API_KEY')
        neo.alterar(self.slug, self.pid, status='trabalhando')   # o `neo.py pegar`
        self.rodar('--prompt', 'a', chave=sem_chave)
        ped = self.estado()[self.pid]
        self.assertEqual((ped['status'], ped['saidas']), ('erro', []))
        self.assertIn('OPENROUTER_API_KEY', ped['erro'])

    def test_placeholder_apagado_no_meio_nao_prende_o_pedido(self):
        apagou = threading.Lock()

        def pedir_e_apaga(*a, **k):
            if apagou.acquire(blocking=False):   # uma vez só: o usuário apaga um placeholder enquanto as imagens são geradas
                B.caminho_no(self.slug, next(n['id'] for n in B.nos(self.slug) if n.get('gerando'))).unlink()
            return {'data': [{'b64_json': PNG}], 'usage': {'cost': 0.14}}
        codigo, saida = self.rodar('--prompt', 'a', '--prompt', 'b', pedir=pedir_e_apaga)
        nos = self.estado()
        self.assertEqual(nos[self.pid]['status'], 'concluido', saida)
        self.assertFalse([n['id'] for n in nos.values() if n.get('gerando')])

    def test_gera_e_fecha_o_pedido(self):
        neo.alterar(self.slug, self.pid, status='trabalhando')   # o que o `neo.py pegar` faz antes do gerar.py
        codigo, saida = self.rodar('--prompt', 'a', '--prompt', 'b')
        self.assertEqual(codigo, 0, saida)
        nos = self.estado()
        ped = nos[self.pid]
        self.assertEqual((ped['status'], len(ped['saidas']), ped['custo']), ('concluido', 2, 0.28))
        for i in ped['saidas']:
            self.assertNotIn('gerando', nos[i])
            self.assertTrue((B.pasta(self.slug) / nos[i]['arquivo']).exists())
        self.assertEqual(len(self.chamadas), 2)

    def test_nao_roda_duas_vezes_ao_mesmo_tempo(self):
        with B.travado(self.slug):   # outra execução no meio do caminho
            img = B.novo_no(self.slug, 'imagem', pedido=self.pid, gerando=True)
            ped = B.ler_no(self.slug, self.pid)
            ped.update(status='trabalhando', saidas=[img['id']])
            B.gravar_no(self.slug, ped)
        codigo, saida = self.rodar('--prompt', 'a')
        self.assertTrue(codigo)
        self.assertIn('neo.py erro', str(codigo) + saida)
        self.assertEqual(self.estado()[self.pid]['saidas'], [img['id']])
        self.assertEqual(self.chamadas, [])

    def test_interrompido_nao_deixa_nada_gerando(self):
        def cai(*a, **k):
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.rodar('--prompt', 'a', '--prompt', 'b', pedir=cai)
        nos = self.estado()
        self.assertEqual(nos[self.pid]['status'], 'erro')
        self.assertEqual(len(nos[self.pid]['saidas']), 2)
        for i in nos[self.pid]['saidas']:
            self.assertNotIn('gerando', nos[i])
            self.assertTrue(nos[i].get('erro'))

    def test_neo_erro_solta_os_placeholders_presos(self):
        with B.travado(self.slug):
            img = B.novo_no(self.slug, 'imagem', pedido=self.pid, gerando=True)
            ped = B.ler_no(self.slug, self.pid)
            ped.update(status='trabalhando', saidas=[img['id']])
            B.gravar_no(self.slug, ped)
        with mock.patch.object(sys, 'argv', ['neo.py', 'erro', self.pid, 'sem chave']), contextlib.redirect_stdout(io.StringIO()):
            neo.main()
        nos = self.estado()
        self.assertEqual(nos[self.pid]['status'], 'erro')
        self.assertNotIn('gerando', nos[img['id']])
        self.assertTrue(nos[img['id']].get('erro'))


if __name__ == '__main__':
    unittest.main()
