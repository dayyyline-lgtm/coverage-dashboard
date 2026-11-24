"""틱톡샵 상품 페이지를 러너에서 헤드리스 크롬으로 열어 화면에 보이는 가격(할인가)을 읽는다 — 일회성 탐침 2.
원문 HTML 은 정가(sale_price)만 준다(Simple $87.10) · 실제 판매가($40.30)는 화면이 따로 부른다(2026-11-24)."""
import json, pathlib, re, asyncio
from playwright.async_api import async_playwright
IDS = open("diag/tts_ids.txt").read().split()
out = pathlib.Path("/tmp/tts"); out.mkdir(exist_ok=True)
async def main():
    log = []
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        c = await b.new_context(locale="en-US", timezone_id="America/New_York", viewport={"width": 1280, "height": 1600},
                                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
        pg = await c.new_page()
        api = []
        pg.on("response", lambda r: api.append(r.url) if ("api" in r.url and "tiktok" in r.url) else None)
        for pid in IDS:
            api.clear()
            try:
                await pg.goto(f"https://shop.tiktok.com/us/pdp/x/{pid}", wait_until="domcontentloaded", timeout=45000)
                await pg.wait_for_timeout(8000)
                txt = await pg.inner_text("body")
                (out / f"{pid}.txt").write_text(txt)
                await pg.screenshot(path=str(out / f"{pid}.png"))
                prices = re.findall(r"\$\s?[\d,]+(?:\.\d{2})?", txt)[:20]
                log.append({"id": pid, "url": pg.url, "prices": prices, "api": api[:25], "n": len(txt)})
            except Exception as e:
                log.append({"id": pid, "err": str(e)[:300]})
        await b.close()
    (out / "log2.json").write_text(json.dumps(log, indent=1))
    print(json.dumps(log, indent=1)[:6000])
asyncio.run(main())
