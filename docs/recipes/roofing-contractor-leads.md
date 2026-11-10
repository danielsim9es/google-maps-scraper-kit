# Exemplo de prospecção: empresas de telhados e coberturas

Roteiro para localizar empresas de manutenção de telhados, calhas e coberturas em uma localidade. Os nomes de empresas só aparecerão após a coleta real.

## 1. Pesquisar o nicho

```bash
python3 scripts/engine.py start
python3 scripts/scrape.py "empresas de telhados em São Paulo" --city "São Paulo, SP" --lang pt --country br --depth 3
```

## 2. Ampliar palavras-chave

```bash
python3 scripts/scrape.py "telhadistas em São Paulo" --keyword "empresas de calhas em São Paulo" --keyword "manutenção de coberturas em São Paulo" --city "São Paulo, SP" --lang pt --out coberturas.csv
```

## 3. Melhorar cobertura geográfica

```bash
python3 scripts/scrape.py "empresas de telhados em São Paulo" --city "São Paulo, SP" --lang pt --grid 3 --out telhados-grade.csv
```

## 4. Qualificar contatos

Utilize `--has-phone`, `--no-website`, `--min-rating` ou os filtros do dashboard para separar estabelecimentos de acordo com os dados disponíveis. E-mails podem ser buscados nos sites das próprias empresas.

Evite tratar resultados incompletos como listas exaustivas e respeite os termos da fonte e a LGPD.
