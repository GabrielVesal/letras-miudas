"""Confere todos os documentos declarados em empresas/*.json e registra o que mudou.

Cada mudança vira um commit próprio, com o diff do documento e uma linha nova em
MUDANCAS.md. Para evitar alarme falso, uma mudança só é aceita se:
  - o texto novo ainda parece o documento (tamanho e vocabulário jurídico);
  - o texto não encolheu pela metade de uma vez (sinal de página de erro);
  - uma segunda leitura, alguns segundos depois, devolve exatamente o mesmo texto.

Uso:
  python scripts/coletar.py                     # tudo
  python scripts/coletar.py --empresas nubank   # só algumas
  python scripts/coletar.py --sem-commit        # só grava os arquivos
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(__file__))

from comum import (  # noqa: E402
    RAIZ, Bloqueado, FalhaLeitura, cabecalho, carregar_declaracoes, fechar_navegador, ler_documento,
)

REPO = os.environ.get("GITHUB_REPOSITORY", "GabrielVesal/letras-miudas")
ARQ_MUDANCAS = RAIZ / "MUDANCAS.md"
ARQ_ESTADO = RAIZ / "dados" / "estado.json"
BOT = {
    "GIT_AUTHOR_NAME": "letras-miudas-bot",
    "GIT_AUTHOR_EMAIL": "letras-miudas-bot@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "letras-miudas-bot",
    "GIT_COMMITTER_EMAIL": "letras-miudas-bot@users.noreply.github.com",
}

CAB_MUDANCAS = """# Mudanças detectadas

Toda vez que o robô encontra uma mudança num documento, ela entra aqui (as mais novas primeiro).
O resumo é feito automaticamente por IA a partir do diff: confira sempre o **histórico**, que mostra
a mudança linha por linha.

| Data | Empresa | Documento | Linhas | Resumo automático | Histórico |
|---|---|---|---:|---|---|
"""
SEPARADOR = "|---|---|---|---:|---|---|\n"

MODELO = os.environ.get("MODELO_RESUMO", "openai/gpt-4.1-mini")
PROMPT = (
    "Você recebe o diff entre duas versões de um documento ({doc}) da empresa {empresa}. "
    "Linhas com '-' saíram, linhas com '+' entraram. Explique em português simples, em no máximo "
    "3 frases curtas, o que mudou na prática para quem usa o serviço. Cite só o que está no diff, "
    "sem suposições. Se a mudança for só de formatação, data de atualização ou redação sem efeito "
    "prático, responda exatamente: Só ajustes de redação ou formatação."
)


def resumir(doc, antigo: str, novo: str) -> str | None:
    """Resumo da mudança via GitHub Models. Opcional: se falhar, segue sem resumo."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    diff = "\n".join(difflib.unified_diff(antigo.splitlines(), novo.splitlines(), lineterm="", n=1))
    diff = diff[:14000]
    try:
        r = requests.post(
            "https://models.github.ai/inference/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"model": MODELO, "temperature": 0.1, "max_tokens": 220, "messages": [
                {"role": "system", "content": PROMPT.format(doc=doc.nome, empresa=doc.nome_empresa)},
                {"role": "user", "content": diff},
            ]},
            timeout=60,
        )
        if r.status_code != 200:
            log(f"  resumo indisponível (HTTP {r.status_code})")
            return None
        texto = r.json()["choices"][0]["message"]["content"].strip()
        return " ".join(texto.split())[:400]
    except Exception as e:  # rede, limite, formato
        log(f"  resumo indisponível ({type(e).__name__})")
        return None


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def git(*args: str, env: dict | None = None) -> str:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def diffstat(caminho: str) -> tuple[int, int]:
    saida = git("diff", "--cached", "--numstat", "--", caminho).strip()
    if not saida:
        return 0, 0
    add, rem, _ = saida.split("\t", 2)
    return int(add), int(rem)


def registrar_mudanca(doc, add: int, rem: int, hoje: str, resumo: str | None) -> None:
    caminho = doc.arquivo.relative_to(RAIZ).as_posix()
    historico = f"https://github.com/{REPO}/commits/main/{caminho}"
    resumo_cel = (resumo or "-").replace("|", "/")
    linha = (f"| {hoje} | {doc.nome_empresa} | {doc.nome} | +{add} −{rem} | {resumo_cel} | "
             f"[histórico]({historico}) |\n")
    antigas = ""
    if ARQ_MUDANCAS.exists():
        antigas = ARQ_MUDANCAS.read_text(encoding="utf-8").split(SEPARADOR, 1)[-1]
    ARQ_MUDANCAS.write_text(CAB_MUDANCAS + linha + antigas, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--empresas", help="lista separada por vírgula (slugs)")
    ap.add_argument("--sem-commit", action="store_true")
    args = ap.parse_args()

    filtro = args.empresas.split(",") if args.empresas else None
    docs = carregar_declaracoes(filtro)
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    estado = json.loads(ARQ_ESTADO.read_text(encoding="utf-8")) if ARQ_ESTADO.exists() else {}
    contagem = {"mudou": 0, "novo": 0, "igual": 0, "falha": 0, "bloqueado": 0}

    for doc in docs:
        chave = f"{doc.empresa}/{doc.tipo}"
        try:
            md = ler_documento(doc)
        except Bloqueado as e:
            log(f"{chave}: bloqueado ({e})")
            estado[chave] = {**estado.get(chave, {}), "status": "bloqueado", "motivo": str(e)}
            contagem["bloqueado"] += 1
            continue
        except FalhaLeitura as e:
            log(f"{chave}: falha ({e})")
            estado[chave] = {**estado.get(chave, {}), "status": "falha", "motivo": str(e)}
            contagem["falha"] += 1
            continue

        novo = cabecalho(doc) + md
        antigo = doc.arquivo.read_text(encoding="utf-8") if doc.arquivo.exists() else None
        if antigo == novo:
            estado[chave] = {**estado.get(chave, {}), "status": "ok", "motivo": ""}
            contagem["igual"] += 1
            continue

        if antigo is not None:
            if len(novo) < 0.5 * len(antigo):
                log(f"{chave}: texto encolheu demais ({len(antigo)} -> {len(novo)}), ignorado por segurança")
                estado[chave] = {**estado.get(chave, {}), "status": "suspeito", "motivo": "texto encolheu mais de 50%"}
                contagem["falha"] += 1
                continue
            time.sleep(5)
            try:
                confirma = ler_documento(doc)
            except (Bloqueado, FalhaLeitura) as e:
                log(f"{chave}: não deu pra confirmar a mudança ({e})")
                contagem["falha"] += 1
                continue
            if confirma != md:
                log(f"{chave}: página instável (duas leituras diferentes), ignorado")
                estado[chave] = {**estado.get(chave, {}), "status": "instável", "motivo": "conteúdo muda a cada leitura"}
                contagem["falha"] += 1
                continue

        doc.arquivo.parent.mkdir(parents=True, exist_ok=True)
        doc.arquivo.write_text(novo, encoding="utf-8")
        estado[chave] = {"status": "ok", "motivo": "", "ultima_mudanca": hoje}
        caminho = doc.arquivo.relative_to(RAIZ).as_posix()

        if args.sem_commit:
            log(f"{chave}: {'mudou' if antigo else 'primeira versão'} (sem commit)")
            contagem["mudou" if antigo else "novo"] += 1
            continue

        git("add", caminho)
        add, rem = diffstat(caminho)
        if antigo is None:
            titulo = f"{doc.nome_empresa} · {doc.nome}: primeira versão arquivada"
            contagem["novo"] += 1
        else:
            titulo = f"{doc.nome_empresa} · {doc.nome}: +{add} −{rem} linhas"
            resumo = resumir(doc, antigo, novo)
            registrar_mudanca(doc, add, rem, hoje, resumo)
            git("add", "MUDANCAS.md")
            contagem["mudou"] += 1
        corpo = f"Fonte: {doc.url}\nDetectado em: {hoje}"
        if antigo is not None and resumo:
            corpo = f"Resumo automático (IA, confira o diff): {resumo}\n\n" + corpo
        git("commit", "-q", "-m", titulo, "-m", corpo, env=BOT)
        log(f"{chave}: {titulo}")

    fechar_navegador()
    ARQ_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ARQ_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if not args.sem_commit:
        git("add", "dados/estado.json")
        if git("diff", "--cached", "--name-only").strip():
            git("commit", "-q", "-m", "estado da coleta", env=BOT)

    log("Resumo: " + ", ".join(f"{k}: {v}" for k, v in contagem.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
