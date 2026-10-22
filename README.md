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
| Bancos | Bradesco | [Política de Privacidade](termos/bradesco/politica-de-privacidade.md) | - |
| Bancos | Caixa | [Política de Privacidade](termos/caixa/politica-de-privacidade.md) · [Termos de Uso](termos/caixa/termos-de-uso.md) | jan/2015 |
| Bancos | Inter | [Política de Privacidade](termos/inter/politica-de-privacidade.md) | set/2023 |
| Bancos | Neon | [Política de Privacidade](termos/neon/politica-de-privacidade.md) · [Termos de Uso](termos/neon/termos-de-uso.md) | nov/2023 |
| Bancos | Nubank | [Política de Privacidade](termos/nubank/politica-de-privacidade.md) · [Termos de Uso](termos/nubank/termos-de-uso.md) | dez/2024 |
| Bancos | PagBank | [Política de Privacidade](termos/pagbank/politica-de-privacidade.md) | - |
| Bancos | PicPay | [Política de Privacidade](termos/picpay/politica-de-privacidade.md) | - |
| Compras | Amazon | [Política de Privacidade](termos/amazon/politica-de-privacidade.md) · [Termos de Uso](termos/amazon/termos-de-uso.md) | out/2020 |
| Compras | Americanas | [Política de Privacidade](termos/americanas/politica-de-privacidade.md) | - |
| Compras | Shein | [Política de Privacidade](termos/shein/politica-de-privacidade.md) | - |
| Compras | Shopee | [Política de Privacidade](termos/shopee/politica-de-privacidade.md) | - |
| Apps | Airbnb | [Termos de Uso](termos/airbnb/termos-de-uso.md) | jun/2015 |
| Apps | Rappi | [Política de Privacidade](termos/rappi/politica-de-privacidade.md) · [Termos de Uso](termos/rappi/termos-de-uso.md) | jun/2019 |
| Apps | Uber | [Política de Privacidade](termos/uber/politica-de-privacidade.md) · [Termos de Uso](termos/uber/termos-de-uso.md) | abr/2025 |
| Telefonia | TIM | [Política de Privacidade](termos/tim/politica-de-privacidade.md) | out/2022 |
| Telefonia | Vivo | [Política de Privacidade](termos/vivo/politica-de-privacidade.md) | - |
| Redes | Google | [Política de Privacidade](termos/google/politica-de-privacidade.md) · [Termos de Uso](termos/google/termos-de-uso.md) | mar/2018 |
| Redes | Instagram | [Política de Privacidade](termos/instagram/politica-de-privacidade.md) | - |
| Redes | TikTok | [Termos de Uso](termos/tiktok/termos-de-uso.md) | jun/2023 |
| Redes | WhatsApp | [Política de Privacidade](termos/whatsapp/politica-de-privacidade.md) · [Termos de Uso](termos/whatsapp/termos-de-uso.md) | dez/2020 |
| Streaming | Globo | [Termos de Uso](termos/globo/termos-de-uso.md) | set/2025 |
| Streaming | Spotify | [Política de Privacidade](termos/spotify/politica-de-privacidade.md) · [Termos de Uso](termos/spotify/termos-de-uso.md) | mar/2023 |
| IA | ChatGPT (OpenAI) | [Política de Privacidade](termos/openai/politica-de-privacidade.md) · [Termos de Uso](termos/openai/termos-de-uso.md) | mai/2024 |
| Serviços | Correios | [Política de Privacidade](termos/correios/politica-de-privacidade.md) | mai/2025 |
| Serviços | Serasa | [Política de Privacidade](termos/serasa/politica-de-privacidade.md) · [Termos de Uso](termos/serasa/termos-de-uso.md) | jun/2021 |
| Governo | gov.br | [Termos de Uso](termos/govbr/termos-de-uso.md) | set/2022 |

26 empresas e 37 documentos. ⚠️ = a última leitura falhou ou foi bloqueada.
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
