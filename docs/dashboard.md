# Prospect Intelligence — painel de prospecção

O dashboard foi desenvolvido para o fork [`danielsim9es/google-maps-scraper-kit`](https://github.com/danielsim9es/google-maps-scraper-kit). Ele **aproveita o motor Python original** (Chrome/CDP, `jobs.Store`, SQLite, filas, importação, API e CSVs). Não duplica o serviço nem depende de um banco externo.

## Funcionalidades entregues

- Dashboard responsivo em português, design dark-tech, KPIs de empresas, e-mails, telefones, websites, avaliação média e cobertura.
- Mapa interativo Leaflet + OpenStreetMap, com pinos de empresas que possuem coordenadas reais.
- Gráficos de segmentos e distribuição das avaliações, derivados dos resultados das coletas.
- Lista paginada com busca, filtro por segmento, trabalho, nota, e-mail, telefone e site; ordenação por data, nome, nota ou volume de avaliações.
- Exportação dos registros **filtrados** para CSV seguro para planilhas ou JSON.
- Modal para criar pesquisas reais na API original; autocomplete de cidades do kit.
- Atividades de coleta, estados e progresso, atualização a cada 20 segundos com a página visível.
- Endpoints de relatório e GeoJSON reutilizáveis em integrações.
- Testes unitários offline para os relatórios, deduplicação, validação e segurança de exportação.

> **Sem dados simulados.** Um banco vazio mostra contadores `0`, mapas vazios e orientações para iniciar a coleta. O backend examina, de forma determinística, os arquivos `.engine/data/<job>.csv` que o motor criou.

## Instalação no fork

Copie os arquivos novos deste pacote preservando os caminhos e execute na raiz do repositório:

```bash
python3 scripts/install_dashboard_patch.py
python3 engine/test_dashboard.py
python3 engine/test_engine.py
python3 scripts/engine.py start
```

Acesse `http://localhost:8080/dashboard`, ou a porta configurada em `SCRAPER_PORT`. O painel aparece também como link no coletor original (`/`). Não há instalação de dependências Python adicionais. A biblioteca JavaScript Leaflet é carregada pela CDN (somente no dashboard), e o mapa usa tiles do OpenStreetMap.

O instalador só altera o arquivo existente `engine/serve.py` nas âncoras conhecidas, adiciona o link da interface e atualiza o `README.md`; rejeita layouts incompatíveis em vez de modificar silenciosamente o motor. É idempotente.

No Docker, reconstrua a imagem após aplicar o pacote:

```bash
docker compose up -d --build
```

## Endpoints

Os endpoints abaixo usam as proteções existentes de `Host`, `Origin` e `SCRAPER_API_KEY` (quando definida). Não são serviços públicos. Exemplo:

```bash
curl 'http://localhost:8080/api/v1/dashboard?email=1&min_rating=4&page=1&limit=20'
curl 'http://localhost:8080/api/v1/dashboard/summary?category=Cafe'
curl 'http://localhost:8080/api/v1/dashboard/leads?sort=rating&limit=50'
curl 'http://localhost:8080/api/v1/dashboard/geojson'
curl 'http://localhost:8080/api/v1/dashboard/export?format=csv&email=1' -o prospects.csv
```

Quando `SCRAPER_API_KEY` está definida, adicione `-H 'X-API-Key: SUA_CHAVE'` nas chamadas. A página solicita a chave; guarda-a no `localStorage` do navegador, de modo semelhante à interface do motor original. Não envie a chave em URL, query string, repositório ou capturas públicas.

### Filtros aceitos

| Parâmetro | Valores | Uso |
|---|---|---|
| `q` | até 120 caracteres | busca por empresa, categoria, endereço, e-mail, telefone ou site |
| `category` | até 100 caracteres | categoria contém a expressão fornecida |
| `job` | ID do trabalho | restringe ao trabalho indicado |
| `min_rating` | 0 a 5 | avaliação mínima |
| `email` / `phone` / `website` | `1` | restringe a leads com o campo presente |
| `sort` | `newest`, `name`, `rating`, `reviews` | ordenação |
| `page` | 1 a 100000 | página |
| `limit` | 1 a 100 | registros por página |
| `format` | `csv` ou `json` | exportação |

Todas as pesquisas retornam dados reais. Campos `latitude` e `longitude` nulos não são plotados. Avaliações inválidas não participam da média.

## Regras de deduplicação e limites

O backend lê os trabalhos do mais novo para o mais antigo e deduplica por `place_id`, depois `data_id`, depois `cid`, finalmente pela combinação título/endereço/site. Assim, a ocorrência mais recente prevalece. Cada consulta examina até **50.000 linhas brutas** por segurança de memória, sinalizando `partial=true` se o limite foi alcançado. O mapa exibe até **700 pontos** e informa `limited=true` se mais empresas geolocalizadas corresponderem aos filtros. A exportação sofre o mesmo limite de varredura e os dados paginados não inventam linhas.

O CSV usa prefixo de apóstrofo em campos potencialmente interpretados como fórmulas pelo Excel/LibreOffice. A interface usa `textContent` para dados externos e valida URLs antes de montar links. A camada de consulta é somente leitura; exclusão de tarefas permanece na API original.

## Segurança e uso responsável

O motor original atende em `127.0.0.1` e bloqueia hosts/origens não autorizados. **Não publique essa porta diretamente na internet** nem execute com `--host 0.0.0.0` fora da configuração protegida de Docker. Para uma implantação pública, acrescente autenticação, TLS, autorização por usuário, limites, filas persistentes com isolamento e um banco preparado para múltiplos usuários antes de liberar acesso externo.

O painel não contorna mecanismos do Google nem adiciona proxy, bypass ou coleta invisível: ele aciona a API local já existente. Coletar dados de plataformas pode violar seus termos de serviço. Avalie as bases legais e responsabilidades sob a **LGPD** e respeite as regras e limites do provedor. Use leads apenas para fins legítimos; não trate contatos como consentimento para marketing indiscriminado.

A visualização cartográfica usa recursos de terceiros (CDN `unpkg.com` e tiles `openstreetmap.org`). A página de relatórios e a lista continuam disponíveis sem mapas caso a CDN esteja indisponível. Não faça download massivo de tiles.

## Verificação

```bash
python3 -m py_compile engine/dashboard_api.py scripts/install_dashboard_patch.py
python3 engine/test_dashboard.py
node --check engine/dashboard/app.js  # opcional: requer Node instalado
python3 engine/test_engine.py
```

Teste manual recomendado após uma coleta: criar pesquisa pelo modal, conferir a tarefa em `/api/v1/jobs`, checar que os registros em `/dashboard` correspondem a `/api/v1/jobs/{id}/download?format=json`, filtrar o resultado e comparar a exportação CSV/JSON. Verifique também a proteção com `SCRAPER_API_KEY`, `Host`/`Origin` incorretos e uma coleta sem coordenadas.

## Compatibilidade

Python 3.9+, sem bibliotecas Python adicionais. O pacote não modifica funções do coletor, schema SQLite, diretório de dados ou contratos existentes. Mudanças de estrutura nas versões futuras do upstream podem exigir nova revisão do script de instalação.