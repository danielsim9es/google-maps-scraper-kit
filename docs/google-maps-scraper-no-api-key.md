# Google Maps Scraper Kit sem chave de API do Google

O motor automatiza um navegador para consultar a interface pública do Google Maps. Por isso, a execução básica **não exige uma chave da API oficial do Google Maps** nem uma conta em serviço de scraping por assinatura.

Isso **não significa acesso ilimitado ou autorizado pelo Google**: o site pode restringir volume, alterar seu comportamento e impor regras próprias de uso.

## Começando

```bash
git clone https://github.com/danielsim9es/google-maps-scraper-kit.git
cd google-maps-scraper-kit
python3 scripts/engine.py start
python3 scripts/scrape.py "salões de beleza em Santos" --city "Santos, SP" --lang pt --country br
```

O resultado final é escrito em CSV por padrão. É possível abrir a interface no endereço `http://localhost:8080/` e o painel de análise em `http://localhost:8080/dashboard`.

## Qual é o custo?

Não há cobrança do kit por consulta, mas seu uso envolve recursos da máquina, conexão com a internet e eventualmente proxies, hospedagem ou serviços opcionais. O navegador pode usar CPU, memória e espaço em disco.

## Limitações e responsabilidade

- O Google pode limitar ou interromper o acesso automatizado.
- Os resultados podem não incluir todos os estabelecimentos de uma região.
- A busca de e-mails e redes sociais depende dos sites das empresas.
- A inexistência de uma chave não substitui os termos da plataforma nem a LGPD.

Para uma solução contratualmente licenciada ou que exija disponibilidade formal, compare com APIs oficiais e provedores autorizados. Consulte [comparativo](best-google-maps-scrapers.md) e [instalação](../SETUP.md).
