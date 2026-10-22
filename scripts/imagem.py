"""Gera a imagem do topo do README: cada empresa numa linha, cada ponto uma versão nova do texto.

Saída: linha-do-tempo.svg (tema escuro) e linha-do-tempo-claro.svg (tema claro). O README usa
<picture> para mostrar a que combina com o tema de quem está vendo.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from html import escape

from acervo import Registro

TEMAS = {
    "escuro": {"fundo": "#0d1117", "texto": "#e6edf3", "suave": "#8b949e", "grade": "#21262d",
               "trilha": "#30363d", "termos-de-uso": "#3987e5", "politica-de-privacidade": "#d95926",
               "outro": "#199e70"},
    "claro": {"fundo": "#ffffff", "texto": "#1f2328", "suave": "#59636e", "grade": "#eaeef2",
              "trilha": "#d1d9e0", "termos-de-uso": "#2a78d6", "politica-de-privacidade": "#eb6834",
              "outro": "#1baf7a"},
}
FONTE = "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"
LARGURA = 1180
X0, X1 = 230, 1068          # área do gráfico
LINHA = 19                  # altura de cada empresa
TOPO = 150                  # onde começa a primeira linha


def _num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _dia(d: str) -> date:
    return date(int(d[:4]), int(d[5:7]), int(d[8:10]))


def tempo_leitura(minutos: float) -> str:
    m = round(minutos)
    if m < 60:
        return f"{max(m, 1)} min"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}"


def tempo_por_extenso(minutos: float) -> str:
    m = round(minutos)
    if m >= 120:
        return f"cerca de {round(m / 60)} horas"
    if m >= 60:
        resto = m - 60
        return "1 hora" + ("" if not resto else " e 1 minuto" if resto == 1 else f" e {resto} minutos")
    return "1 minuto" if m <= 1 else f"{m} minutos"


def gerar_svg(registros: list[Registro], tema: str, hoje: date) -> str:
    c = TEMAS[tema]
    por_empresa: dict[str, list[Registro]] = defaultdict(list)
    for r in registros:
        if r.existe:
            por_empresa[r.doc.empresa].append(r)

    linhas = []
    for slug, regs in por_empresa.items():
        datas = [v.data for r in regs for v in r.versoes]
        linhas.append((min(datas), regs[0].doc.nome_empresa, regs))
    linhas.sort(key=lambda x: (x[0], x[1].lower()))

    ano0 = min(int(x[0][:4]) for x in linhas)
    ano1 = hoje.year
    ini, fim = date(ano0, 1, 1), date(ano1 + 1, 1, 1)
    dias = (fim - ini).days

    def x(d: date) -> float:
        return X0 + (X1 - X0) * (d - ini).days / dias

    n_docs = sum(len(x[2]) for x in linhas)
    n_versoes = sum(len(r.versoes) for x in linhas for r in x[2])
    minutos = sum(r.minutos for x in linhas for r in x[2])
    altura = TOPO + LINHA * len(linhas) + 64

    s = []
    a = s.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{altura}" '
      f'viewBox="0 0 {LARGURA} {altura}" font-family="{FONTE}" role="img" '
      f'aria-label="Linha do tempo das versões de termos de uso e políticas de privacidade">')
    a(f'<rect width="{LARGURA}" height="{altura}" fill="{c["fundo"]}"/>')
    a(f'<text x="24" y="42" font-size="22" font-weight="700" fill="{c["texto"]}">'
      f'Termos de uso e políticas de privacidade, versão por versão</text>')
    a(f'<text x="24" y="68" font-size="14" fill="{c["texto"]}">{len(linhas)} empresas, {n_docs} documentos e '
      f'{_num(n_versoes)} versões arquivadas desde {ano0}. Ler tudo o que vale hoje, sem parar, leva '
      f'{tempo_por_extenso(minutos)}.</text>')

    # legenda
    ly = 98
    a(f'<circle cx="30" cy="{ly - 4}" r="5" fill="{c["termos-de-uso"]}"/>')
    a(f'<text x="42" y="{ly}" font-size="12.5" fill="{c["texto"]}">Termos de uso</text>')
    a(f'<circle cx="150" cy="{ly - 4}" r="5" fill="{c["politica-de-privacidade"]}"/>')
    a(f'<text x="162" y="{ly}" font-size="12.5" fill="{c["texto"]}">Política de privacidade</text>')
    a(f'<text x="330" y="{ly}" font-size="12.5" fill="{c["suave"]}">Cada ponto é uma versão nova do texto. '
      f'A linha cinza mostra desde quando o documento está arquivado.</text>')
    a(f'<text x="{LARGURA - 24}" y="{TOPO - 22}" font-size="11.5" text-anchor="end" fill="{c["suave"]}">'
      f'tempo de leitura</text>')

    # anos
    base = TOPO + LINHA * len(linhas) - 4
    for ano in range(ano0, ano1 + 2):
        gx = x(date(ano, 1, 1))
        a(f'<rect x="{gx:.1f}" y="{TOPO - 14}" width="1" height="{base - TOPO + 14}" fill="{c["grade"]}"/>')
        if ano <= ano1:
            meio = (gx + x(date(ano + 1, 1, 1))) / 2
            a(f'<text x="{meio:.1f}" y="{TOPO - 22}" font-size="11.5" text-anchor="middle" '
              f'fill="{c["suave"]}">{ano}</text>')

    for i, (desde, nome, regs) in enumerate(linhas):
        y = TOPO + LINHA * i + LINHA / 2 - 2
        a(f'<text x="24" y="{y + 4.5:.1f}" font-size="13" font-weight="600" fill="{c["texto"]}">'
          f'{escape(nome)}</text>')
        x_ini = x(_dia(desde))
        a(f'<rect x="{x_ini:.1f}" y="{y - 0.75:.2f}" width="{max(X1 - x_ini, 1):.1f}" height="1.5" '
          f'rx="0.75" fill="{c["trilha"]}"/>')
        for r in sorted(regs, key=lambda r: r.doc.tipo):
            cor = c.get(r.doc.tipo, c["outro"])
            dy = 0 if len(regs) == 1 else -3.5 if r.doc.tipo == "termos-de-uso" else 3.5
            for v in r.versoes:
                a(f'<circle cx="{x(_dia(v.data)):.1f}" cy="{y + dy:.1f}" r="4" fill="{cor}" '
                  f'stroke="{c["fundo"]}" stroke-width="2"/>')
        minutos_emp = sum(r.minutos for r in regs)
        a(f'<text x="{LARGURA - 24}" y="{y + 4.5:.1f}" font-size="12" text-anchor="end" '
          f'fill="{c["suave"]}">{tempo_leitura(minutos_emp)}</text>')

    rod = base + 34
    a(f'<text x="24" y="{rod}" font-size="11.5" fill="{c["suave"]}">Versões antigas: capturas do Wayback '
      f'Machine. Desde out/2026, um robô confere os documentos todo dia. Leitura a 238 palavras por minuto.</text>')
    a(f'<text x="{LARGURA - 24}" y="{rod}" font-size="11.5" text-anchor="end" fill="{c["suave"]}">'
      f'github.com/GabrielVesal/letras-miudas</text>')
    a("</svg>")
    return "".join(s) + "\n"
