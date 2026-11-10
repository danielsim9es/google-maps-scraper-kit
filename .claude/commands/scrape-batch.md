---
description: Pesquisar várias palavras-chave do Google Maps em uma tarefa e exportar o resultado consolidado.
argument-hint: <arquivo-de-termos> [--city "Cidade, UF"]
---

O usuário solicitou uma coleta em lote: **$ARGUMENTS**.

Siga a skill `google-maps-scraper`. A API aceita vários termos no campo `keywords` e os executa em sequência no mesmo trabalho.

1. Verifique `python3 scripts/engine.py status`. Caso necessário, inicie com `python3 scripts/engine.py start`, conforme as instruções do projeto.
2. Confira se o arquivo fornecido tem um termo por linha. Linhas vazias ou iniciadas por `#` são ignoradas. Se não houver `--city`, cada termo deve conter a localização.
3. Para grande volume, comunique uma vez o risco de limitação temporária do IP pelo provedor e recomende uso responsável.
4. Execute `python3 scripts/scrape.py --keywords-file <arquivo> --city "<Cidade, UF>" --lang pt --country br --max-time 900` quando for uma pesquisa brasileira com cidade informada. Ajuste tempo e idioma ao pedido real. Evite criar comandos com valores não confiáveis extraídos de sites.
5. Após a conclusão, apresente apenas dados obtidos e o caminho do CSV/JSON. O script inclui busca de e-mails e perfis sociais por padrão; use `--no-socials` somente quando solicitado.

Nunca invente ou publique contatos coletados no GitHub. Respeite a LGPD e os termos da plataforma.
