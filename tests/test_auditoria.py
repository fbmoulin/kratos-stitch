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
        for nome, valor in (('PROJETOS', self.raiz / 'projects'), ('FILA', self.raiz / 'fila.jsonl')):
            p = mock.patch.object(B, nome, valor)
            p.start()
            self.addCleanup(p.stop)
        B.PROJETOS.mkdir()


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
        self.assertEqual(set(B.galho(todos, a['img'])),
                         {a['p_3d'], a['mod'], a['p_vid'], a['vid'], a['p_ast'], a['ast'], a['p_pag'], a['da_pagina']})

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
