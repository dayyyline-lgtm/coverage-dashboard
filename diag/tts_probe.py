"""틱톡샵 미국 상품 페이지(shop.tiktok.com/us/pdp)를 러너(미국 IP)에서 받아 원문을 그대로 남긴다 — 실제 판매가(할인가)를 읽을 수 있는지 보는 일회성 탐침.
한국 IP 는 'not_supported_region'·'This Zone is disabled' 로 막힌다(2026-11-24)."""
import sys, time, pathlib, urllib.request, gzip, json
IDS = sys.argv[1:] or open("diag/tts_ids.txt").read().split()
out = pathlib.Path("/tmp/tts"); out.mkdir(exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip"}
log = []
for pid in IDS:
    url = f"https://shop.tiktok.com/us/pdp/x/{pid}"
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30)
        b = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            b = gzip.decompress(b)
        (out / f"{pid}.html").write_bytes(b)
        log.append({"id": pid, "st": r.status, "url": r.url, "n": len(b)})
    except Exception as e:
        log.append({"id": pid, "err": str(e)[:200]})
    time.sleep(3)
(out / "log.json").write_text(json.dumps(log, indent=1))
print(json.dumps(log, indent=1))
