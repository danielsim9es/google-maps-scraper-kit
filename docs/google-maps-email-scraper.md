# Como encontrar e-mails de empresas a partir do Google Maps

O Google Maps normalmente fornece dados públicos de estabelecimentos, mas não um campo de e-mail para todos. O Google Maps Scraper Kit complementa a pesquisa acessando **o site público da própria empresa** e procurando endereços de contato, quando disponíveis.

## Fluxo

1. O motor encontra um estabelecimento e seu endereço web.
2. A etapa opcional de sites verifica a página principal e, conforme a configuração, páginas de contato e apresentação.
3. O coletor procura e-mails expostos publicamente.
4. Com `--verify-emails`, o domínio é consultado por DNS/MX. Isso **não valida a existência da caixa de entrada**.

Um site ausente, bloqueado ou sem e-mail pode gerar campo vazio. O processo não adivinha contatos.

## Exemplo no Brasil

```bash
python3 scripts/engine.py start
python3 scripts/scrape.py "clínicas odontológicas em São Paulo" --city "São Paulo, SP" --lang pt --country br --depth 3 --has-email --out clinicas.csv
```

Para evitar a busca de e-mails:

```bash
python3 scripts/scrape.py "barbearias em Campinas" --city "Campinas, SP" --lang pt --no-email
```

Para sites com conteúdo renderizado em JavaScript, após instalar a dependência opcional:

```bash
python3 -m pip install -r requirements-browser.txt
python3 -m playwright install chromium
python3 scripts/scrape.py "clínicas em Santos" --city "Santos, SP" --lang pt --browser-sites
```

## Resultado

As colunas `emails`, `website` e `phone` podem ser exportadas com outras informações do negócio. Utilize os filtros do [dashboard Prospect Intelligence](dashboard.md) para visualizar somente resultados com e-mail.

## Privacidade e boas práticas

Um contato publicamente visível não autoriza qualquer forma de tratamento. Defina finalidade, base legal, controles de acesso e prazo de retenção, de acordo com a LGPD. Não use o sistema para spam ou coleta de dados de pessoas sem justificativa legítima.
