---
description: Iniciar o motor local do Google Maps e verificar se está pronto para uso.
---

Prepare o motor deste kit no computador:

1. Na raiz do projeto, execute `python3 scripts/engine.py status` (Windows: `py scripts/engine.py status`). É necessário Python 3.9+.
2. Se estiver parado, verifique o navegador indicado pelo status. Se não houver navegador compatível, informe que pode ser necessário instalar Chrome ou usar Docker; a inicialização nativa pode baixar o Chrome for Testing na primeira execução. Utilize `docker compose up -d` caso o usuário tenha escolhido Docker.
3. Sem Docker, inicie com `python3 scripts/engine.py start`.
4. Valide novamente o status. A mensagem de sucesso informa a URL, normalmente `http://localhost:8080`.
5. Informe em português as interfaces: coletor em `/`, dashboard em `/dashboard` e documentação em `/api/docs`.
6. Explique uma vez: o motor envia consultas reais ao Google Maps, o acesso automatizado pode contrariar os termos da plataforma, grandes volumes podem provocar limitação temporária do IP e contatos podem ser dados pessoais sujeitos à LGPD.

Em caso de falha, use [SETUP.md](../../SETUP.md) para diagnóstico. Não divulgue `SCRAPER_API_KEY` ou credenciais.
