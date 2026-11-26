#!/usr/bin/env python3
# build_site.py — regenerate the Niigata 2027 site's data-driven pages.
#
# Data sources (the ONLY files a human edits):
#   data/furumachi.json  — the 100 Furumachi shops
#   data/breweries.json  — the 92 sake breweries
# Outputs: the 6 Furumachi pages + furumachi.geojson, the 3 sake pages,
# the 3 brewery-map pages + breweries.geojson, SEO blocks on all 21 pages,
# sitemap.xml and robots.txt.
#
# Standard library only; all paths are relative to the repository root.
# Validation runs BEFORE anything is written: on any failure the script
# exits non-zero and leaves the tree untouched.
# The page templates below are carried over verbatim from the original
# local generators (formerly data/build_*.py + data/apply_seo.py).
import html, json, re, sys, pathlib

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

GENRES = ["jp", "sushi", "bar", "soba", "west", "other"]
GENRE_COLORS = {"jp": "#1f5c3d", "sushi": "#b3402a", "bar": "#6b3fa0",
                "soba": "#20508c", "west": "#b8860b", "other": "#555f58"}

# Populated by main() from the JSON data files.
SHOPS = []      # furumachi entries (JSON order)
BY_SLUG = {}    # slug -> furumachi entry
recs = []       # brewery entries in the shape the sake templates expect
NFULL = 0       # furumachi pins at full precision
data_js = ""    # geojson embedded in the map page being built
colors_js = ""  # genre/region colours embedded in the map page being built

# === SEO data and block builder (from data/apply_seo.py) ===
ROOT = "https://public-dl.github.io/niigata-2027/"
HERO = ROOT + "images/kiyotsu.jpg"

GROUPS = [
    ["index.html", "ja.html", "fr.html"],
    ["sake.html", "sake-ja.html", "sake-fr.html"],
    ["map.html", "map-ja.html", "map-fr.html"],
    ["sushi.html", "sushi-ja.html", "sushi-fr.html"],
    ["sushi-map.html", "sushi-map-ja.html", "sushi-map-fr.html"],
    ["furumachi.html", "furumachi-ja.html", "furumachi-fr.html"],
    ["furumachi-map.html", "furumachi-map-ja.html", "furumachi-map-fr.html"],
]
LANG_OF = {}
for g in GROUPS:
    for f in g:
        LANG_OF[f] = "en" if f in ("index.html", "sake.html", "map.html", "sushi.html", "sushi-map.html", "furumachi.html", "furumachi-map.html") else ("fr" if f.endswith("-fr.html") or f == "fr.html" else "ja")
GROUP_OF = {f: g for g in GROUPS for f in g}

PAGES = {
 "index.html": dict(
   og_type="website",
   title="Niigata 2027 — Chosen by National Geographic and Condé Nast Traveler",
   desc="Niigata Prefecture, Japan, is the only Japanese destination in both National Geographic's Best of the World 2027 and Condé Nast Traveler's 27 Best Places to Go in 2027. Fermentation culture, the Echigo-Tsumari Art Triennale, snow country and Sado Island — a guide from Niigata.",
   schema_type="WebPage"),
 "ja.html": dict(
   og_type="website",
   title="新潟 2027 ― ナショナルジオグラフィックとコンデナスト・トラベラーが選んだ場所",
   desc="新潟県は、ナショナルジオグラフィック「Best of the World 2027」とコンデナスト・トラベラー「2027年に行くべき27の場所」の両方に、日本で唯一選ばれました。発酵文化、大地の芸術祭、雪国と佐渡を、新潟から紹介します。",
   schema_type="WebPage"),
 "fr.html": dict(
   og_type="website",
   title="Niigata 2027 — Choisi par National Geographic et Condé Nast Traveler",
   desc="La préfecture de Niigata, au Japon, est la seule destination japonaise présente à la fois dans le Best of the World 2027 de National Geographic et dans les 27 Best Places to Go in 2027 de Condé Nast Traveler. Culture de la fermentation, Triennale d'art d'Echigo-Tsumari, pays de la neige et île de Sado — un guide écrit depuis Niigata.",
   schema_type="WebPage"),
 "sake.html": dict(
   og_type="website",
   title="Niigata's Sake Breweries — The Complete List | Niigata 2027",
   desc="Every sake brewery in Niigata Prefecture, listed by region: names in English and Japanese, main brands, founding years and which breweries offer tours. Compiled from the Niigata Sake Brewers Association directory.",
   schema_type="CollectionPage"),
 "sake-ja.html": dict(
   og_type="website",
   title="新潟の酒蔵 全一覧 | Niigata 2027",
   desc="新潟県の酒蔵を地域別に全蔵掲載。蔵名・代表銘柄・創業年・見学の可否を、新潟県酒造組合の蔵元紹介をもとにまとめました。英語版もあります。",
   schema_type="CollectionPage"),
 "sake-fr.html": dict(
   og_type="website",
   title="Les brasseries de saké de Niigata — la liste complète | Niigata 2027",
   desc="Toutes les brasseries de saké de la préfecture de Niigata, classées par région : noms en caractères latins et en japonais, marques principales, années de fondation et visites possibles. D'après l'annuaire de l'Association des brasseurs de saké de Niigata.",
   schema_type="CollectionPage"),
 "map.html": dict(
   og_type="website",
   title="Map of Niigata's Sake Breweries | Niigata 2027",
   desc="An interactive map of all 92 sake breweries in Niigata Prefecture, Japan, coloured by region and filterable to breweries offering tours. Data from the Niigata Sake Brewers Association directory.",
   schema_type="WebPage"),
 "map-ja.html": dict(
   og_type="website",
   title="新潟の酒蔵マップ | Niigata 2027",
   desc="新潟県の酒蔵92蔵を地図にプロット。地域別に色分けし、見学できる蔵だけにも絞り込めます。新潟県酒造組合の蔵元紹介をもとに作成しました。",
   schema_type="WebPage"),
 "map-fr.html": dict(
   og_type="website",
   title="Carte des brasseries de saké de Niigata | Niigata 2027",
   desc="Une carte interactive des 92 brasseries de saké de la préfecture de Niigata, au Japon, colorées par région et filtrable sur les brasseries proposant des visites. Données de l'annuaire de l'Association des brasseurs de saké de Niigata.",
   schema_type="WebPage"),
 "sushi.html": dict(
   og_type="website",
   title="Sushi in Niigata City — Local Fish, Niigata Rice | Niigata 2027",
   desc="Where to eat sushi in Niigata City: thirty restaurants where the fish comes from Niigata and Sado waters and the rice is Niigata-grown — from award-winning omakase counters to a conveyor-belt shop inside the fish market.",
   schema_type="WebPage"),
 "sushi-ja.html": dict(
   og_type="website",
   title="新潟市の寿司 ― 地魚と新潟の米 | Niigata 2027",
   desc="新潟市内で、新潟・佐渡沖の地魚と新潟産の米のシャリを味わえる寿司屋30店。食べログアワード受賞のおまかせカウンターから、魚市場の回転寿司まで。",
   schema_type="WebPage"),
 "sushi-fr.html": dict(
   og_type="website",
   title="Les sushis dans la ville de Niigata — poisson local, riz de Niigata | Niigata 2027",
   desc="Où manger des sushis dans la ville de Niigata : trente restaurants où le poisson vient des eaux de Niigata et de Sado et où le riz est cultivé à Niigata — des comptoirs omakase primés au kaiten du marché aux poissons.",
   schema_type="WebPage"),
 "sushi-map.html": dict(
   og_type="website",
   title="Map — Sushi in Niigata City | Niigata 2027",
   desc="An interactive map of thirty sushi restaurants in Niigata City, Japan, where the fish and the rice are both local — omakase counters in Furumachi, station-side shops and a conveyor-belt restaurant in the Pier Bandai market.",
   schema_type="WebPage"),
 "sushi-map-ja.html": dict(
   og_type="website",
   title="新潟市の寿司マップ | Niigata 2027",
   desc="新潟市の寿司特集で紹介した30店を地図にプロット。古町のおまかせカウンター、駅前の店、ピアBandaiの回転寿司まで、価格の目安つき。",
   schema_type="WebPage"),
 "sushi-map-fr.html": dict(
   og_type="website",
   title="Carte — Les sushis à Niigata | Niigata 2027",
   desc="Une carte interactive de trente restaurants de sushis dans la ville de Niigata, au Japon, où le poisson et le riz sont tous deux locaux — comptoirs omakase de Furumachi, adresses près de la gare et un kaiten dans le marché de Pier Bandai.",
   schema_type="WebPage"),
 "furumachi.html": dict(
   og_type="website",
   title="Furumachi — 100 Places to Eat and Drink | Niigata 2027",
   desc="One hundred restaurants and bars in Furumachi, Niigata City's old geisha district: kappo counters, izakaya, sushi, sake bars open until dawn, late-night soba, French and Italian — with the author's own recommendations marked.",
   schema_type="CollectionPage"),
 "furumachi-ja.html": dict(
   og_type="website",
   title="古町100店 ― 食べる・飲む店の全名簿 | Niigata 2027",
   desc="新潟市の花街・古町とその周辺の飲食店100店の名簿。割烹・居酒屋、寿司、明け方まで開くバー、〆の蕎麦、フレンチとイタリアン。",
   schema_type="CollectionPage"),
 "furumachi-fr.html": dict(
   og_type="website",
   title="Furumachi — 100 adresses pour manger et boire | Niigata 2027",
   desc="Cent restaurants et bars de Furumachi, l'ancien quartier des geishas de Niigata City : comptoirs kappo, izakaya, sushis, bars à saké ouverts jusqu'à l'aube, soba de fin de soirée, adresses françaises et italiennes — avec les recommandations de l'auteur.",
   schema_type="CollectionPage"),
 "furumachi-map.html": dict(
   og_type="website",
   title="Map — Furumachi's 100 Places | Niigata 2027",
   desc="An interactive map of 100 restaurants and bars in Furumachi, Niigata City's old geisha district, coloured by genre — kappo, sushi, bars, soba, French and Italian.",
   schema_type="WebPage"),
 "furumachi-map-ja.html": dict(
   og_type="website",
   title="古町100店マップ | Niigata 2027",
   desc="新潟市・古町の飲食店100店をジャンル別に色分けした地図。割烹・居酒屋、寿司、バー、蕎麦、フレンチとイタリアン。",
   schema_type="WebPage"),
 "furumachi-map-fr.html": dict(
   og_type="website",
   title="Carte — Les 100 adresses de Furumachi | Niigata 2027",
   desc="Une carte interactive de 100 restaurants et bars de Furumachi, l'ancien quartier des geishas de Niigata City, colorés par genre — kappo, sushis, bars, soba, français et italien.",
   schema_type="WebPage"),
}

def esc(s):
    return s.replace("&", "&amp;").replace('"', "&quot;")

def url_of(f):
    return ROOT + ("" if f == "index.html" else f)

LOCALES = {"en": "en_US", "ja": "ja_JP", "fr": "fr_FR"}

def block(fname, m):
    lang = LANG_OF[fname]
    group = GROUP_OF[fname]
    url = url_of(fname)
    alt = {LANG_OF[f]: url_of(f) for f in group}
    ld = {
        "@context": "https://schema.org",
        "@type": m["schema_type"],
        "name": m["title"], "url": url, "description": m["desc"],
        "inLanguage": lang,
        "isPartOf": {"@type": "WebSite", "name": "Niigata 2027", "url": ROOT},
    }
    alts = "\n".join(f'<link rel="alternate" hreflang="{l}" href="{alt[l]}">' for l in ("en", "ja", "fr"))
    return f"""<link rel="canonical" href="{url}">
{alts}
<link rel="alternate" hreflang="x-default" href="{alt['en']}">
<meta property="og:type" content="{m['og_type']}">
<meta property="og:site_name" content="Niigata 2027">
<meta property="og:title" content="{esc(m['title'])}">
<meta property="og:description" content="{esc(m['desc'])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{HERO}">
<meta property="og:locale" content="{LOCALES[lang]}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(m['title'])}">
<meta name="twitter:description" content="{esc(m['desc'])}">
<meta name="twitter:image" content="{HERO}">
<script type="application/ld+json">
{json.dumps(ld, ensure_ascii=False, indent=2)}
</script>
"""

OLD_BLOCK = re.compile(r'<link rel="canonical".*?</script>\n?', re.S)

# === Sake brewery list templates (from data/build_sake_pages.py) ===
EN = {
 "abe": ("Abe Shuzo", "Koshi no Otokoyama"),
 "aoi": ("Aoi Shuzo", "Maison Aoi"),
 "aoki": ("Aoki Shuzo", "Kakurei"),
 "asahi": ("Asahi Shuzo", "Kubota"),
 "asazuma": ("Asazuma Shuzo", "Yuki no Maboroshi"),
 "ayumasamune": ("Ayu Masamune Shuzo", "Ayu Masamune"),
 "chiyonohikari": ("Chiyo no Hikari Shuzo", "Chiyo no Hikari"),
 "denemon": ("Echigo Denemon", "GOZ"),
 "dhc": ("DHC Shuzo", "Yuten"),
 "echigo": ("Echigo Shuzojo", "Koshi no Happo"),
 "echigotsurukame": ("Echigo Tsurukame", "Echigo Tsurukame"),
 "echigozakura": ("Echigozakura Shuzo", "Echigozakura"),
 "fujinoi": ("Fujinoi Shuzo", "Fujinoi"),
 "fukugao": ("Fukugao Shuzo", "Echigo Ikarashigawa"),
 "hakkai": ("Hakkaisan Brewery", "Hakkaisan"),
 "hakuro": ("Hakuro Shuzo", "Hakuro"),
 "hakuryu": ("Hakuryu Shuzo", "Hakuryu"),
 "hara": ("Hara Shuzo", "Koshi no Homare"),
 "hasegawa": ("Hasegawa Shuzo", "Echigo Sekkobai"),
 "henmi": ("Henmi Shuzo", "Shinryo"),
 "hiki": ("Hiki Shuzo", "Tsuru no Tomo"),
 "hokusetsu": ("Hokusetsu Shuzo", "Hokusetsu"),
 "ichishima": ("Aumont (Omon) Shuzo", "Aumont"),
 "ikedaya": ("Ikedaya Shuzo", "Kenshin"),
 "ikeura": ("Ikeura Shuzo", "Waraku Goson"),
 "imayotsukasa": ("Imayo Tsukasa Sake Brewery", "Nishikigoi"),
 "inomata": ("Inomata Shuzo", "Tsukimizunoike"),
 "ishiduka": ("Ishizuka Shuzo", "Hime no I"),
 "ishimoto": ("Ishimoto Shuzo", "Koshi no Kanbai"),
 "jouetsu": ("Joetsu Shuzo", "Echigo Bijin"),
 "kaetsu": ("Kaetsu Shuzo", "Homare Kirin"),
 "kaganoi": ("Kaganoi Shuzo", "Kaganoi"),
 "kamonishiki": ("Kamonishiki Shuzo", "Kamonishiki"),
 "kanemasu": ("Kanemasu Shuzo", "Kanemasu"),
 "katoshuzo": ("Kato Shuzo (Joetsu)", "Kiyomasa"),
 "katoshuzoten": ("Kato Shuzoten (Sado)", "Kintsuru"),
 "kawachu": ("Kawachu Shuzo", "Sotembo"),
 "kikusui": ("Kikusui Shuzo", "Kikusui"),
 "kiminoi": ("Kiminoi Shuzo", "Kiminoi"),
 "kinshihai": ("Kinshihai Shuzo", "Echigo Toji"),
 "kirinzan": ("Kirinzan Shuzo", "Kirinzan"),
 "kondo": ("Kondo Shuzo", "Koshi no Karoku"),
 "koshimeijo": ("Koshimeijo", "Koshi no Tsuru"),
 "koshitsukano": ("Koshitsuka no Shuzo", "Koshi no Ajiwai"),
 "koyama": ("Koyama Shuzoten", "Echigo Jiman"),
 "kubiki": ("Kubiki Shuzo", "Koshiji no Kobai"),
 "kusumi": ("Kusumi Shuzo", "Kiyoizumi"),
 "lagoonbrewery": ("Lagoon Brewery", "Shoku"),
 "maruyama": ("Maruyama Shuzo", "Setchubai"),
 "masukagami": ("Masukagami", "Masukagami"),
 "matsunoi": ("Matsunoi Shuzo", "Matsunoi"),
 "midorikawa": ("Midorikawa Shuzo", "Midorikawa"),
 "miho": ("Bihou Shurui — Niigata branch", "Koshihikari rice shochu"),
 "minenohakubai": ("Mine no Hakubai Shuzo", "Mine no Hakubai"),
 "miyao": ("Miyao Shuzo", "Shimeharitsuru"),
 "morohashi": ("Morohashi Shuzo", "Koshi no Kagetora"),
 "murayu": ("Murayu Shuzo", "Hanakoshiji"),
 "musashino": ("Musashino Shuzo", "Ski Masamune"),
 "myoko": ("Myoko Shuzo", "Myokozan"),
 "naeba": ("Naeba Shuzo", "Kamosu Mori"),
 "nakagawa": ("Nakagawa Shuzo", "Koshi no Hakugan"),
 "niigata": ("Niigata Meijo", "Chojazakari"),
 "niigatadaiichi": ("Niigata Daiichi Shuzo", "Koshi no Hakucho"),
 "obata": ("Obata Shuzo", "Manotsuru"),
 "ohuku": ("Ofuku Shuzo", "Ofuku Masamune"),
 "onda": ("Onda Shuzo", "Maitsuru Tsuzumi"),
 "sakeai": ("Sakeai", "SAKENOVA"),
 "sasaiwai": ("Sasaiwai Shuzo", "Sasaiwai"),
 "sekihara": ("Sekihara Shuzo", "Gunki"),
 "shiokawa": ("Shiokawa Shuzo", "Koshi no Seki"),
 "shirataki": ("Shirataki Shuzo", "Jozen Mizunogotoshi"),
 "snowsatoyama": ("Yuki to Satoyama Jozo", None),
 "suminoi": ("Suminoi Shuzo", "Suminoi"),
 "tahara": ("Tahara Shuzo", "Yukitsuru"),
 "taiyo": ("Taiyo Shuzo", "Taiyozakari"),
 "takachiyo": ("Takachiyo Shuzo", "Takachiyo"),
 "takano": ("Takano Shuzo", "Koshiji Fubuki"),
 "takanoi": ("Takanoi Shuzo", "Koshi no Hatsuume"),
 "takarayama": ("Takarayama Jozo", "Takarayama"),
 "takeda": ("Takeda Shuzoten", "Katafune"),
 "tamagawa": ("Tamagawa Shuzo", "Tamafumi"),
 "tanaka": ("Tanaka Shuzo", "Notaka"),
 "tenryohai": ("Tenryohai Shuzo", "Tenryohai"),
 "tochikura": ("Tochikura Shuzo", "Kome Hyappyo"),
 "tsunan": ("Tsunan Jozo", "Tsunan"),
 "uonuma": ("Uonuma Shuzo", "Tenjinbayashi"),
 "watanabe": ("Watanabe Shuzoten", "Nechi Otokoyama"),
 "yahiko": ("Yahiko Shuzo", "Koshi no Hakusetsu"),
 "yoshikawa": ("Yoshikawa Toji no Sato", "Yoshikawa Toji"),
 "yoshinogawa": ("Yoshinogawa", "Yoshinogawa"),
 "yoyogiku": ("Yoyogiku Jozo", "Gindagawa"),
 "yukitsubaki": ("Yukitsubaki Shuzo", "Koshi no Yukitsubaki"),
}

MUNI_EN = {
 "村上市":"Murakami City","新発田市":"Shibata City","阿賀野市":"Agano City","阿賀町":"Aga Town",
 "五泉市":"Gosen City","新潟市":"Niigata City","弥彦村":"Yahiko Village","加茂市":"Kamo City",
 "三条市":"Sanjo City","長岡市":"Nagaoka City","柏崎市":"Kashiwazaki City","南魚沼市":"Minamiuonuma City",
 "魚沼市":"Uonuma City","小千谷市":"Ojiya City","十日町市":"Tokamachi City","津南町":"Tsunan Town",
 "湯沢町":"Yuzawa Town","上越市":"Joetsu City","妙高市":"Myoko City","糸魚川市":"Itoigawa City","佐渡市":"Sado City",
}
REGION_EN = {"下越":("Kaetsu","the north"),"中越":("Chuetsu","the centre"),"上越":("Joetsu","the west"),"佐渡":("Sado","Sado Island")}
REGION_ORDER = ["下越","中越","上越","佐渡"]

# Brands for the 5 association pages whose brand field is broken (from NTA 2021 list)
BRAND_FIX_JA = {"kondo":"越乃鹿六","niigatadaiichi":"越の白鳥","ohuku":"お福正宗","takarayama":"たからやま","snowsatoyama":None}

def founding_en(r):
    f = r["founding"].replace("西暦","").strip()
    if f in ("", "不明"): return "—"
    if f == "安政年間": return "1850s"
    m = re.match(r"(\d{4})", f)
    return m.group(1) if m else f

def founding_ja(r):
    f = r["founding"].replace("西暦","").strip()
    if f == "": return "—"
    return f

def founding_fr(r):
    f = founding_en(r)
    return "années 1850" if f == "1850s" else f

def rows(region, lang):
    out = []
    rs = [r for r in recs if r["region"] == region]
    rs.sort(key=lambda r: (r["municipality"], r["name"]))
    for r in rs:
        en_name, en_brand = EN.get(r["slug"], (r["name"], None))
        brand_ja = r["brand"] or BRAND_FIX_JA.get(r["slug"]) or "—"
        tours = r["tour"] == "あり"
        url = r["url"]
        if lang == "en":
            brand = en_brand if en_brand else "—"
            link = f'<a href="{html.escape(url)}">Website</a>' if url else "—"
            out.append(f"<tr><td><strong>{html.escape(en_name)}</strong><br><span class='jp'>{html.escape(r['name'])}</span></td>"
                       f"<td>{MUNI_EN.get(r['municipality'], r['municipality'])}</td><td>{html.escape(brand)}</td>"
                       f"<td>{founding_en(r)}</td><td>{'Yes' if tours else '—'}</td><td>{link}</td></tr>")
        elif lang == "fr":
            brand = en_brand if en_brand else "—"
            link = f'<a href="{html.escape(url)}">Site officiel</a>' if url else "—"
            out.append(f"<tr><td><strong>{html.escape(en_name)}</strong><br><span class='jp'>{html.escape(r['name'])}</span></td>"
                       f"<td>{MUNI_EN.get(r['municipality'], r['municipality'])}</td><td>{html.escape(brand)}</td>"
                       f"<td>{founding_fr(r)}</td><td>{'Oui' if tours else '—'}</td><td>{link}</td></tr>")
        else:
            link = f'<a href="{html.escape(url)}">公式サイト</a>' if url else "—"
            out.append(f"<tr><td><strong>{html.escape(r['name'])}</strong></td>"
                       f"<td>{html.escape(r['municipality'])}</td><td>{html.escape(brand_ja)}</td>"
                       f"<td>{founding_ja(r)}</td><td>{'あり' if tours else '—'}</td><td>{link}</td></tr>")
    return "\n".join(out)

CSS = """
  :root { --ink:#1d2a24; --accent:#1f5c3d; --vermillion:#b3402a; --paper:#faf7f0; --card:#ffffff; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: Georgia, 'Times New Roman', serif; color:var(--ink); background:var(--paper); line-height:1.65; }
  .lang { max-width:960px; margin:0 auto; padding:.8rem 1.2rem 0; text-align:right; font-size:.9rem; }
  main { max-width:960px; margin:0 auto; padding:0 1.2rem 3rem; }
  h1 { font-size:clamp(1.5rem, 4vw, 2.3rem); color:var(--accent); line-height:1.3; }
  h2 { font-size:1.35rem; color:var(--accent); border-bottom:3px solid var(--vermillion); padding-bottom:.3rem; margin-top:2.4rem; }
  table { width:100%; border-collapse:collapse; font-size:.92rem; background:var(--card); }
  th, td { border:1px solid #ddd5c3; padding:.45rem .55rem; text-align:left; vertical-align:top; }
  th { background:#f1ebdd; }
  .jp { color:#5c665f; font-size:.85em; }
  .note { font-size:.88rem; color:#444; background:#fff; border:1px solid #ddd5c3; border-left:5px solid var(--vermillion); padding:.8rem 1rem; }
  a { color:var(--accent); }
  footer { border-top:1px solid #ddd5c3; margin-top:3rem; padding-top:1.2rem; font-size:.85rem; color:#5c665f; }
  .tablewrap { overflow-x:auto; }
"""

def build_en():
    secs = []
    for reg in REGION_ORDER:
        en_name, desc = REGION_EN[reg]
        n = sum(1 for r in recs if r["region"] == reg)
        secs.append(f"""<section>
  <h2>{en_name} — {desc} ({n})</h2>
  <div class="tablewrap"><table>
    <tr><th>Brewery</th><th>City / Town</th><th>Main brand</th><th>Founded</th><th>Tours</th><th>Link</th></tr>
    {rows(reg, 'en')}
  </table></div>
</section>""")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Niigata's Sake Breweries — The Complete List | Niigata 2027</title>
<meta name="description" content="Every sake brewery in Niigata Prefecture, listed by region: names in English and Japanese, main brands, founding years and which breweries offer tours. Compiled from the Niigata Sake Brewers Association directory.">
<style>{CSS}</style>
</head>
<body>
<div class="lang"><a href="index.html">← Niigata 2027</a> · <a href="sake-ja.html">日本語版</a> · <a href="sake-fr.html">Version française</a></div>
<main>
<h1>Niigata's sake breweries — the complete list</h1>
<p>Niigata has more sake breweries than any other prefecture in Japan — <strong>88</strong> by the count usually cited, and the Niigata Sake Brewers Association's own directory currently lists <strong>92</strong>, including new micro-breweries founded in the last few years. Until now there has been no single English list of them all: the association's detailed brewery pages are Japanese-only. This page is that list — and there is also <a href="map.html">a map of all the breweries</a>.</p>
<p>Every brewery below is in the association's directory (as of 23 November 2026), grouped by region. English names and brands are cross-checked against the National Tax Agency's English sake brewery map; founding years and tour availability are as the association lists them. "Tours: Yes" means the brewery accepts visitors in some form — most require booking, and details change, so check the brewery's own site before you go.</p>
<div class="note"><strong>Short on time? Start with these.</strong>
<ul>
<li><strong>Imayo Tsukasa</strong> (Niigata City) — brewery tours with an English guide, a short walk from the old Nuttari fermentation district.</li>
<li><strong><a href="https://ponshukan.com/en/niigata/">Ponshukan</a></strong> (Niigata, Nagaoka and Echigo-Yuzawa stations) — not a brewery, but the tasting room where you can try sake from across the whole prefecture, one small cup at a time.</li>
<li><strong>Yoshinogawa</strong> (Nagaoka, founded 1548) — Niigata's oldest brewery, with its own sake museum in the Settaya brewing district.</li>
<li><strong>Asahi Shuzo</strong> (Nagaoka) — maker of Kubota; free short brewery tours year-round.</li>
<li><strong>Shirataki</strong> (Yuzawa) — beside Echigo-Yuzawa Station; the easiest brewery visit on a ski trip.</li>
<li><strong>Obata — Gakkogura</strong> (Sado Island) — a working brewery inside a closed school, where visitors can join the brewing.</li>
</ul></div>
{''.join(secs)}
<section>
  <h2>Sources</h2>
  <p>Niigata Sake Brewers Association, brewery directory (niigata-sake.or.jp/kuramoto), as of 23 November 2026 · National Tax Agency, Kanto-Shinetsu Regional Taxation Bureau, "Sake Breweries Map" (English, 2021) for English names and brands · For visits, <a href="https://sake-guide.com/visit?pref=niigata">Sake Guide's Niigata page</a> has practical details on the breweries that welcome visitors.</p>
</section>
<footer>
  <p>Part of <a href="index.html">Niigata 2027 — the place two travel magazines chose</a>, an independent guide made in Niigata, Japan.</p>
  <p>Powered by <a href="https://public-dl.github.io/wooltech/">WoolTech</a></p>
</footer>
</main>
<script data-goatcounter="https://niigata2027.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
</body>
</html>"""

def build_ja():
    secs = []
    for reg in REGION_ORDER:
        n = sum(1 for r in recs if r["region"] == reg)
        secs.append(f"""<section>
  <h2>{reg}地区（{n}蔵）</h2>
  <div class="tablewrap"><table>
    <tr><th>蔵元</th><th>市町村</th><th>代表銘柄</th><th>創業</th><th>見学</th><th>リンク</th></tr>
    {rows(reg, 'ja')}
  </table></div>
</section>""")
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>新潟の酒蔵 全一覧 | Niigata 2027</title>
<meta name="description" content="新潟県の酒蔵を地域別に全蔵掲載。蔵名・代表銘柄・創業年・見学の可否を、新潟県酒造組合の蔵元紹介をもとにまとめました。英語版もあります。">
<style>{CSS}</style>
</head>
<body>
<div class="lang"><a href="ja.html">← 新潟 2027</a> · <a href="sake.html">English version</a> · <a href="sake-fr.html">Version française</a></div>
<main>
<h1>新潟の酒蔵 ― 全一覧</h1>
<p>新潟県の酒蔵は全国最多で、通常は<strong>88蔵</strong>とされます。新潟県酒造組合の蔵元紹介には現在<strong>92蔵</strong>が掲載されており、近年の新しい小規模な蔵も含まれます。このページは、その全蔵を地域別に並べたものです。<a href="map-ja.html">地図版（酒蔵マップ）</a>もあります。英語版では、蔵名と銘柄の英語表記を国税局の英語版酒蔵マップで照合しています。</p>
<p>創業年と見学の可否は酒造組合の掲載情報（2026年11月23日現在）によります。「見学：あり」は何らかの形で受け入れがあるという意味で、多くは予約が必要です。行く前に各蔵の公式サイトで確認してください。</p>
<div class="note"><strong>時間がないときは、まずこのあたりから。</strong>
<ul>
<li><strong>今代司酒造</strong>（新潟市）― 英語ガイド付きの蔵見学。沼垂の発酵の町からも歩けます。</li>
<li><strong><a href="https://www.ponshukan.com">ぽんしゅ館</a></strong>（新潟・長岡・越後湯沢の各駅）― 蔵ではありませんが、県内の酒を少しずつ飲み比べられる利き酒の場所です。</li>
<li><strong>吉乃川</strong>（長岡市、1548年創業）― 県内最古の蔵。摂田屋に酒ミュージアムがあります。</li>
<li><strong>朝日酒造</strong>（長岡市）― 「久保田」の蔵。短時間の蔵見学を無料で通年実施しています。</li>
<li><strong>白瀧酒造</strong>（湯沢町）― 越後湯沢駅のすぐそば。スキー旅行のついでに寄れる蔵です。</li>
<li><strong>尾畑酒造・学校蔵</strong>（佐渡市）― 廃校の中で酒を造る蔵。仕込みへの参加もできます。</li>
</ul></div>
{''.join(secs)}
<section>
  <h2>出典</h2>
  <p>新潟県酒造組合「蔵元紹介」（niigata-sake.or.jp/kuramoto、2026年11月23日現在）／国税局関東信越国税局「酒蔵マップ」英語版（2021年、英語表記の照合用）。見学の実用情報は <a href="https://sake-guide.com/visit?pref=niigata">Sake Guide の新潟ページ</a> も詳しいです。</p>
</section>
<footer>
  <p><a href="ja.html">新潟 2027 ― 2誌が選んだ場所</a> の一部です。新潟で作った独立したガイドです。</p>
  <p>Powered by <a href="https://public-dl.github.io/wooltech/">WoolTech</a></p>
</footer>
</main>
<script data-goatcounter="https://niigata2027.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
</body>
</html>"""

REGION_FR = {"下越":("Kaetsu","le nord"),"中越":("Chuetsu","le centre"),"上越":("Joetsu","l'ouest"),"佐渡":("Sado","l'île de Sado")}

def build_fr():
    secs = []
    for reg in REGION_ORDER:
        fr_name, desc = REGION_FR[reg]
        n = sum(1 for r in recs if r["region"] == reg)
        secs.append(f"""<section>
  <h2>{fr_name} — {desc} ({n})</h2>
  <div class="tablewrap"><table>
    <tr><th>Brasserie</th><th>Ville</th><th>Marque principale</th><th>Fondation</th><th>Visites</th><th>Lien</th></tr>
    {rows(reg, 'fr')}
  </table></div>
</section>""")
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Les brasseries de saké de Niigata — la liste complète | Niigata 2027</title>
<meta name="description" content="Toutes les brasseries de saké de la préfecture de Niigata, classées par région : noms en caractères latins et en japonais, marques principales, années de fondation et visites possibles. D'après l'annuaire de l'Association des brasseurs de saké de Niigata.">
<style>{CSS}</style>
</head>
<body>
<div class="lang"><a href="fr.html">← Niigata 2027</a> · <a href="sake.html">English version</a> · <a href="sake-ja.html">日本語版</a></div>
<main>
<h1>Les brasseries de saké de Niigata — la liste complète</h1>
<p>Niigata compte plus de brasseries de saké que toute autre préfecture du Japon — <strong>88</strong> selon le chiffre habituellement cité, et l'annuaire de l'Association des brasseurs de saké de Niigata en recense actuellement <strong>92</strong>, y compris de nouvelles micro-brasseries fondées ces dernières années. Il n'existait jusqu'ici aucune liste complète en français ni en anglais : les pages détaillées de l'association sont en japonais uniquement. Voici cette liste — il existe aussi <a href="map-fr.html">une carte de toutes les brasseries</a>.</p>
<p>Toutes les brasseries ci-dessous figurent dans l'annuaire de l'association (au 23 novembre 2026), classées par région. Les noms et marques en caractères latins ont été vérifiés dans la carte anglaise des brasseries publiée par l'Agence nationale des impôts ; les années de fondation et les possibilités de visite sont celles indiquées par l'association. « Visites : Oui » signifie que la brasserie accueille les visiteurs sous une forme ou une autre — la plupart exigent une réservation, et les conditions changent : vérifiez le site de la brasserie avant de vous y rendre.</p>
<div class="note"><strong>Peu de temps ? Commencez par celles-ci.</strong>
<ul>
<li><strong>Imayo Tsukasa</strong> (ville de Niigata) — visites de brasserie avec guide en anglais, à quelques pas de l'ancien quartier de fermentation de Nuttari.</li>
<li><strong><a href="https://ponshukan.com/en/niigata/">Ponshukan</a></strong> (gares de Niigata, Nagaoka et Echigo-Yuzawa) — ce n'est pas une brasserie, mais la salle de dégustation où goûter les sakés de toute la préfecture, petite coupe par petite coupe.</li>
<li><strong>Yoshinogawa</strong> (Nagaoka, fondée en 1548) — la plus ancienne brasserie de Niigata, avec son musée du saké dans le quartier de brasseurs de Settaya.</li>
<li><strong>Asahi Shuzo</strong> (Nagaoka) — la maison du Kubota ; visites courtes et gratuites toute l'année.</li>
<li><strong>Shirataki</strong> (Yuzawa) — juste à côté de la gare d'Echigo-Yuzawa ; la visite de brasserie la plus simple lors d'un séjour de ski.</li>
<li><strong>Obata — Gakkogura</strong> (île de Sado) — une brasserie en activité dans une école fermée, où les visiteurs peuvent participer au brassage.</li>
</ul></div>
{''.join(secs)}
<section>
  <h2>Sources</h2>
  <p>Association des brasseurs de saké de Niigata, annuaire des brasseries (niigata-sake.or.jp/kuramoto), au 23 novembre 2026 · Agence nationale des impôts, bureau régional des impôts de Kanto-Shinetsu, « Sake Breweries Map » (anglais, 2021) pour les noms et marques en caractères latins · Pour préparer une visite, <a href="https://sake-guide.com/visit?pref=niigata">la page Niigata de Sake Guide</a> donne des informations pratiques sur les brasseries qui accueillent les visiteurs.</p>
</section>
<footer>
  <p>Page du guide <a href="fr.html">Niigata 2027 — l'endroit choisi par deux magazines de voyage</a>, un guide indépendant réalisé à Niigata, au Japon.</p>
  <p>Powered by <a href="https://public-dl.github.io/wooltech/">WoolTech</a></p>
</footer>
</main>
<script data-goatcounter="https://niigata2027.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
</body>
</html>"""

# === Furumachi directory templates (from data/build_furumachi_pages.py) ===
GENRE_TITLES = {
 "en": {"jp": "Japanese, kappo & izakaya", "sushi": "Sushi", "bar": "Bars",
        "soba": "Soba & noodles", "west": "French, Italian & Western", "other": "Yakitori & more"},
 "ja": {"jp": "日本料理・割烹・居酒屋", "sushi": "寿司", "bar": "バー",
        "soba": "蕎麦・麺", "west": "フレンチ・イタリアン・洋食", "other": "焼鳥・その他"},
 "fr": {"jp": "Cuisine japonaise, kappo & izakaya", "sushi": "Sushis", "bar": "Bars",
        "soba": "Soba & nouilles", "west": "Français, italien & occidental", "other": "Yakitori & autres"},
}

# Recommended blurbs, carried over from the top pages' wording.
REC_TEXT = {
 "en": {
  "picks_h": "The author's own picks — places he has actually been",
  "picks": {
   "kokon": "More than 20 sake labels from across Japan, all ¥500 a glass, with carefully made creative dishes. A grown-up sake bar.",
   "jikon": "Kappo-level Japanese cooking with an izakaya's ease, built on Niigata ingredients.",
   "saito": "Reservation only, eight seats, a single omakase course of many small tsumami dishes. A drinker's restaurant.",
   "faro": "The bar for a final drink.",
   "suzuya": "And the first place to send a visitor: a former geisha house turned restaurant, serving Niigata's local dishes and jizake in the old hanamachi atmosphere."},
  "money_h": "And if money is no object",
  "money": {
   "nabedyaya": "Founded in 1846; a registered cultural property at the heart of the geisha district, where geigi can still be called to your room.",
   "yukihana": "Monthly-changing kaiseki built on Niigata's seasons, up to A5 Murakami beef.",
   "ikinariya": "Nearly 300 years old; kaiseki served in detached rooms across a 6,600 m² garden.",
   "kyodai": "Omakase only, “Niigata-mae” sushi from local ingredients alone (see the sushi feature).",
   "tokiwa": "The Niigata branch of Shibata's celebrated shop; 99% Niigata ingredients, down to the seasonings."},
  "shime_h": "To finish: shime-soba",
  "shime_intro": "Niigata has a custom of finishing a night's drinking with soba — a <em>shime</em>, an epilogue in noodles. Two shops keep the custom alive deep into the night:",
  "shime": {
   "magoshiro": "Open from 7:30 p.m. until dawn; the classic way to end the night, with the old shop's hegisoba.",
   "nishibori": "Opened in spring 2026; hand-made nihachi soba and soba-mae snacks until 2:30 a.m."}},
 "ja": {
  "picks_h": "筆者のおすすめ ― 実際に行った店だけ",
  "picks": {
   "kokon": "県内外の銘酒を常時20種以上、グラス500円で。手間をかけた創作料理が肴になる、大人の酒処",
   "jikon": "居酒屋の気軽さで、割烹の料理を。新潟の食材にこだわる和食店",
   "saito": "完全予約制・1日8名まで。おまかせコースのみ、つまみを少しずつ何品も出す、酒飲みの店",
   "faro": "締めの一杯に寄りたいバー",
   "suzuya": "観光で来た方にまず勧めたい店。もとは芸妓の置屋だった建物で、花街の雰囲気の中、郷土料理と地酒を楽しめます"},
  "money_h": "そして、あなたがお金持ちなら",
  "money": {
   "nabedyaya": "弘化3年（1846年）創業。登録文化財の木造三階建てで、芸妓を呼べる古町花街の中心",
   "yukihana": "月替わりの会席で新潟の旬を。村上牛のA5まで揃います",
   "ikinariya": "300年近い歴史。2000坪の庭園と離れの座敷でいただく会席",
   "kyodai": "「新潟前」のおまかせのみ、地元の素材だけで握ります（寿司特集にも掲載）",
   "tokiwa": "新発田の名店の新潟店。食材の99%が新潟産という徹底ぶり"},
  "shime_h": "〆は蕎麦で",
  "shime_intro": "新潟には、酒の後の〆に蕎麦を食べる習慣があります。深夜まで開いている蕎麦屋があるのも、この街の魅力です。",
  "shime": {
   "magoshiro": "夜7時半から明け方まで。飲んだ後に老舗のへぎそばで〆る、古町の定番です",
   "nishibori": "2026年春に開店。深夜2時半まで、手打ちの二八蕎麦と蕎麦前で〆られます"}},
 "fr": {
  "picks_h": "Les adresses de l'auteur — uniquement des lieux où il est allé",
  "picks": {
   "kokon": "Plus de 20 sakés de tout le Japon, tous à 500 ¥ le verre, avec une cuisine créative soignée. Un bar à saké pour adultes.",
   "jikon": "Une cuisine japonaise de niveau kappo, avec la simplicité d'un izakaya, autour des produits de Niigata.",
   "saito": "Sur réservation uniquement, huit places, un seul menu omakase composé de nombreux petits tsumami. Une adresse pour buveurs.",
   "faro": "Le bar pour un dernier verre.",
   "suzuya": "Et la première adresse à conseiller à un visiteur : une ancienne maison de geishas devenue restaurant, où l'on sert la cuisine locale de Niigata et ses jizake dans l'atmosphère de l'ancien quartier des geishas."},
  "money_h": "Et si l'argent n'est pas un problème",
  "money": {
   "nabedyaya": "Fondé en 1846 ; un bâtiment classé au cœur du quartier des geishas, où l'on peut encore faire venir des geigi dans son salon.",
   "yukihana": "Un kaiseki qui change chaque mois au fil des saisons de Niigata, jusqu'au bœuf de Murakami A5.",
   "ikinariya": "Près de 300 ans d'histoire ; un kaiseki servi dans des pavillons dispersés dans un jardin de 6 600 m².",
   "kyodai": "Omakase uniquement, des sushis « Niigata-mae » faits des seuls produits locaux (voir notre dossier sushi).",
   "tokiwa": "L'adresse niigataise de la célèbre maison de Shibata ; 99 % d'ingrédients de Niigata, assaisonnements compris."},
  "shime_h": "Pour finir : le shime-soba",
  "shime_intro": "À Niigata, on termine volontiers une soirée arrosée par un soba — un <em>shime</em>, un épilogue en nouilles. Deux adresses font vivre la coutume tard dans la nuit :",
  "shime": {
   "magoshiro": "Ouvert de 19 h 30 jusqu'à l'aube ; la façon classique de finir la nuit, avec le hegisoba de cette vieille maison.",
   "nishibori": "Ouvert au printemps 2026 ; soba nihachi faits main et amuse-bouche soba-mae jusqu'à 2 h 30."}},
}

TEXT = {
 "en": dict(
   title="Furumachi — 100 Places to Eat and Drink | Niigata 2027",
   h1="Furumachi: one hundred places to eat and drink",
   intro=[
    "Furumachi, in Niigata City, is where Niigata's sake lovers gather. In the Edo period it was counted among Japan's three great geisha districts, named alongside Shinbashi in Tokyo and Gion in Kyoto — and if you are lucky, walking these streets today you may still pass a <em>geigi</em>, a geisha in full kimono, on her way to an evening engagement. High-end ryotei and humble drinking spots stand side by side along the same few streets, a short trip from Toki Messe, the hall that hosts the Niigata Sake no Jin festival each March.",
    "Sake here is chosen to match the dish, as wine is — and the food that goes with it has its own names, <em>tsumami</em> or <em>ate</em>: small plates meant to be enjoyed slowly, together with the cup. This page lists one hundred places in and around Furumachi where that culture lives: kappo counters and izakaya, sushi shops, bars open until dawn, soba for the road home, and the French and Italian restaurants scattered through the same streets.",
    "The author's own recommendations are places he has actually visited. The rest are listed as a factual directory, compiled from official sites, Tabelog and local guides in November 2026. Hours are a guide; check before you go. There is also <a href=\"furumachi-map.html\">a map of all 100</a>."],
   dir_h="The directory — all 100",
   cols=("Name", "Address", "About", "Hours", "Link"),
   link="Website",
   src="Directory compiled November 2026 from restaurant official websites and Instagram accounts, Tabelog, the Niigata Furumachi official guide and local media. The list is as of November 2026.",
   part="Part of <a href=\"index.html\">Niigata 2027 — the place two travel magazines chose</a>, an independent guide made in Niigata, Japan.",
   langbar=[("index.html", "← Niigata 2027"), ("furumachi-ja.html", "日本語版"), ("furumachi-fr.html", "Version française")]),
 "ja": dict(
   title="古町100店 ― 食べる・飲む店の全名簿 | Niigata 2027",
   h1="古町100店 ― 食べる・飲む店の全名簿",
   intro=[
    "新潟市の古町は、酒好きが集まる街です。江戸時代には日本三大花街の一つとされ、東京の新橋、京都の祇園と並び称されました。今も運が良ければ、街を歩く芸妓の姿に出会うことができます。高級料亭から大衆酒場までが同じ通りに軒を連ね、にいがた酒の陣の会場・朱鷺メッセからも行きやすい場所にあります。",
    "日本酒は料理に合わせて銘柄を選び、酒に合わせて食べる料理を「つまみ」「あて」と呼びます。このページは、古町とその周辺でその文化を味わえる店を100店、名簿としてまとめました。割烹と居酒屋、寿司、明け方まで開くバー、帰り道の蕎麦、そして同じ通りに点在するフレンチとイタリアンです。",
    "おすすめは筆者が実際に行った店だけです。それ以外は公式サイト、食べログ、地元ガイドをもとにした事実の名簿です（2026年11月調査）。営業時間は目安ですので、お出かけ前にご確認ください。<a href=\"furumachi-map-ja.html\">100店の地図</a>もあります。"],
   dir_h="名簿 ― 全100店",
   cols=("店名", "住所", "一言", "営業時間目安", "リンク"),
   link="公式サイト等",
   src="名簿は各店の公式サイト・Instagram、食べログ、新潟ふるまち公式ガイド、地元メディアをもとに2026年11月に作成。掲載内容は2026年11月現在のものです。",
   part="<a href=\"ja.html\">新潟 2027 ― 2誌が選んだ場所</a> の一部です。新潟で作った独立したガイドです。",
   langbar=[("ja.html", "← 新潟 2027"), ("furumachi.html", "English version"), ("furumachi-fr.html", "Version française")]),
 "fr": dict(
   title="Furumachi — 100 adresses pour manger et boire | Niigata 2027",
   h1="Furumachi : cent adresses pour manger et boire",
   intro=[
    "Furumachi, à Niigata City, est le quartier où se retrouvent les amateurs de saké de Niigata. À l'époque d'Edo, il comptait parmi les trois grands quartiers de geishas du Japon, cité aux côtés de Shinbashi à Tokyo et de Gion à Kyoto — et avec un peu de chance, en vous promenant dans ces rues aujourd'hui, vous croiserez peut-être encore une <em>geigi</em>, une geisha en kimono, en route pour sa soirée. Grandes tables ryotei et petits bars populaires s'y côtoient dans les mêmes rues, à quelques minutes du Toki Messe, la halle qui accueille chaque mois de mars le festival Niigata Sake no Jin.",
    "Ici, le saké se choisit en accord avec le plat, comme le vin — et les mets qui l'accompagnent ont leurs propres noms, <em>tsumami</em> ou <em>ate</em> : de petites assiettes pensées pour être savourées lentement, avec la coupe. Cette page recense cent adresses de Furumachi et des alentours où vit cette culture : comptoirs kappo et izakaya, restaurants de sushis, bars ouverts jusqu'à l'aube, soba pour le retour, et les restaurants français et italiens des mêmes rues.",
    "Les recommandations de l'auteur sont des lieux où il est réellement allé. Les autres forment un annuaire factuel, compilé à partir des sites officiels, de Tabelog et de guides locaux en novembre 2026. Les horaires sont indicatifs ; vérifiez avant de partir. Il existe aussi <a href=\"furumachi-map-fr.html\">une carte des 100 adresses</a>."],
   dir_h="L'annuaire — les 100 adresses",
   cols=("Nom", "Adresse", "À propos", "Horaires", "Lien"),
   link="Site officiel",
   src="Annuaire compilé en novembre 2026 à partir des sites officiels et comptes Instagram des établissements, de Tabelog, du guide officiel de Niigata Furumachi et de médias locaux. Liste arrêtée à novembre 2026.",
   part="Page du guide <a href=\"fr.html\">Niigata 2027 — l'endroit choisi par deux magazines de voyage</a>, un guide indépendant réalisé à Niigata, au Japon.",
   langbar=[("fr.html", "← Niigata 2027"), ("furumachi.html", "English version"), ("furumachi-ja.html", "日本語版")]),
}
NOTE_KEY = {"en": "note_en", "ja": "note_ja", "fr": "note_fr"}
HOURS_IDX = {"en": 1, "ja": 0, "fr": 2}

def name_html(s, lang):
    disp = s["ja"] if lang == "ja" else s["en"]
    sub = "" if lang == "ja" else f"<br><span class='jp'>{s['ja']}</span>"
    if s["url"]:
        return f"<a href=\"{s['url']}\"><strong>{disp}</strong></a>{sub}"
    return f"<strong>{disp}</strong>{sub}"

def rec_block(lang):
    t = REC_TEXT[lang]
    out = []
    def group(h, items):
        lis = []
        for slug, text in items.items():
            s = BY_SLUG[slug]
            nm = name_html(s, lang)
            lis.append(f"<li>{nm} — {text}</li>")
        return f"<h3>{h}</h3>\n<ul>\n" + "\n".join(lis) + "\n</ul>"
    out.append(group(t["picks_h"], t["picks"]))
    out.append(group(t["money_h"], t["money"]))
    out.append(f"<h3>{t['shime_h']}</h3>\n<p>{t['shime_intro']}</p>\n<ul>\n" +
               "\n".join(f"<li>{name_html(BY_SLUG[sl], lang)} — {tx}</li>" for sl, tx in t["shime"].items()) + "\n</ul>")
    return "\n".join(out)

def furumachi_page(lang):
    t = TEXT[lang]
    nk, hi = NOTE_KEY[lang], HOURS_IDX[lang]
    intro = "\n".join(f"<p>{p}</p>" for p in t["intro"])
    sections = []
    for g in GENRES:
        rows = [s for s in SHOPS if s["genre"] == g]
        trs = []
        for s in rows:
            link = f"<a href=\"{s['url']}\">{t['link']}</a>" if s["url"] else "—"
            trs.append(f"<tr class=\"shop\"><td>{name_html(s, lang)}</td><td>{s['addr']}</td>"
                       f"<td>{s[nk]}</td><td>{s['hours'][hi]}</td><td>{link}</td></tr>")
        sections.append(f"<section>\n<h2>{t and GENRE_TITLES[lang][g]} ({len(rows)})</h2>\n"
                        f"<div class=\"tablewrap\"><table>\n<tr>{''.join(f'<th>{c}</th>' for c in t['cols'])}</tr>\n"
                        + "\n".join(trs) + "\n</table></div>\n</section>")
    langbar = " · ".join(f"<a href=\"{h}\">{x}</a>" for h, x in t["langbar"])
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t['title']}</title>
<style>
  :root {{ --ink:#1d2a24; --accent:#1f5c3d; --vermillion:#b3402a; --paper:#faf7f0; --card:#ffffff; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: Georgia, 'Times New Roman', serif; color:var(--ink); background:var(--paper); line-height:1.65; }}
  .lang {{ max-width:960px; margin:0 auto; padding:.8rem 1.2rem 0; text-align:right; font-size:.9rem; }}
  main {{ max-width:960px; margin:0 auto; padding:0 1.2rem 3rem; }}
  h1 {{ font-size:clamp(1.5rem, 4vw, 2.3rem); color:var(--accent); line-height:1.3; }}
  h2 {{ font-size:1.35rem; color:var(--accent); border-bottom:3px solid var(--vermillion); padding-bottom:.3rem; margin-top:2.4rem; }}
  h3 {{ font-size:1.1rem; color:var(--accent); margin-top:1.8rem; }}
  table {{ width:100%; border-collapse:collapse; font-size:.92rem; background:var(--card); }}
  th, td {{ border:1px solid #ddd5c3; padding:.45rem .55rem; text-align:left; vertical-align:top; }}
  th {{ background:#f1ebdd; }}
  .jp {{ color:#5c665f; font-size:.85em; }}
  .note {{ font-size:.88rem; color:#444; background:#fff; border:1px solid #ddd5c3; border-left:5px solid var(--vermillion); padding:.8rem 1rem; }}
  a {{ color:var(--accent); }}
  footer {{ border-top:1px solid #ddd5c3; margin-top:3rem; padding-top:1.2rem; font-size:.85rem; color:#5c665f; }}
  .tablewrap {{ overflow-x:auto; }}
</style>
</head>
<body>
<div class="lang">{langbar}</div>
<main>
<h1>{t['h1']}</h1>
{intro}
<div class="note">
{rec_block(lang)}
</div>
<h2>{t['dir_h']}</h2>
{''.join(sections)}
<p style="font-size:.85rem;color:#5c665f">{t['src']}</p>
<footer>
  <p>{t['part']}</p>
  <p>Powered by <a href="https://public-dl.github.io/wooltech/">WoolTech</a></p>
</footer>
</main>
<script data-goatcounter="https://niigata2027.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
</body>
</html>"""

# === Furumachi map template (from data/build_furumachi_map.py) ===
ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"
OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

def furumachi_map_page(lang):
    if lang == "en":
        title = "Map — Furumachi's 100 Places | Niigata 2027"
        h1 = "The Furumachi map: one hundred places to eat and drink"
        intro = ("All 100 places from <a href='furumachi.html'>the Furumachi directory</a>, plotted. "
                 "Click a pin for the shop's note, hours and website. Pins are coloured by genre. "
                 f"{NFULL} pins sit on the shop's exact street number; the rest are placed at street or block level, so treat each pin as “on this street, around here”.")
        back, backhref, o1, o1h, o2, o2h = "← Furumachi: 100 places", "furumachi.html", "日本語版", "furumachi-map-ja.html", "Version française", "furumachi-map-fr.html"
        legend = {"jp": "Japanese / kappo / izakaya", "sushi": "Sushi", "bar": "Bars", "soba": "Soba & noodles", "west": "French / Italian / Western", "other": "Yakitori & more"}
        popup = """`<strong>${p.en}</strong><br><span style="color:#5c665f">${p.ja}</span><br>${p.note_en}<br>${p.hours[1]}` +
          (p.url ? `<br><a href="${p.url}" target="_blank" rel="noopener">Official website</a>` : "")"""
        tooltip = "p.en"
        names_label = "Show names"
        tile_url, tile_attr = ESRI, "Esri, OpenStreetMap contributors"
        src_note = "Addresses checked November 2026 against official websites, Tabelog and local guides; coordinates from Japan's Geospatial Information Authority address search. Base map: Esri World Street Map, with place names in Japanese and English; map data © OpenStreetMap contributors."
        geojson_note = 'The plotted data is also published as <a href="furumachi.geojson">furumachi.geojson</a>.'
        part = "Part of <a href=\"index.html\">Niigata 2027 — the place two travel magazines chose</a>, an independent guide made in Niigata, Japan."
    elif lang == "fr":
        title = "Carte — Les 100 adresses de Furumachi | Niigata 2027"
        h1 = "La carte de Furumachi : cent adresses pour manger et boire"
        intro = ("Les 100 adresses de <a href='furumachi-fr.html'>l'annuaire de Furumachi</a>, placées sur la carte. "
                 "Cliquez sur un repère pour la note, les horaires et le site de l'établissement. Les repères sont colorés par genre. "
                 f"{NFULL} repères sont sur le numéro exact de l'établissement ; les autres sont placés au niveau de la rue ou du pâté de maisons — considérez chaque repère comme « dans cette rue, par ici ».")
        back, backhref, o1, o1h, o2, o2h = "← Furumachi : 100 adresses", "furumachi-fr.html", "English version", "furumachi-map.html", "日本語版", "furumachi-map-ja.html"
        legend = {"jp": "Japonais / kappo / izakaya", "sushi": "Sushis", "bar": "Bars", "soba": "Soba & nouilles", "west": "Français / italien / occidental", "other": "Yakitori & autres"}
        popup = """`<strong>${p.en}</strong><br><span style="color:#5c665f">${p.ja}</span><br>${p.note_fr}<br>${p.hours[2]}` +
          (p.url ? `<br><a href="${p.url}" target="_blank" rel="noopener">Site officiel</a>` : "")"""
        tooltip = "p.en"
        names_label = "Afficher les noms"
        tile_url, tile_attr = ESRI, "Esri, OpenStreetMap contributors"
        src_note = "Adresses vérifiées en novembre 2026 sur les sites officiels, Tabelog et des guides locaux ; coordonnées issues de la recherche d'adresses de l'Autorité d'information géospatiale du Japon. Fond de carte : Esri World Street Map, noms de lieux en japonais et en anglais ; données cartographiques © OpenStreetMap contributors."
        geojson_note = 'Les données sont aussi publiées au format <a href="furumachi.geojson">furumachi.geojson</a>.'
        part = "Page du guide <a href=\"fr.html\">Niigata 2027 — l'endroit choisi par deux magazines de voyage</a>, un guide indépendant réalisé à Niigata, au Japon."
    else:
        title = "古町100店マップ | Niigata 2027"
        h1 = "古町100店マップ"
        intro = ("<a href='furumachi-ja.html'>古町100店の名簿</a>の全店を地図に落としました。"
                 "ピンを押すと、店の一言・営業時間目安・公式サイトが表示されます。色はジャンル別です。"
                 f"{NFULL}店は番地まで特定した位置、それ以外は通り・番町レベルの位置ですので、ピンは「この通りのこのあたり」とお考えください。")
        back, backhref, o1, o1h, o2, o2h = "← 古町100店", "furumachi-ja.html", "English version", "furumachi-map.html", "Version française", "furumachi-map-fr.html"
        legend = {"jp": "日本料理・割烹・居酒屋", "sushi": "寿司", "bar": "バー", "soba": "蕎麦・麺", "west": "フレンチ・イタリアン・洋食", "other": "焼鳥・その他"}
        popup = """`<strong>${p.ja}</strong><br>${p.note_ja}<br>${p.hours[0]}` +
          (p.url ? `<br><a href="${p.url}" target="_blank" rel="noopener">公式サイト等</a>` : "")"""
        tooltip = "p.ja"
        names_label = "店名を表示"
        tile_url, tile_attr = OSM, "&copy; OpenStreetMap contributors"
        src_note = "住所は各店の公式サイト、食べログ、地元ガイドで2026年11月に確認。座標は国土地理院の住所検索による。地図 © OpenStreetMap contributors。"
        geojson_note = 'プロットしたデータは <a href="furumachi.geojson">furumachi.geojson</a> でも公開しています。'
        part = "<a href=\"ja.html\">新潟 2027 ― 2誌が選んだ場所</a> の一部です。新潟で作った独立したガイドです。"
    legend_items = "".join(
        f'<span class="lg"><span class="dot" style="background:{GENRE_COLORS[k]}"></span>{v}</span>'
        for k, v in legend.items())
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  :root {{ --ink:#1d2a24; --accent:#1f5c3d; --vermillion:#b3402a; --paper:#faf7f0; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: Georgia, 'Times New Roman', serif; color:var(--ink); background:var(--paper); line-height:1.65; }}
  .lang {{ max-width:1060px; margin:0 auto; padding:.8rem 1.2rem 0; text-align:right; font-size:.9rem; }}
  main {{ max-width:1060px; margin:0 auto; padding:0 1.2rem 3rem; }}
  h1 {{ font-size:clamp(1.5rem, 4vw, 2.2rem); color:var(--accent); line-height:1.3; }}
  #map {{ height: 72vh; min-height:420px; border:1px solid #ddd5c3; }}
  .legend {{ margin:.7rem 0; font-size:.92rem; }}
  .lg {{ margin-right:1.1rem; white-space:nowrap; }}
  .dot {{ display:inline-block; width:.8em; height:.8em; border-radius:50%; margin-right:.35em; border:1px solid #fff; box-shadow:0 0 0 1px #999; }}
  .leaflet-tooltip.name-label {{ background:rgba(255,255,255,.85); border:1px solid rgba(29,42,36,.25); color:#1d2a24; font-size:11px; line-height:1.3; padding:0 4px; border-radius:3px; box-shadow:0 1px 2px rgba(0,0,0,.15); pointer-events:none; }}
  .leaflet-tooltip.name-label:before {{ display:none; }}
  #map .name-label {{ display:none; }}
  #map.show-names .name-label {{ display:block; }}
  a {{ color:var(--accent); }}
  footer {{ border-top:1px solid #ddd5c3; margin-top:2rem; padding-top:1.2rem; font-size:.85rem; color:#5c665f; }}
</style>
</head>
<body>
<div class="lang"><a href="{backhref}">{back}</a> · <a href="{o1h}">{o1}</a> · <a href="{o2h}">{o2}</a></div>
<main>
<h1>{h1}</h1>
<p>{intro}</p>
<div class="legend">{legend_items}<label style="margin-left:1rem"><input type="checkbox" id="showNames"> {names_label}</label></div>
<div id="map"></div>
<p style="font-size:.85rem;color:#5c665f">{src_note} {geojson_note}</p>
<footer>
  <p>{part}</p>
  <p>Powered by <a href="https://public-dl.github.io/wooltech/">WoolTech</a></p>
</footer>
</main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = {data_js};
const COLORS = {colors_js};
const map = L.map('map');
L.tileLayer('{tile_url}', {{
  maxZoom: 18, attribution: '{tile_attr}'
}}).addTo(map);
const layer = L.geoJSON(DATA, {{
  pointToLayer: (f, latlng) => L.circleMarker(latlng, {{
    radius: 7, color: '#ffffff', weight: 1.5,
    fillColor: COLORS[f.properties.genre] || '#333333', fillOpacity: 0.9
  }}),
  onEachFeature: (f, l) => {{
    const p = f.properties;
    l.bindPopup({popup});
    l.bindTooltip({tooltip}, {{ permanent: true, direction: 'top', offset: [0, -9], className: 'name-label', interactive: false }});
  }}
}}).addTo(map);
map.fitBounds(layer.getBounds().pad(0.08));
const LABEL_ZOOM = 16;
let namesOverride = null;
const namesBox = document.getElementById('showNames');
function updateLabels() {{
  const show = namesOverride !== null ? namesOverride : map.getZoom() >= LABEL_ZOOM;
  document.getElementById('map').classList.toggle('show-names', show);
  namesBox.checked = show;
}}
map.on('zoomend', () => {{ if (namesOverride === null) updateLabels(); }});
namesBox.addEventListener('change', () => {{ namesOverride = namesBox.checked; updateLabels(); }});
updateLabels();
</script>
<script data-goatcounter="https://niigata2027.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
</body>
</html>"""

# === Brewery map template (from data/build_map.py) ===
REGION_COLORS = {"下越": "#1f5c3d", "中越": "#b3402a", "上越": "#20508c", "佐渡": "#6b3fa0"}
def brewery_map_page(lang):
    if lang == "en":
        title = "Map of Niigata's Sake Breweries | Niigata 2027"
        h1 = "Niigata's sake breweries, on the map"
        intro = ("Every brewery in the Niigata Sake Brewers Association's directory, plotted. "
                 "Colours mark the four regions — Kaetsu (north), Chuetsu (centre), Joetsu (west) and Sado Island. "
                 "Click a pin for the brewery's brand, founding year and whether it accepts visitors. "
                 "Most pins sit on the brewery's exact address; a few are placed at district level. "
                 "See also <a href='sake.html'>the complete list</a>.")
        back, backhref, other, otherhref = "← Niigata 2027", "index.html", "日本語版", "map-ja.html"
        other2, other2href = "Version française", "map-fr.html"
        legend = {"下越": "Kaetsu", "中越": "Chuetsu", "上越": "Joetsu", "佐渡": "Sado"}
        tours_label = "Breweries offering tours only"
        popup = """`<strong>${p.name_en}</strong><br><span style="color:#5c665f">${p.name_ja}</span><br>${p.municipality_en}` +
          (p.brand_en ? `<br>Brand: ${p.brand_en}` : "") +
          (p.founded ? `<br>Founded: ${p.founded}` : "") +
          `<br>Tours: ${p.tours ? "Yes" : "—"}` +
          (p.url ? `<br><a href="${p.url}" target="_blank" rel="noopener">Official website</a>` : "")"""
        tooltip = "p.name_en"
        names_label = "Show names"
        tile_url = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"
        tile_attr = "Esri, OpenStreetMap contributors"
        src_note = "Data: Niigata Sake Brewers Association brewery directory (as of 23 November 2026); English names cross-checked against the National Tax Agency's English sake brewery map (2021). Base map: Esri World Street Map, with place names in Japanese and English; map data © OpenStreetMap contributors. The plotted data is also published as <a href=\"breweries.geojson\">breweries.geojson</a>."
        part = "Part of <a href=\"index.html\">Niigata 2027 — the place two travel magazines chose</a>, an independent guide made in Niigata, Japan."
    elif lang == "fr":
        title = "Carte des brasseries de saké de Niigata | Niigata 2027"
        h1 = "Les brasseries de saké de Niigata, sur la carte"
        intro = ("Toutes les brasseries de l'annuaire de l'Association des brasseurs de saké de Niigata, placées sur la carte. "
                 "Les couleurs distinguent les quatre régions — Kaetsu (nord), Chuetsu (centre), Joetsu (ouest) et l'île de Sado. "
                 "Cliquez sur un repère pour la marque, l'année de fondation et les visites possibles. "
                 "La plupart des repères sont sur l'adresse exacte de la brasserie ; quelques-uns sont placés au niveau du quartier. "
                 "Voir aussi <a href='sake-fr.html'>la liste complète</a>.")
        back, backhref, other, otherhref = "← Niigata 2027", "fr.html", "English version", "map.html"
        other2, other2href = "日本語版", "map-ja.html"
        legend = {"下越": "Kaetsu", "中越": "Chuetsu", "上越": "Joetsu", "佐渡": "Sado"}
        tours_label = "Brasseries proposant des visites uniquement"
        popup = """`<strong>${p.name_en}</strong><br><span style="color:#5c665f">${p.name_ja}</span><br>${p.municipality_en}` +
          (p.brand_en ? `<br>Marque : ${p.brand_en}` : "") +
          (p.founded ? `<br>Fondation : ${p.founded}` : "") +
          `<br>Visites : ${p.tours ? "Oui" : "—"}` +
          (p.url ? `<br><a href="${p.url}" target="_blank" rel="noopener">Site officiel</a>` : "")"""
        tooltip = "p.name_en"
        names_label = "Afficher les noms"
        tile_url = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"
        tile_attr = "Esri, OpenStreetMap contributors"
        src_note = "Données : annuaire des brasseries de l'Association des brasseurs de saké de Niigata (au 23 novembre 2026) ; noms en caractères latins vérifiés dans la carte anglaise des brasseries de l'Agence nationale des impôts (2021). Fond de carte : Esri World Street Map, noms de lieux en japonais et en anglais ; données cartographiques © OpenStreetMap contributors. Les données sont aussi publiées au format <a href=\"breweries.geojson\">breweries.geojson</a>."
        part = "Page du guide <a href=\"fr.html\">Niigata 2027 — l'endroit choisi par deux magazines de voyage</a>, un guide indépendant réalisé à Niigata, au Japon."
    else:
        title = "新潟の酒蔵マップ | Niigata 2027"
        h1 = "新潟の酒蔵マップ"
        intro = ("新潟県酒造組合の蔵元紹介に載る全蔵を地図に落としました。"
                 "色は4つの地域（下越・中越・上越・佐渡）を示します。"
                 "ピンを押すと、代表銘柄・創業年・見学の可否が表示されます。"
                 "ほとんどのピンは蔵の住所そのものですが、一部は地区レベルの位置です。"
                 "一覧は<a href='sake-ja.html'>新潟の酒蔵 全一覧</a>へ。")
        back, backhref, other, otherhref = "← 新潟 2027", "ja.html", "English version", "map.html"
        other2, other2href = "Version française", "map-fr.html"
        legend = {"下越": "下越", "中越": "中越", "上越": "上越", "佐渡": "佐渡"}
        tours_label = "見学できる蔵だけ"
        popup = """`<strong>${p.name_ja}</strong><br>${p.municipality_ja}` +
          (p.brand_ja ? `<br>代表銘柄：${p.brand_ja}` : "") +
          (p.founded ? `<br>創業：${p.founded}年` : "") +
          `<br>見学：${p.tours ? "あり" : "—"}` +
          (p.url ? `<br><a href="${p.url}" target="_blank" rel="noopener">公式サイト</a>` : "")"""
        tooltip = "p.name_ja"
        names_label = "店名を表示"
        tile_url = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        tile_attr = "&copy; OpenStreetMap contributors"
        src_note = "データ：新潟県酒造組合「蔵元紹介」（2026年11月23日現在）。英語表記は国税局の英語版酒蔵マップ（2021年）で照合。地図 © OpenStreetMap contributors。プロットしたデータは <a href=\"breweries.geojson\">breweries.geojson</a> でも公開しています。"
        part = "<a href=\"ja.html\">新潟 2027 ― 2誌が選んだ場所</a> の一部です。新潟で作った独立したガイドです。"
    legend_items = "".join(
        f'<span class="lg"><span class="dot" style="background:{REGION_COLORS[k]}"></span>{v}</span>'
        for k, v in legend.items())
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  :root {{ --ink:#1d2a24; --accent:#1f5c3d; --vermillion:#b3402a; --paper:#faf7f0; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: Georgia, 'Times New Roman', serif; color:var(--ink); background:var(--paper); line-height:1.65; }}
  .lang {{ max-width:1060px; margin:0 auto; padding:.8rem 1.2rem 0; text-align:right; font-size:.9rem; }}
  main {{ max-width:1060px; margin:0 auto; padding:0 1.2rem 3rem; }}
  h1 {{ font-size:clamp(1.5rem, 4vw, 2.2rem); color:var(--accent); line-height:1.3; }}
  #map {{ height: 72vh; min-height:420px; border:1px solid #ddd5c3; }}
  .legend {{ margin:.7rem 0; font-size:.92rem; }}
  .lg {{ margin-right:1.1rem; white-space:nowrap; }}
  .dot {{ display:inline-block; width:.8em; height:.8em; border-radius:50%; margin-right:.35em; border:1px solid #fff; box-shadow:0 0 0 1px #999; }}
  .leaflet-tooltip.name-label {{ background:rgba(255,255,255,.85); border:1px solid rgba(29,42,36,.25); color:#1d2a24; font-size:11px; line-height:1.3; padding:0 4px; border-radius:3px; box-shadow:0 1px 2px rgba(0,0,0,.15); pointer-events:none; }}
  .leaflet-tooltip.name-label:before {{ display:none; }}
  #map .name-label {{ display:none; }}
  #map.show-names .name-label {{ display:block; }}
  a {{ color:var(--accent); }}
  footer {{ border-top:1px solid #ddd5c3; margin-top:2rem; padding-top:1.2rem; font-size:.85rem; color:#5c665f; }}
</style>
</head>
<body>
<div class="lang"><a href="{backhref}">{back}</a> · <a href="{otherhref}">{other}</a> · <a href="{other2href}">{other2}</a></div>
<main>
<h1>{h1}</h1>
<p>{intro}</p>
<div class="legend">{legend_items}
<label style="margin-left:1rem"><input type="checkbox" id="toursOnly"> {tours_label}</label><label style="margin-left:1rem"><input type="checkbox" id="showNames"> {names_label}</label></div>
<div id="map"></div>
<p style="font-size:.85rem;color:#5c665f">{src_note}</p>
<footer>
  <p>{part}</p>
  <p>Powered by <a href="https://public-dl.github.io/wooltech/">WoolTech</a></p>
</footer>
</main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = {data_js};
const COLORS = {colors_js};
const map = L.map('map');
L.tileLayer('{tile_url}', {{
  maxZoom: 18, attribution: '{tile_attr}'
}}).addTo(map);
let layer = null;
function draw() {{
  const toursOnly = document.getElementById('toursOnly').checked;
  if (layer) map.removeLayer(layer);
  layer = L.geoJSON(DATA, {{
    filter: f => !toursOnly || f.properties.tours,
    pointToLayer: (f, latlng) => L.circleMarker(latlng, {{
      radius: 7, color: '#ffffff', weight: 1.5,
      fillColor: COLORS[f.properties.region_ja] || '#333333', fillOpacity: 0.9
    }}),
    onEachFeature: (f, l) => {{
      const p = f.properties;
      l.bindPopup({popup});
      l.bindTooltip({tooltip}, {{ permanent: true, direction: 'top', offset: [0, -9], className: 'name-label', interactive: false }});
    }}
  }}).addTo(map);
  return layer;
}}
const full = draw();
map.fitBounds(full.getBounds().pad(0.05));
document.getElementById('toursOnly').addEventListener('change', draw);
const LABEL_ZOOM = 10;
let namesOverride = null;
const namesBox = document.getElementById('showNames');
function updateLabels() {{
  const show = namesOverride !== null ? namesOverride : map.getZoom() >= LABEL_ZOOM;
  document.getElementById('map').classList.toggle('show-names', show);
  namesBox.checked = show;
}}
map.on('zoomend', () => {{ if (namesOverride === null) updateLabels(); }});
namesBox.addEventListener('change', () => {{ namesOverride = namesBox.checked; updateLabels(); }});
updateLabels();
</script>
<script data-goatcounter="https://niigata2027.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Glue: data loading, validation, geojson building, SEO application, main.
# ---------------------------------------------------------------------------

def fail(msg):
    print("BUILD FAILED:", msg, file=sys.stderr)
    sys.exit(1)

def founding_map_value(raw):
    """Brewery-map 'founded' value: int year, '1850s', or None."""
    f = raw.replace("西暦", "").strip()
    if f in ("", "不明"):
        return None
    if f == "安政年間":
        return "1850s"
    m = re.match(r"(\d{4})", f)
    return int(m.group(1)) if m else f

def load_data():
    fpath = DATA_DIR / "furumachi.json"
    bpath = DATA_DIR / "breweries.json"
    try:
        shops = json.loads(fpath.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"cannot read {fpath}: {e}")
    try:
        brews = json.loads(bpath.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"cannot read {bpath}: {e}")
    if len(shops) != 100:
        fail(f"data/furumachi.json must contain exactly 100 shops, found {len(shops)}")
    if len(brews) != 92:
        fail(f"data/breweries.json must contain exactly 92 breweries, found {len(brews)}")
    n_rec = sum(1 for s in shops if s.get("rec"))
    if n_rec != 12:
        fail(f"data/furumachi.json must have exactly 12 entries with 'rec' set, found {n_rec}")
    for s in shops:
        if not isinstance(s.get("lat"), (int, float)) or not isinstance(s.get("lng"), (int, float)):
            fail(f"furumachi entry '{s.get('slug', '?')}' has no lat/lng — geocode it first (see docs/updating.md)")
    for b in brews:
        if not isinstance(b.get("lat"), (int, float)) or not isinstance(b.get("lng"), (int, float)):
            fail(f"brewery entry '{b.get('slug', '?')}' has no lat/lng — geocode it first (see docs/updating.md)")
    slugs = [s["slug"] for s in shops]
    if len(set(slugs)) != len(slugs):
        fail("data/furumachi.json contains duplicate slugs")
    bslugs = [b["slug"] for b in brews]
    if len(set(bslugs)) != len(bslugs):
        fail("data/breweries.json contains duplicate slugs")
    return shops, brews

def furumachi_geojson(shops):
    global NFULL
    NFULL = sum(1 for s in shops if s["precision"] == "full")
    features = []
    for s in shops:
        props = {k: v for k, v in s.items() if k not in ("lat", "lng", "precision")}
        props["hours"] = list(s["hours"])
        props["precision"] = s["precision"]
        features.append({"type": "Feature",
                         "geometry": {"type": "Point", "coordinates": [s["lng"], s["lat"]]},
                         "properties": props})
    return {"type": "FeatureCollection", "features": features}

def breweries_geojson(brews):
    features = []
    for b in brews:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [b["lng"], b["lat"]]},
            "properties": {
                "name_en": b["name_en"], "name_ja": b["name_ja"],
                "brand_en": b["brand_en"], "brand_ja": b["brand_ja"],
                "municipality_en": b["municipality_en"],
                "municipality_ja": b["municipality_ja"],
                "region_ja": b["region"],
                "founded": founding_map_value(b["founding"]),
                "tours": b["tours"], "url": b["url"],
                "precision": b["precision"],
            },
        })
    return {"type": "FeatureCollection", "features": features}

def seo_transform(fname, s):
    """The apply_seo.py logic, in memory: refresh the SEO head block."""
    m = PAGES[fname]
    if 'rel="canonical"' in s:
        s = OLD_BLOCK.sub("", s, count=1)
    if '<meta name="description"' not in s:
        desc_line = '<meta name="description" content="' + esc(m["desc"]) + '">'
        s = re.sub(r"(</title>)", lambda mo: mo.group(1) + "\n" + desc_line, s, count=1)
    anchor = None
    for line in s.splitlines():
        if '<meta name="description"' in line:
            anchor = line
            break
    if not anchor:
        fail(f"{fname}: no meta description anchor found")
    return s.replace(anchor, anchor + "\n" + block(fname, m).rstrip(), 1)

def sitemap_text():
    entries = []
    for g in GROUPS:
        for f in g:
            entries.append(f"""  <url>
    <loc>{url_of(f)}</loc>
    <lastmod>2026-11-25</lastmod>
  </url>""")
    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
""" + "\n".join(entries) + "\n</urlset>\n"

GENERATED_HTML = ["furumachi.html", "furumachi-ja.html", "furumachi-fr.html",
                  "furumachi-map.html", "furumachi-map-ja.html", "furumachi-map-fr.html",
                  "sake.html", "sake-ja.html", "sake-fr.html",
                  "map.html", "map-ja.html", "map-fr.html"]
HANDWRITTEN_HTML = ["index.html", "ja.html", "fr.html",
                    "sushi.html", "sushi-ja.html", "sushi-fr.html",
                    "sushi-map.html", "sushi-map-ja.html", "sushi-map-fr.html"]

def main():
    global SHOPS, BY_SLUG, recs, data_js, colors_js
    shops, brews = load_data()
    SHOPS = shops
    BY_SLUG = {s["slug"]: s for s in shops}
    # The sake templates were written against the association-scrape record
    # shape; adapt the JSON entries to it.
    recs = [{"slug": b["slug"], "name": b["name_ja"],
             "brand": b["brand_ja"] or "", "tour": "あり" if b["tours"] else "なし",
             "url": b["url"] or "", "founding": b["founding"],
             "municipality": b["municipality_ja"], "region": b["region"]}
            for b in brews]

    outputs = {}  # repo-relative path -> text

    # Furumachi directory pages
    outputs["furumachi.html"] = furumachi_page("en")
    outputs["furumachi-ja.html"] = furumachi_page("ja")
    outputs["furumachi-fr.html"] = furumachi_page("fr")

    # Furumachi map + geojson
    fgj = furumachi_geojson(shops)
    outputs["furumachi.geojson"] = json.dumps(fgj, ensure_ascii=False, indent=1)
    data_js = json.dumps(fgj, ensure_ascii=False)
    colors_js = json.dumps(GENRE_COLORS, ensure_ascii=False)
    outputs["furumachi-map.html"] = furumachi_map_page("en")
    outputs["furumachi-map-ja.html"] = furumachi_map_page("ja")
    outputs["furumachi-map-fr.html"] = furumachi_map_page("fr")

    # Sake brewery pages
    outputs["sake.html"] = build_en()
    outputs["sake-ja.html"] = build_ja()
    outputs["sake-fr.html"] = build_fr()

    # Brewery map + geojson
    bgj = breweries_geojson(brews)
    outputs["breweries.geojson"] = json.dumps(bgj, ensure_ascii=False, indent=1)
    data_js = json.dumps(bgj, ensure_ascii=False)
    colors_js = json.dumps(REGION_COLORS, ensure_ascii=False)
    outputs["map.html"] = brewery_map_page("en")
    outputs["map-ja.html"] = brewery_map_page("ja")
    outputs["map-fr.html"] = brewery_map_page("fr")

    # SEO blocks on every page (generated ones get them fresh; the
    # hand-written pages are refreshed in place, as apply_seo.py did).
    for fname in GENERATED_HTML:
        outputs[fname] = seo_transform(fname, outputs[fname])
    for fname in HANDWRITTEN_HTML:
        p = ROOT_DIR / fname
        if not p.exists():
            fail(f"missing page {fname} (expected in the repository)")
        outputs[fname] = seo_transform(fname, p.read_text(encoding="utf-8"))
    outputs["sitemap.xml"] = sitemap_text()
    outputs["robots.txt"] = f"User-agent: *\nAllow: /\n\nSitemap: {ROOT}sitemap.xml\n"

    # ---- validation of the generated output (nothing written yet) ----
    for name, text in outputs.items():
        if "★" in text:
            fail(f"{name}: contains a ★ character, which must never appear")
    for fname in ("map.html", "map-ja.html", "map-fr.html"):
        if "LABEL_ZOOM = 10" not in outputs[fname]:
            fail(f"{fname}: brewery map must contain 'LABEL_ZOOM = 10'")
    for fname in ("furumachi-map.html", "furumachi-map-ja.html", "furumachi-map-fr.html"):
        if "LABEL_ZOOM = 16" not in outputs[fname]:
            fail(f"{fname}: Furumachi map must contain 'LABEL_ZOOM = 16'")
    for fname in ("furumachi.html", "furumachi-ja.html", "furumachi-fr.html"):
        n = outputs[fname].count('<tr class="shop">')
        if n != 100:
            fail(f"{fname}: expected 100 shop rows, found {n}")
    if len(json.loads(outputs["furumachi.geojson"])["features"]) != 100:
        fail("furumachi.geojson must contain 100 features")
    if len(json.loads(outputs["breweries.geojson"])["features"]) != 92:
        fail("breweries.geojson must contain 92 features")

    # ---- all checks passed: write ----
    for name, text in outputs.items():
        (ROOT_DIR / name).write_text(text, encoding="utf-8")
    print(f"build_site: wrote {len(outputs)} files "
          f"(100 furumachi shops, 92 breweries, 12 recommended)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
