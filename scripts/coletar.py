"""Confere todos os documentos declarados em empresas/*.json e registra o que mudou.

Cada mudança vira um commit próprio (o diff do documento) e uma entrada em MUDANCAS.md.
Para evitar alarme falso, uma mudança só é aceita se:
  - o texto mudou de verdade (mudança só de formatação, espaço ou caractere invisível não conta);
  - o texto novo ainda parece o documento (tamanho, vocabulário jurídico, português);
  - o texto não encolheu pela metade de uma vez (sinal de página de erro);
  - uma segunda leitura, alguns segundos depois, devolve o mesmo texto;
  - a rodada seguinte (no outro dia) encontra exatamente o mesmo texto novo. Alguns sites mostram
    trechos diferentes conforme o país do servidor que acessa, e o GitHub Actions nem sempre roda
    no mesmo lugar: sem essa confirmação, o vai e volta desses trechos viraria mudança falsa.

A primeira leitura direta do site depois de um histórico vindo do Wayback é registrada como
"versão atual", sem entrar em MUDANCAS.md: não dá para saber quando ela mudou entre a última
captura do Wayback e hoje.

Resumo por IA (opcional): defina RESUMO_API_URL (endpoint compatível com a API de chat da
OpenAI), RESUMO_API_KEY e RESUMO_MODELO. Sem isso, as mudanças entram sem resumo.

Uso:
  python scripts/coletar.py                     # tudo
  python scripts/coletar.py --empresas nubank   # só algumas
  python scripts/coletar.py --sem-commit        # só grava os arquivos
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(__file__))

from comum import (  # noqa: E402
    RAIZ, Bloqueado, FalhaLeitura, cabecalho, carregar_declaracoes, corpo, fechar_navegador,
    ler_documento, texto_puro,
)

REPO = os.environ.get("GITHUB_REPOSITORY", "GabrielVesal/letras-miudas")
ARQ_MUDANCAS = RAIZ / "MUDANCAS.md"
ARQ_ESTADO = RAIZ / "dados" / "estado.json"
ARQ_LINHA = RAIZ / "dados" / "linha-do-tempo.json"
BOT = {
    "GIT_AUTHOR_NAME": "letras-miudas-bot",
    "GIT_AUTHOR_EMAIL": "letras-miudas-bot@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "letras-miudas-bot",
    "GIT_COMMITTER_EMAIL": "letras-miudas-bot@users.noreply.github.com",
}

CAB_MUDANCAS = """# Mudanças detectadas

Toda vez que o robô encontra uma mudança num documento, ela entra aqui, as mais novas primeiro.
Clique em **ver o que mudou** para ver o diff: vermelho saiu, verde entrou.

A data é a do dia em que a mudança foi vista pela primeira vez. Ela só entra aqui depois de
confirmada na rodada do dia seguinte, para não registrar como mudança um trecho que aparece e some.

O acompanhamento diário começou em 22/10/2026. As versões anteriores a isso vieram do
Wayback Machine e estão no histórico de cada arquivo em [termos/](termos/).

<!-- MUDANCAS -->
"""
MARCADOR = "<!-- MUDANCAS -->\n"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

PROMPT = (
    "Você recebe o diff entre duas versões de um documento ({doc}) da empresa {empresa}. "
    "Linhas com '-' saíram, linhas com '+' entraram. Explique em português simples, em no máximo "
    "3 frases curtas, o que mudou na prática para quem usa o serviço. Cite só o que está no diff, "
    "sem suposições. Se a mudança for só de redação, data de atualização ou formatação, sem efeito "
    "prático, responda exatamente: Só ajustes de redação."
)


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def resumir(doc, antigo: str, novo: str) -> str | None:
    """Resumo da mudança por IA, se configurado. Se falhar, segue sem resumo."""
    url, chave = os.environ.get("RESUMO_API_URL"), os.environ.get("RESUMO_API_KEY")
    modelo = os.environ.get("RESUMO_MODELO")
    if not (url and chave and modelo):
        return None
    diff = "\n".join(difflib.unified_diff(antigo.splitlines(), novo.splitlines(), lineterm="", n=1))
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
            json={"model": modelo, "temperature": 0.1, "max_tokens": 250, "messages": [
                {"role": "system", "content": PROMPT.format(doc=doc.nome, empresa=doc.nome_empresa)},
                {"role": "user", "content": diff[:14000]},
            ]},
            timeout=90,
        )
        texto = r.json()["choices"][0]["message"]["content"].strip()
        return " ".join(texto.split())[:500]
    except Exception as e:  # rede, limite, formato: o resumo é opcional
        log(f"  resumo indisponível ({type(e).__name__})")
        return None


def git(*args: str, env: dict | None = None) -> str:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def diffstat(antigo: str, novo: str) -> tuple[int, int]:
    """Linhas que entraram e saíram no texto (sem contar o cabeçalho do arquivo)."""
    add = rem = 0
    for linha in difflib.unified_diff(antigo.splitlines(), novo.splitlines(), lineterm="", n=0):
        if linha.startswith("+") and not linha.startswith("+++"):
            add += 1
        elif linha.startswith("-") and not linha.startswith("---"):
            rem += 1
    return add, rem


def registrar_mudancas(entradas: list[dict]) -> None:
    """Põe as mudanças do dia no topo de MUDANCAS.md."""
    atual = ARQ_MUDANCAS.read_text(encoding="utf-8") if ARQ_MUDANCAS.exists() else CAB_MUDANCAS
    antigas = atual.split(MARCADOR, 1)[1] if MARCADOR in atual else ""
    blocos = []
    for e in entradas:
        d = datetime.strptime(e["data"], "%Y-%m-%d")
        bloco = (f"### {d.day:02d}/{d.month:02d}/{d.year} · {e['empresa']} · {e['documento']}\n\n"
                 f"+{e['add']} −{e['rem']} linhas · [ver o que mudou](https://github.com/{REPO}/commit/{e['sha']})")
        if e.get("resumo"):
            bloco += f"\n\n> **Resumo automático (IA, confira o diff):** {e['resumo']}"
        blocos.append(bloco + "\n")
    ARQ_MUDANCAS.write_text(CAB_MUDANCAS + "\n".join(blocos) + ("\n" + antigas if antigas else ""), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--empresas", help="lista separada por vírgula (slugs)")
    ap.add_argument("--sem-commit", action="store_true")
    args = ap.parse_args()

    filtro = args.empresas.split(",") if args.empresas else None
    docs = carregar_declaracoes(filtro)
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    estado = json.loads(ARQ_ESTADO.read_text(encoding="utf-8")) if ARQ_ESTADO.exists() else {}
    linha = json.loads(ARQ_LINHA.read_text(encoding="utf-8")) if ARQ_LINHA.exists() else None
    contagem = {"mudou": 0, "novo": 0, "igual": 0, "pendente": 0, "falha": 0, "bloqueado": 0}
    mudancas: list[dict] = []

    for doc in docs:
        chave = f"{doc.empresa}/{doc.tipo}"
        # documento novo cujo histórico do Wayback ainda não foi buscado: espera a próxima rodada,
        # senão a versão de hoje entraria no Git antes das antigas
        if (linha is not None and chave not in linha and not doc.arquivo.exists()
                and not args.sem_commit):
            log(f"{chave}: aguardando o histórico do Wayback")
            estado[chave] = {**estado.get(chave, {}), "status": "aguardando", "motivo": "histórico pendente"}
            continue
        anterior = estado.get(chave, {})
        primeira_leitura = (doc.arquivo.exists() and not anterior.get("ultima_leitura_ok")
                            and anterior.get("status") != "ok")
        try:
            md = ler_documento(doc)
        except Bloqueado as e:
            log(f"{chave}: bloqueado ({e})")
            estado[chave] = {**anterior, "status": "bloqueado", "motivo": str(e)}
            contagem["bloqueado"] += 1
            continue
        except FalhaLeitura as e:
            log(f"{chave}: falha ({e})")
            estado[chave] = {**anterior, "status": "falha", "motivo": str(e)}
            contagem["falha"] += 1
            continue

        antigo = doc.arquivo.read_text(encoding="utf-8") if doc.arquivo.exists() else None
        if antigo is not None and texto_puro(antigo) == texto_puro(md):
            info = {**anterior, "status": "ok", "motivo": "", "ultima_leitura_ok": hoje}
            if info.pop("pendente", None):
                log(f"{chave}: a possível mudança de antes não se confirmou (voltou ao texto arquivado)")
            estado[chave] = info
            contagem["igual"] += 1
            continue

        if antigo is not None and not primeira_leitura:
            if len(md) < 0.5 * len(corpo(antigo)):
                log(f"{chave}: texto encolheu demais ({len(corpo(antigo))} -> {len(md)}), ignorado por segurança")
                estado[chave] = {**anterior, "status": "suspeito", "motivo": "texto encolheu mais de 50%"}
                contagem["falha"] += 1
                continue
            time.sleep(5)
            try:
                confirma = ler_documento(doc)
            except (Bloqueado, FalhaLeitura) as e:
                log(f"{chave}: não deu pra confirmar a mudança ({e})")
                contagem["falha"] += 1
                continue
            if texto_puro(confirma) != texto_puro(md):
                log(f"{chave}: página instável (duas leituras diferentes), ignorado")
                estado[chave] = {**anterior, "status": "instável", "motivo": "conteúdo muda a cada leitura"}
                contagem["falha"] += 1
                continue
            impressao = hashlib.sha1(texto_puro(md).encode()).hexdigest()[:16]
            pendente = anterior.get("pendente") or {}
            if pendente.get("impressao") != impressao:
                log(f"{chave}: possível mudança; só registra se a rodada de amanhã encontrar o mesmo texto")
                estado[chave] = {**anterior, "status": "ok", "motivo": "", "ultima_leitura_ok": hoje,
                                 "pendente": {"impressao": impressao, "desde": hoje}}
                contagem["pendente"] += 1
                continue
            if pendente.get("desde") == hoje:  # outra rodada no mesmo dia não confirma: precisa ser outro dia
                log(f"{chave}: mesma possível mudança de hoje; a confirmação fica para amanhã")
                estado[chave] = {**anterior, "status": "ok", "motivo": "", "ultima_leitura_ok": hoje}
                contagem["pendente"] += 1
                continue
            detectada_em = pendente.get("desde", hoje)
        else:
            detectada_em = hoje

        doc.arquivo.parent.mkdir(parents=True, exist_ok=True)
        doc.arquivo.write_text(cabecalho(doc, detectada_em) + md, encoding="utf-8")
        info = {"status": "ok", "motivo": "", "ultima_leitura_ok": hoje}
        if antigo is not None and not primeira_leitura:
            info["ultima_mudanca"] = detectada_em
        elif anterior.get("ultima_mudanca"):
            info["ultima_mudanca"] = anterior["ultima_mudanca"]
        estado[chave] = info
        caminho = doc.arquivo.relative_to(RAIZ).as_posix()

        if args.sem_commit:
            log(f"{chave}: {'mudou' if antigo else 'primeira versão'} (sem commit)")
            contagem["mudou" if antigo else "novo"] += 1
            continue

        git("add", caminho)
        add, rem = diffstat(corpo(antigo), md) if antigo is not None else (0, 0)
        mensagem = f"Fonte: {doc.url}\nLido em: {hoje}"
        resumo = None
        if antigo is None:
            titulo = f"{doc.nome_empresa} · {doc.nome}: primeira versão arquivada"
            contagem["novo"] += 1
        elif primeira_leitura:
            titulo = f"{doc.nome_empresa} · {doc.nome}: versão atual (difere da última captura do Wayback)"
            mensagem = ("Primeira leitura direta do site. O texto difere da última captura do Wayback Machine; "
                        "a mudança aconteceu em algum momento entre essa captura e hoje.\n\n" + mensagem)
            contagem["mudou"] += 1
        else:
            titulo = f"{doc.nome_empresa} · {doc.nome}: +{add} −{rem} linhas"
            mensagem = f"Fonte: {doc.url}\nVista pela primeira vez em: {detectada_em}\nConfirmada em: {hoje}"
            resumo = resumir(doc, corpo(antigo), md)
            if resumo:
                mensagem = f"Resumo automático (IA, confira o diff): {resumo}\n\n" + mensagem
            contagem["mudou"] += 1
        git("commit", "-q", "-m", titulo, "-m", mensagem, env=BOT)
        log(f"{chave}: {titulo}")
        if antigo is not None and not primeira_leitura:
            mudancas.append({"data": detectada_em, "empresa": doc.nome_empresa, "documento": doc.nome,
                             "add": add, "rem": rem, "resumo": resumo,
                             "sha": git("rev-parse", "HEAD").strip()})

    fechar_navegador()
    ARQ_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ARQ_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if not args.sem_commit:
        if mudancas:
            registrar_mudancas(mudancas)
            git("add", "MUDANCAS.md")
        git("add", "dados/estado.json")
        if git("diff", "--cached", "--name-only").strip():
            msg = f"registra {len(mudancas)} mudança(s)" if mudancas else "estado da coleta"
            git("commit", "-q", "-m", msg, env=BOT)

    log("Resumo: " + ", ".join(f"{k}: {v}" for k, v in contagem.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
