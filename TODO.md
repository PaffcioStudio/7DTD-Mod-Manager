tu masz url do miniaturki dla modpacka https://i.ytimg.com/vi/3tRd7tNzTXk/maxresdefault.jpg

tutaj url do bezpośredniego pobrania: https://ul.subquake.com/dl?v=mirror który rozpoczyna pobieranie w przeglądarce https://uc30b559325f6754990d0ee60d99.dl.dropboxusercontent.com/cd/0/get/DJUHyCW0QnCVKvGRu6tNJiUR9T6Ilhj-D63rVxzUMweuWZy0jnlLIaK3Ypy_8QFvJo9hij1SntH2oDc-0uAQo0DKpDpDJ6iX-6bu5WS0tSFKmES1M1fM8E67mc9sBYxkUvDTyNCiYiUTglOfCgl8vUc-/file?dl=1#



plik akurat z tego pobrania nazywa się UndeadLegacy_2.7.40.zip

na samej ich stronie jest https://ul.subquake.com/download wersja 2026.09.28 - 2.7.40 czyli 2.7.40 co by musiało być wpisane do manifestu a samo obadanie w devtools wygląda tak:



nagłówek żadania:

GET /scl/fi/8e3j59xgi9d5wb7t66zl6/UndeadLegacy_2.7.40.zip?rlkey=71ncnbtqexxa4ckrjr9rxy3cn&st=9r66770o&dl=1 HTTP/2
Host: www.dropbox.com
User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:156.0) Gecko/20100101 Firefox/156.0
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: pl
Accept-Encoding: gzip, deflate, br, zstd
Referer: https://ul.subquake.com/
Sec-GPC: 1
Connection: keep-alive
Cookie: gvc=MTgwMDMzMDUyNjUzNTA3Nzg2NDEzMjIzODE2MzgwNTgzMDYzNTY2; t=f829qPinr03yd1q_g96SJ3mq; __Host-js_csrf=f829qPinr03yd1q_g96SJ3mq; locale=pl
Upgrade-Insecure-Requests: 1
Sec-Fetch-Dest: document
Sec-Fetch-Mode: navigate
Sec-Fetch-Site: cross-site
Sec-Fetch-User: ?1
Priority: u=0, i



nagłówek odpowiedzi:

HTTP/2 302 
content-security-policy: base-uri 'self'; child-src https://www.dropbox.com/static/serviceworker/ blob:; connect-src https://* ws://127.0.0.1:*/ws blob: wss://dsimports.dropbox.com/; default-src https://www.dropbox.com/playlist/ https://www.dropbox.com/v/s/playlist/ https://*.dropboxusercontent.com/p/hls_master_playlist/ https://*.dropboxusercontent.com/p/hls_playlist/; font-src 'self' data: https://*; form-action https://*.purple.officeapps.live-int.com https://officeapps-df.live.com https://*.officeapps-df.live.com https://officeapps.live.com https://*.officeapps.live.com 'self' https://www.dropbox.com/ https://dl-web.dropbox.com/ https://photos.dropbox.com/ https://paper.dropbox.com/ https://showcase.dropbox.com/ https://www.hellofax.com/ https://app.hellofax.com/ https://www.hellosign.com/ https://app.hellosign.com/ https://docsend.com/ https://www.docsend.com/ https://help.dropbox.com/ https://navi.dropbox.jp/ https://a.sprig.com/ https://selfguidedlearning.dropboxbusiness.com/ https://instructorledlearning.dropboxbusiness.com/ https://sales.dropboxbusiness.com/ https://accounts.google.com/ https://api.login.yahoo.com/ https://login.yahoo.com/ https://experience.dropbox.com/ https://pal-test.adyen.com https://2e83413d8036243b-Dropbox-pal-live.adyenpayments.com/ https://onedrive.live.com/picker https://*.sharepoint.com/; frame-ancestors 'self' https://*.dropbox.com; frame-src https://* dbapi-6: dbapi-7: dbapi-8: dropbox-client: itms-apps: itms-appss: blob:; img-src https://* data: blob:; media-src https://* blob:; object-src 'self' https://cfl.dropboxstatic.com/static/ https://www.dropboxstatic.com/static/ https://edge-live.dropboxstatic.com/static/; report-to csp-metaserver-whitelist; report-uri https://www.dropbox.com/csp_log?policy_name=metaserver-whitelist; script-src 'unsafe-eval' 'inline-speculation-rules' https://www.dropbox.com/static/api/ https://www.dropbox.com/pithos/ https://cfl.dropboxstatic.com/static/ https://www.dropboxstatic.com/static/ https://edge-live.dropboxstatic.com/static/ https://accounts.google.com/gsi/client https://reveal.clearbit.com/v1/companies/reveal https://www.paypal.com/sdk/js https://applepay.cdn-apple.com https://snippet.meticulous.ai/record/ https://edge.cofra.me/cf-static-97646a4fe3e6.js https://edge.cofra.me/cf-static-4d85f2a0ba2d.js 'nonce-PJGnmATd9t8ucSvSdeSHi5YArjA='; style-src https://* 'unsafe-inline' 'unsafe-eval'; worker-src https://www.dropbox.com/static/serviceworker/ https://www.dropbox.com/encrypted_folder_download/service_worker.js https://www.dropbox.com/service_worker.js blob:, report-to csp-metaserver-dynamic; report-uri https://www.dropbox.com/csp_log?policy_name=metaserver-dynamic; script-src 'unsafe-eval' 'strict-dynamic' 'nonce-PJGnmATd9t8ucSvSdeSHi5YArjA=' 'nonce-yzf66ND32R/mR5od2yG+ZZLFIk4='
content-type: text/html; charset=utf-8
cross-origin-opener-policy: same-origin-allow-popups
location: https://uc0f0fadf8f1c5eda3614df1434e.dl.dropboxusercontent.com/cd/0/get/DJUKjcNy4oqh_YqDuKtOJztmyE26yxwV6c2AjPQvq5x_aDOuYd3dBZtOlkURIMzfetA1hyHItSrI5_N1nU1Zkcnevzlbx6syXdW4x2kTP_7d53j3yaKMPU08nP4D52X-eI0G2Bx1FoJyyhKEo2QRb26s/file?dl=1#
pragma: no-cache
referrer-policy: strict-origin-when-cross-origin
reporting-endpoints: coop-dws2="https://www.dropbox.com/csp_log?policy_name=coop-dws2", max_age=10886400, csp-metaserver-whitelist="https://www.dropbox.com/csp_log?policy_name=metaserver-whitelist", max_age=10886400, csp-metaserver-dynamic="https://www.dropbox.com/csp_log?policy_name=metaserver-dynamic", max_age=10886400
set-cookie: t=f829qPinr03yd1q_g96SJ3mq; Path=/; Domain=dropbox.com; Expires=Mon, 04 Oct 2027 13:09:37 GMT; HttpOnly; Secure; SameSite=None
__Host-js_csrf=f829qPinr03yd1q_g96SJ3mq; Path=/; Expires=Mon, 04 Oct 2027 13:09:37 GMT; Secure; SameSite=None
__Host-ss=g5RJP_D5CI; Path=/; Expires=Mon, 04 Oct 2027 13:09:37 GMT; HttpOnly; Secure; SameSite=Strict
__Host-logged-out-session=ChAzGRChvDwY26al3HORqY30EJGgidYGGi5BUmswdFRTYWIyRHNzTHJWZXdaTmZwanVuRWdCZEhfcm56OG9RdklLNTBaRXBn; Path=/; HttpOnly; Secure; SameSite=None
x-content-type-options: nosniff
x-permitted-cross-domain-policies: none
x-robots-tag: noindex, nofollow, noimageindex
x-xss-protection: 1; mode=block
content-length: 17
date: Sun, 04 Oct 2026 13:09:38 GMT
strict-transport-security: max-age=31536000; includeSubDomains
server: envoy
cache-control: no-cache, no-store
alt-svc: h3=":443"; ma=86400, h3-29=":443"; ma=86400
x-dropbox-response-origin: far_remote
x-dropbox-request-id: dfefd90bb6e34633a3238e166ac25011
X-Firefox-Spdy: h2



fetch:

await fetch("https://www.dropbox.com/scl/fi/8e3j59xgi9d5wb7t66zl6/UndeadLegacy_2.7.40.zip?rlkey=71ncnbtqexxa4ckrjr9rxy3cn&st=9r66770o&dl=1", {
    "credentials": "include",
    "headers": {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:156.0) Gecko/20100101 Firefox/156.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl",
        "Sec-GPC": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Priority": "u=0, i"
    },
    "referrer": "https://ul.subquake.com/",
    "method": "GET",
    "mode": "cors"
});



i curl:

curl 'https://www.dropbox.com/scl/fi/8e3j59xgi9d5wb7t66zl6/UndeadLegacy_2.7.40.zip?rlkey=71ncnbtqexxa4ckrjr9rxy3cn&st=9r66770o&dl=1' \
  -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:156.0) Gecko/20100101 Firefox/156.0' \
  -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' \
  -H 'Accept-Language: pl' \
  -H 'Accept-Encoding: gzip, deflate, br, zstd' \
  -H 'Referer: https://ul.subquake.com/' \
  -H 'Sec-GPC: 1' \
  -H 'Connection: keep-alive' \
  -H 'Cookie: gvc=MTgwMDMzMDUyNjUzNTA3Nzg2NDEzMjIzODE2MzgwNTgzMDYzNTY2; t=f829qPinr03yd1q_g96SJ3mq; __Host-js_csrf=f829qPinr03yd1q_g96SJ3mq; locale=pl' \
  -H 'Upgrade-Insecure-Requests: 1' \
  -H 'Sec-Fetch-Dest: document' \
  -H 'Sec-Fetch-Mode: navigate' \
  -H 'Sec-Fetch-Site: cross-site' \
  -H 'Sec-Fetch-User: ?1' \
  -H 'Priority: u=0, i'



i zastanawiam się jak to wdrążyć aby wykrywało zawsze najnowsżą wersje  bo same linki na stronie są stąd <table class="customTableClass1 contentTable1" style="height: 144px; border-collapse: collapse; width: 100%; border-spacing: 1px; margin-left: auto; margin-right: auto;" border="1" cellspacing="1">
<tbody>
<tr style="height: 48px;">
<td style="width: 107.7px; text-align: center; height: 48px;">Game<br>Version</td>
<td style="width: 218.25px; text-align: center; height: 48px;">Undead Legacy<br>Version</td>
<td style="text-align: center; width: 350.05px; height: 48px;"><span style="color: #ff6600;"><strong>(EasyAntiCheat must be turned off)</strong></span></td>
</tr>
<tr style="height: 48px;">
<td style="width: 107.7px; text-align: center; height: 48px;">v2.6</td>
<td style="width: 218.25px; text-align: center; height: 48px;">2026.09.28 - 2.7.40</td>
<td style="text-align: center; width: 350.05px; height: 48px;"><span style="color: rgb(241, 196, 15);"><strong>Both parts are required!</strong></span><br><a title="Experimental Version of Undead Legacy" href="/dl?v=exp_part1">Download Part 1</a><br><a title="Experimental Version of Undead Legacy" href="/dl?v=exp_part2">Download Part 2</a></td>
</tr>
<tr style="height: 48px;">
<td style="width: 107.7px; text-align: center; height: 48px;">v2.6</td>
<td style="width: 218.25px; text-align: center; height: 48px;">2026.09.28 - 2.7.40</td>
<td style="text-align: center; width: 350.05px; height: 48px;">Use only if the main download doesn't work<a title="Experimental Version of Undead Legacy" href="/dl?v=mirror"><br>Download (Mirror)</a><br><a title="Experimental Version of Undead Legacy" href="/dl?v=nexusmods">Download (Nexus Mods)</a></td>
</tr>
</tbody>
</table>



mnie interesuje Download (Mirror) czyli <a title="Experimental Version of Undead Legacy" href="/dl?v=mirror"><br>Download (Mirror)</a> 



I cały overhaul jest dla wersji v2.6
i całość daj w zip jak zrobisz, i zastanawiam się jak to zrobić, bo w pełni automatyzacja czyli json z manifestu miałby zawsze najnowszą wersję to trzeba scrapować strone czy coś a na sztywno to pewnie prosto da się ustawić url, ale patrząc po dacie to wciąz aktualizują ten projekt
