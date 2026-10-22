"""Atualiza a tabela de empresas no README.md (entre os marcadores <!-- EMPRESAS -->)."""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))

from comum import RAIZ, carregar_declaracoes  # noqa: E402

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
ORDEM = ["Bancos", "Compras", "Apps", "Telefonia", "Redes", "Streaming", "IA", "Serviços", "Governo"]


def main() -> int:
    docs = carregar_declaracoes()
    linha = {}
    arq = RAIZ / "dados" / "linha-do-tempo.json"
    if arq.exists():
        linha = json.loads(arq.read_text(encoding="utf-8"))
    estado = {}
    arq_e = RAIZ / "dados" / "estado.json"
    if arq_e.exists():
        estado = json.loads(arq_e.read_text(encoding="utf-8"))

    categorias = {}
    for f in (RAIZ / "empresas").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        categorias[f.stem] = d.get("categoria", "Outros")

    por_cat: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for doc in docs:
        por_cat[categorias.get(doc.empresa, "Outros")][doc.nome_empresa].append(doc)

    saida = ["| Categoria | Empresa | Documentos | Arquivado desde |", "|---|---|---|---|"]
    total_docs = 0
    for cat in sorted(por_cat, key=lambda c: (ORDEM.index(c) if c in ORDEM else 99, c)):
        for nome in sorted(por_cat[cat], key=str.lower):
            links, desde = [], None
            for doc in por_cat[cat][nome]:
                chave = f"{doc.empresa}/{doc.tipo}"
                caminho = doc.arquivo.relative_to(RAIZ).as_posix()
                st = (estado.get(chave) or {}).get("status")
                marca = " ⚠️" if st in ("bloqueado", "falha", "suspeito", "instável") else ""
                if doc.arquivo.exists():
                    links.append(f"[{doc.nome}]({caminho}){marca}")
                    total_docs += 1
                else:
                    links.append(f"{doc.nome}{marca}")
                versoes = linha.get(chave) or []
                if versoes:
                    d0 = versoes[0]["data"]
                    desde = d0 if desde is None or d0 < desde else desde
            quando = f"{MESES[int(desde[4:6]) - 1]}/{desde[:4]}" if desde else "-"
            saida.append(f"| {cat} | {nome} | {' · '.join(links)} | {quando} |")
    saida.append("")
    saida.append(f"{len({d.empresa for d in docs})} empresas e {total_docs} documentos. ⚠️ = a última leitura falhou ou foi bloqueada.")

    readme = RAIZ / "README.md"
    texto = readme.read_text(encoding="utf-8")
    bloco = "<!-- EMPRESAS -->\n" + "\n".join(saida) + "\n<!-- /EMPRESAS -->"
    if "<!-- /EMPRESAS -->" in texto:
        texto = re.sub(r"<!-- EMPRESAS -->.*?<!-- /EMPRESAS -->", lambda _: bloco, texto, flags=re.S)
    else:
        texto = texto.replace("<!-- EMPRESAS -->", bloco)
    readme.write_text(texto, encoding="utf-8")
    print("README atualizado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
