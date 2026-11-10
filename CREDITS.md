# Créditos, autorias e atribuições

Esta página preserva a proveniência dos componentes reutilizados pelo Google Maps Scraper Kit. A tradução de documentação e a interface em português não transferem a autoria do projeto original.

## Projeto original

O kit original, seu motor `engine/`, os scripts, a skill e os comandos foram desenvolvidos por **Mahan ([@Mahanaicoach](https://github.com/Mahanaicoach))** e distribuídos sob a **licença MIT**. Veja [LICENSE](LICENSE).

Este repositório é o fork mantido em `danielsim9es/google-maps-scraper-kit`, com interface e documentação em pt-BR e o módulo adicional **Prospect Intelligence**.

## Histórico: gosom/google-maps-scraper

As versões 1.x do kit utilizavam o projeto [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper), criado por Georgios Komninos ([@gosom](https://github.com/gosom)), distribuído sob licença MIT. Seu formato de tarefas, API e colunas CSV inspirou a compatibilidade mantida pelo kit. O motor da série 2.x é próprio e não incorpora o código Go daquele motor.

## Chrome for Testing e Chromium

Quando não há navegador disponível, o kit pode baixar o [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/), distribuído pelo Google, verificando SHA-256 conforme `engine/browser.py`. O navegador é um componente externo e tem seus próprios termos e licenças; o repositório não distribui o binário diretamente.

## Base de cidades: GeoNames

As cidades de `engine/presets/cities.tsv.gz` derivam de [GeoNames](https://www.geonames.org/), distribuído sob **Creative Commons Attribution 4.0**. Consulte [licença CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) e `engine/presets/NOTICE.md` para informações adicionais de atribuição.

## Tecnologias de sites e OpenLeadFinder

Parte das ideias ou lógica de análise de tecnologias e sinais de marketing em sites foi adaptada de **OpenLeadFinder**, conforme os créditos do projeto original. Observe os termos e arquivos de licença da fonte e da distribuição original; a referência não significa endosso deste fork.

## Playwright

A renderização opcional de sites utiliza [Microsoft Playwright para Python](https://github.com/microsoft/playwright-python), sob [Apache License 2.0](https://github.com/microsoft/playwright-python/blob/main/LICENSE). A dependência é instalada separadamente via `requirements-browser.txt`.

## Prospect Intelligence

A camada de visualização adicionada neste fork usa componentes web e a biblioteca Leaflet com mapas do OpenStreetMap. Consulte os avisos de licença e atribuição desses projetos, além das condições de uso dos serviços de tiles.

## Licenças e marcas

Os avisos de licença original são mantidos em `LICENSE`. As marcas citadas pertencem aos seus respectivos titulares. O conteúdo presente neste fork não concede permissão adicional sobre fontes de dados de terceiros.

Documento de autoria original e histórico disponível no [repositório de origem](https://github.com/Mahanaicoach/google-maps-scraper-kit/blob/master/CREDITS.md).
