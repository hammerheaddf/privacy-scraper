import datetime
from time import sleep
import playwright.async_api as pw
from playwright.async_api import expect
from playwright_stealth import stealth_async
from config import settings
from sqlalchemy.engine.result import ScalarResult
import httpx
import os
import hashlib
import datetime as datetime
import metadata as meta
import asyncclick as click
import asyncio
import multiprocessing
from tqdm.asyncio import tqdm
import re
from dateutil.parser import parse
import time

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
termCols = 0
postBar: tqdm
linkBar: tqdm
downloadBar: tqdm
global barFormat
barFormat = '{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}, {rate_fmt}]'

async def fetchLinks(page: pw.Page, jar):
    # https://privacy.com.br/Index?handler=PartialPosts&skip=10&take=20&nomePerfil=Suelenstodulskii&agendado=false
    skip = 0
    take = 40
    global numPosts
    global postBar
    global linkBar
    global linksTotal
    linkBar = tqdm(total=linksTotal,colour='magenta',dynamic_ncols=True,position=1,desc='Mídia...',delay=5,bar_format=barFormat)
    # linkBarD = tqdm(bar_format='{desc}',position=2,desc='Mídia...')
    postBar = tqdm(total=numPosts,colour='yellow',dynamic_ncols=True,position=0,desc='Postagem...',delay=5,bar_format=barFormat)
    # postBarD = tqdm(bar_format='{desc}',position=0,desc='Postagem...')
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
    # postBarD.close()
    postBar.close()
    # linkBarD.close()
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
            global termCols
            if termCols < 80:
                desc = f"P {truncate_middle(imageId,12)}"
            else:
                desc = f"Post  {imageId}"
            postBar.set_description(desc)
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
    
        global linkBar, linkBarD
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
            if termCols < 80:
                desc = f"M {truncate_middle(filename,12)}"
            else:
                desc = f"Mídia {filename}"
            linkBar.set_description(desc)
            linkBar.update()
            mediaCount += 1
            await asyncio.sleep(0)
        
async def downloadLinks(drv, cookiejar):
    profilePath = os.path.join(settings.downloaddir, profile)
    os.makedirs(name=profilePath, exist_ok=True)
    global metadata
    mediaCount = 0
    mediastoDownload = metadata.getMediaDownload()
    medias = asyncio.Queue()

    async with httpx.AsyncClient() as client:
        tasks = []
        for m in mediastoDownload:
            link = m.link
            task = asyncio.ensure_future(
                client.request('HEAD',link,headers=hdr,cookies=cookiejar)
            )
            tasks.append(task)
        responses = await asyncio.gather(*tasks)
        tasks.clear()
        
        async def check(media, response):
            filepath = os.path.join(media.directory, media.filename)
            response_status = False
            if response.status_code == 200:
                response_status = True
                if response.headers.get('content-length'):
                    media.size = int(response.headers.get('content-length'))
            if os.path.exists(filepath):
                if os.path.getsize(filepath) == response.headers.get('content-length'):
                    media.downloaded = True
                else:
                    return media
            else:
                if response_status:
                    return media
                
        mediastoDownload = metadata.getMediaDownload()
        for media in mediastoDownload:
            temp_response = [
                response
                for response in responses
                if response and str(response.url) == media.link
                ]
            if temp_response:
                temp_response = temp_response[0]
                task = check(media, temp_response)
                tasks.append(task)
        results = await asyncio.gather(*tasks)
        metadata.session.commit()
        medialist = [x for x in results if x]
        tasks.clear()

    mediastoDownload = metadata.getMediaDownload()
    global downloadBar
    with tqdm(dynamic_ncols=True,colour='green',bar_format=barFormat,unit='B',unit_scale=True,miniters=1) as downloadBar:
        # downloadBarD = tqdm(bar_format='{desc}',position=0,desc='Baixando...')
        # while True:
        total = 0
        for x in medialist:
            total += int(x.size)
        downloadBar.total = total*1.001
        global savedTotal
        if savedTotal>0 and savedTotal % 200 == 0:
            await drv.reload()
            cookiejar = await refreshCookies(drv)
        await asyncio.gather(*([retrieveLinks(mediastoDownload,medias)] + [requestLink(medias, cookiejar) for _ in range(4)]))
        # global filesTotal
        # filesTotal += 1
        # mediaCount += 1
        # medias.task_done()
        # downloadBarD.close()

async def retrieveLinks(mediastoDownload, medias: asyncio.Queue()):
    for m in mediastoDownload:
        await medias.put(m)
    # return medias

async def requestLink(medias, cookiejar):
    while not medias.empty():
        media = await medias.get()
        global downloadBar
        global termCols
        if termCols < 80:
            desc = truncate_middle(media.filename,12)
        else:
            desc = media.filename
        downloadBar.set_description(f"{desc}")
        downloadBar.update()
        mediainfo = {}
        client = httpx.AsyncClient()
        timeout = httpx.Timeout(10.0, read=60.0)
        async with client.stream('GET',url=media.link,headers=hdr,cookies=cookiejar,timeout=timeout) as req:
            if req.status_code == 413:
                req = await client.stream('GET',url=media.inner_link,headers=hdr,cookies=cookiejar,timeout=timeout)
            if req.status_code == 200:
                saved = 0
                global filesTotal
                if int(req.headers['Content-Length']) < 100000000: #100MB
                    await req.aread()
                    with open(os.path.join(media.directory,media.filename), 'wb') as download:
                        saved = download.write(req.content)
                    filesTotal += saved
                    downloadBar.update(saved)
                else:
                    with open(os.path.join(media.directory,media.filename), 'wb') as download:
                        async for chunk in req.aiter_bytes():
                            f = download.write(chunk)
                            saved += f
                            downloadBar.update(f)
                        filesTotal += f

                if saved > 0:
                    date = parse(req.headers['last-modified'])
                    mtime = time.mktime(date.timetuple())
                    os.utime(os.path.join(media.directory,media.filename),(mtime,mtime))
                    mediainfo['media_id'] = media.media_id
                    mediainfo['size'] = os.path.getsize(os.path.join(media.directory,media.filename))
                    mediainfo['created_at'] = date
                    metadata.markDownloaded(mediainfo)
                    global savedTotal
                    savedTotal += 1
                    # print(f"{media.filename} {saved} bytes salvo.")
            else:
                tqdm.write(f"Download de {media.filename} falhou, HTTP erro {req.status_code}")
            # print(filesTotal)
            medias.task_done()

async def refreshCookies(driver: pw.Page):
    # reconstrói cookie do navegador para Requests
    jar = httpx.Cookies()
    # await driver.reload()
    for c in await driver.context.cookies():
        # print(type(c))
        # print(c['name'])
        jar.set(c['name'], c['value'], path=c['path'], domain=c['domain'])#, secure=c['secure']) #, httpOnly=c['httpOnly'], sameSite=c['sameSite'])
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

def truncate_middle(s, n):
    if len(s) <= n:
        # string is already short-enough
        return s
    # half of the size, minus the 3 .'s
    n_2 = int(n / 2 - 3)
    # whatever's left
    n_1 = int(n - n_2 - 3)
    return '{0}...{1}'.format(s[:n_1], s[-n_2:])


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
    global termCols
    termCols = os.get_terminal_size().columns
    async with pw.async_playwright() as p:
        global profile
        profile = perfil
        browser = await p.chromium.launch(
            args=['--blink-settings=imagesEnabled=false'],
            headless=False
        )
        print("Abrindo página de login...")
        page = await browser.new_page()
        # await page.set_viewport_size({"width": 1024, "height": 768})
        # await stealth_async(page)
        await page.goto('about:blank')
        sleep(5)
        await page.goto(url)
        # user = await page.locator('xpath=//input[@id="txtEmailLight"]')
        # await page.screenshot(path="ss.png")
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

        await browser.close()
        print('Encerrado.')

if __name__ == "__main__":
    asyncio.run(main())
