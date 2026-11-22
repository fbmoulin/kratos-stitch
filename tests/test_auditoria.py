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
import os
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


TETOS_DO_CLONE = dict(B.TETOS)   # os de verdade (zero: todo pedido pago para na saída 3); só o PortaoDeGasto roda com eles
TETOS_FOLGADOS = {'imagens_por_pedido': 6, 'diario_usd': 20.0, 'video_por_pedido_usd': 2.0}


class Isolado(unittest.TestCase):
    """Aponta B.PROJETOS e B.FILA para uma pasta temporária. Os projetos nascem com tetos folgados, para os testes que
    geram sem --confirmado exercitarem o gerador e não o portão."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)
        for nome, valor in (('RAIZ', self.raiz), ('PROJETOS', self.raiz / 'projects'), ('FILA', self.raiz / 'fila.jsonl'),
                            ('TETOS', dict(TETOS_FOLGADOS))):
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


class EmLote(Api):
    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Modelos')['slug']
        self.a = arvore_3d(self.slug)
        self.url = f'/api/projetos/{self.slug}/nos'

    def test_mudar_varios(self):
        a = self.a
        status, nos = self.pedir('PATCH', self.url, {a['img']: {'recolhido': True, 'escondidos': []}, a['vid']: {'estado': 'descartada'}})
        self.assertEqual((status, [n['id'] for n in nos]), (200, [a['img'], a['vid']]))
        self.assertTrue(B.ler_no(self.slug, a['img'])['recolhido'])
        self.assertEqual(B.ler_no(self.slug, a['vid'])['estado'], 'descartada')

    def test_mudar_varios_e_tudo_ou_nada(self):
        a = self.a
        for ruim in ({a['vid']: {'estado': 'inexistente'}}, {'NAO-999': {'recolhido': True}}, {a['p_3d']: {'intencao': 'já foi concluído'}},
                     {f'{a["img"]}/v1': {'desloc': None}}, {a['vid']: 'isto não é um objeto'}):
            status, _ = self.pedir('PATCH', self.url, {a['img']: {'recolhido': True}, **ruim})
            self.assertIn(status, (404, 422), ruim)
            self.assertFalse(B.ler_no(self.slug, a['img']).get('recolhido'), ruim)

    def test_apagar_varios_e_um_lote_so(self):
        a = self.a
        antes = sorted(n['id'] for n in B.nos(self.slug))
        status, dados = self.pedir('POST', f'{self.url}/apagar', {'ids': [a['p_3d'], a['p_vid'], a['p_3d']]})
        some = {a['p_3d'], a['mod'], a['p_vid'], a['vid'], a['p_ast'], a['ast']}
        self.assertEqual((status, set(dados['apagados'])), (200, some))
        self.assertEqual(len(dados['apagados']), len(some))
        self.assertEqual(sorted(n['id'] for n in B.nos(self.slug)), sorted(set(antes) - some))
        self.assertEqual(len(list((B.pasta(self.slug) / 'lixeira').iterdir())), 1)
        self.assertEqual(self.pedir('POST', f'{self.url}/{a["p_3d"]}/restaurar')[0], 200)
        self.assertEqual(sorted(n['id'] for n in B.nos(self.slug)), antes)

    def test_apagar_varios_recusa_o_lote_inteiro(self):
        a = self.a
        antes = sorted(n['id'] for n in B.nos(self.slug))
        brief = next(n['id'] for n in B.nos(self.slug) if n['tipo'] == 'brief')
        neo.alterar(self.slug, a['p_vid'], status='trabalhando')
        for ids in ([a['p_3d'], brief], [a['p_3d'], a['p_vid']], [a['p_3d'], 'NAO-999'], []):
            self.assertIn(self.pedir('POST', f'{self.url}/apagar', {'ids': ids})[0], (404, 422), ids)
            self.assertEqual(sorted(n['id'] for n in B.nos(self.slug)), antes, ids)


class EntradasDeRascunho(Api):
    """Apagar tira dos rascunhos que ficam as entradas que saíram; restaurar tem de devolvê-las, na ordem."""

    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Modelos')['slug']
        self.a = a = arvore_3d(self.slug)
        self.url = f'/api/projetos/{self.slug}/nos'
        with B.travado(self.slug):   # sai da imagem; o asset e o modelo 3D entram como referências secundárias
            self.ref = B.novo_no(self.slug, 'referencia', tela=a['tela'], pos={'x': 0, 'y': 0})['id']
            self.rasc = B.novo_no(self.slug, 'pedido', tela=a['tela'], entradas=[a['img'], a['ast'], self.ref, a['vid']])['id']

    def entradas(self):
        return B.ler_no(self.slug, self.rasc)['entradas']

    def apagar(self, *ids):
        status, _ = self.pedir('POST', f'{self.url}/apagar', {'ids': list(ids)})
        self.assertEqual(status, 200)

    def restaurar(self, id_):
        self.assertEqual(self.pedir('POST', f'{self.url}/{id_}/restaurar')[0], 200)

    def test_restaurar_devolve_as_entradas_na_ordem(self):
        a = self.a
        self.apagar(a['p_vid'])   # leva o vídeo e, com ele, o pedido de assets e o asset
        self.assertEqual(self.entradas(), [a['img'], self.ref])
        self.restaurar(a['p_vid'])
        self.assertEqual(self.entradas(), [a['img'], a['ast'], self.ref, a['vid']])

    def test_o_que_o_usuario_mudou_no_meio_fica(self):
        a = self.a
        self.apagar(a['p_ast'])
        with B.travado(self.slug):
            outra = B.novo_no(self.slug, 'imagem', pedido=a['p_img'])['id']
        # pelo app: tirou a referência e ligou outra imagem enquanto o asset estava na lixeira
        self.assertEqual(self.pedir('PATCH', f'{self.url}/{self.rasc}', {'entradas': [a['img'], a['vid'], outra]})[0], 200)
        self.restaurar(a['p_ast'])
        self.assertEqual(self.entradas(), [a['img'], a['ast'], a['vid'], outra])

    def test_pedido_ja_enviado_nao_e_mexido(self):
        a = self.a
        self.apagar(a['p_ast'])
        neo.alterar(self.slug, self.rasc, status='enviado')
        self.restaurar(a['p_ast'])
        self.assertEqual(self.entradas(), [a['img'], self.ref, a['vid']])

    def test_rascunho_apagado_no_meio_nao_quebra_o_restaurar(self):
        a = self.a
        self.apagar(a['p_ast'])
        self.apagar(self.rasc)
        self.restaurar(a['p_ast'])
        self.assertTrue(B.caminho_no(self.slug, a['ast']).exists())
        self.restaurar(self.rasc)
        self.assertEqual(self.entradas(), [a['img'], a['ast'], self.ref, a['vid']])   # o asset voltou antes dele: entra de novo

    def test_lotes_restaurados_fora_de_ordem_mantem_a_ordem_das_entradas(self):
        a = self.a
        self.apagar(a['p_ast'])      # sai o asset
        self.apagar(self.ref)        # depois a referência
        self.assertEqual(self.entradas(), [a['img'], a['vid']])
        self.restaurar(a['p_ast'])   # volta primeiro o que saiu primeiro
        self.assertEqual(self.entradas(), [a['img'], a['ast'], a['vid']])
        self.restaurar(self.ref)
        self.assertEqual(self.entradas(), [a['img'], a['ast'], self.ref, a['vid']])
        self.assertNotIn('entradas_antes', B.ler_no(self.slug, self.rasc))   # tudo de volta: a marca some

    def test_o_que_o_usuario_tirou_pelo_app_nao_volta_num_restaurar(self):
        a = self.a
        self.apagar(a['p_ast'])
        status, _ = self.pedir('PATCH', f'{self.url}/{self.rasc}', {'entradas': [a['img'], a['vid']]})   # tirou a referência
        self.assertEqual(status, 200)
        self.restaurar(a['p_ast'])
        self.assertEqual(self.entradas(), [a['img'], a['ast'], a['vid']])

    def patch(self, entradas):
        self.assertEqual(self.pedir('PATCH', f'{self.url}/{self.rasc}', {'entradas': entradas})[0], 200)

    def test_segundo_apagar_tambem_e_desfeito(self):
        a = self.a   # apaga o asset, liga outra imagem pelo app, apaga essa e desfaz: ela tem de voltar
        with B.travado(self.slug):
            p = B.novo_no(self.slug, 'pedido', tela=a['tela'], status='concluido')['id']
            z = B.novo_no(self.slug, 'imagem', pedido=p)['id']
        self.apagar(a['p_ast'])
        self.patch([a['img'], self.ref, a['vid'], z])
        self.apagar(p)
        self.assertEqual(self.entradas(), [a['img'], self.ref, a['vid']])
        self.restaurar(p)
        self.assertEqual(self.entradas(), [a['img'], self.ref, a['vid'], z])
        self.restaurar(a['p_ast'])
        self.assertEqual(self.entradas(), [a['img'], a['ast'], self.ref, a['vid'], z])

    def test_desfazer_em_pilha_nao_troca_o_pai(self):
        a = self.a   # [img, ast]: apaga o asset, tira a imagem, desfaz a retirada, desfaz o apagar → a imagem segue em 1º
        self.patch([a['img'], a['ast']])
        self.apagar(a['p_ast'])
        self.patch([])
        self.patch([a['img']])
        self.restaurar(a['p_ast'])
        self.assertEqual(self.entradas(), [a['img'], a['ast']])

    def test_trocar_a_origem_com_uma_entrada_na_lixeira(self):
        a = self.a   # [img, ast]: com o asset na lixeira, troca a imagem pelo vídeo; o asset volta depois dele, não antes
        self.patch([a['img'], a['ast']])
        self.apagar(a['p_ast'])
        self.patch([self.ref])
        self.restaurar(a['p_ast'])
        self.assertEqual(self.entradas(), [self.ref, a['ast']])

    def test_quem_era_o_primeiro_volta_a_ser_o_primeiro(self):
        a = self.a   # [ref, img]: a referência (com posição) sai e volta; continua em 1º mesmo com algo acrescentado no meio
        self.patch([self.ref, a['img']])
        self.apagar(self.ref)
        self.patch([a['img'], a['ast']])
        self.restaurar(self.ref)
        self.assertEqual(self.entradas(), [self.ref, a['img'], a['ast']])

    def test_com_pagina_nas_entradas_a_marca_some(self):
        a = self.a
        pagina = pagina_com_print(self.slug, a['img'])
        self.patch([a['img'], pagina, a['ast']])
        self.apagar(a['p_ast'])
        self.assertEqual(self.entradas(), [a['img'], pagina])
        self.restaurar(a['p_ast'])
        self.assertEqual(self.entradas(), [a['img'], pagina, a['ast']])
        self.assertNotIn('entradas_antes', B.ler_no(self.slug, self.rasc))

    def test_restaurar_nao_regrava_rascunho_que_nao_mudou(self):
        a = self.a
        with B.travado(self.slug):   # outro rascunho, que espera a referência voltar
            outro = B.novo_no(self.slug, 'pedido', tela=a['tela'], entradas=[a['img'], self.ref])['id']
        self.apagar(self.ref)
        self.apagar(a['p_ast'])
        arq = B.caminho_no(self.slug, outro)
        antes = (arq.stat().st_ino, arq.stat().st_mtime_ns)   # gravar_json troca o arquivo: o inode muda
        self.restaurar(a['p_ast'])   # não tem nada a ver com o outro rascunho
        self.assertEqual((arq.stat().st_ino, arq.stat().st_mtime_ns), antes)

    def test_enviar_tira_a_marca(self):
        a = self.a
        self.apagar(a['p_ast'])
        self.assertIn('entradas_antes', B.ler_no(self.slug, self.rasc))
        self.assertEqual(self.pedir('POST', f'{self.url}/{self.rasc}/enviar')[0], 200)
        self.assertNotIn('entradas_antes', B.ler_no(self.slug, self.rasc))

    def test_refazer_e_desfazer_de_novo(self):
        a = self.a
        for _ in range(2):
            self.apagar(a['p_ast'])
            self.assertEqual(self.entradas(), [a['img'], self.ref, a['vid']])
            self.restaurar(a['p_ast'])
            self.assertEqual(self.entradas(), [a['img'], a['ast'], self.ref, a['vid']])
        self.assertEqual(list((B.pasta(self.slug) / 'lixeira').iterdir()), [])


class EnviarSemEntradaViva(Api):
    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Modelos')['slug']
        self.a = arvore_3d(self.slug)
        self.url = f'/api/projetos/{self.slug}/nos'

    def pedido(self, **campos):
        with B.travado(self.slug):
            return B.novo_no(self.slug, 'pedido', tela=self.a['tela'], **campos)['id']

    def test_pedido_so_com_entradas_que_nao_existem_nao_e_enviado(self):
        pid = self.pedido(entradas=['NAO-999', f'{self.a["img"]}/v9'])
        status, dados = self.pedir('POST', f'{self.url}/{pid}/enviar')
        self.assertEqual(status, 422, dados)
        self.assertEqual(B.ler_no(self.slug, pid)['status'], 'rascunho')
        self.assertFalse(B.FILA.exists())

    def test_com_texto_ou_com_uma_entrada_viva_segue_passando(self):
        for campos in ({'entradas': ['NAO-999'], 'intencao': 'mais neon'}, {'entradas': ['NAO-999', self.a['img']]}):
            self.assertEqual(self.pedir('POST', f'{self.url}/{self.pedido(**campos)}/enviar')[0], 200, campos)

    def test_pedido_de_video_sem_imagem_viva_nao_e_enviado(self):
        with mock.patch.object(B, 'modelos_video', lambda todos=False: {'m/x': {'nome': 'X'}}):
            for campos in ({'entradas': ['NAO-999'], 'intencao': 'gira'}, {'entradas': [], 'intencao': 'gira'}):
                pid = self.pedido(midia='video', modelos=['m/x'], **campos)
                self.assertEqual(self.pedir('POST', f'{self.url}/{pid}/enviar')[0], 422, campos)
                self.assertEqual(B.ler_no(self.slug, pid)['status'], 'rascunho')
            pid = self.pedido(midia='video', modelos=['m/x'], entradas=[self.a['img']])
            self.assertEqual(self.pedir('POST', f'{self.url}/{pid}/enviar')[0], 200)

    def test_video_sem_imagem_de_entrada_devolve_o_pedido(self):
        import gerar_video
        pid = self.pedido(midia='video', modelos=['m/x'], entradas=['NAO-999'], status='trabalhando')

        def rede(*a, **k):
            raise AssertionError('chegou à chave ou à rede')
        with mock.patch.object(gerar_video, 'chave', rede), mock.patch.object(gerar_video, 'catalogo_api', rede), \
                mock.patch.object(gerar_video, 'pedir', rede), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            gerar_video.por_pedido(pid, 'prompt', confirmado=False)
        ped = B.ler_no(self.slug, pid)
        self.assertEqual(ped['status'], 'erro')
        self.assertIn('imagem de entrada', ped['erro'])

    def test_video_com_o_catalogo_fora_do_ar_devolve_o_pedido(self):
        # a 1ª chamada de rede do pedido (rede fora, 401/402, resposta sem `data`) acontece antes de o gerador ser
        # registrado: sem devolver, o pedido fica "trabalhando" para sempre e o varredor de órfãos não o enxerga
        import gerar_video

        def rede(*a, **k):
            raise AssertionError('chegou à geração')
        with B.travado(self.slug):   # a imagem de entrada existe no disco: o pedido passa do 1º portão e chega ao catálogo
            img = B.ler_no(self.slug, self.a['img'])
            img['arquivo'] = f'{img["id"]}.png'
            (B.pasta(self.slug) / img['arquivo']).write_bytes(base64.b64decode(PNG))
            B.gravar_no(self.slug, img)
        for falha, trecho in ((OSError('rede fora'), 'rede fora'), (RuntimeError('OpenRouter HTTP 402: sem saldo'), 'HTTP 402'),
                              (KeyError('data'), 'KeyError'), (ValueError('não é JSON'), 'ValueError'),
                              (None, 'TypeError')):   # None: o catálogo responde, mas o modelo vem sem preço (o `plano` quebra)
            pid = self.pedido(midia='video', modelos=['m/x'], entradas=[self.a['img']], status='trabalhando')

            def cai(key, falha=falha):
                if falha is None:
                    return {'m/x': {'id': 'm/x', 'name': 'X', 'pricing_skus': {'duration_seconds': None}}}
                raise falha
            with mock.patch.object(gerar_video, 'chave', lambda: 'k'), mock.patch.object(gerar_video, 'catalogo_api', cai), \
                    mock.patch.object(gerar_video, 'pedir', rede), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as saiu:
                gerar_video.por_pedido(pid, 'prompt', confirmado=False)
            self.assertIn('ERRO', str(saiu.exception.code))   # quem rodou o script vê a falha, não um sucesso
            ped = B.ler_no(self.slug, pid)
            self.assertEqual(ped['status'], 'erro', falha)
            self.assertIn(trecho, ped['erro'])
            self.assertNotIn('gerador', ped)


class CancelarEnvio(Api):
    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Loja')['slug']
        self.url = f'/api/projetos/{self.slug}/nos'

    def pedido(self, **campos):
        with B.travado(self.slug):
            return B.novo_no(self.slug, 'pedido', tela='LOJ-002', intencao='teste', **campos)['id']

    def test_pedido_na_fila_volta_a_rascunho_e_pode_ser_reenviado(self):
        pid = self.pedido()
        self.assertEqual(self.pedir('POST', f'{self.url}/{pid}/enviar')[0], 200)
        B.aguardar_ok(self.slug, pid, 0.42)
        status, dados = self.pedir('POST', f'{self.url}/{pid}/cancelar')
        self.assertEqual((status, dados.get('status')), (200, 'rascunho'), dados)
        no = B.ler_no(self.slug, pid)
        self.assertEqual(no['status'], 'rascunho')
        self.assertFalse({'enviado_em', 'aguarda_ok', 'erro'} & no.keys())
        self.assertEqual(self.pedir('PATCH', f'{self.url}/{pid}', {'intencao': 'outro texto'})[0], 200)   # editável de novo
        self.assertEqual(self.pedir('POST', f'{self.url}/{pid}/enviar')[0], 200)

    def test_pedido_que_ja_gerou_volta_a_erro_com_as_saidas(self):
        pid = self.pedido(status='enviado', saidas=['LOJ-099'], variacoes=[{'nome': 'a', 'prompt': 'p'}])
        self.assertEqual(self.pedir('POST', f'{self.url}/{pid}/cancelar')[0], 200)
        no = B.ler_no(self.slug, pid)
        self.assertEqual((no['status'], no['erro'], no['saidas']), ('erro', 'Envio cancelado', ['LOJ-099']))

    def test_so_o_que_esta_na_fila_e_cancelado(self):
        for estado in ('rascunho', 'trabalhando', 'concluido', 'erro'):
            pid = self.pedido(status=estado)
            antes = B.ler_no(self.slug, pid)
            self.assertEqual(self.pedir('POST', f'{self.url}/{pid}/cancelar')[0], 422, estado)
            self.assertEqual(B.ler_no(self.slug, pid), antes, estado)
        self.assertEqual(self.pedir('POST', f'{self.url}/LOJ-002/cancelar')[0], 422)   # a tela não é pedido
        self.assertEqual(self.pedir('POST', f'{self.url}/LOJ-001/enviar')[0], 200)     # o brief enviado também não
        self.assertEqual(self.pedir('POST', f'{self.url}/LOJ-001/cancelar')[0], 422)
        self.assertEqual(B.ler_no(self.slug, 'LOJ-001')['status'], 'enviado')

    def test_o_agente_nao_pega_um_envio_cancelado(self):
        # a linha do envio continua na fila.jsonl: sem a recusa, o agente pegava o rascunho que o usuário está editando
        pid = self.pedido()
        self.pedir('POST', f'{self.url}/{pid}/enviar')
        self.pedir('POST', f'{self.url}/{pid}/cancelar')
        with mock.patch.object(sys, 'argv', ['neo.py', 'pegar', pid]), contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit) as saiu:
            neo.main()
        self.assertIn('cancelado', str(saiu.exception.code))
        self.assertEqual(B.ler_no(self.slug, pid)['status'], 'rascunho')
        self.assertEqual(self.pedir('POST', f'{self.url}/{pid}/enviar')[0], 200)   # enviado de novo, volta a poder ser pego
        with mock.patch.object(sys, 'argv', ['neo.py', 'pegar', pid]), contextlib.redirect_stdout(io.StringIO()):
            neo.main()
        self.assertEqual(B.ler_no(self.slug, pid)['status'], 'trabalhando')

    def test_reenviar_tira_a_espera_do_envio_anterior(self):
        pid = self.pedido()
        self.pedir('POST', f'{self.url}/{pid}/enviar')
        B.aguardar_ok(self.slug, pid, 0.42)
        self.assertEqual(B.ler_no(self.slug, pid)['aguarda_ok'], 0.42)
        B.devolver_pedido(self.slug, pid, 'sem chave')   # o gerador falhou depois do ok: o pedido volta como erro
        self.assertEqual(self.pedir('POST', f'{self.url}/{pid}/enviar')[0], 200)
        self.assertNotIn('aguarda_ok', B.ler_no(self.slug, pid))


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


def pid_morto() -> int:
    """O PID de um processo que já terminou (e foi recolhido)."""
    import subprocess
    p = subprocess.Popen([sys.executable, '-c', 'pass'])
    p.wait()
    return p.pid


class Orfaos(Isolado):
    """Um gerador que morreu (SIGKILL, queda da máquina) não deixa o pedido preso."""

    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Loja')['slug']

    def pedido(self, pid, pronta=False, com_gerador=True):
        with B.travado(self.slug):
            ped = B.novo_no(self.slug, 'pedido', tela='LOJ-002', status='trabalhando', custo=1.0)
            antiga = B.novo_no(self.slug, 'imagem', pedido=ped['id'], arquivo='images/a.png', custo=0.5)   # de outra execução
            a = B.novo_no(self.slug, 'imagem', pedido=ped['id'], gerando=True)
            b = B.novo_no(self.slug, 'imagem', pedido=ped['id'], **({'arquivo': 'images/b.png', 'custo': 0.2} if pronta else {'gerando': True}))
            ped['saidas'] = [antiga['id'], a['id'], b['id']]
            if com_gerador:
                ped['gerador'] = {'pid': pid, 'desde': B.agora(), 'saidas': [a['id'], b['id']]}
            B.gravar_no(self.slug, ped)
        return ped['id'], a['id'], b['id']

    def test_gerador_morto_sem_nada_pronto_vira_erro(self):
        pid, a, b = self.pedido(pid_morto())
        self.assertEqual(B.soltar_orfaos(self.slug), [pid])
        ped = B.ler_no(self.slug, pid)
        self.assertEqual((ped['status'], ped['custo'], 'gerador' in ped), ('erro', 1.0, False))
        for i in (a, b):
            no = B.ler_no(self.slug, i)
            self.assertNotIn('gerando', no)
            self.assertTrue(no['erro'])

    def test_gerador_morto_com_imagem_pronta_conclui_e_soma_so_esta_execucao(self):
        pid, a, b = self.pedido(pid_morto(), pronta=True)
        B.soltar_orfaos(self.slug)
        ped = B.ler_no(self.slug, pid)
        self.assertEqual((ped['status'], ped['custo']), ('concluido', 1.2))   # 1.0 + 0.2; a imagem antiga (0.5) não conta de novo
        self.assertTrue(B.ler_no(self.slug, a)['erro'])
        self.assertNotIn('erro', B.ler_no(self.slug, b))

    def test_gerador_vivo_ou_pedido_sem_gerador_nao_mudam(self):
        import os
        vivo, a, _ = self.pedido(os.getpid())
        sem, c, _ = self.pedido(0, com_gerador=False)
        self.assertEqual(B.soltar_orfaos(self.slug), [])
        for pid, i in ((vivo, a), (sem, c)):
            self.assertEqual(B.ler_no(self.slug, pid)['status'], 'trabalhando')
            self.assertTrue(B.ler_no(self.slug, i)['gerando'])

    def test_pedido_solto_e_pego_de_novo_nao_e_tocado(self):
        pid, _, _ = self.pedido(pid_morto())
        for cmd in (['erro', pid, 'travou'], ['pegar', pid]):
            with mock.patch.object(sys, 'argv', ['neo.py', *cmd]), contextlib.redirect_stdout(io.StringIO()):
                neo.main()
        self.assertNotIn('gerador', B.ler_no(self.slug, pid))
        self.assertEqual(B.soltar_orfaos(self.slug), [])
        self.assertEqual(B.ler_no(self.slug, pid)['status'], 'trabalhando')

    def test_gerar_roda_num_pedido_cujo_gerador_morreu(self):
        pid, a, b = self.pedido(pid_morto())
        saida = io.StringIO()
        with mock.patch.object(gerar, 'chave', lambda: 'chave-de-teste'), \
                mock.patch.object(gerar, 'pedir', lambda *a, **k: {'data': [{'b64_json': PNG}], 'usage': {'cost': 0.14}}), \
                mock.patch.object(sys, 'argv', ['gerar.py', pid, '--prompt', 'x']), \
                contextlib.redirect_stdout(saida), self.assertRaises(SystemExit) as fim:
            gerar.main()
        self.assertEqual(fim.exception.code, 0, saida.getvalue())
        ped = B.ler_no(self.slug, pid)
        self.assertEqual((ped['status'], len(ped['saidas']), 'gerador' in ped), ('concluido', 4, False))

    def test_sigterm_fecha_o_pedido_e_o_processo_morre_logo(self):
        import signal
        import subprocess
        import time
        with B.travado(self.slug):
            pid = B.novo_no(self.slug, 'pedido', tela='LOJ-002', status='trabalhando')['id']
        codigo = f"""
import sys, time
sys.path.insert(0, {str(Path(gerar.__file__).parent)!r})
from pathlib import Path
import base as B, gerar
B.RAIZ = Path({str(self.raiz)!r}); B.PROJETOS = B.RAIZ / 'projects'; B.FILA = B.RAIZ / 'fila.jsonl'
gerar.chave = lambda: 'chave-de-teste'
gerar.pedir = lambda *a, **k: time.sleep(60)
sys.argv = ['gerar.py', {pid!r}, '--prompt', 'a', '--prompt', 'b']
gerar.main()
"""
        p = subprocess.Popen([sys.executable, '-c', codigo], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(p.kill)
        fim = time.time() + 10
        while time.time() < fim and 'gerador' not in B.ler_no(self.slug, pid):   # espera os placeholders
            time.sleep(0.05)
        self.assertIn('gerador', B.ler_no(self.slug, pid))
        t0 = time.time()
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=3), 143)
        self.assertLess(time.time() - t0, 3)
        ped = B.ler_no(self.slug, pid)
        self.assertEqual((ped['status'], 'gerador' in ped), ('erro', False))
        self.assertFalse([n['id'] for n in B.nos(self.slug) if n.get('gerando')])

    def test_o_varredor_do_servidor_solta_os_orfaos(self):
        pid, a, _ = self.pedido(pid_morto())

        class Chega(Exception):
            pass

        def uma_volta(_segundos):
            raise Chega
        with mock.patch.object(servidor.time, 'sleep', uma_volta), self.assertRaises(Chega):
            servidor.varredor()
        self.assertEqual(B.ler_no(self.slug, pid)['status'], 'erro')
        self.assertNotIn('gerando', B.ler_no(self.slug, a))

    def test_sigterm_no_gerador_de_video(self):
        import signal
        import subprocess
        import time
        with B.travado(self.slug):
            img = B.novo_no(self.slug, 'imagem', arquivo='images/x.png')['id']
            (B.pasta(self.slug) / 'images' / 'x.png').write_bytes(base64.b64decode(PNG))
            pid = B.novo_no(self.slug, 'pedido', tela='LOJ-002', status='trabalhando', midia='video', entradas=[img], modelos=['m/x'])['id']
        codigo = f"""
import sys, time
sys.path.insert(0, {str(Path(gerar.__file__).parent)!r})
from pathlib import Path
import base as B, gerar_video
B.RAIZ = Path({str(self.raiz)!r}); B.PROJETOS = B.RAIZ / 'projects'; B.FILA = B.RAIZ / 'fila.jsonl'
B.medidas = lambda arquivo: (16, 9)
gerar_video.chave = lambda: 'chave-de-teste'
gerar_video.catalogo_api = lambda key: {{'m/x': {{'id': 'm/x', 'name': 'M: X', 'supported_durations': [4], 'supported_resolutions': ['720p']}}}}
gerar_video.gerar_um = lambda *a, **k: time.sleep(60)
gerar_video.por_pedido({pid!r}, 'prompt', confirmado=False)
"""
        p = subprocess.Popen([sys.executable, '-c', codigo], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(p.kill)
        fim = time.time() + 10
        while time.time() < fim and 'gerador' not in B.ler_no(self.slug, pid):
            time.sleep(0.05)
        self.assertIn('gerador', B.ler_no(self.slug, pid))
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=3), 143)
        ped = B.ler_no(self.slug, pid)
        self.assertEqual((ped['status'], 'gerador' in ped), ('erro', False))
        self.assertFalse([n['id'] for n in B.nos(self.slug) if n.get('gerando')])


class Preco(Isolado):
    """A estimativa que decide o teto de custo: a tabela, ou o histórico do projeto quando ele é mais caro."""
    FLASH = 'google/gemini-3.1-flash-image'

    def setUp(self):
        super().setUp()
        self.slug = B.criar_projeto('Loja')['slug']

    def imagens(self, custos, **campos):
        with B.travado(self.slug):
            for c in custos:
                B.novo_no(self.slug, 'imagem', **{'modelo': self.FLASH, 'resolucao': '1K', 'arquivo': 'images/x.png', 'custo': c, **campos})

    def test_sem_historico_vale_a_tabela(self):
        self.assertEqual(B.preco_estimado(self.slug, self.FLASH, '1K'), B.MODELOS[self.FLASH]['preco'])
        self.assertEqual(B.preco_estimado(self.slug, 'modelo/desconhecido', '1K'), 0.15)
        self.imagens([0.5, 0.5])   # duas amostras ainda não bastam
        self.assertEqual(B.preco_estimado(self.slug, self.FLASH, '1K'), B.MODELOS[self.FLASH]['preco'])

    def test_historico_mais_caro_sobe_a_estimativa(self):
        self.imagens([0.20, 0.22, 0.90])
        self.assertEqual(B.preco_estimado(self.slug, self.FLASH, '1K'), 0.22)

    def test_historico_mais_barato_nao_baixa_a_estimativa(self):
        self.imagens([0.01, 0.01, 0.01])
        self.assertEqual(B.preco_estimado(self.slug, self.FLASH, '1K'), B.MODELOS[self.FLASH]['preco'])

    def test_o_que_nao_entra_na_mediana(self):
        self.imagens([0.9] * 3, modelo='openai/gpt-image-2')
        self.imagens([0.9] * 3, resolucao='4K')
        self.imagens([0.9] * 3, erro='falhou')
        self.imagens([0.9] * 3, asset=True)
        self.imagens([0.9] * 3, legado=True)
        self.imagens([None, 0, 0.9])
        self.assertEqual(B.preco_estimado(self.slug, self.FLASH, '1K'), B.MODELOS[self.FLASH]['preco'])

    def test_o_teto_diario_usa_o_historico(self):
        self.imagens([6.0, 6.0, 6.0], criado='2020-01-01T00:00:00')   # caras, mas de outro dia: hoje = $0
        with B.travado(self.slug):
            pid = B.novo_no(self.slug, 'pedido', tela='LOJ-002', modelo=self.FLASH, resolucao='1K')['id']
        saida = io.StringIO()
        with mock.patch.object(gerar, 'chave', lambda: 'chave-de-teste'), mock.patch.object(gerar, 'pedir', lambda *a, **k: self.fail('gerou')), \
                mock.patch.object(sys, 'argv', ['gerar.py', pid, '--prompt', 'a', '--prompt', 'b', '--prompt', 'c', '--prompt', 'd']), \
                contextlib.redirect_stdout(saida), self.assertRaises(SystemExit) as fim:
            gerar.main()
        self.assertEqual(fim.exception.code, 3, saida.getvalue())   # 4 × $6 passa do teto diário de $20; pela tabela seriam $0,28
        self.assertIn('BLOQUEADO', saida.getvalue())


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'precisa do ffmpeg e do ffprobe')
class VideoBaixado(Isolado):
    """O que o gerar_video.py faz com o arquivo que chega: mede as dimensões reais e tira a trilha de áudio."""

    def setUp(self):
        super().setUp()
        import subprocess
        import gerar_video
        self.gv = gerar_video
        self.mp4 = self.raiz / 'origem.mp4'   # 320×180, 1 s, com áudio
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:d=1', '-f', 'lavfi', '-i', 'sine=d=1',
                        '-shortest', '-c:v', 'mpeg4', '-c:a', 'aac', str(self.mp4)], check=True)

    def baixar(self):
        """gerar_um de verdade, com o OpenRouter trocado: o job termina na 1ª consulta e o conteúdo é o mp4 de teste."""
        def pedir(metodo, caminho, key, corpo=None, bruto=False, timeout=300):
            if bruto:
                return self.mp4.read_bytes()
            return {'id': 'job'} if metodo == 'POST' else {'status': 'completed', 'usage': {'cost': 0.05}}
        destino, capa = self.raiz / 'saida.mp4', self.raiz / 'saida.jpg'
        plano = {'modelo': 'm/x', 'duracao': 1, 'resolucao': '480p', 'estimativa': 0.05, 'audio_controlavel': False}
        with mock.patch.object(self.gv, 'pedir', pedir), mock.patch.object(self.gv.time, 'sleep', lambda s: None), \
                contextlib.redirect_stdout(io.StringIO()):
            return self.gv.gerar_um(plano, 'prompt', 'data:image/png;base64,x', '16:9', 'chave', destino, capa), destino, capa

    def test_mede_o_arquivo_e_tira_o_audio(self):
        self.assertEqual(self.gv.sondar(self.mp4), {'largura': 320, 'altura': 180, 'audio': True})
        r, destino, capa = self.baixar()
        self.assertEqual((r['status'], r['largura'], r['altura']), ('completed', 320, 180))
        self.assertEqual(self.gv.sondar(destino), {'largura': 320, 'altura': 180, 'audio': False})
        self.assertTrue(capa.exists())
        self.assertFalse(list(self.raiz.glob('*.mudo.mp4')))   # o temporário não fica

    def test_video_sem_audio_nao_e_regravado(self):
        import subprocess
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(self.mp4), '-an', '-c', 'copy', str(self.raiz / 'mudo.mp4')], check=True)
        self.mp4 = self.raiz / 'mudo.mp4'
        chamadas = []
        with mock.patch.object(self.gv, 'tirar_audio', chamadas.append):
            r, destino, _ = self.baixar()
        self.assertEqual(chamadas, [])   # não regrava um vídeo que já era mudo
        self.assertNotIn('erro', r)
        self.assertEqual(destino.read_bytes(), self.mp4.read_bytes())
        self.assertEqual((r['largura'], r['altura']), (320, 180))

    def test_sem_ffprobe_o_video_fica_como_veio(self):
        qual = shutil.which
        with mock.patch.object(self.gv.shutil, 'which', lambda nome: None if nome in ('ffprobe', 'ffmpeg') else qual(nome)):
            self.assertIsNone(self.gv.sondar(self.mp4))
            r, destino, capa = self.baixar()
        self.assertEqual(r['status'], 'completed')
        self.assertNotIn('largura', r)
        self.assertEqual(destino.read_bytes(), self.mp4.read_bytes())
        self.assertFalse(capa.exists())

    def test_ffmpeg_que_falha_nao_estraga_o_arquivo(self):
        ruim = self.raiz / 'ruim.mp4'
        ruim.write_bytes(b'isto nao e um mp4')
        self.assertIsNone(self.gv.sondar(ruim))
        self.gv.tirar_audio(ruim)
        self.assertEqual(ruim.read_bytes(), b'isto nao e um mp4')
        self.assertFalse(list(self.raiz.glob('*.mudo.mp4')))

    def test_a_capa_embutida_nao_e_o_video(self):
        # o ffmpeg grava a capa por último num mp4, mas a ordem é do provedor: a saída do ffprobe é dada aqui à mão
        import subprocess
        faixas = [{'codec_type': 'video', 'width': 640, 'height': 360, 'disposition': {'attached_pic': 1}},
                  {'codec_type': 'video', 'width': 320, 'height': 180, 'disposition': {'attached_pic': 0}},
                  {'codec_type': 'audio'}]
        saida = subprocess.CompletedProcess([], 0, stdout=json.dumps({'streams': faixas}), stderr='')
        with mock.patch.object(self.gv.subprocess, 'run', lambda *a, **k: saida):
            self.assertEqual(self.gv.sondar(self.mp4), {'largura': 320, 'altura': 180, 'audio': True})

    def test_video_girado_usa_as_dimensoes_de_exibicao(self):
        # o arquivo codifica 320×180 e manda girar 90°: quem assiste vê 180×320 (a saída do ffprobe é dada à mão)
        import subprocess
        for giro, esperado in ((-90, (180, 320)), (90, (180, 320)), (270, (180, 320)), (180, (320, 180)), (0, (320, 180))):
            faixas = [{'codec_type': 'video', 'width': 320, 'height': 180, 'disposition': {'attached_pic': 0},
                       'side_data_list': [{}, {'rotation': giro}]}]
            saida = subprocess.CompletedProcess([], 0, stdout=json.dumps({'streams': faixas}), stderr='')
            with mock.patch.object(self.gv.subprocess, 'run', lambda *a, **k: saida):
                r = self.gv.sondar(self.mp4)
            self.assertEqual((r['largura'], r['altura']), esperado, giro)

    def test_falha_ao_baixar_nao_vira_video_pronto(self):
        slug = B.criar_projeto('Loja')['slug']
        with B.travado(slug):
            img = B.novo_no(slug, 'imagem', arquivo='images/x.png')['id']
            (B.pasta(slug) / 'images' / 'x.png').write_bytes(base64.b64decode(PNG))
            pid = B.novo_no(slug, 'pedido', tela='LOJ-002', midia='video', entradas=[img], modelos=['m/x'])['id']
        catalogo = {'m/x': {'id': 'm/x', 'name': 'M: X', 'supported_durations': [4], 'supported_resolutions': ['720p']}}

        def pedir(metodo, caminho, key, corpo=None, bruto=False, timeout=300):
            if bruto:
                raise RuntimeError('OpenRouter HTTP 502: caiu no download')
            return {'id': 'job'} if metodo == 'POST' else {'status': 'completed', 'usage': {'cost': 0.05}}
        with mock.patch.object(self.gv, 'chave', lambda: 'chave-de-teste'), mock.patch.object(self.gv, 'catalogo_api', lambda key: catalogo), \
                mock.patch.object(self.gv, 'pedir', pedir), mock.patch.object(self.gv.time, 'sleep', lambda s: None), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as fim:
            self.gv.por_pedido(pid, 'prompt', confirmado=False)
        ped = B.ler_no(slug, pid)
        video = B.ler_no(slug, ped['saidas'][0])
        self.assertEqual((fim.exception.code, ped['status']), (1, 'erro'))
        self.assertNotIn('arquivo', video)
        self.assertIn('502', video['erro'])
        self.assertEqual(video['custo'], 0.05)   # o que foi cobrado continua registrado

    def test_falha_ao_medir_ou_tirar_o_audio_nao_perde_o_video(self):
        def quebra(arq):
            raise OSError('o ffprobe sumiu no meio')
        with mock.patch.object(self.gv, 'sondar', quebra):
            r, destino, capa = self.baixar()
        self.assertEqual((r['status'], r['arquivo']), ('completed', 'saida.mp4'))
        self.assertNotIn('erro', r)
        self.assertEqual(destino.read_bytes(), self.mp4.read_bytes())
        self.assertTrue(capa.exists())   # a capa ainda é tirada

    def test_o_no_do_video_fica_com_as_dimensoes_do_arquivo(self):
        slug = B.criar_projeto('Loja')['slug']
        with B.travado(slug):
            img = B.novo_no(slug, 'imagem', arquivo='images/x.png')['id']
            (B.pasta(slug) / 'images' / 'x.png').write_bytes(base64.b64decode(PNG))
            pid = B.novo_no(slug, 'pedido', tela='LOJ-002', midia='video', entradas=[img], modelos=['m/x'])['id']
        catalogo = {'m/x': {'id': 'm/x', 'name': 'M: X', 'supported_durations': [4], 'supported_resolutions': ['720p']}}

        def gerar_um(p, prompt, url_img, proporcao, key, destino, capa):
            destino.write_bytes(b'mp4')
            return dict(p, status='completed', custo=0.05, segundos=1.0, arquivo=destino.name, largura=736, altura=400)
        with mock.patch.object(self.gv, 'chave', lambda: 'chave-de-teste'), mock.patch.object(self.gv, 'catalogo_api', lambda key: catalogo), \
                mock.patch.object(self.gv, 'gerar_um', gerar_um), mock.patch.object(B, 'medidas', lambda arq: (1376, 768)), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            self.gv.por_pedido(pid, 'prompt', confirmado=False)
        video = B.ler_no(slug, B.ler_no(slug, pid)['saidas'][0])
        self.assertEqual((video['largura'], video['altura']), (736, 400))   # e não 1376×768, as da imagem de origem


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


class PortaoDeGasto(Isolado):
    """Com os tetos do clone (zero), todo pedido pago para na saída 3 e volta para a fila à espera do ok no chat."""
    rodar = Gerar.rodar

    def setUp(self):
        super().setUp()
        self.chamadas = []
        p = mock.patch.object(B, 'TETOS', dict(TETOS_DO_CLONE))
        p.start()
        self.addCleanup(p.stop)
        self.slug = B.criar_projeto('Portao')['slug']
        tela = next(n['id'] for n in B.nos(self.slug) if n['tipo'] == 'tela')
        with B.travado(self.slug):
            self.pid = B.novo_no(self.slug, 'pedido', tela=tela, intencao='teste')['id']
            self.img = B.novo_no(self.slug, 'imagem', nome='base')
            self.img['arquivo'] = f'{self.img["id"]}.png'
            (B.pasta(self.slug) / self.img['arquivo']).write_bytes(base64.b64decode(PNG))
            B.gravar_no(self.slug, self.img)
            self.vid = B.novo_no(self.slug, 'pedido', tela=tela, midia='video', modelos=['m/x'], entradas=[self.img['id']])['id']

    def video(self, confirmado, preco='0.01'):
        import gerar_video
        posts = []

        def pedir(metodo, *a, **k):
            posts.append(metodo)
            raise RuntimeError('sem rede no teste')
        catalogo = {'m/x': {'id': 'm/x', 'name': 'X', 'pricing_skus': {'duration_seconds': preco}}}
        saida = io.StringIO()
        with mock.patch.object(gerar_video, 'chave', lambda: 'k'), mock.patch.object(gerar_video, 'catalogo_api', lambda key: catalogo), \
                mock.patch.object(gerar_video, 'pedir', pedir), mock.patch.object(gerar_video.time, 'sleep', lambda s: None), \
                contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            try:
                gerar_video.por_pedido(self.vid, 'prompt', confirmado=confirmado)
            except SystemExit as e:
                return e.code, saida.getvalue(), posts
        return 0, saida.getvalue(), posts

    def test_o_clone_nasce_com_os_tetos_em_zero(self):
        self.assertEqual((TETOS_DO_CLONE['imagens_por_pedido'], TETOS_DO_CLONE['video_por_pedido_usd']), (0, 0.0))
        self.assertEqual(B.ler_projeto(self.slug)['tetos'], TETOS_DO_CLONE)

    def test_imagem_para_na_estimativa_e_volta_para_a_fila(self):
        neo.alterar(self.slug, self.pid, status='trabalhando')   # o `neo.py pegar`
        codigo, saida = self.rodar('--prompt', 'a')
        self.assertEqual(codigo, 3, saida)
        self.assertIn('Estimativa $', saida)
        self.assertIn('hoje $', saida)
        self.assertEqual(self.chamadas, [])
        ped = B.ler_no(self.slug, self.pid)
        self.assertEqual((ped['status'], ped.get('saidas', [])), ('enviado', []))
        self.assertGreater(ped['aguarda_ok'], 0)

    def test_com_o_ok_gera_e_a_espera_some(self):
        neo.alterar(self.slug, self.pid, status='trabalhando')
        self.rodar('--prompt', 'a')
        codigo, saida = self.rodar('--prompt', 'a', '--confirmado')
        self.assertEqual(codigo, 0, saida)
        ped = B.ler_no(self.slug, self.pid)
        self.assertEqual((ped['status'], len(ped['saidas'])), ('concluido', 1))
        self.assertNotIn('aguarda_ok', ped)

    def test_pegar_de_novo_tira_a_espera(self):
        neo.alterar(self.slug, self.pid, status='trabalhando')
        self.rodar('--prompt', 'a')
        self.assertNotIn('aguarda_ok', neo.alterar(self.slug, self.pid, status='trabalhando'))

    def test_a_parada_nao_mexe_em_pedido_com_gerador_nem_em_rascunho(self):
        neo.alterar(self.slug, self.pid, status='trabalhando')
        with B.travado(self.slug):
            ped = B.ler_no(self.slug, self.pid)
            ped['gerador'] = {'pid': os.getpid(), 'desde': B.agora(), 'saidas': []}
            B.gravar_no(self.slug, ped)
        self.assertEqual(self.rodar('--prompt', 'a')[0], 3)
        ped = B.ler_no(self.slug, self.pid)
        self.assertEqual((ped['status'], 'aguarda_ok' in ped), ('trabalhando', False))
        with B.travado(self.slug):
            rascunho = B.novo_no(self.slug, 'pedido', tela=ped['tela'], intencao='direto')['id']
        self.pid = rascunho
        self.assertEqual(self.rodar('--prompt', 'a')[0], 3)
        ped = B.ler_no(self.slug, rascunho)
        self.assertEqual((ped['status'], 'aguarda_ok' in ped), ('rascunho', False))

    def test_video_para_na_estimativa_e_volta_para_a_fila(self):
        neo.alterar(self.slug, self.vid, status='trabalhando')
        codigo, saida, posts = self.video(confirmado=False)
        self.assertEqual(codigo, 3, saida)
        self.assertIn('estimativa $', saida)
        self.assertEqual(posts, [])
        ped = B.ler_no(self.slug, self.vid)
        self.assertEqual((ped['status'], ped.get('saidas', [])), ('enviado', []))
        self.assertGreater(ped['aguarda_ok'], 0)

    def test_video_sem_preco_no_catalogo_tambem_para(self):
        codigo, saida, posts = self.video(confirmado=False, preco='0')
        self.assertEqual((codigo, posts), (3, []), saida)

    def test_pedido_que_ninguem_pegou_tambem_fica_esperando(self):
        neo.alterar(self.slug, self.pid, status='enviado')
        self.assertEqual(self.rodar('--prompt', 'a')[0], 3)
        ped = B.ler_no(self.slug, self.pid)
        self.assertEqual(ped['status'], 'enviado')
        self.assertGreater(ped['aguarda_ok'], 0)

    def test_o_teto_diario_tambem_devolve_o_pedido_a_fila(self):
        proj = B.ler_projeto(self.slug)
        proj['tetos'] = {'imagens_por_pedido': 6, 'diario_usd': 0.0, 'video_por_pedido_usd': 0.0}
        B.gravar_projeto(self.slug, proj)
        neo.alterar(self.slug, self.pid, status='trabalhando')
        codigo, saida = self.rodar('--prompt', 'a')
        self.assertEqual(codigo, 3, saida)
        self.assertIn('teto diário', saida)
        self.assertGreater(B.ler_no(self.slug, self.pid)['aguarda_ok'], 0)

    def test_video_avulso_usa_o_teto_do_clone(self):
        import gerar_video
        posts = []

        def pedir(metodo, *a, **k):
            posts.append(metodo)
            raise RuntimeError('sem rede no teste')
        catalogo = {'m/x': {'id': 'm/x', 'name': 'X', 'pricing_skus': {'duration_seconds': '0.01'}}}
        args = ['gerar_video.py', '--imagem', str(B.pasta(self.slug) / self.img['arquivo']), '--saida', str(self.raiz / 'avulso'),
                '--prompt', 'p', '--modelos', 'm/x']
        saida = io.StringIO()
        with mock.patch.object(gerar_video, 'chave', lambda: 'k'), mock.patch.object(gerar_video, 'catalogo_api', lambda key: catalogo), \
                mock.patch.object(gerar_video, 'pedir', pedir), mock.patch.object(sys, 'argv', args), \
                contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida), self.assertRaises(SystemExit) as saiu:
            gerar_video.main()
        self.assertEqual((saiu.exception.code, posts), (3, []), saida.getvalue())

    def test_video_com_o_ok_passa_do_portao(self):
        neo.alterar(self.slug, self.vid, status='trabalhando')
        self.video(confirmado=False)
        _, saida, posts = self.video(confirmado=True)
        self.assertEqual(posts[:1], ['POST'], saida)
        self.assertNotIn('aguarda_ok', B.ler_no(self.slug, self.vid))


if __name__ == '__main__':
    unittest.main()
