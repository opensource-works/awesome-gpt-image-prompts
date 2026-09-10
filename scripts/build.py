#!/usr/bin/env python3
"""Render data/posts.json into the GitHub Pages gallery and both READMEs."""
import json, os, re, html
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "posts.json")
DOCS = os.path.join(ROOT, "docs")

CATEGORY_ORDER = [
    "Showcase", "Photoreal & Portrait", "Text & Typography",
    "Infographic & Diagram", "Product & Ads", "Design & Poster",
    "Illustration & Anime", "Editing & Restyle", "Prompting & Workflow",
    "Model Comparisons", "Launch & Announcements",
]
CATEGORY_ZH = {
    "Showcase": "综合展示", "Photoreal & Portrait": "写实与人像",
    "Text & Typography": "文字与排版", "Infographic & Diagram": "信息图与示意图",
    "Product & Ads": "产品与广告", "Design & Poster": "设计与海报",
    "Illustration & Anime": "插画与动漫", "Editing & Restyle": "编辑与改绘",
    "Prompting & Workflow": "提示词与工作流", "Model Comparisons": "模型横评",
    "Launch & Announcements": "发布与官方消息",
}

# Where readers can run a prompt from this repo themselves. Sits at the top of
# both READMEs, above the gallery link.
TRY_URL = "https://seadanse.com/models/gpt-image-2-5"
TRY_HOST = "seadanse.com"


def load():
    posts = json.load(open(DATA))
    posts.sort(key=lambda p: -p.get("reach", 0))

    # scripts/mirror.py copies each still to R2 and cuts a thumbnail. Display
    # prefers the mirror: X rotates pbs.twimg URLs and Reddit signs its preview
    # URLs with an expiry, so the original is provenance, not a display source.
    mpath = os.path.join(ROOT, "data", "mirror.json")
    mirror = json.load(open(mpath)) if os.path.exists(mpath) else {}

    for p in posts:
        m = mirror.get(p["id"])
        p["image"]["source_url"] = p["image"]["url"]
        if p.get("prompt") and not p.get("prompt_source_urls"):
            p["prompt_source_urls"] = [p["url"]]
        if m:
            p["image"]["url"] = m["image"]
            p["image"]["thumb"] = m["thumb"]
            for extra, mm in zip(p.get("extra_images") or [], m.get("extra") or []):
                extra["source_url"] = extra["url"]
                extra["url"] = mm["image"]
                extra["thumb"] = mm["thumb"]
        else:
            p["image"]["thumb"] = None
    return posts


def by_category(posts):
    out = OrderedDict()
    for c in CATEGORY_ORDER:
        group = [p for p in posts if p["category"] == c]
        if group:
            out[c] = group
    for p in posts:                       # anything a new rule invented
        if p["category"] not in out:
            out[p["category"]] = [q for q in posts if q["category"] == p["category"]]
    return out


def human(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n/1_000:.1f}K".replace(".0K", "K")
    return str(n)


def engagement(p):
    """The post's own platform metric, in that platform's own words.

    There is no honest conversion between an X view and a Reddit upvote, so
    nothing here tries to make one. Ordering uses `reach`, a per-platform
    percentile computed in harvest.py; this is only what the card prints.
    """
    if p["source"] == "reddit":
        return f"{human(p['stats'].get('score', 0))} upvotes"
    return f"{human(p['stats'].get('views', 0))} views"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def clip(s, n):
    """Trim to n chars on a word boundary."""
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def still(p):
    """What to show in a README or a grid: the mirrored thumbnail, then the
    mirrored display copy, then the platform's own URL as a last resort."""
    return p["image"].get("thumb") or p["image"]["url"]


def source_label(p, zh=False):
    if p["source"] == "reddit":
        return "Reddit 原帖" if zh else "Original post"
    return "X 原帖" if zh else "Original post"


def prompt_source_links(p, zh=False):
    """Markdown links to the exact post/replies from which prompt text came."""
    urls = p.get("prompt_source_urls") or [p["url"]]
    reply_word = "回复" if zh else "reply"
    site = "Reddit" if p["source"] == "reddit" else "X"
    links = []
    for i, url in enumerate(urls, 1):
        if url == p["url"]:
            label = source_label(p, zh)
        elif len(urls) == 1:
            label = f"{site} {reply_word}"
        else:
            label = f"{site} {reply_word} {i}"
        links.append(f"[{label}]({url})")
    return " · ".join(links)


# ============================================================== GitHub Pages site

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Awesome GPT Image 2.5 Prompts — every GPT Image 2.5 still worth copying</title>
<meta name="description" content="A community index of GPT Image 2.5 images posted on X and Reddit. See the picture, read the exact prompt, credit the creator.">
<meta property="og:title" content="Awesome GPT Image 2.5 Prompts">
<meta property="og:description" content="Every GPT Image 2.5 image shared on X and Reddit, with the prompt and full credit to the creator.">
<style>
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#0a0a0f; --bg-soft:#12121a; --card:#15151f; --card-hover:#1b1b28;
  --line:#26263a; --fg:#ececf5; --fg-dim:#9a9ab5; --fg-faint:#6a6a85;
  --accent:#ff8a3d; --accent-soft:#ff8a3d22; --accent-fg:#ffb27a;
  --radius:14px; --maxw:1400px;
}
@media (prefers-color-scheme: light){
  :root{--bg:#fbfbfd;--bg-soft:#f4f2ef;--card:#fff;--card-hover:#fff;--line:#e8e3dc;
        --fg:#16161f;--fg-dim:#5b5b73;--fg-faint:#8a8aa0;--accent:#d9600f;--accent-soft:#d9600f12;--accent-fg:#c1540b}
}
:root[data-theme="dark"]{--bg:#0a0a0f;--bg-soft:#12121a;--card:#15151f;--card-hover:#1b1b28;--line:#26263a;
  --fg:#ececf5;--fg-dim:#9a9ab5;--fg-faint:#6a6a85;--accent:#ff8a3d;--accent-soft:#ff8a3d22;--accent-fg:#ffb27a}
:root[data-theme="light"]{--bg:#fbfbfd;--bg-soft:#f4f2ef;--card:#fff;--card-hover:#fff;--line:#e8e3dc;
  --fg:#16161f;--fg-dim:#5b5b73;--fg-faint:#8a8aa0;--accent:#d9600f;--accent-soft:#d9600f12;--accent-fg:#c1540b}

html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);
  font:15px/1.55 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif;
  overflow-x:hidden}
a{color:inherit}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 20px}

/* ---------- header ---------- */
header{border-bottom:1px solid var(--line);background:
  radial-gradient(900px 380px at 12% -12%, var(--accent-soft), transparent 62%), var(--bg-soft)}
.head{padding:44px 0 34px}
h1{margin:0 0 10px;font-size:clamp(26px,4.4vw,42px);line-height:1.1;letter-spacing:-.022em;font-weight:700}
h1 .g{background:linear-gradient(96deg,var(--accent-fg),#ffd166 62%,#ff6b9d);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.tagline{margin:0;color:var(--fg-dim);font-size:clamp(14px,1.7vw,17px);max-width:65ch}
.metrics{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}
.metric{background:var(--card);border:1px solid var(--line);border-radius:999px;
  padding:6px 14px;font-size:12.5px;color:var(--fg-dim)}
.metric b{color:var(--fg);font-variant-numeric:tabular-nums}
.headlinks{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}
.btn{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);background:var(--card);
  color:var(--fg);border-radius:9px;padding:8px 14px;font-size:13.5px;font-weight:500;
  text-decoration:none;cursor:pointer;transition:.15s}
.btn:hover{border-color:var(--accent);color:var(--accent-fg)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#1a0f06}
.btn.primary:hover{filter:brightness(1.12);color:#1a0f06}

/* ---------- controls ---------- */
.controls{position:sticky;top:0;z-index:30;background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:blur(14px);border-bottom:1px solid var(--line);padding:12px 0}
.crow{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.search{flex:1 1 240px;min-width:180px;position:relative}
.search input{width:100%;background:var(--card);border:1px solid var(--line);color:var(--fg);
  border-radius:9px;padding:9px 12px 9px 34px;font-size:14px;font-family:inherit}
.search input:focus{outline:2px solid var(--accent);outline-offset:-1px;border-color:transparent}
.search svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);opacity:.45;pointer-events:none}
select{background:var(--card);border:1px solid var(--line);color:var(--fg);border-radius:9px;
  padding:9px 11px;font-size:13.5px;font-family:inherit;cursor:pointer}
select:focus{outline:2px solid var(--accent);outline-offset:-1px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{border:1px solid var(--line);background:var(--card);color:var(--fg-dim);border-radius:999px;
  padding:7px 14px;font-size:13px;cursor:pointer;font-family:inherit;transition:.15s;white-space:nowrap}
.chip:hover{color:var(--fg);border-color:var(--fg-faint)}
.chip[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#1a0f06;font-weight:600}
.count{color:var(--fg-faint);font-size:12.5px;margin-left:auto;white-space:nowrap;font-variant-numeric:tabular-nums}

/* ---------- grid ---------- */
main{padding:26px 0 70px}
.grid{display:grid;gap:18px;grid-template-columns:repeat(auto-fill,minmax(330px,1fr))}
@media(max-width:719px){.grid{grid-template-columns:1fr;gap:16px}}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  overflow:hidden;display:flex;flex-direction:column;transition:.18s}
.card:hover{border-color:var(--fg-faint);background:var(--card-hover)}

.shot{position:relative;aspect-ratio:4/3;background:var(--bg-soft);overflow:hidden;
  border:0;padding:0;display:block;width:100%;cursor:zoom-in}
.shot.tall{aspect-ratio:4/5}
.shot img{width:100%;height:100%;object-fit:cover;display:block}
.badges{position:absolute;left:9px;top:9px;display:flex;gap:5px;flex-wrap:wrap;pointer-events:none;z-index:2}
.badge{background:#000000b8;color:#fff;font-size:11px;font-weight:600;letter-spacing:.02em;
  padding:3px 8px;border-radius:6px;backdrop-filter:blur(4px)}
.badge.ck{background:#ff8a3de0;color:#1a0f06}
.badge.src{background:#ffffffcc;color:#16161f}
.more{position:absolute;right:9px;bottom:9px;background:#000000b8;color:#fff;font-size:11px;
  padding:3px 7px;border-radius:5px;font-variant-numeric:tabular-nums;pointer-events:none;z-index:2}

.body{padding:14px 15px 15px;display:flex;flex-direction:column;gap:11px;flex:1}
.title{margin:0;font-size:14.5px;line-height:1.42;font-weight:600;letter-spacing:-.005em}
.title a{text-decoration:none}
.title a:hover{color:var(--accent-fg);text-decoration:underline;text-underline-offset:2px}
.who{display:flex;align-items:center;gap:9px;min-width:0}
.who img{width:30px;height:30px;border-radius:50%;flex:none;background:var(--bg-soft)}
.who .nm{min-width:0;line-height:1.3}
.who .n{font-size:13px;font-weight:600;display:block;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;text-decoration:none}
.who .n:hover{color:var(--accent-fg)}
.who .h{font-size:11.5px;color:var(--fg-faint);text-decoration:none}
.who .h:hover{color:var(--accent-fg)}
.source,.prompt-source{font-size:11.5px;color:var(--fg-faint);line-height:1.5}
.source a,.prompt-source a{color:var(--accent-fg);text-decoration:none}
.source a:hover,.prompt-source a:hover{text-decoration:underline;text-underline-offset:2px}
.meta{display:flex;gap:12px;font-size:11.5px;color:var(--fg-faint);
  font-variant-numeric:tabular-nums;flex-wrap:wrap;margin-top:auto;padding-top:2px}
.meta span{display:inline-flex;align-items:center;gap:4px}

details.prompt{border:1px solid var(--line);border-radius:9px;background:var(--bg-soft)}
details.prompt summary{cursor:pointer;padding:8px 11px;font-size:12.5px;font-weight:600;
  color:var(--accent-fg);list-style:none;display:flex;align-items:center;gap:6px;user-select:none}
details.prompt summary::-webkit-details-marker{display:none}
details.prompt summary::before{content:"▸";font-size:10px;transition:.15s;display:inline-block}
details.prompt[open] summary::before{transform:rotate(90deg)}
.ptext{margin:0;padding:0 11px 11px;font:11.5px/1.62 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  color:var(--fg-dim);white-space:pre-wrap;word-break:break-word;max-height:280px;overflow:auto}
.prompt-source{padding:0 11px 9px}
.copy{margin:0 11px 11px;border:1px solid var(--line);background:var(--card);color:var(--fg-dim);
  border-radius:7px;padding:5px 11px;font-size:11.5px;cursor:pointer;font-family:inherit;transition:.15s}
.copy:hover{border-color:var(--accent);color:var(--accent-fg)}
.copy.done{border-color:#3ec98a;color:#3ec98a}
.thread{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--fg-faint);
  text-decoration:none;border:1px dashed var(--line);border-radius:8px;padding:7px 11px}
.thread:hover{color:var(--accent-fg);border-color:var(--accent)}

/* ---------- lightbox ---------- */
dialog.lb{border:0;padding:0;background:transparent;max-width:96vw;max-height:96vh}
dialog.lb::backdrop{background:#000000e0}
dialog.lb .lbwrap{display:flex;flex-direction:column;gap:10px;align-items:center}
dialog.lb img{max-width:96vw;max-height:82vh;object-fit:contain;border-radius:10px;display:block}
dialog.lb .lbbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:center}
dialog.lb .lbbar a,dialog.lb .lbbar button{border:1px solid #ffffff33;background:#ffffff14;color:#fff;
  border-radius:8px;padding:6px 12px;font:13px/1.4 inherit;text-decoration:none;cursor:pointer}
dialog.lb .lbbar a:hover,dialog.lb .lbbar button:hover{background:#ffffff26}

.empty{text-align:center;padding:80px 20px;color:var(--fg-faint)}
footer{border-top:1px solid var(--line);background:var(--bg-soft);padding:32px 0;
  color:var(--fg-faint);font-size:13px;line-height:1.7}
footer a{color:var(--accent-fg)}
footer p{margin:0 0 8px;max-width:78ch}
.totop{position:fixed;right:18px;bottom:18px;width:42px;height:42px;border-radius:50%;
  background:var(--accent);color:#1a0f06;border:0;cursor:pointer;display:none;place-items:center;
  box-shadow:0 4px 18px #0005;z-index:40}
.totop.show{display:grid}
</style>
</head>
<body>

<header>
  <div class="wrap head">
    <h1>Awesome <span class="g">GPT Image 2.5</span> Prompts</h1>
    <p class="tagline">Every GPT Image 2.5 still people are posting on X and Reddit, collected in one place —
      see the picture, read the exact prompt, and follow the cited source account and post.</p>
    <div class="metrics">
      <div class="metric"><b>__NPOSTS__</b> posts</div>
      <div class="metric"><b>__NCREATORS__</b> source accounts</div>
      <div class="metric"><b>__NPROMPTS__</b> full prompts</div>
      <div class="metric"><b>__NSOURCES__</b></div>
    </div>
    <div class="headlinks">
      <a class="btn primary" href="__TRY__">✨ Run a prompt on __TRYHOST__</a>
      <a class="btn" href="__REPO__">★ Star on GitHub</a>
      <a class="btn" href="__REPO__/blob/main/CONTRIBUTING.md">＋ Add a post</a>
      <a class="btn" href="__REPO__/blob/main/data/posts.json">JSON dataset</a>
      <button class="btn" id="theme" type="button">◐ Theme</button>
    </div>
  </div>
</header>

<div class="controls">
  <div class="wrap crow">
    <label class="search">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
        <circle cx="11" cy="11" r="7"/><path d="m20 20-3.2-3.2"/></svg>
      <input id="q" type="search" placeholder="Search prompts, creators, anything…" autocomplete="off">
    </label>
    <div class="chips" id="models"></div>
    <select id="src">
      <option value="">All sources</option>
      <option value="x">X</option>
      <option value="reddit">Reddit</option>
    </select>
    <select id="cat"><option value="">All categories</option></select>
    <select id="sort">
      <option value="reach">Most engaged</option>
      <option value="date">Newest first</option>
      <option value="prompt">Has a full prompt</option>
    </select>
    <span class="count" id="count"></span>
  </div>
</div>

<main class="wrap"><div class="grid" id="grid"></div><div class="empty" id="empty" hidden>
  No post matches that. Try a looser search.</div></main>

<dialog class="lb" id="lb"><div class="lbwrap">
  <img id="lbimg" src="" alt="">
  <div class="lbbar">
    <button type="button" id="lbprev">‹ Previous</button>
    <span id="lbcount" style="color:#fff;font-size:13px"></span>
    <button type="button" id="lbnext">Next ›</button>
    <a id="lbpost" href="" target="_blank" rel="noopener">Open the original post ↗</a>
    <button type="button" id="lbclose">Close</button>
  </div>
</div></dialog>

<footer><div class="wrap">
  <p><b>Every card credits the source account and links to the original post and prompt source.</b>
     Source credit does not infer ownership beyond what the linked posts show. If you want an entry changed or
     removed, <a href="__REPO__/issues/new">open an issue</a> and it comes down, no questions asked.</p>
  <p>GPT Image 2.5 is an image model by OpenAI. This is an unaffiliated, community-run index.
     Data refreshed __UPDATED__ · <a href="__REPO__">source on GitHub</a> · MIT licensed.</p>
</div></footer>

<button class="totop" id="totop" type="button" aria-label="Back to top">
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6">
    <path d="M12 19V5M5 12l7-7 7 7"/></svg></button>

<script id="data" type="application/json">__DATA__</script>
<script>
const POSTS = JSON.parse(document.getElementById('data').textContent);
const $ = s => document.querySelector(s);
const esc = s => (s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const human = n => n >= 1e6 ? (n/1e6).toFixed(1).replace(/\\.0$/,'')+'M'
                 : n >= 1e3 ? (n/1e3).toFixed(1).replace(/\\.0$/,'')+'K' : ''+n;
// The mirrored thumbnail if there is one, then the mirrored display copy.
const still = p => p.image.thumb || p.image.url;
// Each platform's own metric, in its own words. No exchange rate is invented.
const engagement = p => p.source === 'reddit'
  ? human(p.stats.score || 0) + ' upvotes'
  : human(p.stats.views || 0) + ' views';
const allImages = p => [p.image, ...(p.extra_images || [])];

/* ---- filter state ---- */
const state = { q:'', model:'', cat:'', src:'', sort:'reach' };

const MODELS = [...new Set(POSTS.map(p => p.model))]
  .sort((a,b) => POSTS.filter(p=>p.model===b).length - POSTS.filter(p=>p.model===a).length);
$('#models').innerHTML = [['','All checkpoints'], ...MODELS.map(m=>[m,m])]
  .map(([v,l]) => `<button class="chip" data-m="${esc(v)}" aria-pressed="${v===''}">${esc(l)}</button>`).join('');
$('#models').addEventListener('click', e => {
  const b = e.target.closest('[data-m]'); if (!b) return;
  state.model = b.dataset.m;
  [...$('#models').children].forEach(c => c.setAttribute('aria-pressed', c === b));
  render();
});

const CATS = [...new Set(POSTS.map(p => p.category))].sort();
$('#cat').insertAdjacentHTML('beforeend',
  CATS.map(c => `<option value="${esc(c)}">${esc(c)} (${POSTS.filter(p=>p.category===c).length})</option>`).join(''));

$('#q').addEventListener('input', e => { state.q = e.target.value.toLowerCase().trim(); render(); });
$('#cat').addEventListener('change', e => { state.cat = e.target.value; render(); });
$('#src').addEventListener('change', e => { state.src = e.target.value; render(); });
$('#sort').addEventListener('change', e => { state.sort = e.target.value; render(); });

/* ---- card ---- */
function card(p) {
  const tall = (p.image.height || 0) > (p.image.width || 0);
  const named = p.model !== 'GPT Image 2.5';
  const extra = (p.extra_images || []).length;
  const promptLinks = (p.prompt_source_urls || []).map((url, i, all) => {
    const site = p.source === 'reddit' ? 'Reddit' : 'X';
    const label = url === p.url ? 'Original post' : (all.length > 1 ? site + ' reply ' + (i + 1) : site + ' reply');
    return `<a href="${esc(url)}" target="_blank" rel="noopener">${label}</a>`;
  }).join(' · ');
  const promptBlock = p.prompt
    ? `<details class="prompt"><summary>Prompt</summary>
         <pre class="ptext">${esc(p.prompt)}</pre>
         <div class="prompt-source"><b>Prompt credit / source:</b>
           <a href="${esc(p.author.url)}" target="_blank" rel="noopener">${esc(p.author.name)}</a>
           · ${promptLinks}</div>
         <button class="copy" type="button" data-id="${esc(p.id)}">Copy prompt</button></details>`
    : p.prompt_in_thread
      ? `<a class="thread" href="${esc(p.url)}" target="_blank" rel="noopener">Prompt mentioned in the thread ↗</a>`
      : '';
  return `<article class="card" data-id="${esc(p.id)}">
    <button class="shot${tall ? ' tall' : ''}" type="button" data-open="${esc(p.id)}" aria-label="View full size">
      <img src="${esc(still(p))}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">
      <div class="badges">
        <span class="badge${named ? ' ck' : ''}">${esc(p.model)}</span>
        <span class="badge src">${p.source === 'reddit' ? 'r/' + esc(p.subreddit || 'reddit') : 'X'}</span>
      </div>
      ${extra ? `<span class="more">+${extra}</span>` : ''}
    </button>
    <div class="body">
      <h2 class="title"><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a></h2>
      <div class="who">
        <img src="${esc(p.author.avatar||'')}" alt="" loading="lazy" referrerpolicy="no-referrer">
        <div class="nm">
          <a class="n" href="${esc(p.author.url)}" target="_blank" rel="noopener">${esc(p.author.name)}</a>
          <a class="h" href="${esc(p.author.url)}" target="_blank" rel="noopener">${p.source === 'reddit' ? '' : '@'}${esc(p.author.handle)}</a>
        </div>
      </div>
      <div class="source"><b>Image credit / source:</b>
        <a href="${esc(p.author.url)}" target="_blank" rel="noopener">${esc(p.author.name)}</a>
        · <a href="${esc(p.url)}" target="_blank" rel="noopener">Original post ↗</a></div>
      ${promptBlock}
      <div class="meta">
        <span>${esc(p.date)}</span>
        <span>${engagement(p)}</span>
      </div>
    </div>
  </article>`;
}

function render() {
  let list = POSTS.filter(p => {
    if (state.model && p.model !== state.model) return false;
    if (state.cat && p.category !== state.cat) return false;
    if (state.src && p.source !== state.src) return false;
    if (state.q) {
      const hay = (p.title + ' ' + p.text + ' ' + (p.prompt||'') + ' ' +
                   p.author.name + ' ' + p.author.handle + ' ' + p.category).toLowerCase();
      if (!state.q.split(/\\s+/).every(w => hay.includes(w))) return false;
    }
    return true;
  });
  if (state.sort === 'date')        list.sort((a,b) => b.date.localeCompare(a.date));
  else if (state.sort === 'prompt') list.sort((a,b) => (b.prompt?1:0)-(a.prompt?1:0) || b.reach-a.reach);
  else                              list.sort((a,b) => b.reach - a.reach);

  $('#grid').innerHTML = list.map(card).join('');
  $('#count').textContent = `${list.length} of ${POSTS.length}`;
  $('#empty').hidden = list.length > 0;
}

/* ---- lightbox: the full-size still, and the rest of a gallery ---- */
const lb = $('#lb');
let lbImages = [], lbIndex = 0;

function showLb() {
  const image = lbImages[lbIndex];
  $('#lbimg').src = image.url;
  $('#lbcount').textContent = lbImages.length > 1 ? `${lbIndex + 1} / ${lbImages.length}` : '';
  $('#lbprev').hidden = $('#lbnext').hidden = lbImages.length < 2;
}

$('#grid').addEventListener('click', e => {
  const open = e.target.closest('[data-open]');
  if (open) {
    const p = POSTS.find(x => x.id === open.dataset.open);
    lbImages = allImages(p);
    lbIndex = 0;
    $('#lbpost').href = p.url;
    showLb();
    lb.showModal();
    return;
  }
  const copy = e.target.closest('.copy');
  if (copy) {
    const p = POSTS.find(x => x.id === copy.dataset.id);
    navigator.clipboard.writeText(p.prompt).then(() => {
      copy.textContent = '✓ Copied'; copy.classList.add('done');
      setTimeout(() => { copy.textContent = 'Copy prompt'; copy.classList.remove('done'); }, 1600);
    });
  }
});

$('#lbprev').addEventListener('click', () => { lbIndex = (lbIndex - 1 + lbImages.length) % lbImages.length; showLb(); });
$('#lbnext').addEventListener('click', () => { lbIndex = (lbIndex + 1) % lbImages.length; showLb(); });
$('#lbclose').addEventListener('click', () => lb.close());
lb.addEventListener('click', e => { if (e.target === lb) lb.close(); });
addEventListener('keydown', e => {
  if (!lb.open || lbImages.length < 2) return;
  if (e.key === 'ArrowLeft') $('#lbprev').click();
  if (e.key === 'ArrowRight') $('#lbnext').click();
});

/* ---- theme + back to top ---- */
$('#theme').addEventListener('click', () => {
  const cur = document.documentElement.dataset.theme ||
    (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.dataset.theme = cur === 'dark' ? 'light' : 'dark';
});
const totop = $('#totop');
addEventListener('scroll', () => totop.classList.toggle('show', scrollY > 900), {passive:true});
totop.addEventListener('click', () => scrollTo({top:0, behavior:'smooth'}));

render();
</script>
</body>
</html>
"""


def source_summary(posts):
    counts = Counter(p["source"] for p in posts)
    parts = []
    if counts.get("x"):
        parts.append(f"{counts['x']} from X")
    if counts.get("reddit"):
        parts.append(f"{counts['reddit']} from Reddit")
    return " · ".join(parts) or "no posts yet"


def build_site(posts, repo, updated):
    slim = [{
        "id": p["id"], "source": p["source"], "url": p["url"], "title": p["title"],
        "text": p["text"], "prompt": p["prompt"], "prompt_in_thread": p["prompt_in_thread"],
        "prompt_source_urls": p.get("prompt_source_urls", []),
        "model": p["model"], "category": p["category"], "date": p["date"],
        "author": p["author"], "stats": p["stats"], "reach": p.get("reach", 0),
        "subreddit": p.get("subreddit"),
        "image": p["image"], "extra_images": p.get("extra_images") or [],
    } for p in posts]
    page = (PAGE
            .replace("__DATA__", json.dumps(slim, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__NPOSTS__", str(len(posts)))
            .replace("__NCREATORS__", str(len({p["author"]["handle"] for p in posts})))
            .replace("__NPROMPTS__", str(sum(1 for p in posts if p["prompt"])))
            .replace("__NSOURCES__", source_summary(posts))
            .replace("__UPDATED__", updated)
            .replace("__TRYHOST__", TRY_HOST)
            .replace("__TRY__", TRY_URL)
            .replace("__REPO__", repo))
    os.makedirs(DOCS, exist_ok=True)
    open(os.path.join(DOCS, "index.html"), "w").write(page)
    json.dump(slim, open(os.path.join(DOCS, "posts.json"), "w"), indent=2, ensure_ascii=False)
    open(os.path.join(DOCS, ".nojekyll"), "w").write("")


# ============================================================== READMEs

def readme_en(posts, repo, site, updated):
    groups = by_category(posts)
    nprompt = sum(1 for p in posts if p["prompt"])
    L = []
    L.append("# Awesome GPT Image 2.5 Prompts\n")
    L.append("**Every GPT Image 2.5 still people are posting on X and Reddit, collected in one place — "
             "see the picture, read the exact prompt, and follow the cited source account and post.**\n")
    L.append(f"[![Try it yourself](https://img.shields.io/badge/✨%20Try%20it%20yourself-"
             f"{TRY_HOST.replace('-', '--')}-C6F24E?style=flat-square&labelColor=0A0B0A)]({TRY_URL})\n"
             f"[![Browse the gallery](https://img.shields.io/badge/▦%20Browse%20the%20gallery-"
             f"opensource--works.github.io-FF8A3D?style=flat-square)]({site})\n"
             "[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](CONTRIBUTING.md)\n"
             "[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)\n")
    L.append("**English** | [简体中文](README.zh-CN.md)\n")
    L.append(f"### ✨ Want to try it yourself? Generate with GPT Image 2.5 at **[{TRY_HOST}]({TRY_URL})**\n")
    L.append(f"Copy any prompt from this repo, paste it into [{TRY_HOST}]({TRY_URL}), and get your own image "
             "back in seconds — no install, no waitlist, free credits to start. Both named checkpoints, "
             "Sunburst and Flare, are on the same page.\n")
    L.append(f"### ▦ [Open the gallery]({site})\n")
    L.append("**Every image below renders right here on GitHub.** Open the gallery instead if you want to "
             "search across prompts, filter by checkpoint, source or category, view a still full size, "
             "or copy a prompt in one click.\n")

    L.append("## What's in here\n")
    L.append(f"| | |\n|---|---|\n"
             f"| Posts | **{len(posts)}** |\n"
             f"| Source accounts credited | **{len({p['author']['handle'] for p in posts})}** |\n"
             f"| Posts with the full prompt | **{nprompt}** |\n"
             f"| Where they came from | {source_summary(posts)} |\n"
             f"| Checkpoints covered | {', '.join(f'**{m}** ({n})' for m, n in Counter(p['model'] for p in posts).most_common())} |\n"
             f"| Last refreshed | {updated} |\n")

    if posts:
        L.append("## Most engaged\n")
        L.append("<table><tr>")
        for i, p in enumerate(posts[:6]):
            if i and i % 3 == 0:
                L.append("</tr><tr>")
            L.append(f'<td width="33%" valign="top"><a href="{p["url"]}">'
                     f'<img src="{still(p)}" width="100%" alt=""></a><br>'
                     f'<sub><b>{html.escape(clip(p["title"], 62))}</b><br>'
                     f'<a href="{p["author"]["url"]}">{html.escape(p["author"]["name"])}</a> · '
                     f'{engagement(p)}</sub></td>')
        L.append("</tr></table>\n")
        L.append("> Ordering is each post's standing among the posts from its own platform. "
                 "An X view and a Reddit upvote are not the same unit and this repo does not "
                 "pretend to convert between them.\n")

    L.append("## Contents\n")
    for c, g in groups.items():
        L.append(f"- [{c}](#{slug(c)}) — {len(g)} posts")
    L.append("")

    for c, g in groups.items():
        L.append(f"## {c}\n")
        for p in g:
            L.append(f"### {p['title']}\n")
            L.append(f'<a href="{p["url"]}"><img src="{still(p)}" '
                     f'width="460" alt="{html.escape(p["title"])}"></a>\n')
            where = f"r/{p['subreddit']}" if p["source"] == "reddit" else "X"
            L.append(f"**Image credit / source:** [{html.escape(p['author']['name'])}]({p['author']['url']}) · "
                     f"[Original post]({p['url']}) · {where} · "
                     f"{p['model']} · {p['date']} · {engagement(p)}\n")
            if p["prompt"]:
                L.append("<details><summary><b>Prompt</b></summary>\n")
                L.append("```text")
                L.append(p["prompt"])
                L.append("```\n")
                L.append("</details>\n")
                L.append(f"**Prompt credit / source:** [{html.escape(p['author']['name'])}]({p['author']['url']}) · "
                         f"{prompt_source_links(p)}\n")
            elif p["prompt_in_thread"]:
                L.append(f"> A prompt is mentioned in the [thread]({p['url']}); "
                         "the exact reply has not been indexed yet.\n")
        L.append("")

    L.append("## Credit and takedowns\n")
    L.append("Every entry credits the source account and links to the original post and exact prompt source. "
             "Source credit does not infer ownership beyond what the linked posts show.\n")
    L.append("If you are a creator and want your post edited or removed, "
             f"[open an issue]({repo}/issues/new) and it comes down, no questions asked.\n")
    L.append("## Adding a post\n")
    L.append("Drop the X or Reddit link into `scripts/urls.txt` and open a PR. "
             "X posts hydrate themselves; a Reddit post needs a row in `data/reddit.json` too, because "
             "Reddit refuses anonymous API access and CI cannot fetch it. "
             "See [CONTRIBUTING.md](CONTRIBUTING.md).\n")
    L.append("## How the data is built\n")
    L.append("```bash\npython3 scripts/harvest.py   # urls.txt + reddit.json -> data/posts.json\n"
             "python3 scripts/mirror.py    # stills -> R2, data/mirror.json\n"
             "python3 scripts/build.py     # data/posts.json -> docs/ + READMEs\n```\n")
    L.append("GPT Image 2.5 is an image model by OpenAI. This is an unaffiliated, community-run index. "
             "Repo content is MIT licensed; the linked posts and images remain the property of their authors.\n")
    return "\n".join(L)


def readme_zh(posts, repo, site, updated):
    groups = by_category(posts)
    nprompt = sum(1 for p in posts if p["prompt"])
    L = []
    L.append("# Awesome GPT Image 2.5 Prompts\n")
    L.append("**把 X 和 Reddit 上大家发的 GPT Image 2.5 出图集中到一个入口——直接看图、"
             "看到完整提示词，并且一键找到有明确引用的来源账号和原帖。**\n")
    L.append(f"[![自己试试](https://img.shields.io/badge/✨%20自己试一试-"
             f"{TRY_HOST.replace('-', '--')}-C6F24E?style=flat-square&labelColor=0A0B0A)]({TRY_URL})\n"
             f"[![浏览画廊](https://img.shields.io/badge/▦%20打开图片画廊-opensource--works.github.io-FF8A3D?style=flat-square)]({site})\n"
             "[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](CONTRIBUTING.md)\n"
             "[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)\n")
    L.append("[English](README.md) | **简体中文**\n")
    L.append(f"### ✨ 想亲手试试？上 **[{TRY_HOST}]({TRY_URL})** 直接用 GPT Image 2.5 出图\n")
    L.append(f"把这里任意一条提示词复制到 [{TRY_HOST}]({TRY_URL})，几秒钟就能拿到你自己的图——"
             "免安装、免排队，注册即送免费额度。Sunburst 和 Flare 两个官方检查点都在同一个页面上。\n")
    L.append(f"### ▦ [打开图片画廊]({site})\n")
    L.append("**下面每张图都能在 GitHub 页面上直接看到。**"
             "如果想跨提示词搜索、按检查点或来源筛选、看原图大小、或者一键复制提示词，再去画廊。\n")

    L.append("## 收录概况\n")
    L.append(f"| | |\n|---|---|\n"
             f"| 帖子数 | **{len(posts)}** |\n"
             f"| 署名来源账号 | **{len({p['author']['handle'] for p in posts})}** |\n"
             f"| 含完整提示词 | **{nprompt}** |\n"
             f"| 来源分布 | {source_summary(posts)} |\n"
             f"| 覆盖检查点 | {', '.join(f'**{m}**（{n}）' for m, n in Counter(p['model'] for p in posts).most_common())} |\n"
             f"| 最近更新 | {updated} |\n")

    L.append("## 目录\n")
    for c, g in groups.items():
        L.append(f"- [{CATEGORY_ZH.get(c, c)}](#{slug(c)}) — {len(g)} 条")
    L.append("")

    for c, g in groups.items():
        L.append(f"## {CATEGORY_ZH.get(c, c)}\n")
        L.append(f'<a id="{slug(c)}"></a>\n')
        for p in g:
            L.append(f"### {p['title']}\n")
            L.append(f'<a href="{p["url"]}"><img src="{still(p)}" '
                     f'width="460" alt="{html.escape(p["title"])}"></a>\n')
            where = f"r/{p['subreddit']}" if p["source"] == "reddit" else "X"
            metric = (f"{human(p['stats'].get('score', 0))} 赞同" if p["source"] == "reddit"
                      else f"{human(p['stats'].get('views', 0))} 浏览")
            L.append(f"**图片署名 / 来源：** [{html.escape(p['author']['name'])}]({p['author']['url']}) · "
                     f"[{source_label(p, zh=True)}]({p['url']}) · {where} · "
                     f"{p['model']} · {p['date']} · {metric}\n")
            if p["prompt"]:
                L.append("<details><summary><b>提示词</b></summary>\n")
                L.append("```text")
                L.append(p["prompt"])
                L.append("```\n")
                L.append("</details>\n")
                L.append(f"**提示词署名 / 来源：** [{html.escape(p['author']['name'])}]({p['author']['url']}) · "
                         f"{prompt_source_links(p, zh=True)}\n")
            elif p["prompt_in_thread"]:
                L.append(f"> [原帖讨论]({p['url']})提到了提示词，但尚未索引到准确回复。\n")
        L.append("")

    L.append("## 署名与下架\n")
    L.append("每条内容都会标注来源账号，并链接到图片原帖和提示词的准确来源。"
             "来源署名不额外推断链接帖子未说明的原创归属。\n")
    L.append(f"如果你是作者，希望修改或删除自己的内容，[提一个 issue]({repo}/issues/new) 即可，我们立刻下架。\n")
    L.append("## 投稿\n")
    L.append("把 X 或 Reddit 链接加进 `scripts/urls.txt` 提 PR 即可。X 的帖子脚本会自己补全；"
             "Reddit 的帖子还需要在 `data/reddit.json` 里附上一行——因为 Reddit 拒绝匿名接口访问，"
             "CI 抓不到。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。\n")
    L.append("GPT Image 2.5 是 OpenAI 的图像模型，本仓库为非官方社区索引。"
             "仓库代码与整理内容以 MIT 协议开源；被索引的帖子和图片版权归原作者所有。\n")
    return "\n".join(L)


def main():
    import subprocess
    posts = load()
    repo = "https://github.com/opensource-works/awesome-gpt-image-prompts"
    site = "https://opensource-works.github.io/awesome-gpt-image-prompts/"
    updated = subprocess.run(["date", "-u", "+%Y-%m-%d"], capture_output=True, text=True).stdout.strip()

    build_site(posts, repo, updated)
    open(os.path.join(ROOT, "README.md"), "w").write(readme_en(posts, repo, site, updated))
    open(os.path.join(ROOT, "README.zh-CN.md"), "w").write(readme_zh(posts, repo, site, updated))
    print(f"built docs/index.html + README.md + README.zh-CN.md from {len(posts)} posts")


if __name__ == "__main__":
    main()
