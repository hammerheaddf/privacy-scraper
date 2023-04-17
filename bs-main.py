

from urllib import request
from bs4 import BeautifulSoup

url = "https://privacy.com.br/v2/auth/sign-in?ReturnUrl=%2F"
# url = "https://onlyfans.com/"

hdr = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Pragma': 'no-cache',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0'
}
# page = request.urlopen(url)
req = request.Request(url=url,headers=hdr,method='GET')
page = request.urlopen(req)
bs = BeautifulSoup(page, "html.parser")
imgs = bs.find_all("img")
print(imgs) 