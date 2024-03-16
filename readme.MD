# Privacy Scraper

## Copyright 
Creative Commons

## Como instalar:

1. Instale os requerimentos utilizando

```
pip install -r requirements.txt

```

2. Crie um arquivo na raiz chamado .secrets.yaml com a seguinte arvore:
```
user: "<email do usuario>"
pwd: "<senha>"
```

3. caso necessario, verifique a necessidade de rodar um
```
playwright install
```

4. No arquivo *settings.yaml*, verifique o caminho da pasta downloads.
Coloque o caminho completa da pasta, exemplo:
```
downloaddir: C:\downloads
```


## Como usar:

1. Após tudo configurado, apenas faça
```
python main.py
```

2. Quando aparecer a lista de perfis, aperta o numero do perfil escolhido ou 0 para varrer todos os perfis.

