---
description: Pesquisar estabelecimentos no Google Maps por segmento e cidade, exportando os resultados em CSV ou JSON.
argument-hint: <tipo de empresa> em <cidade, UF> [profundidade]
---

O usuário solicitou uma pesquisa no Google Maps: **$ARGUMENTS**.

Utilize a skill `google-maps-scraper` para executar o fluxo completo:

1. **Verificar o motor:** execute `python3 scripts/engine.py status` na raiz do projeto. O status usa o cabeçalho `X-Engine` para confirmar a instância correta. Caso esteja parado e haja navegador disponível, utilize `python3 scripts/engine.py start`. Se não houver navegador, explique a necessidade de instalar Chrome ou de usar Docker (`docker compose up -d`), conforme [SETUP.md](../../SETUP.md).
2. **Entender a busca:** identifique tipo de empresa, cidade, UF e profundidade opcional (padrão 5). Para pesquisa no Brasil, `--lang pt --country br`.
3. **Executar** `python3 scripts/scrape.py "<tipo> em <Cidade, UF>" --city "<Cidade, UF>" --lang pt --country br --depth <n>`. No Windows, use `py`. Se a ferramenta de execução oferecer modo de tarefa longa, utilize-o; não invente resultados enquanto a coleta está em andamento.
4. **Apresentar os dados reais:** inclua nome (`title`), telefone (`phone`), e-mail (`emails`), site (`website`), categoria (`category`), endereço (`address`), nota (`review_rating`) e avaliações (`review_count`). As redes sociais são adicionais e vêm ativas, salvo quando o usuário pedir `--no-socials`.
5. **Informar o arquivo:** mostre caminho/nome do CSV ou JSON criado, total efetivamente obtido e qualquer limite ou falha ocorrida.

Não invente leads. Evite revelar dados privados ou segredos de configuração. Respeite os termos da fonte e a LGPD. Para pesquisas grandes, avise uma vez sobre limitações temporárias e necessidade de uso responsável.
