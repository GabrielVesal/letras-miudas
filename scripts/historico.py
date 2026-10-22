"""Reconstrói o passado dos documentos a partir do Wayback Machine (archive.org).

Para cada documento declarado:
  1. Lista as capturas da URL no Wayback (só as com status 200).
  2. Lê uma captura por trimestre e converte para Markdown com o mesmo extrator do dia a dia.
  3. Quando o texto muda de um trimestre para o outro, olha os meses do meio para achar
     em que mês a mudança apareceu.
  4. Cria um commit para cada versão, com a data da captura e o link do Wayback na mensagem,
     para qualquer pessoa conferir a fonte.

As datas são as das capturas do Wayback: indicam quando a versão foi vista pela primeira vez,
não necessariamente o dia em que a empresa publicou.

Uso:
  python scripts/historico.py                      # todas as empresas sem histórico ainda
  python scripts/historico.py --empresas nubank    # só algumas
  python scripts/historico.py --desde 2016
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from collections import OrderedDict
from dataclasses import replace
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(__file__))

from comum import HEADERS, RAIZ, FalhaLeitura, cabecalho, carregar_declaracoes, converter  # noqa: E402

CDX = "https://web.archive.org/cdx/search/cdx"
ARQ_LINHA = RAIZ / "dados" / "linha-do-tempo.json"
BOT = {
    "GIT_AUTHOR_NAME": "letras-miudas-bot",
    "GIT_AUTHOR_EMAIL": "letras-miudas-bot@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "letras-miudas-bot",
    "GIT_COMMITTER_EMAIL": "letras-miudas-bot@users.noreply.github.com",
}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# termos acompanhados na linha do tempo (para os "achados")
TERMOS = OrderedDict([
    ("LGPD", r"\blgpd\b|lei geral de protecao de dados"),
    ("Encarregado/DPO", r"\bencarregado\b|\bdpo\b|data protection officer"),
    ("Inteligência artificial", r"inteligencia artificial|\bia generativa\b|machine learning|aprendizado de maquina"),
    ("Treinar modelos", r"trein\w* (de |dos |de nossos |nossos )?(modelos|algoritmos|sistemas de ia)"),
    ("Biometria", r"biometri"),
    ("Reconhecimento facial", r"reconhecimento facial|biometria facial"),
    ("Localização", r"geolocaliza|localizacao (precisa|do dispositivo|geografica)"),
    ("Open Finance", r"open finance|open banking"),
    ("Publicidade personalizada", r"publicidade (personalizada|direcionada|segmentada)|anuncios personalizados"),
    ("Transferência internacional", r"transferencia internacional"),
])

_ultimo = 0.0


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def wayback_get(url: str, params: dict | None = None, timeout: int = 60) -> requests.Response | None:
    global _ultimo
    for tentativa in range(4):
        falta = _ultimo + 2.5 - time.monotonic()
        if falta > 0:
            time.sleep(falta)
        _ultimo = time.monotonic()
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        except requests.RequestException:
            time.sleep(10 * (tentativa + 1))
            continue
        if r.status_code in (429, 502, 503, 504):
            time.sleep(30 * (tentativa + 1))
            continue
        return r
    return None


def capturas(url: str, desde: str) -> list[tuple[str, str]]:
    """Lista (timestamp, url original) das capturas com status 200, sem repetir conteúdo idêntico."""
    params = {"url": url, "output": "json", "fl": "timestamp,original", "filter": "statuscode:200",
              "collapse": "digest", "from": desde, "limit": "20000"}
    r = wayback_get(CDX, params)
    if r is None or r.status_code != 200 or not r.text.strip():
        return []
    try:
        linhas = r.json()[1:]
    except ValueError:
        return []
    return [(ts, orig) for ts, orig in linhas]


def por_mes(caps: list[tuple[str, str]]) -> "OrderedDict[str, tuple[str, str]]":
    """Última captura de cada mês (AAAAMM)."""
    meses: OrderedDict[str, tuple[str, str]] = OrderedDict()
    for ts, orig in caps:
        meses[ts[:6]] = (ts, orig)
    return meses


def ler_captura(doc, ts: str, original: str) -> str | None:
    r = wayback_get(f"https://web.archive.org/web/{ts}id_/{original}", timeout=90)
    if r is None or r.status_code != 200:
        return None
    ctype = r.headers.get("content-type", "")
    for tentativa_doc in (doc, replace(doc, seletor=None)):  # layout antigo pode não ter o seletor atual
        try:
            return converter(r.content, ctype, tentativa_doc)
        except FalhaLeitura:
            continue
    return None


def versoes_do_documento(doc, desde: str) -> list[tuple[str, str]]:
    """Devolve [(timestamp, markdown)] só com as versões em que o texto mudou."""
    urls = [doc.url] + doc.urls_antigas
    caps = []
    for u in urls:
        caps += capturas(u, desde)
    caps.sort()
    if not caps:
        return []
    meses = por_mes(caps)
    chaves = list(meses.keys())
    # amostra trimestral + sempre o último mês
    amostra = [m for m in chaves if int(m[4:6]) in (3, 6, 9, 12)]
    if chaves[0] not in amostra:
        amostra.insert(0, chaves[0])
    if chaves[-1] not in amostra:
        amostra.append(chaves[-1])

    lidos: dict[str, str | None] = {}

    def texto(mes: str) -> str | None:
        if mes not in lidos:
            ts, orig = meses[mes]
            lidos[mes] = ler_captura(doc, ts, orig)
        return lidos[mes]

    versoes: list[tuple[str, str]] = []
    anterior_mes, anterior_txt = None, None
    for mes in amostra:
        atual = texto(mes)
        if atual is None:
            continue
        if anterior_txt is None:
            versoes.append((meses[mes][0], atual))
        elif atual != anterior_txt:
            # procura nos meses do meio em que mês o texto novo apareceu
            i0, i1 = chaves.index(anterior_mes), chaves.index(mes)
            primeiro = mes
            for m in chaves[i0 + 1:i1]:
                t = texto(m)
                if t is not None and t == atual:
                    primeiro = m
                    break
                if t is not None and t != anterior_txt:
                    # uma versão intermediária diferente das duas: registra também
                    versoes.append((meses[m][0], t))
                    anterior_txt = t
            if atual != anterior_txt:
                versoes.append((meses[primeiro][0], atual))
        anterior_mes, anterior_txt = mes, atual
    # remove repetições consecutivas
    limpas: list[tuple[str, str]] = []
    for ts, md in versoes:
        if not limpas or limpas[-1][1] != md:
            limpas.append((ts, md))
    return limpas


def presentes(md: str) -> list[str]:
    n = unicodedata.normalize("NFKD", md).encode("ascii", "ignore").decode().lower()
    return [nome for nome, rx in TERMOS.items() if re.search(rx, n)]


def git(*args: str, env: dict | None = None) -> str:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--empresas", help="slugs separados por vírgula")
    ap.add_argument("--desde", default="2014")
    ap.add_argument("--sem-commit", action="store_true")
    ap.add_argument("--forcar", action="store_true", help="refaz mesmo se já houver histórico")
    ap.add_argument("--max-minutos", type=float, default=240,
                    help="para de buscar documentos novos depois desse tempo (o resto fica para a próxima)")
    args = ap.parse_args()
    prazo = time.monotonic() + args.max_minutos * 60

    docs = carregar_declaracoes(args.empresas.split(",") if args.empresas else None)
    linha = json.loads(ARQ_LINHA.read_text(encoding="utf-8")) if ARQ_LINHA.exists() else {}

    todas: list[tuple[str, object, str]] = []
    for doc in docs:
        chave = f"{doc.empresa}/{doc.tipo}"
        if time.monotonic() > prazo:
            log("Tempo esgotado: o restante fica para a próxima execução.")
            break
        if chave in linha and not args.forcar:
            log(f"{chave}: já tem histórico, pulando")
            continue
        if doc.arquivo.exists() and not args.forcar:
            log(f"{chave}: já existe versão atual; histórico antigo só com --forcar")
            continue
        try:
            versoes = versoes_do_documento(doc, args.desde)
        except Exception as e:  # um documento ruim não derruba o resto
            log(f"{chave}: erro {e!r}")
            continue
        log(f"{chave}: {len(versoes)} versões no Wayback")
        linha[chave] = [
            {"data": ts[:8], "caracteres": len(md), "termos": presentes(md),
             "wayback": f"https://web.archive.org/web/{ts}/{doc.url}"}
            for ts, md in versoes
        ]
        todas += [(ts, doc, md) for ts, md in versoes]

    todas.sort(key=lambda x: x[0])
    for ts, doc, md in todas:
        doc.arquivo.parent.mkdir(parents=True, exist_ok=True)
        primeira = not doc.arquivo.exists()
        doc.arquivo.write_text(cabecalho(doc) + md, encoding="utf-8")
        if args.sem_commit:
            continue
        caminho = doc.arquivo.relative_to(RAIZ).as_posix()
        git("add", caminho)
        if not git("diff", "--cached", "--name-only").strip():
            continue
        quando = f"{MESES[int(ts[4:6]) - 1]}/{ts[:4]}"
        titulo = (f"{doc.nome_empresa} · {doc.nome}: versão mais antiga arquivada ({quando})" if primeira
                  else f"{doc.nome_empresa} · {doc.nome}: versão de {quando}")
        data = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()
        env = {**BOT, "GIT_AUTHOR_DATE": data, "GIT_COMMITTER_DATE": data}
        git("commit", "-q", "-m", titulo, "-m",
            f"Fonte: Wayback Machine, captura de {ts[:4]}-{ts[4:6]}-{ts[6:8]}\n"
            f"https://web.archive.org/web/{ts}/{doc.url}", env=env)

    ARQ_LINHA.parent.mkdir(parents=True, exist_ok=True)
    ARQ_LINHA.write_text(json.dumps(linha, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if not args.sem_commit:
        git("add", "dados/linha-do-tempo.json")
        if git("diff", "--cached", "--name-only").strip():
            git("commit", "-q", "-m", "linha do tempo do histórico", env=BOT)
    log(f"Pronto: {len(todas)} versões históricas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
