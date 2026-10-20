import asyncio, os, sys
from PIL import Image
async def main(name):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        b=await pw.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
            args=["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist","--allow-file-access-from-files"])
        pg=await b.new_page(viewport={"width":960,"height":480},device_scale_factor=2)
        err=[]; pg.on("pageerror",lambda e:err.append(str(e))); pg.on("console",lambda m: m.type=="error" and err.append(m.text))
        await pg.goto("file://"+os.path.abspath(name+".html"))
        try: await pg.wait_for_function("window.DONE===true",timeout=120000)
        except Exception: print("timeout",err[:6]); await b.close(); return
        await pg.wait_for_timeout(500)
        await pg.locator("#stage").screenshot(path=name+"_raw.png"); print("errors",err[:5]); await b.close()
    im=Image.open(name+"_raw.png").convert("RGB").resize((1200,600),Image.LANCZOS)
    im.save(name+".jpg",quality=86,optimize=True,progressive=True); print(name, os.path.getsize(name+".jpg"))
asyncio.run(main(sys.argv[1]))
