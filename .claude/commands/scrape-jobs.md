---
description: Consultar ou excluir coletas do motor local do Google Maps.
argument-hint: "[list | delete <id-da-coleta>]"
---

Gerencie as coletas existentes. Solicitação: **$ARGUMENTS** (padrão: `list` quando vazio).

- **Listar:** execute `python3 scripts/engine.py jobs` (Windows: `py scripts/engine.py jobs`). Apresente ID, situação, data e nome em tabela, sem inventar campos.
- **Excluir:** quando o usuário pedir explicitamente, execute `python3 scripts/engine.py delete <id-da-coleta>`. Isso remove a tarefa e os respectivos resultados. Informe a confirmação do próprio script.
- **Exportar resultados:** no endereço exibido por `python3 scripts/engine.py status`, a interface tem botões de CSV e JSON para cada coleta. O script `scripts/scrape.py` também grava seus arquivos.

Se o motor estiver indisponível, siga `/scrape-setup`. Caso o projeto não contenha `scripts/`, oriente a instalação do kit completo. Não exponha credenciais nem resultados pessoais em logs públicos.
