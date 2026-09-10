# Contributing

The fastest way to help is to add posts we missed.

## Add a post from X

1. Find a post on X that shows a **GPT Image 2.5 image**.
2. Add its URL on its own line in [`scripts/urls.txt`](scripts/urls.txt).
3. Open a pull request. That's it — you don't need to run anything locally.

A post gets included automatically if it has a still attached and names GPT Image 2.5.
Everything else — the caption, the prompt, the author's name and handle, the view
count — is pulled from the post itself. If the exact prompt is in a public reply by the
same source account, it can be preserved with a source link as described below.

## Add a post from Reddit

Reddit takes one extra step, and there is no way around it: Reddit refuses anonymous
API access from every host and user agent we tried, so CI cannot fetch a Reddit post.
Its data has to arrive with the pull request.

1. Add the permalink to [`scripts/urls.txt`](scripts/urls.txt) as usual.
2. Add a row to [`data/reddit.json`](data/reddit.json) with the post's own values:

```json
{
  "id": "1wcgjqp",
  "url": "https://www.reddit.com/r/ChatGPT/comments/1wcgjqp/...",
  "subreddit": "ChatGPT",
  "title": "…",
  "selftext": "…",
  "author": "someone",
  "date": "2026-09-10",
  "createdAt": "2026-09-10T04:12:33.000Z",
  "score": 512,
  "comments": 84,
  "images": [{ "url": "https://i.redd.it/….png", "width": 1536, "height": 1024 }]
}
```

Opening `https://www.reddit.com/comments/<id>.json` in a browser you are signed in to
gives you every one of those fields. Copy them; do not adjust them.

A build fails loudly if `urls.txt` names a Reddit post with no row here, rather than
quietly dropping it.

## What belongs here

- Real GPT Image 2.5 output: images someone actually generated and posted.
- Prompts, workflows and technique breakdowns.
- Honest failure cases and model comparisons. A post does not have to be flattering.

## What doesn't

- Reposts of someone else's generation without credit.
- Images that aren't GPT Image 2.5.
- Launch notices and discount codes. A prompt with a tracking link inside it is an ad.
- Pure engagement bait with no image and no prompt.

## Fixing a title, category or reply prompt

Titles and categories are guessed from the post text, so some land wrong. Correct them in
[`scripts/overrides.json`](scripts/overrides.json), keyed by post id:

```json
"2095556181012128005": {
  "title": "Einstein's handwriting from a plain description",
  "category": "Text & Typography"
}
```

The accepted fields are `title`, `category`, `model`, `prompt`, `prompt_source_urls` and
`prompt_in_thread`. A reply prompt must be copied verbatim, list every public post or
reply used as its source, and set `prompt_in_thread` to `false`. Author names and stats
are never overridden.

## Regenerating everything

```bash
python3 scripts/harvest.py          # urls.txt + data/reddit.json -> data/posts.json
python3 scripts/mirror.py           # copy stills to R2 and cut thumbnails
python3 scripts/build.py            # data/posts.json -> docs/ + both READMEs
```

`harvest.py --cache` reuses `.cache/` and only fetches URLs it hasn't seen, which is
much faster while you're iterating. It needs no API key or login.

`mirror.py` is the only step that needs credentials (`R2_ACCOUNT`, `R2_KEY_ID`,
`R2_SECRET`, plus `R2_BUCKET` and `R2_PUBLIC_BASE`) and `ffmpeg` on your PATH. You can
skip it locally — CI runs it for you on merge, so a PR that only adds a URL doesn't need
to touch R2 at all.

Why the mirror exists: X rotates its `pbs.twimg.com` URLs, and Reddit signs its
`preview.redd.it` URLs with an expiry. Left unmirrored, a Reddit entry goes blank on its
own schedule with nothing in this repo having changed. The mirror keeps a WebP display
copy capped at 1600px on the long side, plus a 640px thumbnail for grids, neither ever
upscaled past the source.

Please don't hand-edit `data/posts.json`, `data/mirror.json`, `docs/index.html` or the
READMEs — they are generated, and your changes will be overwritten on the next build.

## If it's your post

Everything here is credited and links back to you. If you'd still rather not be listed,
or something is wrong, [open an issue](https://github.com/opensource-works/awesome-gpt-image-prompts/issues/new)
and it comes down — no questions asked.
