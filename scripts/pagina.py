"""Gera index.html: "As letras miúdas em números", uma página única, sem servidor nem build.

Tudo é calculado a partir do acervo (arquivos + histórico do git). A página funciona aberta
direto do disco e no GitHub Pages. O JavaScript só cuida do tema, das dicas ao passar o mouse
e da ordenação da tabela; sem ele, todo o conteúdo continua lá.
"""

from __future__ import annotations

import html
import json
from collections import defaultdict
from datetime import date

from acervo import GITHUB, PALAVRAS_POR_MINUTO, TERMOS, Registro, primeira_mencao
from comum import REPO, texto_puro
from imagem import tempo_leitura, tempo_por_extenso

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
TIPOS = {"termos-de-uso": "termos", "politica-de-privacidade": "privacidade"}
PAGES = f"https://{REPO.split('/')[0].lower()}.github.io/{REPO.split('/')[1]}/"


def e(s) -> str:
    return html.escape(str(s), quote=True)


def num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def mes_ano(d: str) -> str:
    return f"{MESES[int(d[5:7]) - 1]}/{d[:4]}"


def data_br(d: str) -> str:
    return f"{d[8:10]}/{d[5:7]}/{d[:4]}"


def _dia(d: str) -> date:
    return date(int(d[:4]), int(d[5:7]), int(d[8:10]))


def classe(r: Registro) -> str:
    return TIPOS.get(r.doc.tipo, "outro")


def rotulo(r: Registro) -> str:
    return f"{r.doc.nome_empresa} · {r.doc.nome[0]}{r.doc.nome[1:].lower()}"


def arquivo_github(r: Registro) -> str:
    return f"{GITHUB}/blob/main/{r.caminho}"


# ------------------------------------------------------------------ pedaços
def letras_miudas(regs: list[Registro], limite: int = 46000) -> str:
    """Trechos reais dos documentos, para o fundo do topo da página."""
    from comum import RAIZ
    partes = []
    for r in sorted(regs, key=lambda r: -r.minutos):
        t = texto_puro((RAIZ / r.caminho).read_text(encoding="utf-8"))
        ini = int(len(t) * 0.3)
        trecho = t[ini:ini + 1300]
        trecho = trecho[trecho.find(" ") + 1:trecho.rfind(" ")]
        partes.append(trecho)
    return e(" ".join(partes)[:limite])


def primeira_leitura(r: Registro, k: int) -> bool:
    """Versão da primeira leitura do robô depois do histórico do Wayback: a data dela não é a da mudança."""
    v = r.versoes[k]
    return k > 0 and not v.wayback and bool(r.versoes[k - 1].wayback)


def secao_recentes(regs: list[Registro]) -> str:
    """As mudanças mais recentes com data conhecida (fica de fora a primeira versão de cada documento e a
    primeira leitura do robô, que só mostra que o texto mudou em algum momento desde a última captura)."""
    todas = []
    for r in regs:
        for i, v in enumerate(r.versoes):
            if i == 0 or primeira_leitura(r, i):
                continue
            todas.append((v.data, i, r, v))
    todas.sort(key=lambda x: (x[0], x[2].doc.nome_empresa), reverse=True)
    itens = []
    for data, i, r, v in todas[:12]:
        oque = "ver o que mudou"
        origem = "Wayback Machine" if v.wayback else "robô diário"
        itens.append(
            f'<li><time datetime="{data}">{data_br(data)}</time>'
            f'<span class="quem"><i class="marca {classe(r)}" aria-hidden="true"></i>{e(rotulo(r))}</span>'
            f'<span class="origem">{origem}</span>'
            f'<a href="{GITHUB}/commit/{v.sha}">{oque}</a></li>')
    return "\n".join(itens)


def secao_linha_do_tempo(regs: list[Registro], hoje: date) -> tuple[str, str]:
    por_empresa: dict[str, list[Registro]] = defaultdict(list)
    for r in regs:
        por_empresa[r.doc.empresa].append(r)
    linhas = []
    for slug, lista in por_empresa.items():
        linhas.append((min(v.data for r in lista for v in r.versoes), lista[0].doc.nome_empresa, lista))
    linhas.sort(key=lambda x: (x[0], x[1].lower()))
    ano0, ano1 = min(int(x[0][:4]) for x in linhas), hoje.year
    ini, fim = date(ano0, 1, 1), date(ano1 + 1, 1, 1)
    L, X0, X1, H, TOPO = 1000, 150, 990, 22, 26

    def x(d: date) -> float:
        return X0 + (X1 - X0) * (d - ini).days / (fim - ini).days

    altura = TOPO + H * len(linhas) + 8
    s = [f'<svg class="tempo" viewBox="0 0 {L} {altura}" role="group" '
         f'aria-label="Versões de cada documento ao longo do tempo">']
    for ano in range(ano0, ano1 + 2):
        gx = x(date(ano, 1, 1))
        s.append(f'<rect class="grade" x="{gx:.1f}" y="{TOPO - 8}" width="1" height="{altura - TOPO + 8}"/>')
        if ano <= ano1:
            meio = (gx + x(date(ano + 1, 1, 1))) / 2
            s.append(f'<text class="eixo" x="{meio:.1f}" y="{TOPO - 13}" text-anchor="middle">{ano}</text>')
    for i, (desde, nome, lista) in enumerate(linhas):
        y = TOPO + H * i + H / 2
        s.append(f'<text class="empresa" x="0" y="{y + 4.5:.1f}">{e(nome)}</text>')
        xi = x(_dia(desde))
        s.append(f'<rect class="trilha" x="{xi:.1f}" y="{y - 0.75:.2f}" width="{X1 - xi:.1f}" height="1.5" rx=".75"/>')
        for r in sorted(lista, key=lambda r: r.doc.tipo):
            dy = 0 if len(lista) == 1 else (-4 if r.doc.tipo == "termos-de-uso" else 4)
            for k, v in enumerate(r.versoes):
                ant = r.versoes[k - 1].palavras if k else None
                origem = "Wayback Machine" if v.wayback else "robô diário"
                if primeira_leitura(r, k):
                    origem = (f"primeira leitura do robô; o texto mudou em algum momento depois de "
                              f"{data_br(r.versoes[k - 1].data)}")
                dica = json.dumps({
                    "t": rotulo(r), "d": data_br(v.data), "o": origem,
                    "p": num(v.palavras), "a": num(ant) if ant is not None else "", "k": k,
                }, ensure_ascii=False)
                s.append(
                    f'<a href="{GITHUB}/commit/{v.sha}" class="ponto {classe(r)}" data-dica="{e(dica)}" '
                    f'aria-label="{e(rotulo(r))}, versão de {data_br(v.data)}">'
                    f'<circle class="alvo" cx="{x(_dia(v.data)):.1f}" cy="{y + dy:.1f}" r="9"/>'
                    f'<circle class="bola" cx="{x(_dia(v.data)):.1f}" cy="{y + dy:.1f}" r="4.5"/></a>')
    s.append("</svg>")

    lista_html = []
    for r in sorted(regs, key=lambda r: (r.doc.nome_empresa.lower(), r.doc.nome)):
        datas = ", ".join(f'<a href="{GITHUB}/commit/{v.sha}">{data_br(v.data)}</a>' for v in r.versoes)
        lista_html.append(f"<li><b>{e(rotulo(r))}</b>: {datas}</li>")
    return "".join(s), "\n".join(lista_html)


def barras_leitura(regs: list[Registro]) -> tuple[str, str]:
    ordem = sorted(regs, key=lambda r: -r.minutos)
    maior = ordem[0].minutos or 1

    def li(r: Registro) -> str:
        w = 100 * r.minutos / maior
        return (f'<li><a class="rotulo" href="{arquivo_github(r)}">{e(rotulo(r))}</a>'
                f'<span class="trilho"><span class="barra {classe(r)}" style="width:{w:.2f}%"></span></span>'
                f'<span class="valor">{tempo_leitura(r.minutos)}</span></li>')
    topo = "\n".join(li(r) for r in ordem[:15])
    resto = "\n".join(li(r) for r in ordem[15:])
    return topo, resto


def secao_crescimento(regs: list[Registro], hoje: date) -> tuple[str, int]:
    dados = []
    for r in regs:
        if len(r.versoes) < 2:
            continue
        v0, v1 = r.versoes[0], r.versoes[-1]
        if (hoje - _dia(v0.data)).days < 730 or not v0.palavras:
            continue
        dados.append((v1.palavras / v0.palavras, r, v0, v1))
    dados.sort(key=lambda x: -x[0])
    dados = [d for d in dados if d[0] >= 1.15][:12]
    if not dados:
        return "", 0
    maior = max(max(v0.palavras, v1.palavras) for _, _, v0, v1 in dados)
    L, X0, X1, H = 1000, 300, 830, 34

    def x(p: int) -> float:
        return X0 + (X1 - X0) * p / maior

    altura = H * len(dados) + 30
    s = [f'<svg class="crescimento" viewBox="0 0 {L} {altura}" role="img" '
         f'aria-label="Tamanho da primeira versão arquivada e de hoje, em palavras">']
    passo = 2000 if maior > 8000 else 1000
    for p in range(0, maior + 1, passo):
        s.append(f'<rect class="grade" x="{x(p):.1f}" y="0" width="1" height="{altura - 26}"/>')
        s.append(f'<text class="eixo" x="{x(p):.1f}" y="{altura - 8}" text-anchor="middle">'
                 f'{num(p) if p < 1000 else str(p // 1000) + " mil"}</text>')
    for i, (fator, r, v0, v1) in enumerate(dados):
        y = H * i + H / 2
        s.append(f'<text class="empresa" x="0" y="{y + 4.5:.1f}">{e(rotulo(r))}</text>')
        s.append(f'<rect class="ligacao" x="{x(v0.palavras):.1f}" y="{y - 1:.1f}" '
                 f'width="{x(v1.palavras) - x(v0.palavras):.1f}" height="2" rx="1"/>')
        s.append(f'<circle class="antes" cx="{x(v0.palavras):.1f}" cy="{y:.1f}" r="4.5"/>')
        s.append(f'<circle class="bola {classe(r)}" cx="{x(v1.palavras):.1f}" cy="{y:.1f}" r="5"/>')
        s.append(f'<text class="fator" x="{L}" y="{y + 4.5:.1f}" text-anchor="end">'
                 f'{f"{fator:.1f}".replace(".", ",")}× desde {v0.data[:4]}</text>')
    s.append("</svg>")
    return "".join(s), len(dados)


def secao_assuntos(regs: list[Registro]) -> str:
    total = len(regs)
    linhas = []
    for termo in TERMOS:
        com = [r for r in regs if termo in r.termos]
        primeiro: dict[str, tuple[str, Registro]] = {}
        for r in regs:
            pm = primeira_mencao(r).get(termo)
            if pm and r.versoes and pm != r.versoes[0].data:
                if r.doc.empresa not in primeiro or pm < primeiro[r.doc.empresa][0]:
                    primeiro[r.doc.empresa] = (pm, r)
        aparicoes = sorted(primeiro.values(), key=lambda x: x[0])
        if aparicoes:
            itens = ", ".join(f"{e(r.doc.nome_empresa)} ({mes_ano(d)})" for d, r in aparicoes[:6])
            if len(aparicoes) > 6:
                itens += f" e mais {len(aparicoes) - 6}"
        else:
            itens = '<span class="suave">já estava em todas as primeiras versões arquivadas</span>' if com else \
                '<span class="suave">nenhum documento</span>'
        pct = 100 * len(com) / total if total else 0
        linhas.append(
            f'<tr><th scope="row">{e(termo)}</th>'
            f'<td class="n"><span class="medidor"><span style="width:{pct:.1f}%"></span></span>'
            f'{len(com)} de {total}</td><td>{itens}</td></tr>')
    return "\n".join(linhas)


def tabela_documentos(regs: list[Registro]) -> str:
    linhas = []
    for r in sorted(regs, key=lambda r: (r.doc.nome_empresa.lower(), r.doc.nome)):
        v0, v1 = r.versoes[0], r.versoes[-1]
        linhas.append(
            f'<tr><td data-v="{e(rotulo(r).lower())}"><a href="{arquivo_github(r)}">{e(rotulo(r))}</a></td>'
            f'<td data-v="{e(r.doc.categoria)}">{e(r.doc.categoria)}</td>'
            f'<td class="n" data-v="{r.palavras}">{num(r.palavras)}</td>'
            f'<td class="n" data-v="{r.minutos:.1f}">{tempo_leitura(r.minutos)}</td>'
            f'<td class="n" data-v="{len(r.versoes)}">{len(r.versoes)}</td>'
            f'<td class="n" data-v="{v0.data}">{mes_ano(v0.data)}</td>'
            f'<td class="n" data-v="{v1.data}">{data_br(v1.data)}</td>'
            f'<td><a href="{r.historico}">histórico</a></td></tr>')
    return "\n".join(linhas)


# ------------------------------------------------------------------ página
def gerar_pagina(registros: list[Registro], hoje: date) -> str:
    regs = [r for r in registros if r.existe]
    n_emp = len({r.doc.empresa for r in regs})
    n_versoes = sum(len(r.versoes) for r in regs)
    palavras = sum(r.palavras for r in regs)
    minutos = sum(r.minutos for r in regs)
    ano0 = min(r.versoes[0].data[:4] for r in regs)
    horas = round(minutos / 60)
    numero = f"{horas} horas" if minutos >= 120 else tempo_por_extenso(minutos)

    tempo_svg, tempo_lista = secao_linha_do_tempo(regs, hoje)
    topo, resto = barras_leitura(regs)
    cresc_svg, n_cresc = secao_crescimento(regs, hoje)
    maior = max(regs, key=lambda r: r.minutos)
    mais_mudou = max(regs, key=lambda r: len(r.versoes))
    exemplo = next((r for r in regs if r.chave == "nubank/politica-de-privacidade"), regs[0])

    pagina = MODELO
    trocas = {
        "{{MIUDAS}}": letras_miudas(regs),
        "{{NUMERO}}": e(numero),
        "{{N_EMP}}": str(n_emp),
        "{{N_DOCS}}": str(len(regs)),
        "{{N_VERSOES}}": num(n_versoes),
        "{{PALAVRAS_MIL}}": num(round(palavras / 1000)),
        "{{ANO0}}": ano0,
        "{{PPM}}": str(PALAVRAS_POR_MINUTO),
        "{{RECENTES}}": secao_recentes(regs),
        "{{TEMPO_SVG}}": tempo_svg,
        "{{TEMPO_LISTA}}": tempo_lista,
        "{{BARRAS_TOPO}}": topo,
        "{{BARRAS_RESTO}}": resto,
        "{{N_RESTO}}": str(len(regs) - 15),
        "{{MAIOR}}": e(rotulo(maior)),
        "{{MAIOR_TEMPO}}": e(tempo_por_extenso(maior.minutos)),
        "{{MAIS_MUDOU}}": e(rotulo(mais_mudou)),
        "{{MAIS_MUDOU_N}}": str(len(mais_mudou.versoes)),
        "{{MAIS_MUDOU_DESDE}}": mes_ano(mais_mudou.versoes[0].data),
        "{{CRESC_SVG}}": cresc_svg,
        "{{ASSUNTOS}}": secao_assuntos(regs),
        "{{TABELA}}": tabela_documentos(regs),
        "{{GITHUB}}": GITHUB,
        "{{RAW_LLMS}}": f"https://raw.githubusercontent.com/{REPO}/main/llms.txt",
        "{{PAGES}}": PAGES,
        "{{GITMCP}}": f"https://gitmcp.io/{REPO}",
        "{{EXEMPLO_RAW}}": exemplo.raw,
        "{{EXEMPLO_EMPRESA}}": e(("o " if exemplo.doc.empresa in ("nubank", "inter", "itau", "bradesco", "google", "airbnb", "uber", "spotify", "whatsapp", "instagram", "tiktok") else "a ") + exemplo.doc.nome_empresa),
    }
    for k, v in trocas.items():
        pagina = pagina.replace(k, v)
    if not n_cresc:
        pagina = pagina.replace('<section id="cresceram"', '<section hidden id="cresceram"')
    if not resto:
        pagina = pagina.replace('<details class="mais">', '<details class="mais" hidden>')
    return pagina


MODELO = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Letras miúdas em números</title>
<meta name="description" content="{{NUMERO}} para ler os termos de uso e as políticas de privacidade de {{N_EMP}} empresas. Versões arquivadas desde {{ANO0}}, com o histórico de cada mudança.">
<meta property="og:title" content="Letras miúdas em números">
<meta property="og:description" content="{{NUMERO}} para ler os termos de uso e as políticas de privacidade de {{N_EMP}} empresas que você usa.">
<meta property="og:url" content="{{PAGES}}">
<meta name="color-scheme" content="light dark">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Next:wght@400;600;800&display=swap" rel="stylesheet">
<style>
:root {
  color-scheme: light;
  --papel: #fbfcfd; --cartao: #ffffff; --tinta: #18202e; --tinta2: #3f4859; --suave: #646d7e;
  --miuda: #b9c0cc; --regua: #e3e6ec; --grade: #eceef2; --trilha: #d3d8e0; --link: #1f4fd1;
  --termos: #2a78d6; --privacidade: #eb6834; --outro: #1baf7a; --foco: #1f4fd1;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-tema="claro"]) {
    color-scheme: dark;
    --papel: #0e1116; --cartao: #151a21; --tinta: #e8ebf0; --tinta2: #c0c7d2; --suave: #8f99a8;
    --miuda: #313a48; --regua: #262d38; --grade: #1d232c; --trilha: #343c49; --link: #8fb0ff;
    --termos: #3987e5; --privacidade: #d95926; --outro: #199e70; --foco: #8fb0ff;
  }
}
:root[data-tema="escuro"] {
  color-scheme: dark;
  --papel: #0e1116; --cartao: #151a21; --tinta: #e8ebf0; --tinta2: #c0c7d2; --suave: #8f99a8;
  --miuda: #313a48; --regua: #262d38; --grade: #1d232c; --trilha: #343c49; --link: #8fb0ff;
  --termos: #3987e5; --privacidade: #d95926; --outro: #199e70; --foco: #8fb0ff;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--papel); color: var(--tinta);
  font: 17px/1.55 "Atkinson Hyperlegible Next", "Atkinson Hyperlegible", system-ui, -apple-system, "Segoe UI", sans-serif;
}
a { color: var(--link); text-underline-offset: .18em; }
a:focus-visible, button:focus-visible, input:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; border-radius: 3px; }
.coluna { max-width: 1060px; margin: 0 auto; padding: 0 20px; }

/* topo: o fundo é o próprio texto miúdo */
.topo { position: relative; overflow: hidden; border-bottom: 1px solid var(--regua); }
.miudas {
  position: absolute; inset: 0; margin: 0; padding: 10px 12px;
  font: 6.6px/1.32 ui-serif, Georgia, "Times New Roman", serif; color: var(--miuda);
  text-align: justify; hyphens: auto; word-break: break-word; user-select: none;
  -webkit-mask-image: linear-gradient(to bottom, #000 55%, transparent 100%);
  mask-image: linear-gradient(to bottom, #000 55%, transparent 100%);
}
.topo .coluna { position: relative; padding-top: 72px; padding-bottom: 88px; }
.recorte {
  background: var(--papel); max-width: 640px; padding: 26px 30px 30px 30px; margin-left: -30px;
  box-shadow: 0 0 0 10px var(--papel);
}
h1 { margin: 0 0 14px; font-weight: 400; }
@media (max-width: 640px) {
  .topo .coluna { padding-top: 64px; padding-bottom: 64px; }
  .recorte { margin-left: 0; padding: 20px 18px 22px; box-shadow: none; }
}
.numero { display: block; font-size: clamp(64px, 13vw, 140px); line-height: .92; font-weight: 800; letter-spacing: -.035em; margin: 0 0 18px; }
.frase { display: block; font-size: clamp(19px, 2.4vw, 23px); line-height: 1.42; max-width: 30em; }
.fundo-nota { color: var(--suave); font-size: 15px; margin: 0 0 24px; }
.acoes { display: flex; flex-wrap: wrap; gap: 12px 22px; align-items: center; margin: 0; }
.botao {
  display: inline-block; background: var(--tinta); color: var(--papel); text-decoration: none;
  padding: 11px 18px; border-radius: 8px; font-weight: 600;
}
.tema {
  position: absolute; top: 18px; right: 20px; z-index: 2; font: inherit; font-size: 14px;
  color: var(--tinta2); background: var(--papel); border: 1px solid var(--regua); border-radius: 8px;
  padding: 6px 12px; cursor: pointer;
}

/* números */
.numeros { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 22px 28px; margin: 44px 0 8px; }
.numeros div { border-top: 2px solid var(--tinta); padding-top: 10px; }
.numeros b { display: block; font-size: 34px; line-height: 1.1; font-weight: 800; letter-spacing: -.02em; }
.numeros span { color: var(--suave); font-size: 15px; }

section { margin: 76px 0 0; }
h2 { font-size: clamp(25px, 3.2vw, 32px); line-height: 1.15; letter-spacing: -.015em; margin: 0 0 10px; }
.lede { color: var(--tinta2); max-width: 68ch; margin: 0 0 24px; }
.suave { color: var(--suave); }
.nota { color: var(--suave); font-size: 15px; max-width: 72ch; margin: 14px 0 0; }

.legenda { display: flex; flex-wrap: wrap; gap: 6px 20px; margin: 0 0 14px; font-size: 15px; color: var(--tinta2); }
.legenda span, .quem { display: inline-flex; align-items: center; gap: 8px; }
.marca { width: 10px; height: 10px; border-radius: 50%; flex: none; display: inline-block; }
.marca.termos, .barra.termos, .bola.termos, .ponto.termos .bola { background: var(--termos); fill: var(--termos); }
.marca.privacidade, .barra.privacidade, .bola.privacidade, .ponto.privacidade .bola { background: var(--privacidade); fill: var(--privacidade); }
.marca.outro, .barra.outro, .bola.outro, .ponto.outro .bola { background: var(--outro); fill: var(--outro); }

/* mudanças recentes */
.recentes { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--regua); }
.recentes li {
  display: grid; grid-template-columns: 110px 1fr 140px 210px; gap: 4px 20px; align-items: baseline;
  padding: 11px 0; border-bottom: 1px solid var(--regua);
}
.recentes time { font-variant-numeric: tabular-nums; color: var(--tinta2); }
.recentes .origem { color: var(--suave); font-size: 15px; }
.recentes a { justify-self: end; }
@media (max-width: 640px) {
  .recentes li { grid-template-columns: 1fr auto; }
  .recentes .origem { display: none; }
  .recentes time { grid-column: 1 / -1; font-size: 14px; }
}

/* gráficos em svg */
.rolagem { overflow-x: auto; -webkit-overflow-scrolling: touch; }
svg { display: block; width: 100%; height: auto; font-family: inherit; }
svg.tempo { min-width: 760px; }
svg.crescimento { min-width: 640px; }
svg .grade { fill: var(--grade); }
svg .trilha { fill: var(--trilha); }
svg .eixo { fill: var(--suave); font-size: 12px; font-variant-numeric: tabular-nums; }
svg .empresa { fill: var(--tinta); font-size: 13.5px; font-weight: 600; }
svg .fator { fill: var(--tinta2); font-size: 13.5px; font-variant-numeric: tabular-nums; }
svg .bola { stroke: var(--papel); stroke-width: 2; }
svg .alvo { fill: transparent; }
svg .ponto { cursor: pointer; }
svg .ponto:hover .bola, svg .ponto:focus .bola { stroke: var(--tinta); }
svg .ligacao { fill: var(--trilha); }
svg .antes { fill: var(--papel); stroke: var(--suave); stroke-width: 2; }
.dica {
  position: fixed; z-index: 10; pointer-events: none; max-width: 280px;
  background: var(--cartao); color: var(--tinta); border: 1px solid var(--regua); border-radius: 10px;
  padding: 10px 12px; font-size: 14px; line-height: 1.4; box-shadow: 0 6px 24px rgb(0 0 0 / .12);
}
.dica b { display: block; }
.dica .suave { font-size: 13px; }

/* barras */
.barras { list-style: none; margin: 0; padding: 0; }
.barras li {
  display: grid; grid-template-columns: minmax(150px, 290px) 1fr 64px; gap: 14px; align-items: center;
  padding: 4px 0;
}
.barras .rotulo { color: var(--tinta); text-decoration: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.barras .rotulo:hover { text-decoration: underline; }
.trilho { display: block; height: 14px; }
.barra { display: block; height: 14px; border-radius: 0 4px 4px 0; min-width: 3px; }
.valor { text-align: right; font-variant-numeric: tabular-nums; color: var(--tinta2); }
details.mais { margin-top: 6px; }
details.mais summary { cursor: pointer; color: var(--link); padding: 8px 0; }
@media (max-width: 640px) {
  .barras li { grid-template-columns: 1fr 56px; gap: 2px 12px; }
  .barras .rotulo { grid-column: 1 / -1; font-size: 15px; }
}

/* tabelas */
table { width: 100%; border-collapse: collapse; font-size: 15.5px; }
th, td { text-align: left; padding: 9px 12px 9px 0; border-bottom: 1px solid var(--regua); vertical-align: top; }
thead th { font-size: 14px; color: var(--suave); font-weight: 600; border-bottom-color: var(--tinta2); }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.assuntos th[scope=row] { font-weight: 600; white-space: nowrap; }
.medidor { display: inline-block; width: 70px; height: 8px; border-radius: 4px; background: var(--grade); margin-right: 10px; vertical-align: middle; overflow: hidden; }
.medidor span { display: block; height: 8px; background: var(--tinta2); border-radius: 0 4px 4px 0; }
.ordenar { font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: pointer; }
.ordenar[aria-sort]::after { content: attr(data-seta); margin-left: 4px; }
.filtro {
  font: inherit; width: 100%; max-width: 340px; padding: 9px 12px; margin: 0 0 14px;
  border: 1px solid var(--regua); border-radius: 8px; background: var(--cartao); color: var(--tinta);
}
.lista-versoes { font-size: 15px; color: var(--tinta2); padding-left: 18px; }
.lista-versoes li { margin: 4px 0; }

pre.prompt {
  background: var(--cartao); border: 1px solid var(--regua); border-radius: 10px; padding: 14px 16px;
  white-space: pre-wrap; font: 15px/1.5 ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace; margin: 12px 0;
}
.passos { padding-left: 22px; max-width: 72ch; }
.passos li { margin: 8px 0; }
code { font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace; font-size: .9em; }
pre.prompt, code { overflow-wrap: anywhere; }

footer { margin: 96px 0 0; padding: 28px 0 60px; border-top: 1px solid var(--regua); color: var(--suave); font-size: 15px; }
footer p { max-width: 76ch; }
@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
</style>
</head>
<body>
<header class="topo">
  <p class="miudas" aria-hidden="true">{{MIUDAS}}</p>
  <button class="tema" type="button" id="tema">Tema: automático</button>
  <div class="coluna">
    <div class="recorte">
      <h1><span class="numero">{{NUMERO}}</span> <span class="frase">é o tempo para ler, sem parar, os termos de uso e as políticas de privacidade de {{N_EMP}} empresas que você usa.</span></h1>
      <p class="fundo-nota">O fundo desta página é um pedaço desse texto.</p>
      <p class="acoes"><a class="botao" href="{{GITHUB}}">Abrir o acervo no GitHub</a><a href="#recentes">Ver as últimas mudanças</a></p>
    </div>
  </div>
</header>

<main class="coluna">
  <div class="numeros">
    <div><b>{{N_EMP}}</b><span>empresas</span></div>
    <div><b>{{N_DOCS}}</b><span>documentos</span></div>
    <div><b>{{N_VERSOES}}</b><span>versões arquivadas</span></div>
    <div><b>{{ANO0}}</b><span>ano da versão mais antiga</span></div>
    <div><b>{{PALAVRAS_MIL}} mil</b><span>palavras nos textos de hoje</span></div>
  </div>

  <section id="recentes">
    <h2>As mudanças mais recentes</h2>
    <p class="lede">Cada linha é uma versão nova de um documento, com a data em que ela apareceu. O link abre o diff no GitHub: o que saiu em vermelho, o que entrou em verde.</p>
    <ol class="recentes">
{{RECENTES}}
    </ol>
  </section>

  <section id="linha-do-tempo">
    <h2>Quantas vezes cada um mudou</h2>
    <p class="lede">Cada ponto é uma versão nova do texto. A linha cinza mostra desde quando a empresa está arquivada. O que mais mudou foi {{MAIS_MUDOU}}: {{MAIS_MUDOU_N}} versões desde {{MAIS_MUDOU_DESDE}}. Clique num ponto para ver o que mudou naquela versão.</p>
    <div class="legenda"><span><i class="marca termos"></i>Termos de uso</span><span><i class="marca privacidade"></i>Política de privacidade</span></div>
    <div class="rolagem">{{TEMPO_SVG}}</div>
    <details class="mais"><summary>Ver as versões em lista</summary><ul class="lista-versoes">
{{TEMPO_LISTA}}
    </ul></details>
  </section>

  <section id="leitura">
    <h2>Quanto tempo leva para ler cada um</h2>
    <p class="lede">O mais longo é {{MAIOR}}: {{MAIOR_TEMPO}} de leitura. A conta usa {{PPM}} palavras por minuto, a média de leitura silenciosa de adultos, sem pausa para entender juridiquês.</p>
    <div class="legenda"><span><i class="marca termos"></i>Termos de uso</span><span><i class="marca privacidade"></i>Política de privacidade</span></div>
    <ol class="barras">
{{BARRAS_TOPO}}
    </ol>
    <details class="mais"><summary>Mostrar os outros {{N_RESTO}}</summary><ol class="barras" start="16">
{{BARRAS_RESTO}}
    </ol></details>
  </section>

  <section id="cresceram">
    <h2>Os que mais cresceram</h2>
    <p class="lede">Tamanho da primeira versão arquivada (círculo vazio) e de hoje (círculo cheio), em palavras. Só entram documentos com pelo menos dois anos de histórico.</p>
    <div class="rolagem">{{CRESC_SVG}}</div>
  </section>

  <section id="assuntos">
    <h2>Quando cada assunto apareceu</h2>
    <p class="lede">Quantos documentos falam de cada assunto hoje e quais passaram a falar depois da primeira versão arquivada. Aparecer não quer dizer fazer: às vezes o texto cita o assunto para dizer que a empresa não faz aquilo. Confira o trecho no histórico.</p>
    <div class="rolagem"><table class="assuntos">
      <thead><tr><th>Assunto</th><th class="n">Documentos hoje</th><th>Começaram a falar disso</th></tr></thead>
      <tbody>
{{ASSUNTOS}}
      </tbody>
    </table></div>
  </section>

  <section id="documentos">
    <h2>Todos os documentos</h2>
    <p class="lede">Clique no nome para ler o texto atual e em histórico para ver todas as versões. Clique no título de uma coluna para ordenar.</p>
    <label class="suave" for="filtro">Procurar empresa</label><br>
    <input class="filtro" id="filtro" type="search" placeholder="Ex.: Nubank" autocomplete="off">
    <div class="rolagem"><table id="tabela">
      <thead><tr>
        <th><button class="ordenar" data-col="0">Documento</button></th>
        <th><button class="ordenar" data-col="1">Categoria</button></th>
        <th class="n"><button class="ordenar" data-col="2">Palavras</button></th>
        <th class="n"><button class="ordenar" data-col="3">Leitura</button></th>
        <th class="n"><button class="ordenar" data-col="4">Versões</button></th>
        <th class="n"><button class="ordenar" data-col="5">Desde</button></th>
        <th class="n"><button class="ordenar" data-col="6">Última versão</button></th>
        <th>Links</th>
      </tr></thead>
      <tbody>
{{TABELA}}
      </tbody>
    </table></div>
  </section>

  <section id="ia">
    <h2>Pergunte para a sua IA</h2>
    <p class="lede">Ninguém precisa ler tudo isso. Os textos estão em Markdown, num formato que qualquer IA lê, com um índice em <a href="{{RAW_LLMS}}">llms.txt</a>.</p>
    <ol class="passos">
      <li>Para um documento: no ChatGPT, Claude ou Gemini com acesso à web, cole o link do texto e pergunte. Por exemplo:
        <pre class="prompt">Leia {{EXEMPLO_RAW}} e me diga com quem {{EXEMPLO_EMPRESA}} compartilha meus dados. Cite os trechos.</pre></li>
      <li>Para o acervo todo: clone o repositório e abra a pasta no Claude Code, Cursor ou Codex, ou conecte o repositório como servidor MCP pelo GitMCP (<code>{{GITMCP}}</code>). Aí dá para perguntar coisas como “quais empresas dizem usar meus dados para treinar IA?” ou “o que mudou na política do WhatsApp desde 2021?”.</li>
    </ol>
  </section>

  <footer>
    <p><b>De onde vêm os números.</b> As versões antigas vêm das capturas do Wayback Machine (archive.org); desde outubro de 2026, um robô confere as páginas oficiais todo dia. A data de cada versão é a da captura em que ela apareceu, então indica quando o texto já estava no ar, não o dia exato da publicação. Mudanças só de formatação não contam como versão nova. O tempo de leitura usa {{PPM}} palavras por minuto (Brysbaert, 2019, <i>Journal of Memory and Language</i>).</p>
    <p>Projeto independente, sem vínculo com as empresas. Os textos pertencem a elas e estão aqui para transparência e pesquisa. Nada aqui é orientação jurídica. Código aberto em <a href="{{GITHUB}}">{{GITHUB}}</a>.</p>
  </footer>
</main>

<div class="dica" id="dica" hidden></div>

<script>
(() => {
  // tema: automático, claro ou escuro (lembrado neste navegador, se der)
  const raiz = document.documentElement, botao = document.getElementById("tema");
  const nomes = { auto: "automático", claro: "claro", escuro: "escuro" };
  let tema = "auto";
  try { tema = localStorage.getItem("tema") || "auto"; } catch (e) {}
  const aplicar = () => {
    if (tema === "auto") raiz.removeAttribute("data-tema"); else raiz.setAttribute("data-tema", tema);
    botao.textContent = "Tema: " + nomes[tema];
  };
  aplicar();
  botao.addEventListener("click", () => {
    tema = tema === "auto" ? "claro" : tema === "claro" ? "escuro" : "auto";
    try { localStorage.setItem("tema", tema); } catch (e) {}
    aplicar();
  });

  // dica ao passar o mouse (ou focar com o teclado) num ponto da linha do tempo
  const dica = document.getElementById("dica");
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const mostrar = (el, x, y) => {
    const d = JSON.parse(el.dataset.dica);
    let mudou = "";
    if (d.k === 0) mudou = "primeira versão arquivada";
    else mudou = d.a + " → " + d.p + " palavras";
    dica.innerHTML = "<b>" + esc(d.t) + "</b>versão de " + esc(d.d) + "<br><span class=suave>" + esc(mudou) +
      "<br>fonte: " + esc(d.o) + "<br>clique para ver o que mudou</span>";
    dica.hidden = false;
    const r = dica.getBoundingClientRect();
    const px = Math.min(x + 14, window.innerWidth - r.width - 8), py = y + 16 + r.height > window.innerHeight ? y - r.height - 12 : y + 16;
    dica.style.left = Math.max(8, px) + "px"; dica.style.top = py + "px";
  };
  document.querySelectorAll(".ponto").forEach(el => {
    el.addEventListener("mousemove", ev => mostrar(el, ev.clientX, ev.clientY));
    el.addEventListener("mouseleave", () => { dica.hidden = true; });
    el.addEventListener("focus", () => { const b = el.getBoundingClientRect(); mostrar(el, b.right, b.bottom); });
    el.addEventListener("blur", () => { dica.hidden = true; });
  });

  // tabela: ordenar e filtrar
  const tabela = document.getElementById("tabela");
  const corpo = tabela.tBodies[0];
  tabela.querySelectorAll(".ordenar").forEach(b => b.addEventListener("click", () => {
    const col = +b.dataset.col, atual = b.getAttribute("aria-sort");
    const desc = atual ? atual === "ascending" : col >= 2;
    tabela.querySelectorAll(".ordenar").forEach(o => { o.removeAttribute("aria-sort"); });
    b.setAttribute("aria-sort", desc ? "descending" : "ascending");
    b.dataset.seta = desc ? "↓" : "↑";
    const linhas = [...corpo.rows];
    const val = tr => { const v = tr.cells[col].dataset.v; return col >= 2 && col <= 4 ? +v : v; };
    linhas.sort((a, z) => { const x = val(a), y = val(z); return (x > y ? 1 : x < y ? -1 : 0) * (desc ? -1 : 1); });
    linhas.forEach(tr => corpo.appendChild(tr));
  }));
  const filtro = document.getElementById("filtro");
  const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  filtro.addEventListener("input", () => {
    const q = norm(filtro.value.trim());
    [...corpo.rows].forEach(tr => { tr.hidden = q && !norm(tr.textContent).includes(q); });
  });
})();
</script>
</body>
</html>
"""
