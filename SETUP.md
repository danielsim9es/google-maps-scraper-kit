# Instalação e configuração — Google Maps Scraper Kit

Guia em português do Brasil para instalar, executar e solucionar problemas do motor e do painel Prospect Intelligence.

## 0. Requisitos

| Ferramenta | Necessidade |
|---|---|
| Python 3.9 ou superior | Executar o motor, testes e scripts |
| Chrome, Chromium, Edge ou Brave | Navegador automatizado do motor |
| Git | Clonar o repositório e acompanhar alterações |
| Docker Desktop (opcional) | Executar o motor em contêiner |
| Playwright (opcional) | Renderizar sites que exigem JavaScript |

No Windows, marque a opção para adicionar o Python ao PATH e utilize `py` quando indicado. Para executar `.sh`, use Git Bash ou WSL2. No Linux, prefira um Chromium que aceite automação (algumas instalações Snap apresentam restrições).

Se não encontrar um navegador, a inicialização pode baixar o Chrome for Testing para `.engine/`, verificando a integridade SHA-256. Trata-se de um download maior que a instalação do próprio projeto.

## 1. Obter o fork

```bash
git clone https://github.com/danielsim9es/google-maps-scraper-kit.git
cd google-maps-scraper-kit
python3 --version
```

No Windows:
```powershell
py --version
```

Opcionalmente, copie as configurações:

```bash
cp .env.example .env
```

Edite `.env` sem incluir senhas ou chaves nos commits. Variáveis mais relevantes:

| Variável | Padrão / finalidade |
|---|---|
| `SCRAPER_PORT` | `8080` — porta da API |
| `SCRAPER_API_KEY` | Vazia em uso local; ativa autenticação `X-API-Key` quando preenchida |
| `SCRAPER_HEADLESS` | Modo sem janela por padrão; `0` abre janela quando suportado |
| `SCRAPER_BASE_URL` | URL de um motor acessado pelo cliente Python |
| `SCRAPER_NO_UPDATE_CHECK` | `1` evita a consulta de aviso de atualização |

## 2. Iniciar o motor

### Sem Docker

```bash
python3 scripts/engine.py start
python3 scripts/engine.py status
```

Para reiniciar ou interromper:

```bash
python3 scripts/engine.py restart
python3 scripts/engine.py stop
```

O motor funciona apenas quando iniciado. Sua tarefa em execução pode ser retomada depois de reinício, seguindo as restrições do sistema de tarefas. O processo deve possuir acesso a um navegador suportado.

### Com Docker

```bash
docker compose up -d --build
docker compose ps
```

A imagem inclui Chromium. A API do contêiner é exposta somente no `127.0.0.1` da máquina hospedeira. Evite iniciar ao mesmo tempo a versão nativa na mesma porta.

### Acessos

- **Painel em português:** http://localhost:8080/dashboard
- **Coletor em português:** http://localhost:8080/
- **Documentação:** http://localhost:8080/api/docs
- **OpenAPI:** http://localhost:8080/api/openapi.json

Altere `8080` nos endereços se configurar outra porta.

## 3. Primeira coleta em português

Pelo coletor visual, escolha um tipo de empresa e uma cidade da lista. Em uma nova pesquisa, selecione idioma `pt` e país `br`, ajuste profundidade, e-mail e redes sociais, e inicie a tarefa.

Pelo terminal:

```bash
python3 scripts/scrape.py "restaurantes em São Paulo" --city "São Paulo, SP, Brasil" --lang pt --country br --depth 3
```

Com coordenadas:

```bash
python3 scripts/scrape.py "cafeterias em São Paulo" -23.5505 -46.6333 --lang pt --country br --depth 2
```

O CSV é salvo com nome automático, a menos que `--out` seja informado.

### Mais de uma cidade

```bash
python3 scripts/scrape.py "academias" --city "Campinas, SP" --city "Santos, SP" --lang pt --country br
```

### Aumentar a cobertura geográfica

```bash
python3 scripts/scrape.py "padarias em Curitiba" --city "Curitiba, PR" --lang pt --grid 3
```

`--grid N` subdivide a região em até `N x N` quadrículas, com deduplicação. `--deep-scan` divide novamente quadrículas em que haja muitos resultados, mas pode ser muito mais lento. Não equivale a uma lista completa garantida.

### E-mails, telefones, sites e filtros

Os e-mails e links sociais são buscados no site da empresa, quando disponíveis; não são dados garantidos pelo Google Maps.

```bash
# Busca mais rápida, sem visitar sites para e-mails nem redes
python3 scripts/scrape.py "barbearias em Santos" --city "Santos, SP" --lang pt --no-email --no-socials

# Buscar empresas sem site
python3 scripts/scrape.py "salões em Campinas" --city "Campinas, SP" --lang pt --no-website

# Coletar só negócios com telefone e avaliação mínima
python3 scripts/scrape.py "clínicas em São Paulo" --city "São Paulo, SP" --lang pt --has-phone --min-rating 4.0
```

`--verify-emails` verifica registros MX do domínio. Isso **não comprova** que determinada caixa postal existe.

### Renderização opcional dos sites

Alguns sites exigem JavaScript. É possível instalar o Playwright e habilitar a renderização de páginas:

```bash
python3 -m pip install -r requirements-browser.txt
python3 -m playwright install chromium
python3 scripts/scrape.py "clínicas em Campinas" --city "Campinas, SP" --lang pt --browser-sites
```

Essas dependências são opcionais e aumentam o consumo de recursos.

### Avaliações e exportação

```bash
python3 scripts/scrape.py "hotéis em Santos" --city "Santos, SP" --lang pt --reviews 3 --max-time 1200 --out hoteis.json
python3 scripts/scrape.py "hotéis em Santos" --city "Santos, SP" --lang pt --full --out hoteis.csv
```

Os campos técnicos no JSON/CSV continuam em inglês por compatibilidade com a API e com scripts externos.

## 4. Prospect Intelligence

Abra http://localhost:8080/dashboard. O painel:

1. Consulta as coletas guardadas em SQLite e seus arquivos CSV.
2. Atualiza indicadores, atividades, gráficos e mapa a partir de resultados reais.
3. Permite selecionar uma coleta, aplicar filtros e exportar registros.
4. Oferece um formulário de pesquisa conectado ao backend local.

Se não houver coletas, o painel estará vazio e mostrará KPIs zerados.

O mapa utiliza Leaflet/OSM pela internet. Se os tiles estiverem indisponíveis, a lista e os indicadores continuarão utilizáveis. Veja [docs/dashboard.md](docs/dashboard.md).

## 5. Utilização com agentes

As instruções estão no arquivo [CLAUDE.md](CLAUDE.md), nos comandos `.claude/commands/` e na skill `.claude/skills/google-maps-scraper/SKILL.md`. Os comandos são `/scrape`, `/scrape-batch`, `/scrape-setup` e `/scrape-jobs`. Podem ser chamados a partir de um agente que ofereça suporte a esses comandos.

Não permita que um agente fabrique resultados, divulgue tokens ou ignore limites legais e operacionais.

## 6. Problemas comuns

### A porta 8080 já está em uso

Edite `SCRAPER_PORT=8081` em `.env` e reinicie o motor. Acesse http://localhost:8081/dashboard.

### Não encontro o navegador

Instale Chrome/Chromium compatível ou utilize Docker. Em sistemas com políticas de segurança restritivas, consulte a documentação do navegador e não desative proteções sem avaliar os riscos.

### O motor não inicia

```bash
python3 scripts/engine.py status
python3 scripts/engine.py restart
```

Confira o log em `.engine/engine.log` e permissões da pasta `.engine/`. O processo pode falhar por falta de memória, navegador indisponível ou porta ocupada.

### A coleta está incompleta

O Google Maps limita a quantidade e a frequência de resultados. Reduza profundidade e número de termos, espere antes de repetir e confira se a cidade foi geocodificada corretamente. Repetir pesquisas intensivas pode resultar em limitação temporária do IP.

### Erro 401 / chave obrigatória

Quando `SCRAPER_API_KEY` está definida, os endpoints protegidos exigem a mesma chave no cabeçalho `X-API-Key`. O painel solicita a chave na própria interface local.

### Erro 403 / origem recusada

O motor protege contra requisições feitas por páginas externas. Acesse diretamente o endereço local do próprio motor; não abra o painel em outra origem sem um desenho de segurança apropriado.

### Erro 421 / Host inválido

O servidor foi projetado para responder ao `localhost`. Não remova a proteção de Host nem publique o serviço bruto em um domínio da internet.

### Docker atualizado, mas painel antigo

```bash
docker compose down
docker compose up -d --build
```

### Arquivos de saída não aparecem

Confira `--out`, a pasta atual e a situação da coleta. O CSV pode estar vazio caso nenhum resultado tenha sido obtido; isso não representa erro de exportação necessariamente.

### Quero usar dois forks simultaneamente

Configure `SCRAPER_PORT` diferente em cada cópia. Com Docker, utilize também nomes de projeto Compose diferentes para evitar concorrência de contêineres.

## 7. Testes e manutenção

```bash
python3 engine/test_dashboard.py
python3 engine/test_engine.py
python3 scripts/test_scrape.py
```

Não execute coletas de produção como parte dos testes offline. Para testes reais, leia primeiro as restrições de uso e execute consultas pequenas e responsáveis.

## 8. Segurança, direitos e atribuição

Os resultados podem conter dados pessoais; proteja-os, estabeleça uma base legal, controle retenção e não divulgue contatos. O acesso automatizado pode contrariar os termos de uso da plataforma. Consulte [SECURITY.md](SECURITY.md) e [README.md](README.md).

Licença MIT e autoria original preservadas. Código e contratos técnicos não são traduzidos quando isso quebraria compatibilidade.
