# Política de segurança

O Google Maps Scraper Kit é um serviço **local**. Não é uma aplicação autenticada para publicação direta na internet.

## Problemas de segurança a reportar

- Acesso indevido ao motor além de `127.0.0.1` e `::1`.
- Exposição de `SCRAPER_API_KEY`, credenciais de proxy ou dados de contatos.
- Contorno das verificações de `Host` e `Origin` existentes.
- Execução de conteúdo ou comandos provenientes de dados não confiáveis.
- Redirecionamento de consultas de sites para IPs internos ou endereços privados (SSRF).
- Download e execução de navegador sem a verificação de integridade prevista.
- Vazamento de arquivos `.env`, SQLite, CSV ou resultados de coleta.

O servidor confere os cabeçalhos `Host` e `Origin` e pode exigir `X-API-Key` quando `SCRAPER_API_KEY` é configurada. O contêiner expõe a porta somente em `127.0.0.1`. **Não altere essas proteções para hospedar a aplicação diretamente.**

## Divulgação responsável

Não publique detalhes de vulnerabilidades exploráveis em issues abertas. Para falhas herdadas do projeto original, utilize o [canal de avisos privados de segurança do projeto de origem](https://github.com/Mahanaicoach/google-maps-scraper-kit/security/advisories/new). Para alterações específicas deste fork, procure um canal privado de comunicação com o mantenedor antes de divulgar detalhes. Nunca envie senhas, tokens ou amostras com dados pessoais.

## Fora de escopo

- Limitações normais de requisições do Google Maps.
- Vulnerabilidades de navegadores e imagens-base mantidos por terceiros (reportar aos respectivos projetos).
- Problemas que ocorram exclusivamente depois que alguém remover deliberadamente as proteções locais.

## Boas práticas

Armazene a configuração sensível fora do Git, restrinja permissões de disco, faça backups seguros, revise dependências e respeite a LGPD. Consulte [SETUP.md](SETUP.md).
