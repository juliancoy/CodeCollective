import json, time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

GRID = "http://172.24.254.44:4444"
URL = "https://codecollective.us/p/"

opts = Options()
opts.add_argument("--window-size=1366,900")
drv = webdriver.Remote(command_executor=GRID, options=opts)
try:
    drv.set_page_load_timeout(60)
    drv.get(URL)
    time.sleep(5)

    # Inject axe-core from CDN (no CSP blocks it) and run.
    drv.execute_script("""
      var s=document.createElement('script');
      s.src='https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js';
      s.id='axe-cdn'; document.head.appendChild(s);
    """)
    # wait for axe to load
    for _ in range(30):
        if drv.execute_script("return !!window.axe"): break
        time.sleep(0.5)

    has_axe = drv.execute_script("return !!window.axe")
    result = {"axe_loaded": has_axe}

    if has_axe:
        axe = drv.execute_async_script("""
          var cb = arguments[arguments.length-1];
          axe.run(document, {resultTypes:['violations']}).then(function(r){
            cb(r.violations.map(function(v){
              return {id:v.id, impact:v.impact, help:v.help,
                      nodes:v.nodes.length,
                      sample:(v.nodes[0]&&v.nodes[0].target)||[]};
            }));
          }).catch(function(e){ cb([{id:'AXE_ERROR', help:String(e)}]); });
        """)
        result["violations"] = axe

    # Manual structural a11y checks
    result["manual"] = drv.execute_script("""
      function names(el){return el? (el.getAttribute('aria-label')||el.textContent||'').trim():'';}
      var html=document.documentElement;
      var imgs=Array.from(document.querySelectorAll('img'));
      var inputs=Array.from(document.querySelectorAll('input,select,textarea'));
      var btns=Array.from(document.querySelectorAll('button,[role=button],a'));
      return {
        lang: html.getAttribute('lang')||null,
        title: document.title||null,
        h1_count: document.querySelectorAll('h1').length,
        landmarks: {main:document.querySelectorAll('main,[role=main]').length,
                    nav:document.querySelectorAll('nav,[role=navigation]').length},
        img_total: imgs.length,
        img_missing_alt: imgs.filter(function(i){return !i.hasAttribute('alt');}).length,
        input_total: inputs.length,
        input_unlabeled: inputs.filter(function(i){
            var id=i.id; var lbl=id&&document.querySelector('label[for=\"'+id+'\"]');
            return !(i.getAttribute('aria-label')||i.getAttribute('aria-labelledby')||lbl||i.getAttribute('placeholder'));
        }).length,
        controls_no_name: btns.filter(function(b){return !names(b);}).length,
        meta_viewport: !!document.querySelector('meta[name=viewport]'),
        meta_description: !!document.querySelector('meta[name=description]')
      };
    """)

    with open("/Users/natan/Documents/CodeCollective/_audit/a11y.json","w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2)[:4000])
finally:
    drv.quit()
