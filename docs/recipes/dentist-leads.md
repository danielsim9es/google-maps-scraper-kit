# Exemplo de prospecção: clínicas odontológicas

Este roteiro demonstra como organizar uma pesquisa de **clínicas e consultórios odontológicos** em uma cidade. Não há dados simulados nem garantia de contatos.

## 1. Fazer uma coleta de teste

```bash
python3 scripts/engine.py start
python3 scripts/scrape.py "dentistas em Campinas" --city "Campinas, SP" --lang pt --country br --depth 3 --out dentistas.csv
```

Avalie se a área está correta antes de ampliar a pesquisa.

## 2. Ampliar a cobertura

```bash
python3 scripts/scrape.py "clínicas odontológicas em Campinas" --city "Campinas, SP" --lang pt --grid 3 --out clinicas.csv
```

A grade divide a área em sub-regiões e tenta reduzir o limite por consulta. Ela não garante encontrar todas as clínicas.

## 3. Identificar contatos e oportunidades

Telefone, site, endereço, e-mail e avaliações são úteis para segmentação. Para empresas sem site:

```bash
python3 scripts/scrape.py "dentistas em Campinas" --city "Campinas, SP" --lang pt --no-website
```

O e-mail é consultado opcionalmente no site; não é fornecido para todos os estabelecimentos.

## 4. Avaliar no painel

Abra `http://localhost:8080/dashboard` e use os filtros de avaliação, telefone, site e segmento. Exporte o CSV filtrado para revisão manual.

**Uso responsável:** observe a LGPD, as regras da plataforma e a legislação de publicidade aplicável à atividade odontológica.
