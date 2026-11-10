# Coletor Google Maps em Python: guia da linha de comando

O arquivo `scripts/scrape.py` executa pesquisas, acompanha as tarefas do motor local e exporta informações de empresas. A versão básica utiliza bibliotecas padrão do Python; para páginas complexas existe a opção de renderização com Playwright.

## Instalar e executar

```bash
git clone https://github.com/danielsim9es/google-maps-scraper-kit.git
cd google-maps-scraper-kit
python3 scripts/engine.py start
python3 scripts/scrape.py "padarias em São Paulo" --city "São Paulo, SP" --lang pt --country br --depth 5
```

É possível fornecer latitude e longitude no lugar de `--city`.

```bash
python3 scripts/scrape.py "barbearias em São Paulo" -23.5505 -46.6333 --lang pt --country br
```

## Parâmetros principais

| Parâmetro | Efeito |
|---|---|
| `keyword` | Termo de busca |
| `lat lon` | Coordenadas do centro de pesquisa |
| `--city` | Localidade geocodificada automaticamente; repetível |
| `--keyword` | Acrescenta termos de pesquisa |
| `--keywords-file` | Lê termos de um arquivo texto, um por linha |
| `--depth N` | Controla a profundidade de coleta |
| `--lang pt` | Define português como idioma da pesquisa |
| `--country br` | Define Brasil como país |
| `--grid N` | Divide uma localidade em uma grade de pesquisa |
| `--deep-scan` | Amplia uma grade, com mais tempo de execução |
| `--max-time` | Limite de tempo da tarefa |
| `--reviews N` | Solicita até N avaliações por empresa (1 a 5) |
| `--no-email`, `--no-socials` | Ignora busca de e-mails e redes sociais |
| `--browser-sites` | Tenta carregar sites com Playwright |
| `--verify-emails` | Consulta registros MX do domínio |
| `--tech` | Pesquisa tecnologias e sinais de marketing no site |
| `--min-rating` | Nota mínima |
| `--min-reviews` | Número mínimo de avaliações |
| `--has-phone`, `--has-email`, `--no-website` | Restringe negócios por contato |
| `--exclude` | Exclui negócios de um CSV/JSON anterior |
| `--limit N` | Limita a quantidade final de linhas |
| `--full` | Inclui o conjunto ampliado de colunas |
| `--fields` | Seleciona explicitamente colunas |
| `--out` | Caminho do arquivo de saída |
| `--json` | Usa JSON em vez de CSV |

Confira os parâmetros da versão instalada com `python3 scripts/scrape.py --help`.

## Exportação e filtros

```bash
python3 scripts/scrape.py "academias em Campinas" --city "Campinas, SP" --lang pt --min-rating 4.5 --has-phone --out academias.csv
python3 scripts/scrape.py "restaurantes em Santos" --city "Santos, SP" --lang pt --json --out restaurantes.json
```

Saídas CSV típicas usam `title`, `phone`, `emails`, `website`, `category`, `address`, `review_rating` e `review_count`, além de redes sociais se solicitadas. Os identificadores permanecem em inglês para preservar scripts de integração.

## Atenção

A quantidade de empresas não é garantida; filtros, limite do provedor e existência de dados influenciam o resultado. A coleta de sites e avaliações aumenta o tempo. Consulte [instalação](../SETUP.md) e [uso responsável](../README.md#responsible-use).
