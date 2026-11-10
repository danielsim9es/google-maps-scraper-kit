# Google Maps Scraper Kit — versão em português (Brasil)

<p align="center">
  <img src="assets/banner.svg" alt="Google Maps Scraper Kit: ferramenta local para pesquisar empresas no Google Maps" width="100%">
</p>

**Pesquise empresas no Google Maps, organize oportunidades comerciais e exporte resultados em CSV ou JSON.** Esta é a versão adaptada para português do Brasil do projeto [Mahanaicoach/google-maps-scraper-kit](https://github.com/Mahanaicoach/google-maps-scraper-kit), com o módulo adicional **Prospect Intelligence** desenvolvido neste fork.

[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776ab)](https://www.python.org/)
[![Projeto original](https://img.shields.io/badge/projeto-original-64748b)](https://github.com/Mahanaicoach/google-maps-scraper-kit)

> **Importante:** é um sistema de execução local; não é um serviço público hospedado. O motor acessa o Google Maps e, quando solicitado, os sites das empresas. Use apenas informações obtidas licitamente, respeite os termos das plataformas e a LGPD.

## O que você encontra neste repositório

- **Coletor Google Maps:** pesquisa empresas por categoria e localização, processa tarefas e salva os resultados localmente.
- **Prospect Intelligence:** painel em português com KPIs, mapa, lista de leads, filtros e acompanhamento das coletas.
- **Dados disponíveis:** empresa, categoria, endereço, telefone, site, e-mail encontrado no site, avaliações e quantidade de avaliações. Campos opcionais incluem redes sociais, coordenadas, recursos do site e informações adicionais.
- **Exportação:** CSV protegido contra fórmulas de planilhas ou JSON, inclusive com filtros do painel.
- **Automação:** API HTTP local, comandos de terminal e integração com Claude Code, Codex e Cursor.
- **Execução:** Python 3.9+, navegador Chrome/Chromium compatível ou Docker. O motor principal usa a biblioteca padrão do Python; renderização opcional dos sites utiliza Playwright.
- **Persistência:** SQLite e arquivos CSV no diretório `.engine/`. Não há necessidade de banco externo.

## Início rápido

<a id="quick-start"></a>

### 1. Instalar

Necessário Python 3.9 ou superior. Para a coleta é necessário Chrome, Chromium, Edge ou Brave; se não encontrar um navegador compatível, o motor pode baixar uma cópia verificada do Chrome for Testing na primeira execução.

```bash
git clone https://github.com/danielsim9es/google-maps-scraper-kit.git
cd google-maps-scraper-kit
python3 scripts/engine.py start
```

No Windows, utilize `py` em vez de `python3`. Se preferir Docker, execute `docker compose up -d --build` em vez do comando de inicialização do motor.

### 2. Abrir as interfaces

| Endereço | Função |
|---|---|
| `http://localhost:8080/dashboard` | **Prospect Intelligence:** indicadores, mapa, filtros e exportação |
| `http://localhost:8080/` | Formulário do coletor original, em português |
| `http://localhost:8080/api/docs` | Documentação HTTP |
| `http://localhost:8080/api/openapi.json` | Especificação OpenAPI |

A porta padrão é `8080`; personalize-a no arquivo `.env` com `SCRAPER_PORT`.

### 3. Fazer a primeira pesquisa

Exemplo para São Paulo:

```bash
python3 scripts/scrape.py "barbearias em São Paulo" --city "São Paulo, SP, Brasil" --lang pt --country br --depth 3
```

Exemplo com coordenadas e exportação JSON:

```bash
python3 scripts/scrape.py "cafeterias em São Paulo" -23.5505 -46.6333 --lang pt --country br --depth 5 --out cafeterias.json
```

**Observação:** os nomes das opções e os campos da API permanecem em inglês para garantir compatibilidade com automações existentes. Os comandos apresentados são exemplos de uso; o número de resultados depende dos dados efetivamente disponíveis.

## Prospect Intelligence — painel de prospecção

O painel usa o mesmo banco SQLite e os arquivos de coletas do motor. Não precisa de API de terceiros nem cria dados demonstrativos.

- Indicadores de empresas identificadas, contatos, sites, e-mails e avaliações.
- Mapa interativo baseado nas coordenadas obtidas, usando Leaflet e OpenStreetMap.
- Segmentação, busca textual, ordenação, filtros e paginação.
- Acompanhamento das tarefas de coleta e seu progresso.
- Exportação de resultados filtrados em CSV e JSON.
- Criação de pesquisas pelo próprio painel, com escolha de localidade.

**Sem coletas, os indicadores começam em zero.** O painel não inventa empresas, números de mercado ou probabilidades de sucesso.

Documentação detalhada: [docs/dashboard.md](docs/dashboard.md).

<a id="what-you-get"></a>
## Campos e dados de saída

| Coluna | Significado |
|---|---|
| `title` | Nome do estabelecimento |
| `phone` | Telefone informado |
| `emails` | E-mail localizado no site da empresa, quando houver |
| `website` | Site |
| `category` | Categoria |
| `address` | Endereço |
| `review_rating` | Nota exibida |
| `review_count` | Quantidade de avaliações |
| `instagram`, `facebook`, `linkedin`, `tiktok`, `youtube`, `x` | Links de redes sociais encontrados no site |

Use `--full` para solicitar o conjunto ampliado de colunas, inclusive coordenadas e identificadores. Use `--tech` para tentar detectar pixels de publicidade e outras tecnologias do site.

<a id="batch-jobs-and-the-python-cli"></a>
## Coletas em lote e opções úteis

```bash
# Mais termos no mesmo trabalho
python3 scripts/scrape.py "barbearias em Campinas" --keyword "salões em Campinas" --city "Campinas, SP" --lang pt

# Lista de termos, um por linha
python3 scripts/scrape.py --keywords-file examples/queries.example.txt --city "São Paulo, SP" --lang pt

# Dividir a região em uma grade e eliminar duplicatas
python3 scripts/scrape.py "restaurantes em Curitiba" --city "Curitiba, PR" --grid 3 --lang pt

# Busca ampliada (mais lenta)
python3 scripts/scrape.py "restaurantes em Curitiba" --city "Curitiba, PR" --deep-scan --lang pt

# Apenas empresas sem site
python3 scripts/scrape.py "oficinas em Santos" --city "Santos, SP" --no-website --lang pt

# Filtrar empresas com telefone e nota mínima
python3 scripts/scrape.py "clínicas em São Paulo" --city "São Paulo, SP" --has-phone --min-rating 4 --lang pt
```

| Opção | O que faz |
|---|---|
| `--city` | Localidade para geocodificação automática |
| `--lang pt --country br` | Solicita idioma e país brasileiros |
| `--depth N` | Quantas etapas de resultados carregar |
| `--grid N` / `--deep-scan` | Amplia a cobertura por subdivisão geográfica |
| `--no-email`, `--no-socials` | Evita etapas opcionais |
| `--verify-emails` | Verifica o domínio do e-mail por DNS/MX |
| `--browser-sites` | Renderiza sites opcionalmente com Playwright |
| `--min-rating`, `--min-reviews` | Filtra por avaliações |
| `--has-phone`, `--has-email`, `--no-website` | Filtra por dados de contato |
| `--limit`, `--exclude` | Limita ou remove resultados já coletados |
| `--out arquivo.csv`, `--json`, `--full` | Controla arquivo e formato |

Veja todas as opções com `python3 scripts/scrape.py --help`.

<a id="use-it-with-claude-code-or-any-agent"></a>
## Agentes de IA

O repositório inclui instruções para agentes e quatro comandos Claude Code:

| Comando | Uso |
|---|---|
| `/scrape` | Pesquisa simples |
| `/scrape-batch` | Pesquisa em lote |
| `/scrape-setup` | Inicializar e verificar o motor |
| `/scrape-jobs` | Listar ou gerenciar coletas |

As instruções operacionais estão em [CLAUDE.md](CLAUDE.md) e [SKILL.md](.claude/skills/google-maps-scraper/SKILL.md). Um agente não deve ignorar limites de uso ou criar dados inexistentes.

## API e backend

A API é disponibilizada **somente no ambiente local**. Endpoints do motor:

- `GET /api/v1/jobs` — listar coletas.
- `POST /api/v1/jobs` — criar coleta.
- `GET /api/v1/jobs/{id}` — consultar situação.
- `DELETE /api/v1/jobs/{id}` — excluir coleta.
- `GET /api/v1/jobs/{id}/download?format=csv|json` — baixar resultados.

O módulo Prospect Intelligence acrescenta endpoints `/api/v1/dashboard`, `/summary`, `/leads`, `/geojson` e `/export`. Consulte [docs/dashboard.md](docs/dashboard.md) para os parâmetros.

## Configuração e segurança

```bash
cp .env.example .env
python3 scripts/engine.py status
python3 scripts/engine.py stop
```

- `SCRAPER_PORT`: porta da API.
- `SCRAPER_API_KEY`: chave opcional de autenticação. Recomendável quando a API for acessada por outras ferramentas locais.
- `SCRAPER_HEADLESS`: controle opcional do modo do navegador.
- `SCRAPER_BASE_URL`: URL utilizada pelos scripts clientes, quando necessário.

O projeto restringe o acesso de rede à máquina local. Não exponha o motor diretamente à internet. Nunca inclua arquivos `.env`, exportações com contatos ou os dados de `.engine/` em commits.

<a id="honest-limits"></a>
## Limitações conhecidas

- Resultados dependem do Google Maps, das páginas públicas consultadas e da disponibilidade de rede.
- O Google pode limitar requisições ou alterar o formato das páginas.
- Não são garantidos todos os estabelecimentos de uma cidade, nem telefones ou e-mails para todas as empresas.
- A verificação MX verifica domínios, não a existência de cada caixa de entrada.
- O mapa depende dos serviços externos Leaflet/OpenStreetMap para carregar scripts e mapas-base.
- O indicador de intenção comercial é apenas heurístico quando ativado; não representa probabilidade validada de conversão.
- O uso de dados pessoais exige finalidade, base legal, segurança e respeito à legislação aplicável.

<a id="how-it-compares"></a>
## Comparações e orientações

Consulte [comparativo de ferramentas](docs/best-google-maps-scrapers.md), [guia Python](docs/google-maps-scraper-python.md), [coleta de e-mails](docs/google-maps-email-scraper.md) e [uso sem chave de API](docs/google-maps-scraper-no-api-key.md).

<a id="guides-and-recipes"></a>
## Guias por segmento

Veja o índice em [docs/README.md](docs/README.md), incluindo exemplos para barbearias, restaurantes, dentistas e outros segmentos. Os exemplos não representam empresas reais.

<a id="faq"></a>
## Perguntas frequentes

**Preciso pagar uma API do Google?** O motor automatiza a interface web, sem exigir uma chave do Google Maps; isso não elimina eventuais restrições ou custos de infraestrutura.

**Preciso de Docker?** Não. Python e um navegador compatível são suficientes.

**Posso usar no Windows?** Sim. Utilize `py` no lugar de `python3`.

**O painel funciona sem nenhuma coleta?** Sim, mostrando estado vazio e métricas zero.

**Posso usar a versão em outro sistema?** Sim, por meio dos endpoints locais, respeitando autenticação e permissões.

<a id="responsible-use"></a>
## Uso responsável, LGPD e termos

A coleta automatizada pode contrariar os termos do Google. Avalie os termos aplicáveis antes de usar, não faça requisições excessivas e não utilize dados coletados para spam, vigilância, assédio ou finalidades ilegítimas. No Brasil, observe a **Lei Geral de Proteção de Dados (LGPD)**, inclusive finalidade, transparência, base legal, retenção e direitos dos titulares.

<a id="updating"></a>
## Atualizações

Este é um **fork independente**, com mudanças próprias. Não execute atualizações automáticas da origem sem revisar os conflitos e preservar o dashboard. Para reconstruir o Docker após atualizar arquivos, use `docker compose up -d --build`.

<a id="support"></a>
## Apoio e contribuição

Erros e sugestões podem ser registrados nas [issues deste fork](https://github.com/danielsim9es/google-maps-scraper-kit/issues). Veja [CONTRIBUTING.md](CONTRIBUTING.md) e [SECURITY.md](SECURITY.md).

<a id="license"></a>
## Licença e créditos

O projeto de origem é de [Mahanaicoach](https://github.com/Mahanaicoach/google-maps-scraper-kit). Este fork mantém seus avisos e créditos. A licença MIT original permanece em [LICENSE](LICENSE), sem alterações. Consulte [CREDITS.md](CREDITS.md). Os arquivos de patrocinadores existentes pertencem à distribuição original; patrocínio não implica endosso do fork.

---

**Idioma:** português do Brasil (`pt-BR`). Os identificadores técnicos, nomes de flags e formatos de saída permanecem estáveis por compatibilidade.
