import json, time, sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

GRID = "http://172.24.254.44:4444"
URL = sys.argv[1] if len(sys.argv) > 1 else "https://codecollective.us/p/"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/Users/natan/Documents/CodeCollective/_audit/home"

opts = Options()
opts.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})
opts.add_argument("--window-size=1366,900")

drv = webdriver.Remote(command_executor=GRID, options=opts)

# Selenium 4.36 removed the get_log binding; register the Grid log endpoint.
drv.command_executor._commands["seGetLog"] = ("POST", "/session/$sessionId/se/log")
def get_log(t):
    try:
        return drv.execute("seGetLog", {"type": t}).get("value", []) or []
    except Exception as ex:
        return [{"level": "ERR", "message": "log unavailable: %s" % ex}]

try:
    drv.set_page_load_timeout(60)
    drv.get(URL)
    time.sleep(6)  # let SPA hydrate + fire API calls

    info = {
        "requested": URL,
        "final_url": drv.current_url,
        "title": drv.title,
        "source_len": len(drv.page_source),
    }

    # screenshot
    drv.save_screenshot(OUT + ".png")

    # save rendered DOM
    with open(OUT + ".html", "w") as f:
        f.write(drv.page_source)

    # links + buttons + nav
    links = drv.execute_script(
        "return Array.from(document.querySelectorAll('a[href]')).map(a=>a.getAttribute('href'))"
    )
    info["links"] = sorted(set(links))[:200]

    # visible text snapshot
    body = drv.execute_script("return document.body ? document.body.innerText : ''")
    info["body_text_head"] = body[:1500]

    # console logs
    console = get_log("browser")
    info["console"] = [{"level": e["level"], "msg": e["message"][:500]} for e in console]

    # network from performance log
    perf = get_log("performance")
    reqs = []
    for e in perf:
        try:
            m = json.loads(e["message"])["message"]
        except Exception:
            continue
        if m.get("method") == "Network.requestWillBeSent":
            r = m["params"]["request"]
            reqs.append({"method": r.get("method"), "url": r.get("url")})
        elif m.get("method") == "Network.responseReceived":
            resp = m["params"]["response"]
            reqs.append({"status": resp.get("status"), "url": resp.get("url"),
                         "mime": resp.get("mimeType")})
    info["network"] = reqs

    with open(OUT + ".json", "w") as f:
        json.dump(info, f, indent=2)

    print(json.dumps({k: v for k, v in info.items()
                      if k in ("requested", "final_url", "title", "source_len")}, indent=2))
    print("LINKS:", json.dumps(info["links"], indent=2)[:2000])
    print("CONSOLE_COUNT:", len(info["console"]))
    print("NETWORK_COUNT:", len(info["network"]))
finally:
    drv.quit()
