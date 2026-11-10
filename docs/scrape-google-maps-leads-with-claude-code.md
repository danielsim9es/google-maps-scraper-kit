# Pesquisa de empresas com Claude Code e outros agentes

O Google Maps Scraper Kit inclui uma skill e comandos para agentes que executam tarefas de prospecção sob supervisão.

## Preparar o ambiente

```bash
git clone https://github.com/danielsim9es/google-maps-scraper-kit.git
cd google-maps-scraper-kit
python3 scripts/engine.py start
python3 scripts/engine.py status
```

As instruções para Claude Code estão em [CLAUDE.md](../CLAUDE.md). A skill é `.claude/skills/google-maps-scraper/SKILL.md`.

## Comandos disponíveis

| Comando | Função |
|---|---|
| `/scrape` | Coleta por segmento e cidade |
| `/scrape-batch` | Várias palavras-chave em um trabalho |
| `/scrape-setup` | Verificar dependências e iniciar o motor |
| `/scrape-jobs` | Consultar tarefas, andamento ou exclusões |

Exemplo de solicitação ao agente:

> Pesquise padarias em Campinas, SP, com idioma português e profundidade 3. Traga somente resultados obtidos de fato, exporte o arquivo CSV e explique as limitações.

O agente deve chamar os scripts disponibilizados pelo projeto, em vez de inventar resultados ou usar consultas incompatíveis com o motor.

## Saídas e painel

Consulte `http://localhost:8080/dashboard` para visualizar resultados e métricas das coletas. Arquivos exportados podem conter telefones e e-mails; não publique esses dados no repositório.

## Cuidados

Grandes volumes podem gerar limitação temporária do acesso pelo Google. Evite requisições excessivas, siga os termos de uso da plataforma e cumpra a LGPD. Não use o sistema para spam, vigilância ou dados de pessoas sem base legal.
