#!/usr/bin/env python3
"""
Hydrate the post URLs in scripts/urls.txt into data/posts.json.

Every field in the dataset comes straight from the public post — we never
invent a prompt, a caption or an author. Posts without a still image are
dropped, because the whole point of this index is that you can see what the
prompt produced.

    python3 scripts/harvest.py            # refresh everything
    python3 scripts/harvest.py --cache    # reuse .cache, only fetch new URLs

Two sources, hydrated very differently on purpose.

X goes through api.fxtwitter.com, which needs no key and works from a CI
runner, so X posts are re-fetched on every refresh and their view counts stay
current.

Reddit blocks anonymous API access outright — every UA and every host tried on
2026-09-10 returned 403, including old.reddit.com and api.reddit.com. Its
`.json` endpoints do answer inside a logged-in browser, so Reddit rows are
hydrated locally by the discovery half (`hydrate-reddit.mjs` in the seadanse
repo) and committed here as data/reddit.json. This file merges them in. The
consequence to know: a Reddit row's score is the value from the last local
run, not from this refresh, and no amount of re-running CI will update it.
"""
import json, os, re, sys, time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")
URLS = os.path.join(ROOT, "scripts", "urls.txt")
REDDIT = os.path.join(ROOT, "data", "reddit.json")
OUT = os.path.join(ROOT, "data", "posts.json")

API = "https://api.fxtwitter.com/i/status/{}"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"

# The model has to be named for a post to belong here. Both checkpoints carry
# the base phrase, so one pattern covers all three names.
MENTIONS_MODEL = re.compile(r"gpt[\s\-_]?image[\s\-_]?2[.·]5|gptimage2\.5", re.I)


# --------------------------------------------------------------------------- fetch

def status_id(url):
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None


def reddit_id(url):
    m = re.search(r"reddit\.com/(?:r/[^/]+/)?comments/([a-z0-9]+)", url, re.I)
    return m.group(1) if m else None


def fetch(sid, use_cache=True):
    path = os.path.join(CACHE, f"{sid}.json")
    if use_cache and os.path.exists(path) and os.path.getsize(path) > 200:
        return json.load(open(path))
    for attempt in range(3):
        try:
            req = urllib.request.Request(API.format(sid), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
            if data.get("code") != 200:
                return None
            os.makedirs(CACHE, exist_ok=True)
            json.dump(data["tweet"], open(path, "w"), ensure_ascii=False)
            return data["tweet"]
        except Exception as e:
            if attempt == 2:
                print(f"  ! {sid}: {e}", file=sys.stderr)
            time.sleep(1.5 * (attempt + 1))
    return None


# --------------------------------------------------------------------------- parse

# Ordered: the first rule that matches wins, so the specific ones come first.
# These are image categories — the Seedance corpus' shot/scene vocabulary does
# not transfer, and a still model's interesting axes are what it can render
# (text, diagrams, skin) rather than what it can move.
CATEGORY_RULES = [
    ("Model Comparisons", r"\b(same prompt (on|in)|side[- ]by[- ]side|blind(ly)? (test|judged)|showdown|"
                          r"head[- ]to[- ]head|comparison|outperform|destroys)\b"
                          r"|\bvs\.?\b.*\b(nano ?banana|midjourney|flux|imagen|seedream|firefly|dall[- ]?e|qwen|grok)\b"
                          r"|\b(nano ?banana|midjourney|flux|imagen|seedream|firefly|dall[- ]?e)\b.*\bvs\.?\b"),
    ("Launch & Announcements", r"\b(now live|is live|now available|rolling out|global launch|"
                               r"officially (announced|launched)|just (dropped|announced|shipped)|"
                               r"coming soon|api (access|is )?(live|available)|new (model|checkpoint|feature))\b"),
    ("Text & Typography", r"\b(text render(ing)?|typograph|handwrit|lettering|calligraph|"
                          r"spell(ing|s) (it|words?) (right|correctly)|legible text|"
                          r"font|word art|signage|menu board|newspaper)\b"),
    ("Infographic & Diagram", r"\b(infographic|diagram|flow ?chart|schematic|explainer|cheat ?sheet|"
                              r"cross[- ]section|cutaway|timeline graphic|chart|blueprint|"
                              r"annotated|labell?ed)\b"),
    ("Editing & Restyle", r"\b(image[- ]to[- ]image|img2img|in ?paint|out ?paint|restyle|re[- ]?style|"
                          r"edit(ed|ing)? (this|the|my) (image|photo|picture)|"
                          r"remove (the )?background|swap|turn (this|it|my|him|her) into|"
                          r"reference image|before (and|&) after|upscal)\b"),
    ("Product & Ads", r"\b(product (shot|photo|photograph|render|mock ?up)|pack ?shot|packaging|"
                      r"e-?commerce|advert|ad creative|\bads?\b|commercial|campaign|brand(ing)?|"
                      r"catalog|billboard|thumbnail)\b"),
    ("Design & Poster", r"\b(poster|album cover|book cover|magazine cover|movie poster|"
                        r"app icon|\bui\b|ux|web ?site design|landing page|logo|wallpaper|"
                        r"sticker|business card|editorial layout)\b"),
    ("Illustration & Anime", r"\b(anime|manga|ghibli|cartoon|comic|illustration|illustrated|"
                             r"watercolou?r|oil painting|pixel art|vector art|line art|"
                             r"storybook|3d render|claymation|isometric)\b"),
    ("Prompting & Workflow", r"\b(prompt (structure|template|library|collection|engineering|guide|tips?|recipe)|"
                             r"json prompt|system prompt|workflow|step[- ]by[- ]step|how to|technique|"
                             r"cheat sheet|what i learned|breakdown)\b"),
    ("Photoreal & Portrait", r"\b(photoreal|photo[- ]?realistic|portrait|head ?shot|selfie|"
                             r"shot on (a |an )?(iphone|film|35mm|leica)|film (photo|grain|stock)|"
                             r"analog(ue)? photo|candid|street photo)\b"),
]

# Marker forms seen in the wild: "Prompt:", "Prompt ⬇️", a bare "Prompt" line,
# "Here's the prompt 👇:", "GPT image 2.5 GIF prompt 👇", "提示词：" …
#
# The third pattern is deliberately loose about what precedes the word: people
# label the block with whatever the picture was — "GIF prompt", "edit prompt",
# "full prompt" — and requiring an exact wording drops the post silently. The
# length cap is what keeps it from matching a sentence that merely ends on the
# word "prompt".
PROMPT_MARKERS = [
    r"here'?s the (?:exact |full )?prompt\s*[👇⬇️]*\s*[:：]?",
    r"(?:gpt[\s\-]?image[^\n]{0,20})?(?:full |exact |base |example |image |final )?prompt(?:\s*(?:used|structure))?\s*[:：]",
    r"^[^\n]{0,48}\bprompts?\s*[⬇️👇🔽]*\s*[:：]?\s*$",
    r"提示词\s*[:：]?\s*[⬇️👇]*\s*$",
]
# "Prompt below", "prompts in comments" — the prompt exists but lives in a reply.
IN_THREAD = re.compile(
    r"\bprompts?\s*(?:is|are|in|below|👇|⬇️)?\s*"
    r"(?:below|in (?:the )?(?:first )?comments?|in (?:the )?(?:thread|replies?)|👇|⬇️)\b", re.I)

# A fenced block in Reddit selftext is almost always the prompt itself.
FENCED = re.compile(r"```+\s*\n(.+?)\n```+", re.S)


def extract_prompt(text, fenced_ok=False):
    """Longest plausible prompt body following a prompt marker, else None.

    On Reddit a fenced code block is the stronger signal — people paste the
    prompt into one and write their commentary around it — so it wins outright
    when present, and the marker scan is the fallback.
    """
    if fenced_ok:
        blocks = [b.strip() for b in FENCED.findall(text)]
        blocks = [b for b in blocks if len(b) >= 80]
        if blocks:
            return max(blocks, key=len)
    best = None
    for pat in PROMPT_MARKERS:
        for m in re.finditer(pat, text, re.I | re.M):
            tail = text[m.end():].strip()
            tail = re.sub(r"\s*https://t\.co/\w+\s*$", "", tail).strip()
            if len(tail) < 80:
                continue
            if best is None or len(tail) > len(best):
                best = tail
    return best


def detect_model(text):
    """Which checkpoint the post names.

    "sunburst" and "flare" are ordinary English words a prompt may well use, so
    they only count as a checkpoint name when they sit next to the model's.
    """
    t = text.lower()
    if re.search(r"gpt[\s\-_]?image[\s\-_]?2[.·]5[\s\-_]*sunburst|sunburst[\s\-_]*(?:checkpoint|variant|model)", t):
        return "GPT Image 2.5 Sunburst"
    if re.search(r"gpt[\s\-_]?image[\s\-_]?2[.·]5[\s\-_]*flare|flare[\s\-_]*(?:checkpoint|variant|model)", t):
        return "GPT Image 2.5 Flare"
    return "GPT Image 2.5"


def categorize(text):
    for name, pat in CATEGORY_RULES:
        if re.search(pat, text, re.I):
            return name
    return "Showcase"


def make_title(text):
    for line in text.split("\n"):
        line = re.sub(r"https?://\S+", "", line).strip()
        line = re.sub(r"\s+", " ", line).strip(" .:-—>#*")
        if len(line) >= 14:
            return (line[:92].rsplit(" ", 1)[0] + "…") if len(line) > 95 else line
    flat = re.sub(r"\s+", " ", re.sub(r"https?://\S+", "", text)).strip()
    return flat[:92] or "Untitled"


def build_x(tweet):
    photos = (tweet.get("media") or {}).get("photos") or []
    text = (tweet.get("text") or "").strip()
    if not photos or not MENTIONS_MODEL.search(text):
        return None
    primary = max(photos, key=lambda x: (x.get("width") or 0) * (x.get("height") or 0))
    a = tweet["author"]
    dt = datetime.strptime(tweet["created_at"], "%a %b %d %H:%M:%S %z %Y").astimezone(timezone.utc)
    prompt = extract_prompt(text)
    return {
        "id": tweet["id"],
        "source": "x",
        "url": f"https://x.com/{a['screen_name']}/status/{tweet['id']}",
        "title": make_title(text),
        "text": text,
        "prompt": prompt,
        "prompt_in_thread": bool(not prompt and IN_THREAD.search(text)),
        "model": detect_model(text),
        "category": categorize(text),
        "date": dt.strftime("%Y-%m-%d"),
        "author": {
            "name": a["name"],
            "handle": a["screen_name"],
            "url": f"https://x.com/{a['screen_name']}",
            "avatar": a.get("avatar_url"),
        },
        "image": {
            "url": primary["url"],
            "width": primary.get("width"),
            "height": primary.get("height"),
        },
        # Several stills in one post is the normal shape for a comparison or a
        # before/after, and dropping the rest would hide half the evidence.
        "extra_images": [
            {"url": p["url"], "width": p.get("width"), "height": p.get("height")}
            for p in photos
            if p["url"] != primary["url"]
        ],
        "stats": {
            "views": tweet.get("views") or 0,
            "likes": tweet.get("likes") or 0,
            "reposts": tweet.get("retweets") or 0,
        },
    }


def build_reddit(row):
    """Normalize one row of data/reddit.json, written by hydrate-reddit.mjs.

    That script already did the platform work — it ran inside a logged-in
    browser and pulled the post's own JSON — so this only shapes the result and
    applies the same title, category and prompt rules the X path uses.
    """
    text = "\n".join(x for x in (row.get("title"), row.get("selftext")) if x).strip()
    images = row.get("images") or []
    if not images or not MENTIONS_MODEL.search(text):
        return None
    primary = max(images, key=lambda x: (x.get("width") or 0) * (x.get("height") or 0))
    prompt = extract_prompt(row.get("selftext") or "", fenced_ok=True)
    return {
        "id": row["id"],
        "source": "reddit",
        "url": row["url"],
        "title": make_title(row.get("title") or text),
        "text": text,
        "prompt": prompt,
        "prompt_in_thread": bool(not prompt and IN_THREAD.search(text)),
        "model": detect_model(text),
        "category": categorize(text),
        "date": row["date"],
        "author": {
            "name": f"u/{row['author']}",
            "handle": row["author"],
            "url": f"https://www.reddit.com/user/{row['author']}",
            "avatar": None,
        },
        "image": {
            "url": primary["url"],
            "width": primary.get("width"),
            "height": primary.get("height"),
        },
        "extra_images": [i for i in images if i["url"] != primary["url"]],
        "subreddit": row.get("subreddit"),
        "stats": {
            "score": row.get("score") or 0,
            "comments": row.get("comments") or 0,
        },
    }


def rank(posts):
    """Order the whole corpus without inventing a shared unit.

    X reports views, Reddit reports upvotes, and there is no honest exchange
    rate between them. So each post is ranked against the posts from its OWN
    platform — a post in the top tenth of the Reddit rows scores the same as a
    post in the top tenth of the X rows — and the mixed listing sorts on that.
    The card still shows each platform's real number, never this one.
    """
    for source in ("x", "reddit"):
        group = [p for p in posts if p["source"] == source]
        key = (lambda p: p["stats"].get("views", 0)) if source == "x" else (
            lambda p: p["stats"].get("score", 0))
        group.sort(key=key, reverse=True)
        n = len(group) or 1
        for i, p in enumerate(group):
            p["reach"] = round(1 - i / n, 6)
    return posts


# --------------------------------------------------------------------------- main

def main():
    use_cache = "--cache" in sys.argv
    urls = [l.strip() for l in open(URLS) if l.strip() and not l.startswith("#")]

    x_ids = list(dict.fromkeys(filter(None, (status_id(u) for u in urls))))
    wanted_reddit = set(filter(None, (reddit_id(u) for u in urls)))
    print(f"hydrating {len(x_ids)} X posts (cache={'on' if use_cache else 'off'}) "
          f"and merging {len(wanted_reddit)} Reddit posts")

    with ThreadPoolExecutor(max_workers=6) as ex:
        tweets = list(ex.map(lambda s: fetch(s, use_cache), x_ids))
    posts = [p for p in (build_x(t) for t in tweets if t) if p]

    if os.path.exists(REDDIT):
        rows = json.load(open(REDDIT))
        missing = wanted_reddit - {r["id"] for r in rows}
        if missing:
            raise SystemExit(
                f"{len(missing)} Reddit URLs in urls.txt have no row in data/reddit.json "
                f"({', '.join(sorted(missing))}). Run hydrate-reddit.mjs and commit "
                f"its output — CI cannot reach Reddit."
            )
        posts += [p for p in (build_reddit(r) for r in rows if r["id"] in wanted_reddit) if p]
    elif wanted_reddit:
        raise SystemExit("urls.txt lists Reddit posts but data/reddit.json is missing")

    rank(posts)
    posts.sort(key=lambda p: -p["reach"])

    # Manual overrides fix titles/categories and preserve prompts copied
    # verbatim from author-posted replies. Reply prompts must include their
    # public URLs so the generated gallery can cite the exact source.
    ov_path = os.path.join(ROOT, "scripts", "overrides.json")
    if os.path.exists(ov_path):
        ov = json.load(open(ov_path))
        for p in posts:
            patch = {k: v for k, v in ov.get(p["id"], {}).items()
                     if k in ("title", "category", "prompt", "prompt_source_urls",
                              "prompt_in_thread", "model")}
            if patch.get("prompt") and not patch.get("prompt_source_urls"):
                raise ValueError(f"{p['id']}: an overridden prompt needs prompt_source_urls")
            p.update(patch)

    json.dump(posts, open(OUT, "w"), indent=2, ensure_ascii=False)
    dropped = len(x_ids) + len(wanted_reddit) - len(posts)
    with_prompt = sum(1 for p in posts if p["prompt"])
    print(f"wrote {len(posts)} posts to data/posts.json "
          f"({with_prompt} with a prompt, {dropped} dropped: no image or not GPT Image 2.5)")


if __name__ == "__main__":
    main()
