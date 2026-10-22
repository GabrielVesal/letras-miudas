# Como contribuir

O jeito mais útil de ajudar é **adicionar uma empresa**. É um arquivo só.

## Adicionar uma empresa

Crie `empresas/<nome-da-empresa>.json`:

```json
{
  "nome": "Nome da Empresa",
  "categoria": "Bancos",
  "site": "https://www.empresa.com.br/",
  "documentos": {
    "politica-de-privacidade": {
      "url": "https://www.empresa.com.br/politica-de-privacidade"
    },
    "termos-de-uso": {
      "url": "https://www.empresa.com.br/termos-de-uso"
    }
  }
}
```

Abra o pull request. Quando ele entrar, o robô busca o histórico da empresa no Wayback Machine e passa a conferir os documentos todo dia.

### Campos opcionais de cada documento

| Campo | Para que serve |
|---|---|
| `seletor` | Seletor CSS do bloco que tem o texto (ex.: `"main .conteudo"`). Use quando a extração automática pega menu ou rodapé junto. |
| `remover` | Lista de seletores CSS para tirar do texto (banners, "leia também" etc.). |
| `remover_linhas` | Lista de expressões regulares: parágrafos que batem são tirados do texto. Use para trechos que aparecem ou não conforme o país de quem acessa (ex.: avisos só para residentes nos EUA). |
| `cortar_em` | Lista de expressões regulares: o texto termina na primeira linha que bater. Use quando a página traz, depois do documento que vale no Brasil, outras versões inteiras (para a Europa, a versão anterior etc.). |
| `navegador` | `true` se a página só mostra o texto depois de rodar JavaScript. |
| `urls_antigas` | Endereços antigos do mesmo documento, para o histórico do Wayback ficar completo. |

Nomes de documento usados: `termos-de-uso`, `politica-de-privacidade`, `politica-de-cookies`, `contrato`. Se precisar de outro, use um nome curto em minúsculas com hífens.

### Testando antes de mandar

```bash
pip install -r requirements.txt
python -m playwright install chromium        # só se usar "navegador": true
python scripts/coletar.py --empresas nome-da-empresa --sem-commit
```

Confira o arquivo gerado em `termos/nome-da-empresa/`. Ele deve ter só o texto do documento, sem menu, rodapé ou banner de cookies.

## Regras do robô

- Ele se identifica (user-agent `letras-miudas/1.0` com link para este repositório).
- Respeita o `robots.txt` de cada site.
- Lê cada página uma vez por dia, com intervalo entre requisições.
- **Não contorna bloqueios.** Se um site pedir captcha ou verificação anti-robô, o documento fica marcado como bloqueado. Não envie PR tentando burlar isso.

## Outras formas de ajudar

- Encontrou um alarme falso (mudança que não muda nada, tipo data ou menu)? Abra uma issue: normalmente se resolve com um `seletor` ou `remover`.
- Melhorias no extrator (`scripts/comum.py`), no histórico (`scripts/historico.py`) ou no que é gerado a partir do acervo (`scripts/gerar.py`, `scripts/pagina.py`, `scripts/imagem.py`) são bem-vindas.
