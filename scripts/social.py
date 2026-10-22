"""Gera social.png (1280x640), a imagem que aparece quando alguém compartilha o link do repositório
ou da página. Não roda todo dia: rode à mão quando os números mudarem bastante.

Uso: python scripts/social.py   (precisa do Playwright com o Chromium instalado)
"""

from __future__ import annotations

import html
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from acervo import carregar_acervo  # noqa: E402
from comum import RAIZ, texto_puro  # noqa: E402
from imagem import tempo_por_extenso  # noqa: E402


def main() -> int:
    regs = [r for r in carregar_acervo() if r.existe]
    minutos = sum(r.minutos for r in regs)
    numero = f"{round(minutos / 60)} horas" if minutos >= 120 else tempo_por_extenso(minutos)
    n_emp = len({r.doc.empresa for r in regs})
    ano0 = min(r.versoes[0].data[:4] for r in regs)
    partes = []
    for r in sorted(regs, key=lambda r: -r.minutos):
        t = texto_puro((RAIZ / r.caminho).read_text(encoding="utf-8"))
        ini = int(len(t) * 0.3)
        partes.append(t[ini:ini + 900])
    miudas = html.escape(" ".join(partes)[:30000])
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; width: 1280px; height: 640px; overflow: hidden; background: #fbfcfd; color: #18202e;
           font-family: "Atkinson Hyperlegible Next", system-ui, -apple-system, "Segoe UI", sans-serif; position: relative; }}
    .miudas {{ position: absolute; inset: 0; margin: 0; padding: 10px 12px; font: 7px/1.32 Georgia, serif;
              color: #b9c0cc; text-align: justify; overflow: hidden; }}
    .recorte {{ position: absolute; left: 72px; top: 92px; width: 760px; background: #fbfcfd; padding: 34px 40px 36px;
               box-shadow: 0 0 0 12px #fbfcfd; }}
    .n {{ font-size: 170px; line-height: .9; font-weight: 800; letter-spacing: -.035em; margin: 0 0 22px; }}
    .f {{ font-size: 34px; line-height: 1.3; margin: 0 0 26px; }}
    .r {{ font-size: 24px; color: #4a5263; margin: 0; }}
    </style></head><body>
    <p class="miudas">{miudas}</p>
    <div class="recorte"><p class="n">{numero}</p>
    <p class="f">para ler os termos de uso e as políticas de privacidade de {n_emp} empresas que você usa.
    Aqui está cada versão, desde {ano0}.</p>
    <p class="r">github.com/GabrielVesal/letras-miudas</p></div>
    </body></html>"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 640})
        pg.set_content(pagina, wait_until="load")
        pg.screenshot(path=str(RAIZ / "social.png"))
        b.close()
    print("social.png gerado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
