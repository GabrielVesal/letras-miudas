"""Lê o acervo inteiro (arquivos + histórico do git) para gerar índices, imagem e página.

Cada versão de cada documento é um commit. A data de cada versão vem do campo
`capturado_em` do cabeçalho do arquivo naquela versão (quando a versão foi vista pela
primeira vez, no Wayback ou pelo robô).

Precisa do histórico completo do git (no GitHub Actions: checkout com fetch-depth: 0).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field

from comum import RAIZ, REPO, Documento, carregar_declaracoes, corpo, texto_puro
from historico import TERMOS, presentes

PALAVRAS_POR_MINUTO = 238  # leitura silenciosa de não ficção (Brysbaert, 2019)
ORDEM_CATEGORIAS = ["Bancos", "Compras", "Apps", "Redes sociais", "Tecnologia", "IA", "Streaming", "Jogos",
                    "Telefonia", "Serviços", "Governo", "Outros"]
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
GITHUB = f"https://github.com/{REPO}"


@dataclass
class Versao:
    data: str              # AAAA-MM-DD
    sha: str
    palavras: int
    termos: list[str]
    wayback: str | None = None

    @property
    def origem(self) -> str:
        return "Wayback Machine" if self.wayback else "robô do letras-miudas"


@dataclass
class Registro:
    doc: Documento
    status: str = ""
    motivo: str = ""
    versoes: list[Versao] = field(default_factory=list)
    palavras: int = 0
    termos: list[str] = field(default_factory=list)

    @property
    def chave(self) -> str:
        return f"{self.doc.empresa}/{self.doc.tipo}"

    @property
    def caminho(self) -> str:
        return f"termos/{self.doc.empresa}/{self.doc.tipo}.md"

    @property
    def existe(self) -> bool:
        return bool(self.versoes)

    @property
    def minutos(self) -> float:
        return self.palavras / PALAVRAS_POR_MINUTO

    @property
    def raw(self) -> str:
        return f"{RAW}/{self.caminho}"

    @property
    def historico(self) -> str:
        return f"{GITHUB}/commits/main/{self.caminho}"


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


CAMPO = re.compile(r"^(\w+): (.*)$", re.M)


def _campos(conteudo: str) -> dict[str, str]:
    if not conteudo.startswith("---\nempresa:"):
        return {}
    cab = conteudo[4:conteudo.find("\n---\n", 4)]
    saida = {}
    for k, v in CAMPO.findall(cab):
        saida[k] = json.loads(v) if v.startswith('"') else v
    return saida


def _versoes(caminho: str) -> list[Versao]:
    log = _git("log", "--reverse", "--format=%H%x1f%aI", "--", caminho)
    versoes = []
    for linha in log.splitlines():
        if not linha.strip():
            continue
        sha, data_autor = linha.split("\x1f")
        try:
            conteudo = _git("show", f"{sha}:{caminho}")
        except RuntimeError:  # commit que apagou o arquivo
            continue
        c = _campos(conteudo)
        texto = texto_puro(conteudo)
        versoes.append(Versao(
            data=c.get("capturado_em") or data_autor[:10], sha=sha, palavras=len(texto.split()),
            termos=presentes(corpo(conteudo)), wayback=c.get("wayback"),
        ))
    return versoes


def carregar_acervo() -> list[Registro]:
    estado = {}
    arq = RAIZ / "dados" / "estado.json"
    if arq.exists():
        estado = json.loads(arq.read_text(encoding="utf-8"))
    registros = []
    for doc in carregar_declaracoes():
        r = Registro(doc=doc)
        st = estado.get(r.chave) or {}
        r.status, r.motivo = st.get("status", ""), st.get("motivo", "")
        if doc.arquivo.exists():
            r.versoes = _versoes(r.caminho)
            atual = doc.arquivo.read_text(encoding="utf-8")
            r.palavras = len(texto_puro(atual).split())
            r.termos = presentes(corpo(atual))
        registros.append(r)
    return registros


def ordem_categoria(cat: str) -> tuple[int, str]:
    return (ORDEM_CATEGORIAS.index(cat) if cat in ORDEM_CATEGORIAS else 99, cat)


def primeira_mencao(r: Registro) -> dict[str, str]:
    """Data da primeira versão arquivada que menciona cada assunto."""
    saida: dict[str, str] = {}
    for v in r.versoes:
        for t in v.termos:
            saida.setdefault(t, v.data)
    return saida


__all__ = ["PALAVRAS_POR_MINUTO", "TERMOS", "Registro", "Versao", "carregar_acervo", "ordem_categoria",
           "primeira_mencao", "RAW", "GITHUB"]
