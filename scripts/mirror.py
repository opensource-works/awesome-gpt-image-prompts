#!/usr/bin/env python3
"""
Mirror every indexed still to R2, so the gallery never depends on a pbs.twimg
or preview.redd.it URL that the platform may rotate or expire.

For each post we take the source image at the largest size the platform will
serve, and write two WebP derivatives: a display copy capped at 1600px on the
long side, and a 640px thumbnail for grids and READMEs. Neither is ever
upscaled past the source.

    R2_ACCOUNT=... R2_KEY_ID=... R2_SECRET=... python3 scripts/mirror.py
    python3 scripts/mirror.py --dry-run       # report what's missing, upload nothing
    python3 scripts/mirror.py --force <post_id[,post_id...]>  # rebuild just these posts
    python3 scripts/mirror.py --force all                     # rebuild every post

Writes data/mirror.json: {post_id: {"image": url, "thumb": url, "width": w,
"height": h, "extra": [{"image": url, "thumb": url}, ...]}}. Objects already in
the bucket are skipped, so re-runs are cheap.

Reddit's signed preview URLs are the reason this step is not optional. They
carry an expiry in the query string, so an unmirrored Reddit row goes blank on
its own schedule with nothing in this repo changing.
"""
import json, os, re, subprocess, sys, tempfile
import concurrent.futures as cf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

BUCKET = os.environ.get("R2_BUCKET", "gpt-image-prompts")
PUBLIC = os.environ.get("R2_PUBLIC_BASE", "").rstrip("/")
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
DISPLAY_MAX = 1600
THUMB_MAX = 640
DRY = "--dry-run" in sys.argv


def _force_arg():
    """Parse --force <post_id[,post_id...]|all> from argv. A forced post has
    both derivatives rebuilt, since they are cut from the same download and a
    post that changed source would otherwise keep the old thumbnail."""
    if "--force" not in sys.argv:
        return None
    i = sys.argv.index("--force")
    if i + 1 >= len(sys.argv):
        raise SystemExit("--force requires a value: a comma-separated "
                         "list of post ids, or 'all'")
    return sys.argv[i + 1]


FORCE = _force_arg()


def source_url(url):
    """The largest copy the platform will serve.

    X sizes pbs.twimg.com media through a `name` parameter and defaults to a
    resized copy; `orig` is the upload itself. Reddit's URLs are already the
    source and their query string is a signature — touching it returns 403.
    """
    if "pbs.twimg.com" in url:
        base = url.split("?")[0]
        return f"{base}?name=orig"
    return url


def media_key(url):
    """A stable object name for one image, derived from the platform's own id.

    Both platforms name the file after the media, not the post, so this
    survives a post being re-harvested and keeps a gallery's images distinct.
    """
    path = url.split("?")[0]
    stem = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r"[^A-Za-z0-9_-]", "", stem) or "image"


def run(cmd):
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode:
        raise RuntimeError(cmd[0] + ": " + p.stderr.decode()[-400:])


def make_webp(src, dst, long_side, quality):
    """Re-encode to WebP, capped on the LONG side and never upscaled.

    `min(long_side,iw)` on width alone would blow up a portrait image, so the
    scale expression picks its axis from the source's own orientation.
    """
    scale = (
        f"scale='if(gte(iw,ih),min({long_side},iw),-2)':"
        f"'if(gte(iw,ih),-2,min({long_side},ih))':flags=lanczos"
    )
    run([FFMPEG, "-y", "-v", "error", "-i", src, "-frames:v", "1",
         "-vf", scale, "-c:v", "libwebp", "-quality", str(quality), dst])


def plan_images(post):
    """Every image of a post, primary first, as (source_url, object_stem)."""
    out = [(source_url(post["image"]["url"]), media_key(post["image"]["url"]))]
    for extra in post.get("extra_images") or []:
        out.append((source_url(extra["url"]), media_key(extra["url"])))
    return out


def main():
    if not PUBLIC:
        raise SystemExit("R2_PUBLIC_BASE must be set to the bucket's public base URL")

    posts = json.load(open(os.path.join(ROOT, "data", "posts.json")))

    # r2.py reads R2_ACCOUNT/R2_KEY_ID/R2_SECRET at import time and ls() hits
    # the network, so a dry run must not require either — it only needs to
    # report what's missing, and with no credentials that just means "assume
    # nothing is mirrored yet."
    have_creds = all(os.environ.get(k) for k in ("R2_ACCOUNT", "R2_KEY_ID", "R2_SECRET"))
    if have_creds:
        import r2
        existing = set(r2.ls(BUCKET))
        print(f"bucket {BUCKET}: {len(existing)} objects already there")
    elif DRY:
        existing = set()
        print("no R2 credentials in the environment — treating the bucket as "
              "empty for this dry run")
    else:
        raise SystemExit("R2_ACCOUNT / R2_KEY_ID / R2_SECRET must be set to mirror "
                         "(use --dry-run to preview without needing them)")

    if FORCE == "all":
        forced = {p["id"] for p in posts}
    elif FORCE:
        forced = {x.strip() for x in FORCE.split(",") if x.strip()}
    else:
        forced = set()
    if forced:
        print(f"forcing a full rebuild for {len(forced)} post(s): {', '.join(sorted(forced))}")

    manifest, todo = {}, []
    for p in posts:
        images = plan_images(p)
        entries, need = [], []
        for src, stem in images:
            display, thumb = f"{stem}.webp", f"{stem}.thumb.webp"
            entries.append({"image": f"{PUBLIC}/{display}", "thumb": f"{PUBLIC}/{thumb}"})
            for key in (display, thumb):
                if key not in existing or p["id"] in forced:
                    need.append((src, key, display == key))
        manifest[p["id"]] = {
            "image": entries[0]["image"],
            "thumb": entries[0]["thumb"],
            "width": p["image"].get("width"),
            "height": p["image"].get("height"),
            "extra": entries[1:],
        }
        if need:
            todo.append((p, need))

    print(f"{len(posts)} posts | {len(todo)} need work | {len(posts)-len(todo)} already mirrored")
    if DRY or not todo:
        json.dump(manifest, open(os.path.join(ROOT, "data", "mirror.json"), "w"),
                  indent=2, ensure_ascii=False)
        print("dry run — nothing uploaded" if DRY else "nothing to do")
        return

    done, failed = [], []

    def handle(item):
        p, need = item
        tag = f"@{p['author']['handle']}"
        total = 0
        # One download per distinct source, both derivatives cut from it.
        by_source = {}
        for src, key, is_display in need:
            by_source.setdefault(src, []).append((key, is_display))
        with tempfile.TemporaryDirectory() as tmp:
            for i, (src, keys) in enumerate(by_source.items()):
                local = os.path.join(tmp, f"src{i}")
                run(["curl", "-sL", "--max-time", "180", "-o", local, src])
                n = os.path.getsize(local)
                if n < 2000:
                    raise RuntimeError(f"download too small ({n}B) for {src}")
                total += n
                for key, is_display in keys:
                    dst = os.path.join(tmp, key)
                    make_webp(local, dst,
                              DISPLAY_MAX if is_display else THUMB_MAX,
                              82 if is_display else 74)
                    r2.put(BUCKET, key, open(dst, "rb").read(), "image/webp")
        return tag, total

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(handle, it): it for it in todo}
        for i, f in enumerate(cf.as_completed(futs), 1):
            it = futs[f]
            try:
                tag, n = f.result()
                done.append(n)
                print(f"  [{i}/{len(todo)}] {tag} {n/1e6:.1f} MB")
            except Exception as e:
                failed.append((it[0]["author"]["handle"], str(e)[:120]))
                print(f"  [{i}/{len(todo)}] FAIL @{it[0]['author']['handle']}: {str(e)[:120]}")

    json.dump(manifest, open(os.path.join(ROOT, "data", "mirror.json"), "w"),
              indent=2, ensure_ascii=False)
    print(f"\nmirrored {len(done)} posts, {sum(done)/1e6:.0f} MB downloaded")
    if failed:
        print(f"{len(failed)} failed:")
        for h, e in failed:
            print(f"  @{h}: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
