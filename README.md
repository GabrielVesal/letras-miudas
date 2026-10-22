# letras-miudas

**O histórico de tudo que as empresas mudam nos termos de uso e nas políticas de privacidade que você aceitou sem ler.**

Todo dia um robô lê os termos de uso e as políticas de privacidade das empresas que o brasileiro mais usa (bancos, lojas, apps, operadoras, redes sociais, IA) e guarda o texto aqui, em Markdown. Mudou uma vírgula, vira um commit: dá para ver exatamente o que entrou e o que saiu, e quando.

E não começa do zero: o passado de cada documento foi reconstruído a partir do [Wayback Machine](https://web.archive.org/), então o histórico volta anos.

- 📜 **[Mudanças detectadas](MUDANCAS.md)**: as mudanças mais recentes, com resumo automático.
- 🔎 **[Achados](ACHADOS.md)**: quem mais mudou, quem mais cresceu, quando cada empresa passou a falar de IA, biometria ou LGPD.
- 📂 **[termos/](termos/)**: o texto atual de cada documento. Abra um arquivo e clique em **History** para ver todas as versões.

## Empresas acompanhadas

<!-- EMPRESAS -->
| Categoria | Empresa | Documentos | Arquivado desde |
|---|---|---|---|
| Bancos | Bradesco | Política de Privacidade | - |
| Bancos | Caixa | Política de Privacidade · Termos de Uso | - |
| Bancos | Inter | Política de Privacidade | - |
| Bancos | Neon | Política de Privacidade · Termos de Uso | - |
| Bancos | Nubank | Política de Privacidade · Termos de Uso | - |
| Bancos | PagBank | Política de Privacidade | - |
| Bancos | PicPay | Política de Privacidade | - |
| Compras | Amazon | Política de Privacidade · Termos de Uso | - |
| Compras | Americanas | Política de Privacidade | - |
| Compras | Shein | Política de Privacidade | - |
| Compras | Shopee | Política de Privacidade | - |
| Apps | Airbnb | Termos de Uso | - |
| Apps | Rappi | Política de Privacidade · Termos de Uso | - |
| Apps | Uber | Política de Privacidade · Termos de Uso | - |
| Telefonia | TIM | Política de Privacidade | - |
| Telefonia | Vivo | Política de Privacidade | - |
| Redes | Google | Política de Privacidade · Termos de Uso | - |
| Redes | Instagram | Política de Privacidade | - |
| Redes | TikTok | Termos de Uso | - |
| Redes | WhatsApp | Política de Privacidade · Termos de Uso | - |
| Streaming | Globo | Termos de Uso | - |
| Streaming | Spotify | Política de Privacidade · Termos de Uso | - |
| IA | ChatGPT (OpenAI) | Política de Privacidade · Termos de Uso | - |
| Serviços | Correios | Política de Privacidade | - |
| Serviços | Serasa | Política de Privacidade · Termos de Uso | - |
| Governo | gov.br | Termos de Uso | - |

26 empresas e 0 documentos. ⚠️ = a última leitura falhou ou foi bloqueada.
<!-- /EMPRESAS -->

Falta alguma? [Adicione](CONTRIBUTING.md): é um arquivo só.

## Como ver o que mudou

1. Abra o documento em `termos/<empresa>/`.
2. Clique em **History** (ou "Histórico") no topo do arquivo.
3. Clique em qualquer versão para ver o diff: vermelho saiu, verde entrou.

Pelo terminal:

```bash
git clone https://github.com/GabrielVesal/letras-miudas
cd letras-miudas
git log -p --follow termos/nubank/politica-de-privacidade.md
```

## Por que isso existe

Ninguém lê os termos de uso, e as empresas sabem disso. Quando uma delas cria uma taxa, passa a compartilhar dados com parceiros ou começa a usar o que você faz para treinar IA, a mudança fica escondida num texto enorme. Aqui ela fica registrada, com data, para qualquer pessoa conferir: consumidores, jornalistas, advogados e pesquisadores.

A ideia vem do [Open Terms Archive](https://opentermsarchive.org/), projeto francês que acompanha termos de serviço na Europa. O Brasil ainda não tinha o seu.

## Como funciona

- `empresas/*.json`: a lista de empresas e o endereço de cada documento.
- `scripts/historico.py`: reconstrói as versões antigas pelo Wayback Machine. Cada commit histórico leva o link da captura original.
- `scripts/coletar.py`: roda todo dia no GitHub Actions, converte cada página em Markdown e cria um commit por mudança.
- `scripts/achados.py`: gera o [ACHADOS.md](ACHADOS.md).

O robô se identifica, respeita o `robots.txt`, lê cada página uma vez por dia e **não contorna bloqueios anti-robô**. Para evitar alarme falso, uma mudança só é registrada se aparecer em duas leituras seguidas e se o texto ainda parecer o documento.

## Aviso

Projeto independente, sem vínculo com as empresas. Os textos pertencem a elas e ficam aqui para fins de transparência e pesquisa. As datas antigas são as das capturas do Wayback, não necessariamente a data de publicação. Nada aqui é orientação jurídica. Detalhes em [AVISO.md](AVISO.md).

Código sob licença [MIT](LICENSE).
