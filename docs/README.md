# Guias e receitas em português

Documentação funcional do [Google Maps Scraper Kit](../README.md) e do dashboard Prospect Intelligence.

## Comece por aqui

- [Instalação e configuração](../SETUP.md)
- [Dashboard Prospect Intelligence](dashboard.md)
- [CLI Python: comandos e parâmetros](google-maps-scraper-python.md)
- [Pesquisa sem chave de API](google-maps-scraper-no-api-key.md)
- [Como encontrar e-mails de empresas](google-maps-email-scraper.md)
- [Uso com Claude Code e agentes](scrape-google-maps-leads-with-claude-code.md)
- [Comparação com outras ferramentas](best-google-maps-scrapers.md)

## Exemplos por segmento

- [Consultórios e clínicas odontológicas](recipes/dentist-leads.md)
- [Restaurantes](recipes/restaurant-leads.md)
- [Empresas de coberturas e telhados](recipes/roofing-contractor-leads.md)

Os exemplos usam consultas ilustrativas e **não** representam leads reais. Os dados de saída são obtidos somente após executar as pesquisas. Use o serviço com moderação, observe os termos das plataformas e a LGPD.

## Referência técnica

- Código do servidor: `engine/serve.py`.
- API de relatórios: `engine/dashboard_api.py`.
- API do coletor: `/api/docs`, disponível quando o motor é iniciado.
- Testes: `engine/test_engine.py` e `engine/test_dashboard.py`.

Os nomes de arquivos, endpoints, variáveis de ambiente e flags permanecem originais para manter compatibilidade.
