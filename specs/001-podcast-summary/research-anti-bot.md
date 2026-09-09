# Research: reaching YouTube and Bilibili without hand-maintained cookies

**Date:** 2026-09-09
**Question:** how do we keep video ingestion working without someone periodically
re-exporting browser cookies?

**Answer:** stop using login state. Everything below is reachable anonymously;
the state that used to expire is now either fetched by the code on demand or not
needed at all. The one genuine exception is members-only / age-gated media,
which no technique reaches without a real account.

## What was measured

All figures come from running the real extractor against live URLs from a
residential IP on 2026-09-09.

| Claim | Evidence |
|---|---|
| Bilibili serves audio anonymously | `BV1XV411o7ra` exposes 3 audio-only DASH formats (`30216`/`30232`/`30280`, up to 110 kbps m4a) with no cookies. Only the 1080p+ **video** streams need login, and this pipeline never wants them. |
| Bilibili's HTTP 412 is probabilistic, not a header problem | Identical headers, repeated 6× three seconds apart: `200, 412, 200, 412, 200, 200`. No header combination removed it. |
| An anonymous fingerprint helps but does not fix it | Without cookies: 2/5 extractions succeeded. With an anonymous `buvid3`/`buvid4` jar: 4/6. |
| `extractor_retries` does not cover it | The 412 lands while the extractor fetches the page, before yt-dlp's own retry budget applies. Only a fresh `YoutubeDL` per attempt recovers. |
| YouTube needs no cookies and no PO token provider | With yt-dlp 2026.08.19 and `PO Token Providers: none`, a full audio download completes. |
| YouTube *does* need a current yt-dlp | 2026.07.04 fails every download with `HTTP 403` (it routes through the `ANDROID_VR` client, whose media URLs are byte-capped: ranges ≤256 KiB return 206, ≥1 MiB return 403, and a chunked download still dies near 22%). 2026.08.19 routes through the `web` client and succeeds. |

## What this means for the code

1. **Never read browser cookies.** `cookiesfrombrowser` was removed. On macOS it
   requires Chrome to be fully closed, YouTube rotates the cookies it is handed
   (silently logging the human out), and yt-dlp warns that account cookies risk
   the account.
2. **Retry Bilibili in the application.** `YTDLP_MAX_ATTEMPTS` (default 5) with a
   fresh `YoutubeDL` per attempt. At the measured ~67% per-attempt success rate
   five attempts leave a ~0.4% residual failure rate, and the pipeline's own
   per-stage retry sits above that.
3. **Fetch Bilibili's fingerprint at run time.** `api.bilibili.com/x/frontend/finger/spi`
   hands out `buvid3`/`buvid4` to anyone. Cached in-process for 6 hours, written
   per episode because yt-dlp rewrites the jar on exit and concurrent jobs must
   not share one.
4. **Keep yt-dlp current.** This is the single highest-value maintenance action;
   the floor is pinned to the version actually verified (`>=2026.8.19`).
5. **Cookies stay available but opt-in.** `YTDLP_COOKIEFILE` exists solely for
   members-only or age-gated media, and is the only path that still needs manual
   refreshing.

## Bugs this work uncovered

- `remote_components` was passed as the string `"ejs:github"`. yt-dlp normalises
  it to a set, so a bare string is iterated character by character; every
  character was rejected and the component silently never loaded.
- `_youtube_error_message` classified errors with `"age" in message`. `"age"` is a
  substring of `"webpage"`, so `Unable to download webpage: HTTP Error 412` — the
  single most common Bilibili failure — was reported to users as "requires
  login". Now matched with word boundaries.
- `YTDLP_COOKIEFILE=` left blank in `.env` parsed to `Path(".")`, which yt-dlp
  would try to read as a cookie jar. Blank values now normalise to unset.

## Known limits

- Members-only, age-gated, region-locked and DRM content is out of reach without
  a real account. These surface as "restricted or requires login" and are not
  retried.
- A datacenter IP will behave far worse than the residential IP measured here,
  particularly for YouTube. None of the above compensates for that.
- Bilibili's 412 rate is not under our control and may drift; the retry count is
  the knob.
- **Some Bilibili videos are unreachable from outside mainland China**, and no
  amount of retrying fixes it. Bilibili assigns DASH streams to PCDN edge nodes
  (`*.mcdn.bilivideo.cn`) whose TLS handshake simply dies:
  `SSL: UNEXPECTED_EOF_WHILE_READING`, reproduced with `curl` as well as the
  extractor. For `BV14dYx6iEwC`, 4 of 4 successful extractions put every audio
  stream on such a host; the signed URLs are host-bound, so rewriting the
  hostname to a normal `upos-*.bilivideo.com` mirror returns 403, and the
  `prefer_multi_flv` format set lands on the same nodes. This is a network-path
  problem, not an anti-bot one — the same video downloads normally from inside
  mainland China or through a mainland egress. `BV1XV411o7ra`, assigned to a
  regular CDN, downloads fine on the same connection.

## Pasted share text

Bilibili's share button produces a whole sentence, e.g.
`【标题】https://www.bilibili.com/video/BV14dYx6iEwC?vd_source=e352aac...`.
The API extracts the first URL from whatever is submitted and drops
share-tracking parameters (`vd_source`, `spm_id_from`, `si`, `feature`, …) while
keeping parameters that describe the media (`p`, `t`, `v`). Two people sharing
the same video therefore produce the same `source_ref`, which is what the
episode dedupe index keys on. Direct audio URLs get the extraction but keep
their query string intact, since those links may be presigned.
