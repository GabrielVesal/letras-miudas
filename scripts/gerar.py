"""Gera tudo o que é derivado do acervo: tabelas do README, llms.txt, dados/documentos.json,
a imagem do topo do README e a página de estatísticas (index.html).

Uso: python scripts/gerar.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from acervo import (  # noqa: E402
    GITHUB, PALAVRAS_POR_MINUTO, RAW, TERMOS, Registro, carregar_acervo, ordem_categoria, primeira_mencao,
)
from comum import RAIZ, REPO  # noqa: E402
from imagem import gerar_svg, tempo_leitura, tempo_por_extenso  # noqa: E402

PAGINA = "https://gabrielvesal.github.io/letras-miudas/"

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def mes_ano(d: str) -> str:
    return f"{MESES[int(d[5:7]) - 1]}/{d[:4]}"


def num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def trocar_bloco(texto: str, nome: str, conteudo: str) -> str:
    ini, fim = f"<!-- {nome} -->", f"<!-- /{nome} -->"
    bloco = f"{ini}\n{conteudo.rstrip()}\n{fim}"
    if fim in texto:
        return re.sub(re.escape(ini) + r".*?" + re.escape(fim), lambda _: bloco, texto, flags=re.S)
    return texto.replace(ini, bloco)


def por_categoria(registros: list[Registro]) -> dict[str, dict[str, list[Registro]]]:
    saida: dict[str, dict[str, list[Registro]]] = defaultdict(lambda: defaultdict(list))
    for r in registros:
        saida[r.doc.categoria][r.doc.nome_empresa].append(r)
    return {c: dict(sorted(saida[c].items(), key=lambda x: x[0].lower()))
            for c in sorted(saida, key=ordem_categoria)}


# ------------------------------------------------------------------ README
def readme(registros: list[Registro]) -> None:
    cats = por_categoria(registros)
    arquivados = [r for r in registros if r.existe]

    numeros = ["| Categoria | Empresas | Documentos | Versões arquivadas | Tempo de leitura |",
               "| --- | ---: | ---: | ---: | ---: |"]
    for cat, empresas in cats.items():
        regs = [r for lista in empresas.values() for r in lista if r.existe]
        if not regs:
            continue
        numeros.append(f"| {cat} | {len({r.doc.empresa for r in regs})} | {len(regs)} | "
                       f"{num(sum(len(r.versoes) for r in regs))} | {tempo_leitura(sum(r.minutos for r in regs))} |")
    numeros.append(f"| **Total** | **{len({r.doc.empresa for r in arquivados})}** | **{len(arquivados)}** | "
                   f"**{num(sum(len(r.versoes) for r in arquivados))}** | "
                   f"**{tempo_leitura(sum(r.minutos for r in arquivados))}** |")

    empresas_md = ["| Empresa | Documentos | Arquivado desde | Versões |", "| --- | --- | --- | ---: |"]
    for cat, empresas in cats.items():
        empresas_md.append(f"| **{cat}** | | | |")
        for nome, regs in empresas.items():
            links, desde, n = [], None, 0
            for r in sorted(regs, key=lambda r: r.doc.nome):
                if r.existe:
                    links.append(f"[{r.doc.nome}]({r.caminho})")
                    d0 = r.versoes[0].data
                    desde = d0 if desde is None or d0 < desde else desde
                    n += len(r.versoes)
                else:
                    links.append(f"{r.doc.nome} (em breve)")
            empresas_md.append(f"| {nome} | {' · '.join(links)} | {mes_ano(desde) if desde else '-'} | {n or '-'} |")

    ano0 = min(r.versoes[0].data[:4] for r in arquivados)
    resumo = (f"**{len(arquivados)} documentos de {len({r.doc.empresa for r in arquivados})} empresas**, com "
              f"**{num(sum(len(r.versoes) for r in arquivados))} versões** arquivadas desde {ano0}. Ler tudo o que "
              f"vale hoje, sem parar, leva **{tempo_por_extenso(sum(r.minutos for r in arquivados))}**.")

    arq = RAIZ / "README.md"
    texto = arq.read_text(encoding="utf-8")
    texto = trocar_bloco(texto, "RESUMO", resumo)
    texto = trocar_bloco(texto, "NUMEROS", "\n".join(numeros))
    texto = trocar_bloco(texto, "EMPRESAS", "\n".join(empresas_md))
    arq.write_text(texto, encoding="utf-8")


# ------------------------------------------------------------- dados/documentos.json
def documentos_json(registros: list[Registro]) -> list[dict]:
    saida = []
    for r in sorted(registros, key=lambda r: (ordem_categoria(r.doc.categoria), r.doc.nome_empresa.lower(), r.doc.tipo)):
        if not r.existe:
            continue
        saida.append({
            "empresa": r.doc.nome_empresa,
            "empresa_slug": r.doc.empresa,
            "documento": r.doc.nome,
            "tipo": r.doc.tipo,
            "categoria": r.doc.categoria,
            "fonte": r.doc.url,
            "arquivo": r.caminho,
            "texto": r.raw,
            "historico": r.historico,
            "palavras": r.palavras,
            "minutos_de_leitura": round(r.minutos),
            "assuntos": r.termos,
            "situacao": r.status or "ok",
            "versoes": [
                {"data": v.data, "commit": v.sha, "origem": v.origem,
                 "texto": f"https://raw.githubusercontent.com/{REPO}/{v.sha}/{r.caminho}",
                 "diff": f"{GITHUB}/commit/{v.sha}",
                 **({"wayback": v.wayback} if v.wayback else {}),
                 "palavras": v.palavras}
                for v in r.versoes
            ],
        })
    return saida


# ------------------------------------------------------------------ ACHADOS.md
def achados_md(registros: list[Registro]) -> str:
    regs = [r for r in registros if r.existe]
    hoje = max(v.data for r in regs for v in r.versoes)

    def nome(r: Registro) -> str:
        return f"[{r.doc.nome_empresa} · {r.doc.nome}]({r.historico})"

    s = ["# Achados", "",
         "Gerado por `scripts/gerar.py` a partir do histórico do git. As datas são as das capturas em que cada",
         "versão apareceu: indicam quando o texto já estava no ar, não o dia exato da publicação. Em gráficos,",
         f"na [página de estatísticas]({PAGINA}).", "",
         "## Os documentos que mais mudaram", "",
         "| Documento | Versões | Desde |", "| --- | ---: | --- |"]
    for r in sorted(regs, key=lambda r: (-len(r.versoes), r.doc.nome_empresa))[:15]:
        s.append(f"| {nome(r)} | {len(r.versoes)} | {mes_ano(r.versoes[0].data)} |")

    s += ["", "## Os mais longos", "",
          f"Tempo de leitura a {PALAVRAS_POR_MINUTO} palavras por minuto, a média de leitura silenciosa de adultos.", "",
          "| Documento | Palavras | Leitura |", "| --- | ---: | ---: |"]
    for r in sorted(regs, key=lambda r: -r.palavras)[:15]:
        s.append(f"| {nome(r)} | {num(r.palavras)} | {tempo_leitura(r.minutos)} |")

    cresc = []
    for r in regs:
        v0, v1 = r.versoes[0], r.versoes[-1]
        anos = (int(hoje[:4]) - int(v0.data[:4])) + (int(hoje[5:7]) - int(v0.data[5:7])) / 12
        if len(r.versoes) >= 2 and anos >= 2 and v0.palavras:
            cresc.append((v1.palavras / v0.palavras, r, v0, v1))
    cresc.sort(key=lambda x: -x[0])
    s += ["", "## Os que mais cresceram", "", "Só documentos com pelo menos dois anos de histórico.", "",
          "| Documento | Primeira versão arquivada | Hoje | Variação |", "| --- | ---: | ---: | ---: |"]
    for fator, r, v0, v1 in cresc[:15]:
        s.append(f"| {nome(r)} | {num(v0.palavras)} palavras ({mes_ano(v0.data)}) | {num(v1.palavras)} palavras | "
                 f"{f'{fator:.1f}'.replace('.', ',')}× |")

    s += ["", "## Quando cada assunto apareceu", "",
          "Quantos documentos falam de cada assunto hoje e quais passaram a falar depois da primeira versão",
          "arquivada. **Aparecer não quer dizer fazer:** às vezes o texto cita o assunto para dizer que a empresa",
          "*não* faz aquilo. Abra o histórico e leia o trecho.", ""]
    for termo in TERMOS:
        com = [r for r in regs if termo in r.termos]
        s.append(f"### {termo}")
        s.append("")
        s.append(f"Aparece hoje em {len(com)} de {len(regs)} documentos.")
        lista = []
        for r in regs:
            pm = primeira_mencao(r).get(termo)
            if pm and pm != r.versoes[0].data:
                lista.append((pm, r))
        if lista:
            s.append("")
            for d, r in sorted(lista, key=lambda x: (x[0], x[1].doc.nome_empresa)):
                s.append(f"- {mes_ano(d)}: {nome(r)}")
        s.append("")
    return "\n".join(s).rstrip() + "\n"


# ------------------------------------------------------------------ llms.txt
def llms_txt(registros: list[Registro]) -> str:
    arquivados = [r for r in registros if r.existe]
    ano0 = min(r.versoes[0].data[:4] for r in arquivados)
    n_emp = len({r.doc.empresa for r in arquivados})
    linhas = [
        "# letras-miudas",
        "",
        f"> Termos de uso e políticas de privacidade de {n_emp} empresas usadas no Brasil, em Markdown, "
        f"com o histórico de cada mudança desde {ano0}. Um robô confere os documentos todo dia.",
        "",
        "Cada documento é um arquivo Markdown com cabeçalho YAML: `empresa`, `documento`, `categoria`, "
        "`fonte` (a página oficial), `capturado_em` (quando esta versão do texto foi vista pela primeira vez), "
        "`wayback` (só em versões antigas vindas do Wayback Machine) e `historico` (a lista de versões no GitHub). "
        "O corpo é o texto da página oficial convertido para Markdown, sem edição.",
        "",
        "Cada versão anterior é um commit do Git. O arquivo `dados/documentos.json` lista todos os documentos e "
        "todas as versões, com a data, o link do texto de cada versão e o link do diff. Para comparar duas versões, "
        f"baixe `https://raw.githubusercontent.com/{REPO}/<commit>/termos/<empresa>/<documento>.md` com os dois "
        "commits e compare, ou abra o link `diff` de cada versão.",
        "",
        "Os textos são informativos e não são orientação jurídica. Vale o que está publicado no site de cada "
        "empresa (campo `fonte`). Quando citar um trecho, cite também a data da versão.",
        "",
        "## Dados e mudanças",
        "",
        f"- [Índice em JSON]({RAW}/dados/documentos.json): todos os documentos e todas as versões, com links",
        f"- [Mudanças detectadas]({RAW}/MUDANCAS.md): as mudanças que o robô viu desde out/2026, a mais nova primeiro",
        f"- [Achados]({RAW}/ACHADOS.md): documentos que mais mudaram e quando cada assunto apareceu",
        f"- [README]({RAW}/README.md): como o acervo é montado",
        "",
    ]
    for cat, empresas in por_categoria(registros).items():
        regs = [r for lista in empresas.values() for r in lista if r.existe]
        if not regs:
            continue
        linhas += [f"## {cat}", ""]
        for r in regs:
            v = r.versoes
            linhas.append(f"- [{r.doc.nome_empresa} · {r.doc.nome}]({r.raw}): {num(r.palavras)} palavras, "
                          f"{tempo_leitura(r.minutos)} de leitura, {len(v)} "
                          f"{'versão' if len(v) == 1 else 'versões'} desde {mes_ano(v[0].data)}")
        linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"


def main() -> int:
    registros = carregar_acervo()
    hoje = datetime.now(timezone.utc).date()

    readme(registros)

    docs = documentos_json(registros)
    (RAIZ / "dados" / "documentos.json").write_text(
        json.dumps({"repositorio": GITHUB, "palavras_por_minuto": PALAVRAS_POR_MINUTO, "documentos": docs},
                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    (RAIZ / "llms.txt").write_text(llms_txt(registros), encoding="utf-8")
    (RAIZ / "ACHADOS.md").write_text(achados_md(registros), encoding="utf-8")

    (RAIZ / "linha-do-tempo.svg").write_text(gerar_svg(registros, "escuro", hoje), encoding="utf-8")
    (RAIZ / "linha-do-tempo-claro.svg").write_text(gerar_svg(registros, "claro", hoje), encoding="utf-8")

    try:
        from pagina import gerar_pagina
    except ImportError:
        gerar_pagina = None
    if gerar_pagina:
        (RAIZ / "index.html").write_text(gerar_pagina(registros, hoje), encoding="utf-8")

    print(f"Gerado: README, ACHADOS, llms.txt, dados/documentos.json, imagens e página ({len(docs)} documentos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
