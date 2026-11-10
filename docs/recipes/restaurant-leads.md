# Exemplo de prospecção: restaurantes

Roteiro de pesquisa de restaurantes, cafeterias e pizzarias, com dados reais somente após a execução.

## 1. Pesquisar um segmento

```bash
python3 scripts/engine.py start
python3 scripts/scrape.py "restaurantes em Santos" --city "Santos, SP" --lang pt --country br --depth 3
```

## 2. Incluir outros tipos de estabelecimento

```bash
python3 scripts/scrape.py "restaurantes em Santos" --keyword "pizzarias em Santos" --keyword "cafeterias em Santos" --city "Santos, SP" --lang pt --out alimentacao.csv
```

## 3. Ampliar a área

```bash
python3 scripts/scrape.py "restaurantes em Santos" --city "Santos, SP" --lang pt --grid 3 --out restaurantes-grade.csv
```

## 4. Avaliar perfil comercial

Confira nome, telefone, endereço, site, avaliação e quantidade de avaliações. O campo de preço pode existir no conjunto ampliado de saída, mas sua disponibilidade varia. Para mais colunas, use `--full`.

No painel `http://localhost:8080/dashboard`, filtre estabelecimentos sem site, com e-mail ou com nota mínima.

**Importante:** os resultados não representam participação de mercado nem audiência comprovada. Use dados de contatos de forma lícita, com moderação e respeito à LGPD.
