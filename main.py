
import datetime
from time import sleep
from seleniumwire import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.relative_locator import locate_with
from selenium.common.exceptions import NoSuchElementException
from config import settings
# from tqdm import tqdm
import requests
import os
import hashlib
import datetime as datetime
import metadata as meta
import click


url = "https://privacy.com.br/v2/auth/sign-in"
base_url = "https://privacy.com.br/profile/"
page_url = "https://privacy.com.br/Index?handler=PartialPosts&skip={0}&take={1}&nomePerfil={2}&agendado=false"
profile = ""
hdr = ""
filesTotal = 0
savedTotal = 0
# pbar: tqdm

def downloadLinks(links, cookiejar, drv: webdriver.Firefox):
    profilePath = os.path.join(settings.downloaddir, profile)
    os.makedirs(name=profilePath, exist_ok=True)
    metadata = meta.metadata(profilePath)
    metadata.openDatabase()
    postContent=''
    for l in links:
        href = l.get_attribute('href')
        imageId = l.get_attribute('data-fancybox')
        # print(href)
        # print(imageId)
        try:
            postTag = drv.find_element(locate_with(By.XPATH,'//p[@style="white-space: pre-line;margin-bottom: 0;margin-top: -20px;"]').above(l))
            if postContent != postTag.text:
                # print(postTag.text)
                postContent = postTag.text
                postinfo = {
                    'post_id': imageId,
                    'post_text': postContent,
                }
                metadata.savePost(postinfo)
        except NoSuchElementException:
            pass
        filename = ''
        imgHash = hashlib.md5(str(href).encode('utf-8')).hexdigest()
        if "mp4" in href:
            filename = href.split('/')[-1]
            media_type = 'video'
        else:
            filename = imageId + '-' + str(imgHash) + '.jpg'
            media_type = 'image'
        filepath = os.path.join(settings.downloaddir, profile, media_type)
        os.makedirs(name=filepath, exist_ok=True)
        mediainfo = {
            'media_id': imgHash,
            'post_id': imageId,
            'link': href,
            'directory': filepath,
            'filename': filename,
            'size': 0,
            'media_type': media_type,
            'downloaded': False,
            'created_at': datetime.datetime.now()
        }
        if not metadata.checkSaved(mediainfo):
            metadata.saveLinks(mediainfo)
        # print(filename)
        # global pbar
        # pbar.set_description("Baixando %s" % (filename))
        if metadata.checkDownloaded(mediainfo) == False:
            req = requests.get(url=href,headers=hdr,cookies=cookiejar)
            # mediainfo['size'] = req.headers['content-length']
            # print(req)
            if req.status_code == 200:
                saved = 0
                with open(os.path.join(filepath,filename), 'wb') as download:
                    saved = download.write(req.content)
                if saved > 0:
                    mediainfo['size'] = saved
                    metadata.markDownloaded(mediainfo)
                    print(f"{filename} {saved} bytes salvo.")
            else:
                print(f"Download de {filename} falhou, HTTP erro {req.status_code}")
            global savedTotal
            savedTotal += 1
            # print(filesTotal)
        else:
            print(f"{filename} já salvo, pulando...")
        global filesTotal
        filesTotal += 1

def refreshCookies(driver):
    # reconstruct Selenium cookie for Requests
    jar = requests.cookies.RequestsCookieJar()
    for c in driver.get_cookies():
        # print(type(c))
        # print(c['name'])
        jar.set(c['name'], c['value'], path=c['path'], domain=c['domain'], secure=c['secure']) #, httpOnly=c['httpOnly'], sameSite=c['sameSite'])
    return jar

#DISABLE IMAGES ON FIREFOX
def disable_images(driver):
    driver.get("about:config")
    warningButton = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.ID,"warningButton"))
    warningButton.click()
    searchArea = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.ID,"about-config-search"))
    searchArea.send_keys("permissions.default.image")
    editButton = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.XPATH,"/html/body/table/tr[1]/td[2]/button"))
    editButton.click()
    editArea = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.XPATH,"/html/body/table/tr[1]/td[1]/form/input"))
    editArea.send_keys("2")
    saveButton = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.XPATH,"/html/body/table/tr[1]/td[2]/button"))
    saveButton.click()

@click.command()
@click.argument('perfil')
def main(perfil):
    """Baixa toda a mídia de um dado perfil. Aceita um perfil por vez."""
    global profile
    profile = perfil
    opt = Options()
    opt.add_argument("--headless")
    opt.page_load_strategy = 'eager'
    driver = webdriver.Firefox(options=opt)
    disable_images(driver)
    print("Abrindo página de login...")
    driver.get(url)
    user = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.XPATH,'//input[@id="txtEmailLight"]'))
    # print(user)
    user.send_keys(settings.user)
    sleep(2)
    pwd = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.XPATH,'//input[@id="txtPasswordLight"]'))
    pwd.send_keys(settings.pwd)
    sleep(2)
    btn = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.XPATH,'/html/body/app-root/template-auth/main/div/div/div[2]/div[2]/sign-in/auth-form-sign-in/form/btn-light-icon'))
    btn.click()
    # procura avatar do usuário
    print("Aguardando autenticação...")
    WebDriverWait(driver,90).until(lambda d: d.find_element(By.XPATH,'/html/body/div[5]/div/div[2]/div[2]/div[4]/div[1]'))
    driver.get(base_url + profile)
    #procura aba (link) de postagens
    print(f"Procurando página de postagens do perfil {profile}...")
    WebDriverWait(driver,90).until(lambda d: d.find_element(By.XPATH,'/html/body/div[6]/div[1]/div/div[5]/div[1]/a'))

    ua = driver.last_request.headers['user-agent'] # 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0'
    global hdr
    hdr = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'cross-site',
        'User-Agent': str(ua),
        'origin': 'https://privacy.com.br',
        'Referer': 'https://privacy.com.br'
    }

    # reconstruct Selenium cookie for Requests
    jar = refreshCookies(driver)

    # 1st block has 10 posts
    print("Buscando links...")
    links = driver.find_elements(By.XPATH,'//a[contains(@class,"videopostagem")]')
    # print(links)
    # global pbar
    # pbar = tqdm(links,dynamic_ncols=True)
    downloadLinks(links, jar, driver)

    # fetch more posts, 30 at a time
    # https://privacy.com.br/Index?handler=PartialPosts&skip=10&take=20&nomePerfil=Suelenstodulskii&agendado=false
    skip = 10
    take = 30
    while True:
        jar = refreshCookies(driver)
        page = driver.get(page_url.format(skip, take, profile))
        links = driver.find_elements(By.XPATH,'//a[contains(@class,"videopostagem")]')
        if len(links) < 1:
            break
        print(f"Buscando mais links... agora em {skip}")
        # pbar.update(filesTotal + len(links))
        downloadLinks(links, jar, driver)
        skip += 30
    print(f"{savedTotal} novos arquivos salvos, {filesTotal} encontrados no total")
    print("Encerrado.")

    driver.quit()
    # pbar.close()

if __name__ == "__main__":
    main()
