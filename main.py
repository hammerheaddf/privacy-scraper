
import datetime
from time import sleep
from seleniumwire import webdriver
# from selenium.webdriver.firefox.options import Options
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.relative_locator import locate_with
from selenium.common.exceptions import NoSuchElementException
from config import settings
from sqlalchemy.engine.result import ScalarResult
import requests
import os
import hashlib
import datetime as datetime
import metadata as meta
import click
import asyncio
import multiprocessing
from tqdm import tqdm

url = "https://privacy.com.br/"
base_url = "https://privacy.com.br/profile/"
page_url = "https://privacy.com.br/Index?handler=PartialPosts&skip={0}&take={1}&nomePerfil={2}&agendado=false"
profile = ""
hdr = ""
filesTotal = 0
savedTotal = 0
postsTotal = 0
linksTotal = 0
metadata = ""
postContent = ''
prevImageId = ''
numPosts = 0
postBar: tqdm
linkBar: tqdm

def fetchLinks(drv: webdriver.Chrome, jar):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # busca posts, 30 por vez
    # https://privacy.com.br/Index?handler=PartialPosts&skip=10&take=20&nomePerfil=Suelenstodulskii&agendado=false
    skip = 0
    take = 30
    global numPosts
    global postBar
    global linkBar
    global linksTotal
    linkBar = tqdm(total=linksTotal,colour='magenta',dynamic_ncols=True,position=1,desc='Mídia...',delay=10)
    postBar = tqdm(total=numPosts,colour='yellow',dynamic_ncols=True,position=0,desc='Postagem...',delay=10)
    while True:
        jar = refreshCookies(drv)
        page = drv.get(page_url.format(skip, take, profile))
        links = drv.find_elements(By.XPATH,'//a[contains(@class,"videopostagem")]')
        if len(links) < 1:
            break
        linksTotal += len(links)
        linkBar.total = linksTotal
        # print(f"Buscando postagens... agora em {skip}")
        task = loop.create_task(parseLinks(links, jar, drv))
        loop.run_until_complete(task)
        skip += 30
    postBar.close()
    linkBar.close()
    global metadata
    global postsTotal
    print(f"{postsTotal} postagens com texto e mídia, {metadata.getMediaCount()} mídias encontradas. Baixando {metadata.getMediaDownloadCount()} mídias.")
    
async def parseLinks(links, cookiejar, drv: webdriver.Chrome):
    openDatabase()
    mediaCount = 0
    for l in links:
        href = l.get_attribute('href')
        imageId = l.get_attribute('data-fancybox')
        inner_link = l.find_element(By.TAG_NAME,'img').get_attribute('src')
        # if href != inner_link:
        #     print('break')
        # print(href)
        # print(imageId)
        global prevImageId
        try:
            if prevImageId != imageId: #postContent != postTag.text:
                postBar.set_description(f"Postagem {imageId}")
                postBar.update()
                # print(postTag.text)
                postTag = drv.find_element(locate_with(By.XPATH,'//p[@style="white-space: pre-line;margin-bottom: 0;margin-top: -20px;"]').above(l))
                global postContent
                postContent = postTag.text
                postinfo = {
                    'post_id': imageId,
                    'post_text': postContent,
                }
                metadata.savePost(postinfo)
                global numPosts
                global postsTotal
                postsTotal += 1
        except NoSuchElementException:
            pass
        filename = ''
        if prevImageId != imageId:
            mediaCount = 1
            prevImageId = imageId
        imgHash = hashlib.md5(str(href).encode('utf-8')).hexdigest()
        if "mp4" in href:
            # filename = href.split('/')[-1]
            filename = imageId + '-' + str(mediaCount).rjust(3,'0') + '.mp4'
            media_type = 'video'
        else:
            # filename = imageId + '-' + str(imgHash) + '.jpg'
            filename = imageId + '-' + str(mediaCount).rjust(3,'0') + '.jpg'
            media_type = 'image'
        filepath = os.path.join(settings.downloaddir, profile, media_type)
        os.makedirs(name=filepath, exist_ok=True)
        mediainfo = {
            'media_id': imgHash,
            'post_id': imageId,
            'link': href,
            'inner_link': inner_link,
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
        global linkBar
        linkBar.set_description(f"Mídia {filename}")
        linkBar.update()
        mediaCount += 1
        await asyncio.sleep(0)
        

def downloadLinks(drv, cookiejar):
    profilePath = os.path.join(settings.downloaddir, profile)
    os.makedirs(name=profilePath, exist_ok=True)
    global metadata
    mediaCount = 0
    medias = metadata.getMediaDownload()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    with tqdm(total=metadata.getMediaDownloadCount(),dynamic_ncols=True,colour='green',desc="Baixando") as downloadBar:
        for media in medias:
            task = loop.create_task(requestLink(media, drv, cookiejar))
            loop.run_until_complete(task)
            downloadBar.set_description(f"Baixando {media.filename}")
            downloadBar.update()
            global filesTotal
            filesTotal += 1
            mediaCount += 1

async def requestLink(media, drv, cookiejar):
    global savedTotal
    mediainfo = {}
    if savedTotal % 200 == 0:
        cookiejar = refreshCookies(drv)
    req = requests.get(url=media.link,headers=hdr,cookies=cookiejar,stream=True)
    # mediainfo['size'] = req.headers['content-length']
    # print(req)
    if req.status_code == 413:
        req = requests.get(url=media.inner_link,headers=hdr,cookies=cookiejar,stream=True)
    if req.status_code == 200:
        saved = 0
        with open(os.path.join(media.directory,media.filename), 'wb') as download:
            saved = download.write(req.content)
        if saved > 0:
            mediainfo['media_id'] = media.media_id
            mediainfo['size'] = saved
            metadata.markDownloaded(mediainfo)
            # print(f"{media.filename} {saved} bytes salvo.")
    else:
        tqdm.write(f"Download de {media.filename} falhou, HTTP erro {req.status_code}")
    savedTotal += 1
    # print(filesTotal)
    await asyncio.sleep(0)

def refreshCookies(driver: webdriver.Chrome):
    # reconstrói cookie do Selenium para Requests
    jar = requests.cookies.RequestsCookieJar()
    driver.refresh()
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

def openDatabase():
    profilePath = os.path.join(settings.downloaddir, profile)
    os.makedirs(name=profilePath, exist_ok=True)
    global metadata
    metadata = meta.metadata(profilePath)
    metadata.openDatabase()


@click.command()
@click.argument('perfil')
@click.option(
    '--backlog',
    '-b',
    is_flag=True,
    default=False,
    help='Baixa apenas o "backlog" de mídias novas no DB, sem varrer a página'
    )
def main(perfil, backlog):
    """Baixa toda a mídia de um dado perfil. Aceita um perfil por vez."""
    global profile
    profile = perfil
    opt = Options()
    opt.add_argument("--headless")
    opt.page_load_strategy = 'eager'
    opt.add_argument('--blink-settings=imagesEnabled=false')
    driver = uc.Chrome(options=opt)
    # driver = webdriver.Chrome(options=opt)
    # disable_images(driver)
    print("Abrindo página de login...")
    driver.get(url)
    user = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.XPATH,'//input[@id="txtEmailLight"]'))
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
    global numPosts
    posts = WebDriverWait(driver,90).until(lambda d: d.find_element(By.XPATH,'/html/body/div[6]/div[1]/div/div[5]/div[1]/a'))
    numPosts = posts.text.split(' ')[0].replace('.','')
    if 'k' in numPosts:
        numPosts = numPosts.replace('k','')
        numPosts = f"{numPosts}000" 
    numPosts = int(numPosts)

    ua = driver.execute_script("return navigator.userAgent")
    # ua = driver.last_request.headers['user-agent'] # 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0'
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

    jar = refreshCookies(driver)

    processes = []
    if not backlog:
        print("Buscando postagens com mídia...")
        proc1 = multiprocessing.Process(target=fetchLinks(driver,jar))
        processes.append(proc1)
        proc1.start()
    else:
        print("Atenção: apenas baixando backlog do banco de dados! A página não vai ser varrida agora.")
    # fetchLinks(driver,jar)
    global metadata
    if type(metadata) == str:
        openDatabase()
    if metadata.getMediaDownloadCount() > 0:
        print("Baixando mídia...")
        proc2 = multiprocessing.Process(target=downloadLinks(driver,jar))
        processes.append(proc2)
        proc2.start()
    else:
        print('Sem mídia para baixar.')
    for proc in processes:
        proc.join()

    driver.quit()
    print('Encerrado.')

if __name__ == "__main__":
    asyncio.run(main())
