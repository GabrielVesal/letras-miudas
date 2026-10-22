"""Peças compartilhadas: leitura das declarações, download educado e extração.

Regras do robô (valem para todo o projeto):
  - se identifica com um user-agent próprio, com link para o repositório;
  - respeita o robots.txt de cada site;
  - espera entre requisições ao mesmo site;
  - se o site pedir verificação anti-robô (captcha, Turnstile etc.), desiste.
    Nunca tentamos contornar esse tipo de bloqueio.
"""

from __future__ import annotations

import html
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

RAIZ = Path(__file__).resolve().parent.parent
DIR_EMPRESAS = RAIZ / "empresas"
DIR_TERMOS = RAIZ / "termos"

REPO = "GabrielVesal/letras-miudas"
UA = "letras-miudas/1.0 (+https://github.com/GabrielVesal/letras-miudas; arquivo publico de termos de uso)"
HEADERS = {"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5"}

NOMES_DOCUMENTOS = {
    "termos-de-uso": "Termos de Uso",
    "politica-de-privacidade": "Política de Privacidade",
    "politica-de-cookies": "Política de Cookies",
    "contrato": "Contrato",
}

DESAFIO_RE = re.compile(
    r"cf-chl|challenge-platform|just a moment|attention required|captcha|"
    r"turnstile|are you a robot|verify you are human|px-captcha|_incapsula_|perimeterx",
    re.I,
)
JURIDICO = ["dados pessoais", "privacidade", "termos", "lgpd", "titular", "tratamento",
            "usuario", "consentimento", "responsabilidade", "condicoes", "contrato", "servico",
            # alguns documentos globais só existem em inglês
            "personal data", "privacy", "terms", "processing", "consent", "liability", "agreement"]


class Bloqueado(Exception):
    """O site pediu verificação anti-robô ou o robots.txt não permite."""


class FalhaLeitura(Exception):
    """Não veio um documento válido (erro HTTP, página vazia, texto curto)."""


# ------------------------------------------------------------ declarações
@dataclass
class Documento:
    empresa: str          # slug da empresa
    nome_empresa: str
    tipo: str             # slug do documento (termos-de-uso, politica-de-privacidade...)
    url: str
    categoria: str = ""
    seletor: str | None = None
    remover: list[str] = field(default_factory=list)
    remover_linhas: list[str] = field(default_factory=list)  # regex de parágrafos para tirar do texto
    cortar_em: list[str] = field(default_factory=list)  # regex: o texto termina na 1ª linha que bater
    navegador: bool = False
    urls_antigas: list[str] = field(default_factory=list)  # endereços antigos, só para o histórico

    @property
    def nome(self) -> str:
        return NOMES_DOCUMENTOS.get(self.tipo, self.tipo.replace("-", " ").title())

    @property
    def arquivo(self) -> Path:
        return DIR_TERMOS / self.empresa / f"{self.tipo}.md"


def carregar_declaracoes(filtro: list[str] | None = None) -> list[Documento]:
    docs = []
    for arq in sorted(DIR_EMPRESAS.glob("*.json")):
        slug = arq.stem
        if filtro and slug not in filtro:
            continue
        d = json.loads(arq.read_text(encoding="utf-8"))
        for tipo, cfg in d["documentos"].items():
            docs.append(Documento(
                empresa=slug, nome_empresa=d["nome"], tipo=tipo, url=cfg["url"],
                categoria=d.get("categoria", "Outros"),
                seletor=cfg.get("seletor"), remover=cfg.get("remover", []),
                remover_linhas=cfg.get("remover_linhas", []), cortar_em=cfg.get("cortar_em", []),
                navegador=cfg.get("navegador", False), urls_antigas=cfg.get("urls_antigas", []),
            ))
    return docs


# ------------------------------------------------------------------ rede
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_ultimo: dict[str, float] = {}


def _esperar(host: str, intervalo: float) -> None:
    falta = _ultimo.get(host, 0) + intervalo - time.monotonic()
    if falta > 0:
        time.sleep(falta)
    _ultimo[host] = time.monotonic()


def robots_permite(url: str) -> bool:
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            _esperar(p.netloc, 1.0)
            r = requests.get(base + "/robots.txt", headers=HEADERS, timeout=15)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
                _robots[base] = rp
            else:
                _robots[base] = None
        except requests.RequestException:
            _robots[base] = None
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(UA, url)


def baixar_http(url: str, intervalo: float = 1.5) -> tuple[bytes, str, str]:
    """Devolve (conteúdo, content-type, url final)."""
    host = urllib.parse.urlsplit(url).netloc
    _esperar(host, intervalo)
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
    except requests.RequestException as e:
        raise FalhaLeitura(f"erro de rede: {type(e).__name__}") from e
    corpo = r.content
    ctype = r.headers.get("content-type", "")
    if "html" in ctype and DESAFIO_RE.search(r.text[:20000]) and len(corpo) < 80000:
        raise Bloqueado(f"verificação anti-robô (HTTP {r.status_code})")
    if r.status_code in (403, 429) and "html" in ctype and len(corpo) < 20000:
        raise Bloqueado(f"HTTP {r.status_code}")
    if r.status_code != 200:
        raise FalhaLeitura(f"HTTP {r.status_code}")
    return corpo, ctype, r.url


_pw = None
_browser = None


def baixar_navegador(url: str) -> tuple[bytes, str, str]:
    global _pw, _browser
    if _browser is None:
        from playwright.sync_api import sync_playwright

        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch()
    host = urllib.parse.urlsplit(url).netloc
    _esperar(host, 2.0)
    ctx = _browser.new_context(locale="pt-BR")
    try:
        pagina = ctx.new_page()
        resp = pagina.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            pagina.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        html = pagina.content()
        status = resp.status if resp else 0
        final = pagina.url
    except Exception as e:
        raise FalhaLeitura(f"navegador: {type(e).__name__}") from e
    finally:
        ctx.close()
    if DESAFIO_RE.search(html[:20000]) and len(html) < 120000:
        raise Bloqueado("verificação anti-robô (navegador)")
    if status != 200:
        raise FalhaLeitura(f"HTTP {status} (navegador)")
    return html.encode("utf-8"), "text/html", final


def fechar_navegador() -> None:
    global _pw, _browser
    if _browser is not None:
        _browser.close()
        _pw.stop()
        _browser = _pw = None


# ---------------------------------------------------------------- extração
LIXO = ["script", "style", "noscript", "svg", "iframe", "input", "select",
        "textarea", "template", "nav", "aside", "dialog", "picture", "video"]
# Só banners e navegação. Nada genérico demais: uma política de privacidade costuma ter
# seções com id "cookies" ou "consentimento", e elas não podem sumir.
LIXO_SELETORES = [
    "[id^=onetrust]", "[class^=onetrust]", "#CybotCookiebotDialog", "[id*=cookie-banner]",
    "[class*=cookie-banner]", "[id*=cookieBanner]", "[class*=cookieBanner]", "[id*=cookie-consent]",
    "[class*=cookie-consent]", "[class*=cookieConsent]", "[id*=lgpd-banner]", "[class*=lgpd-banner]",
    "[role=navigation]", "[role=banner]", "[role=contentinfo]", "[class*=breadcrumb]",
]
LINHAS_LIXO = re.compile(
    r"^(voltar (ao|para o) topo|copiar link|compartilhar|imprimir|baixar pdf|ir para o conte[uú]do|"
    r"pular para o conte[uú]do|menu|fechar|topo|aceitar( todos)?( os)? cookies?|exibir resumo saiba mais)$",
    re.I,
)


def _texto(el) -> str:
    return " ".join(el.get_text(" ", strip=True).split())


def _container(soup: BeautifulSoup):
    corpo = soup.body or soup
    total = len(_texto(corpo))
    if total == 0:
        return corpo
    candidatos = corpo.find_all(["main", "article", "section", "div"])
    bons = [el for el in candidatos if len(_texto(el)) >= 0.8 * total]
    if not bons:
        return corpo
    # o menor elemento que ainda contém quase todo o texto da página
    return min(bons, key=lambda el: len(str(el)))


def html_para_markdown(html: str, seletor: str | None = None, remover: list[str] | None = None) -> str:
    soup = BeautifulSoup(html, "lxml")
    for el in soup(LIXO):
        el.decompose()
    for sel in LIXO_SELETORES + (remover or []):
        for el in soup.select(sel):
            el.decompose()
    # sites em ASP.NET/SharePoint põem a página inteira dentro de um <form>: tira só a casca
    for el in soup.find_all("form"):
        el.unwrap()
    # cabeçalho e rodapé do site somem; os de dentro do texto (título, "atualizado em") ficam
    for el in soup.find_all(["header", "footer"]):
        if el.find_parent(["main", "article"]):
            el.unwrap()
        else:
            el.decompose()
    # botões de acordeão costumam ser o título da seção: viram texto
    for el in soup.find_all("button"):
        if len(el.get_text(strip=True)) > 3:
            el.name = "p"
        else:
            el.decompose()
    if seletor:
        nos = soup.select(seletor)
        if not nos:
            raise FalhaLeitura(f"seletor '{seletor}' não encontrou nada")
        alvo = "\n".join(str(n) for n in nos)
    else:
        alvo = str(_container(soup))
    md = markdownify(alvo, heading_style="ATX", bullets="-", strip=["a", "img", "span", "font"])
    return normalizar(md)


def pdf_para_markdown(dados: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=dados, filetype="pdf")
    paragrafos, atual = [], []
    for pagina in doc:
        for linha in pagina.get_text("text", sort=True).splitlines():
            s = linha.strip()
            if not s:
                if atual:
                    paragrafos.append(" ".join(atual))
                    atual = []
                continue
            if re.fullmatch(r"(p[áa]gina\s*)?\d{1,3}(\s*(de|/)\s*\d{1,3})?", s, re.I):
                continue
            atual.append(s)
            if re.search(r"[.:;]$", s) and len(s) < 70:
                paragrafos.append(" ".join(atual))
                atual = []
    if atual:
        paragrafos.append(" ".join(atual))
    texto = "\n\n".join(re.sub(r"(\w)- (\w)", r"\1\2", p) for p in paragrafos)
    return normalizar(texto)


INVISIVEIS = re.compile(r"[\u00ad\u200b-\u200f\u2060-\u2064\ufeff]")


def normalizar(md: str) -> str:
    md = unicodedata.normalize("NFC", html.unescape(md))
    md = INVISIVEIS.sub("", md.replace("\xa0", " "))
    linhas = []
    for linha in md.splitlines():
        linha = re.sub(r"[ \t]+", " ", linha).rstrip()
        if LINHAS_LIXO.match(linha.strip()):
            continue
        linha = re.sub(r"^(\s*)[*+•·]\s+", r"\1- ", linha)
        # pedaço de frase que o HTML quebrou numa linha própria (". Em vez disso...")
        if linhas and re.match(r"^\s*[.,;:!?)]", linha) and linhas[-1].strip():
            linhas[-1] = linhas[-1].rstrip() + linha.strip()
            continue
        linhas.append(linha)
    linhas = _desquebrar(linhas)
    md = "\n".join(linhas)
    md = re.sub(r"^#{1,6}\s*WP\\?_\w+(-\d+)?\s*$", "", md, flags=re.M)  # ids de web parts do SharePoint
    md = re.sub(r"^#+\s*$", "", md, flags=re.M)  # títulos vazios
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


ESTRUTURA = re.compile(r"^\s*([-+*]\s|#|\||>|\d{1,3}[.)]\s|[a-z][.)]\s|<!--)")


def _desquebrar(linhas: list[str]) -> list[str]:
    """Junta as linhas de um mesmo parágrafo que o site quebrou no meio.

    No Markdown isso não muda nada na tela, mas deixa o diff legível: sem isso, um site que
    passa a quebrar as linhas em outro ponto faz o documento inteiro parecer reescrito.
    """
    saida: list[str] = []
    for linha in linhas:
        anterior = saida[-1] if saida else ""
        if (linha.strip() and anterior.strip() and not ESTRUTURA.match(linha)
                and not re.match(r"^\s*(#|\|)", anterior)):
            saida[-1] = anterior.rstrip() + " " + linha.strip()
        else:
            saida.append(linha)
    return saida


def corpo(conteudo: str) -> str:
    """O texto do documento sem o cabeçalho do arquivo (YAML ou o comentário HTML antigo)."""
    if conteudo.startswith("---\nempresa:"):
        fim = conteudo.find("\n---\n", 4)
        if fim != -1:
            return conteudo[fim + 5:].lstrip("\n")
    if conteudo.lstrip().startswith("<!--"):
        return conteudo.split("-->", 1)[-1].lstrip("\n")
    return conteudo


def texto_puro(md: str) -> str:
    """O texto sem formatação, para decidir se uma mudança é de verdade.

    Ignora o cabeçalho do arquivo, marcação Markdown (títulos, negrito, listas, tabelas),
    caracteres invisíveis, entidades HTML e espaços. Mudança só de formatação não conta.
    """
    md = INVISIVEIS.sub("", unicodedata.normalize("NFKC", html.unescape(corpo(md))))
    md = re.sub(r"\(abre em uma nova janela\)", " ", md)
    md = re.sub(r"[#*_`>|\\]", " ", md)
    md = re.sub(r"^\s*[-+]\s+", " ", md, flags=re.M)
    md = " ".join(md.split())
    return re.sub(r"\s+([.,;:!?)])", r"\1", md)


PT = re.compile(r"\b(de|que|não|para|com|dos|das|seus|suas|você|pelo|pela|são|uma)\b", re.I)
EN = re.compile(r"\b(the|and|you|your|for|with|this|that|are|our|of)\b", re.I)


def eh_portugues(md: str) -> bool:
    """Evita arquivar a versão em inglês que alguns sites servem para servidores fora do Brasil."""
    amostra = md[:20000]
    return len(PT.findall(amostra)) > 1.5 * len(EN.findall(amostra))


def parece_documento(md: str) -> bool:
    n = unicodedata.normalize("NFKD", md).encode("ascii", "ignore").decode().lower()
    hits = sum(1 for k in JURIDICO if k in n)
    return len(md) >= 1500 and hits >= 3


def ler_documento(doc: Documento) -> str:
    """Baixa e converte um documento. Lança Bloqueado ou FalhaLeitura."""
    if not robots_permite(doc.url):
        raise Bloqueado("robots.txt não permite")
    if doc.navegador:
        corpo, ctype, _ = baixar_navegador(doc.url)
    else:
        corpo, ctype, _ = baixar_http(doc.url)
    return converter(corpo, ctype, doc)


def tirar_linhas(md: str, padroes: list[str]) -> str:
    """Tira os parágrafos que batem com algum padrão (ex.: avisos que só aparecem em outro país)."""
    if not padroes:
        return md
    rx = [re.compile(p) for p in padroes]
    linhas = [l for l in md.splitlines() if not any(r.search(l) for r in rx)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip() + "\n"


def cortar(md: str, padroes: list[str]) -> str:
    """Termina o texto na primeira linha que bate com algum padrão.

    Para páginas que trazem, depois do documento que vale no Brasil, outras versões inteiras
    (para a Europa, para a Austrália, a versão anterior...). O corte só vale se sobrar texto antes.
    """
    if not padroes:
        return md
    rx = [re.compile(p) for p in padroes]
    andou = 0
    linhas = md.splitlines()
    for i, linha in enumerate(linhas):
        if andou >= 1000 and any(r.search(linha) for r in rx):
            return "\n".join(linhas[:i]).rstrip().rstrip("-").rstrip() + "\n"
        andou += len(linha)
    return md


def ajustar(md: str, doc: Documento) -> str:
    """Aplica os ajustes declarados do documento (linhas a tirar e ponto de corte)."""
    return cortar(tirar_linhas(md, doc.remover_linhas), doc.cortar_em)


def converter(corpo: bytes, ctype: str, doc: Documento) -> str:
    if "pdf" in ctype or corpo[:4] == b"%PDF":
        md = pdf_para_markdown(corpo)
    else:
        html_txt = corpo.decode("utf-8", "replace")
        md = html_para_markdown(html_txt, doc.seletor, doc.remover)
    md = ajustar(md, doc)
    if not parece_documento(md):
        raise FalhaLeitura(f"não parece o documento ({len(md)} caracteres)")
    if not eh_portugues(md):
        raise FalhaLeitura("veio em outro idioma (provavelmente versão para fora do Brasil)")
    return md


def cabecalho(doc: Documento, capturado_em: str, wayback: str | None = None,
              fonte: str | None = None) -> str:
    """Cabeçalho YAML de cada arquivo (o GitHub mostra como uma tabela no topo).

    capturado_em: AAAA-MM-DD em que esta versão do texto foi vista pela primeira vez.
    wayback: link da captura, quando a versão veio do Wayback Machine.
    """
    q = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731  (string JSON = string YAML válida)
    linhas = [
        "---",
        f"empresa: {q(doc.nome_empresa)}",
        f"documento: {q(doc.nome)}",
        f"categoria: {q(doc.categoria)}",
        f"fonte: {q(fonte or doc.url)}",
        f"capturado_em: {capturado_em}",
    ]
    if wayback:
        linhas.append(f"wayback: {q(wayback)}")
    linhas += [
        f"historico: {q(f'https://github.com/{REPO}/commits/main/termos/{doc.empresa}/{doc.tipo}.md')}",
        "---",
        "",
        "",
    ]
    return "\n".join(linhas)


# ------------------------------------------------------------ filtro de versões
def _linhas_puras(md: str) -> set[str]:
    saida = set()
    for linha in corpo(md).splitlines():
        p = texto_puro(linha)
        if len(p) >= 30:
            saida.add(p)
    return saida


def filtrar_versoes(versoes: list[dict], chave_md: str = "md") -> tuple[list[dict], dict[int, str]]:
    """Tira do histórico o que não é mudança de verdade.

    - só formatação: texto igual ao da versão anterior mantida;
    - transitória: a versão tira linhas que voltam nas 3 versões seguintes (captura parcial,
      variante regional, teste A/B), ou só acrescenta linhas que somem logo depois.
    Texto reescrito de novo mais tarde não é transitório: é mudança de verdade.
    A última versão da lista nunca sai. Devolve (mantidas, {índice original: motivo}).
    """
    itens = list(enumerate(versoes))
    motivos: dict[int, str] = {}

    def tira_formatacao(lista):
        limpa, ant = [], None
        for i, v in lista:
            p = texto_puro(v[chave_md])
            if ant is not None and p == ant:
                motivos[i] = "só formatação"
                continue
            limpa.append((i, v))
            ant = p
        return limpa

    itens = tira_formatacao(itens)
    while True:
        L = [_linhas_puras(v[chave_md]) for _, v in itens]
        pior, pior_score = None, 0.0
        for k in range(1, len(itens) - 1):
            prox = L[k + 1:k + 4]
            tirou, pos = L[k - 1] - L[k], L[k] - L[k - 1]
            score = 0.0
            if len(tirou) >= 3:
                score = sum(1 for x in tirou if any(x in p for p in prox)) / len(tirou)
            elif len(pos) >= 3:
                score = sum(1 for x in pos if all(x not in p for p in prox)) / len(pos)
            if score >= 0.5 and score > pior_score:
                pior, pior_score = k, score
        if pior is None:
            break
        motivos[itens[pior][0]] = f"transitória ({pior_score:.0%})"
        del itens[pior]
        itens = tira_formatacao(itens)
    return [v for _, v in itens], motivos
