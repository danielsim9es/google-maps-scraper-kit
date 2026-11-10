# Como contribuir

Obrigado pelo interesse em melhorar a edição em português brasileiro do Google Maps Scraper Kit.

## Relatórios de problemas

Abra uma [issue](https://github.com/danielsim9es/google-maps-scraper-kit/issues) descrevendo o sistema operacional, versão do Python, comando executado, resultado esperado e erro. Remova dados pessoais, resultados de coletas, senhas e chaves antes de anexar registros.

## Pull Requests

- Mantenha cada PR focada em uma alteração.
- Execute testes offline antes de publicar:
  ```bash
  python3 scripts/test_scrape.py
  python3 engine/test_engine.py
  python3 engine/test_dashboard.py
  python3 engine/test_cdp.py
  ```
- Quando necessário e permitido, valide uma coleta pequena em ambiente local, sem disponibilizar dados coletados no GitHub.
- Preserve compatibilidade com Python 3.9+, Windows, macOS e Linux.
- Não introduza dependências extras no motor padrão sem justificativa e testes.
- Mantenha nomes de campos da API, argumentos CLI e identificadores técnicos existentes.
- Escreva novas mensagens voltadas ao usuário e instruções deste fork em **português do Brasil**.
- Não remova a licença MIT, avisos de terceiros ou créditos ao autor original.

## Cuidados com privacidade

Os arquivos `.env`, `.engine/`, CSV e JSON com empresas ou contatos não devem ser adicionados ao repositório. Avalie a LGPD e a licença/termos das fontes.

## Histórico e patrocínios

O projeto original é de [Mahanaicoach](https://github.com/Mahanaicoach/google-maps-scraper-kit). A caixa de patrocinadores da origem utiliza `assets/sponsors/sponsors.json`. Preserve os créditos e respeite a política de terceiros. Para patrocinar o projeto original, visite [GitHub Sponsors](https://github.com/sponsors/Mahanaicoach).
