import datetime
from time import sleep
import playwright.async_api as pw
from playwright.async_api import expect
from config import settings
from sqlalchemy.engine.result import ScalarResult
import requests
import os
import hashlib
import datetime as datetime
import metadata as meta
import asyncclick as click
import asyncio
import multiprocessing
from tqdm.asyncio import tqdm
import re

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

async def fetchLinks(page: pw.Page, jar):
    # https://privacy.com.br/Index?handler=PartialPosts&skip=10&take=20&nomePerfil=Suelenstodulskii&agendado=false
    skip = 0
    take = 40
    global numPosts
    global postBar
    global linkBar
    global linksTotal
    linkBar = tqdm(total=linksTotal,colour='magenta',dynamic_ncols=True,position=1,desc='Mídia...',delay=10)
    postBar = tqdm(total=numPosts,colour='yellow',dynamic_ncols=True,position=0,desc='Postagem...',delay=10)
    while True:
        await page.goto(page_url.format(skip, take, profile))
        jar = await refreshCookies(page)
        divs = await page.locator('div.card.is-post.my-n2').all()
        links = await page.locator('xpath=//a[contains(@class,"videopostagem")]').all()
        if len(divs) < 1:
            break
        linksTotal += len(links)
        linkBar.total = linksTotal
        await parseLinks(divs, page)
        skip += take
    postBar.close()
    linkBar.close()
    global metadata
    global postsTotal
    print(f"{postsTotal} postagens com texto e mídia, {metadata.getMediaCount()} mídias encontradas. Baixando {metadata.getMediaDownloadCount()} mídias.")
    
async def parseLinks(divs: list[pw.Locator], page: pw.Page):
    openDatabase()
    mediaCount = 0
    for d in divs:
        links = await d.locator('xpath=//a[contains(@class,"videopostagem")]').all()
        postTag = d.get_by_role('paragraph')
        # imageId = await d.get_by_role('link').nth(-1).get_attribute('data-fancybox')
        id_div = await d.locator('css=div.post-view-full').get_attribute('id')
        imageId = id_div.replace('Postagem','')
        global prevImageId
        if prevImageId != imageId: #postContent != postTag.text:
            postBar.set_description(f"Postagem {imageId}")
            postBar.update()
            global postContent
            try:
                await expect(postTag).to_have_count(count=1,timeout=2)
                postContent = await postTag.text_content()
                postContent = postContent.strip()
                postinfo = {
                    'post_id': imageId,
                    'post_text': postContent,
                }
                metadata.savePost(postinfo)
                global numPosts
                global postsTotal
                postsTotal += 1
            except AssertionError:
                pass
    
        global linkBar
        await asyncio.sleep(0)
        for l in links:
            href = await l.get_attribute('href')
            inner_link = await l.get_by_alt_text('').get_attribute('src')
            filename = ''
            if prevImageId != imageId:
                mediaCount = 1
                prevImageId = imageId
            imgHash = hashlib.md5(str(href).encode('utf-8')).hexdigest()
            if "mp4" in href:
                filename = imageId + '-' + str(mediaCount).rjust(3,'0') + '.mp4'
                media_type = 'video'
            else:
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
            linkBar.set_description(f"Mídia {filename}")
            linkBar.update()
            mediaCount += 1
            await asyncio.sleep(0)
        

async def downloadLinks(drv, cookiejar):
    profilePath = os.path.join(settings.downloaddir, profile)
    os.makedirs(name=profilePath, exist_ok=True)
    global metadata
    mediaCount = 0
    medias = metadata.getMediaDownload()
    with tqdm(total=metadata.getMediaDownloadCount(),dynamic_ncols=True,colour='green',desc="Baixando") as downloadBar:
        for media in medias:
            await requestLink(media, drv, cookiejar)
            downloadBar.set_description(f"Baixando {media.filename}")
            downloadBar.update()
            global filesTotal
            filesTotal += 1
            mediaCount += 1

async def requestLink(media, drv, cookiejar):
    global savedTotal
    mediainfo = {}
    if savedTotal % 200 == 0:
        await drv.reload()
        cookiejar = await refreshCookies(drv)
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

async def refreshCookies(driver: pw.Page):
    # reconstrói cookie do navegador para Requests
    jar = requests.cookies.RequestsCookieJar()
    # await driver.reload()
    for c in await driver.context.cookies():
        # print(type(c))
        # print(c['name'])
        jar.set(c['name'], c['value'], path=c['path'], domain=c['domain'], secure=c['secure']) #, httpOnly=c['httpOnly'], sameSite=c['sameSite'])
    return jar

#DISABLE IMAGES ON FIREFOX
# def disable_images(driver):
#     driver.get("about:config")
#     warningButton = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.ID,"warningButton"))
#     warningButton.click()
#     searchArea = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.ID,"about-config-search"))
#     searchArea.send_keys("permissions.default.image")
#     editButton = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.XPATH,"/html/body/table/tr[1]/td[2]/button"))
#     editButton.click()
#     editArea = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.XPATH,"/html/body/table/tr[1]/td[1]/form/input"))
#     editArea.send_keys("2")
#     saveButton = WebDriverWait(driver, timeout=30).until(lambda d: d.find_element(By.XPATH,"/html/body/table/tr[1]/td[2]/button"))
#     saveButton.click()

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
async def main(perfil, backlog):
    """Baixa toda a mídia de um dado perfil. Aceita um perfil por vez."""
    async with pw.async_playwright() as p:
        global profile
        profile = perfil
        browser = await p.chromium.launch(
            args=['--blink-settings=imagesEnabled=false'],
            headless=False
        )
        print("Abrindo página de login...")
        page = await browser.new_page()
        await page.goto(url)
        # user = await page.locator('xpath=//input[@id="txtEmailLight"]')
        user = page.get_by_placeholder('E-mail')
        await expect(user).to_be_editable()
        await user.type(settings.user)
        sleep(1)
        # pwd = await page.locator('xpath=//input[@id="txtPasswordLight"]')
        pwd = page.get_by_placeholder('Senha')
        await expect(pwd).to_be_editable()
        await pwd.type(settings.pwd)
        sleep(1)
        btn = page.get_by_role('button', name=re.compile('entrar',re.IGNORECASE))
        await btn.click()
        # procura avatar do usuário
        print("Aguardando autenticação...")
        await expect(page.get_by_placeholder('Pesquise aqui...')).to_be_visible(timeout=90000)
        await page.goto(base_url + profile)
        #procura aba (link) de postagens
        print(f"Procurando página de postagens do perfil {profile}...")
        global numPosts
        posts = await page.locator('xpath=/html/body/div[6]/div[1]/div/div[5]/div[1]/a').text_content()
        numPosts = posts.strip().split(' ')[0].replace('.','')
        if 'k' in numPosts:
            numPosts = numPosts.replace('k','')
            numPosts = f"{numPosts}000" 
        numPosts = int(numPosts)

        js = await page.evaluate_handle('navigator')
        ua = await js.evaluate('navigator.userAgent')
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

        jar = await refreshCookies(page)

        processes = []
        if not backlog:
            print("Buscando postagens com mídia...")
            proc1 = multiprocessing.Process(target=await fetchLinks(page,jar))
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
            proc2 = multiprocessing.Process(target=await downloadLinks(page,jar))
            processes.append(proc2)
            proc2.start()
        else:
            print('Sem mídia para baixar.')
        for proc in processes:
            proc.join()

        await page.close()
        print('Encerrado.')

if __name__ == "__main__":
    asyncio.run(main())
