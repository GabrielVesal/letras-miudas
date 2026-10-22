"""Gera ACHADOS.md a partir de dados/linha-do-tempo.json.

Responde perguntas como: qual documento mudou mais vezes? Qual cresceu mais?
Quando cada empresa mencionou a LGPD ou inteligência artificial pela primeira vez?
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from comum import RAIZ, carregar_declaracoes  # noqa: E402

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def mes_ano(data: str) -> str:
    return f"{MESES[int(data[4:6]) - 1]}/{data[:4]}"


def main() -> int:
    arq = RAIZ / "dados" / "linha-do-tempo.json"
    if not arq.exists():
        sys.exit("Sem dados/linha-do-tempo.json. Rode scripts/historico.py antes.")
    linha = json.loads(arq.read_text(encoding="utf-8"))
    docs = {f"{d.empresa}/{d.tipo}": d for d in carregar_declaracoes()}

    linhas_doc = []
    primeira_vez: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for chave, versoes in linha.items():
        if not versoes or chave not in docs:
            continue
        d = docs[chave]
        rotulo = f"{d.nome_empresa} · {d.nome}"
        ini, fim = versoes[0], versoes[-1]
        cresc = fim["caracteres"] / ini["caracteres"] if ini["caracteres"] else 0
        linhas_doc.append((rotulo, len(versoes), ini["data"], ini["caracteres"], fim["caracteres"], cresc, chave))
        vistos = set()
        for v in versoes:
            for termo in v["termos"]:
                if termo not in vistos:
                    vistos.add(termo)
                    if v is not ini:  # só conta como "apareceu" se não estava na primeira versão arquivada
                        primeira_vez[termo].append((v["data"], rotulo))

    if not linhas_doc:
        sys.exit("Linha do tempo vazia.")

    repo = os.environ.get("GITHUB_REPOSITORY", "GabrielVesal/letras-miudas")
    def link(chave: str) -> str:
        d = docs[chave]
        return f"https://github.com/{repo}/commits/main/termos/{d.empresa}/{d.tipo}.md"

    saida = [
        "# Achados",
        "",
        "Gerado automaticamente a partir do histórico reconstruído pelo Wayback Machine",
        f"({datetime.now(timezone.utc):%d/%m/%Y}). As datas são de quando cada versão foi capturada pelo",
        "arquivo, então indicam quando a mudança já estava no ar, não o dia exato da publicação.",
        "",
        "## Os documentos que mais mudaram",
        "",
        "| Documento | Versões diferentes | Arquivado desde |",
        "|---|---:|---|",
    ]
    for rotulo, n, ini, _, _, _, chave in sorted(linhas_doc, key=lambda x: -x[1])[:15]:
        saida.append(f"| [{rotulo}]({link(chave)}) | {n} | {mes_ano(ini)} |")

    saida += ["", "## Os que mais cresceram", "",
              "| Documento | Tamanho na 1ª versão | Tamanho hoje | Variação |", "|---|---:|---:|---:|"]
    for rotulo, n, ini, c0, c1, cresc, chave in sorted(linhas_doc, key=lambda x: -x[5])[:15]:
        if n < 2:
            continue
        saida.append(f"| [{rotulo}]({link(chave)}) | {c0:,} | {c1:,} | {cresc:.1f}x |".replace(",", "."))

    saida += ["", "## Quando cada assunto apareceu pela primeira vez", "",
              "Só conta quando o termo surgiu numa versão posterior à primeira arquivada.", ""]
    for termo, lista in sorted(primeira_vez.items(), key=lambda x: -len(x[1])):
        saida.append(f"### {termo}")
        saida.append("")
        for data, rotulo in sorted(lista):
            saida.append(f"- {mes_ano(data)}: {rotulo}")
        saida.append("")

    (RAIZ / "ACHADOS.md").write_text("\n".join(saida).rstrip() + "\n", encoding="utf-8")
    print(f"ACHADOS.md gerado com {len(linhas_doc)} documentos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
