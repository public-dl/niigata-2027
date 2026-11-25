#!/usr/bin/env python3
# Weekly link check for the Niigata 2027 site. Runs on GitHub Actions
# (see .github/workflows/link-check.yml) — never from a chat session.
# Reads the canonical data files (data/furumachi.json, data/breweries.json),
# fetches every official URL, and writes reports/link-check.md (human
# summary) and reports/link-check.json (machine-readable; the workflow
# opens/updates a GitHub Issue when "dead" links are found).
# Classification: ok (2xx/3xx), dead (404/410), restricted (401/403/429
# rate limits, and 400 from facebook.com — bot responses, not dead pages),
# error (5xx, DNS, timeout, SSL; retried once).
import concurrent.futures, datetime, json, pathlib, ssl, sys, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "reports"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 20

def targets():
    out = []
    breweries = json.loads((ROOT / "data/breweries.json").read_text())
    for b in breweries:
        if b.get("url"):
            out.append(("酒蔵", b["name_ja"], b["url"].strip()))
    shops = json.loads((ROOT / "data/furumachi.json").read_text())
    for s in shops:
        if s.get("url"):
            out.append(("古町", s["ja"], s["url"].strip()))
    return out

def fetch(url, method):
    req = urllib.request.Request(url, method=method,
                                 headers={"User-Agent": UA,
                                          "Accept": "text/html,application/xhtml+xml,*/*"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
        resp.read(2048)
        return resp.status

def check(item):
    kind, name, url = item
    last = None
    for attempt in range(2):
        try:
            try:
                status = fetch(url, "HEAD")
            except urllib.error.HTTPError as e:
                if e.code in (405, 501):
                    status = fetch(url, "GET")
                else:
                    raise
            return (kind, name, url, "ok" if status < 400 else "error", str(status))
        except urllib.error.HTTPError as e:
            last = str(e.code)
            if e.code in (404, 410):
                return (kind, name, url, "dead", last)
            if e.code in (401, 403, 429) or (e.code == 400 and "facebook.com" in url):
                return (kind, name, url, "restricted", last)
            if attempt == 1:
                return (kind, name, url, "error", last)
        except Exception as e:
            last = type(e).__name__ + ": " + str(e)[:80]
            if attempt == 1:
                return (kind, name, url, "error", last)
    return (kind, name, url, "error", last or "?")

def main():
    items = targets()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(check, items))
    buckets = {"ok": [], "dead": [], "restricted": [], "error": []}
    for r in results:
        buckets[r[3]].append(r)
    today = datetime.date.today().isoformat()
    OUT.mkdir(exist_ok=True)
    lines = [f"# リンクチェック {today}",
             f"対象 {len(items)} 件（酒蔵と古町の公式リンク等）: "
             f"正常 {len(buckets['ok'])} / リンク切れ {len(buckets['dead'])} / "
             f"制限の可能性 {len(buckets['restricted'])} / エラー {len(buckets['error'])}", ""]
    for key, label in (("dead", "## リンク切れ（404/410）"),
                       ("error", "## エラー（5xx・接続不可など）"),
                       ("restricted", "## アクセス制限の可能性（401/403など、自動アクセス遮断）")):
        if buckets[key]:
            lines.append(label)
            for kind, name, url, _, detail in sorted(buckets[key]):
                lines.append(f"- [{kind}] {name} — {url} （{detail}）")
            lines.append("")
    (OUT / "link-check.md").write_text("\n".join(lines))
    (OUT / "link-check.json").write_text(json.dumps(
        {"date": today, "total": len(items),
         "counts": {k: len(v) for k, v in buckets.items()},
         "dead": [list(r) for r in buckets["dead"]],
         "errors": [list(r) for r in buckets["error"]],
         "restricted": [list(r) for r in buckets["restricted"]]},
        ensure_ascii=False, indent=1))
    print("\n".join(lines))

if __name__ == "__main__":
    main()
