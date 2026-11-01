# HAHA Story Studio — Multi-platform distribution package

## Outcome

The distribution stage turns one Guardian- and human-approved 60-second story
master into publication packages for:

- Xiaohongshu;
- TikTok;
- Instagram Reels;
- YouTube Shorts.

It is a downstream adapter, not a second story generator. Platform formatting may
change the caption layout, call to action, and generic discovery hashtags, but it
cannot add cultural, historical, credential, logistics, price, or availability
claims.

## Approval gate

Distribution is available only when all of these conditions are true:

1. Story Guardian passed the source script;
2. a named human made an explicit `approve` decision;
3. the project remains in `approved` state.

Every platform asset stores the source project ID, source script ID, complete
source scene list, approved fact-reference IDs, Guardian timestamp, approver, and
approval timestamp.

## Export contents

One ZIP contains:

```text
manifest.json
xiaohongshu/
  post.md
  metadata.json
  subtitles.srt
tiktok/
  post.md
  metadata.json
  subtitles.srt
instagram_reels/
  post.md
  metadata.json
  subtitles.srt
youtube_shorts/
  post.md
  metadata.json
  subtitles.srt
```

The SRT track is computed directly from the six approved scene durations and
voiceovers. It begins at `00:00:00,000`, ends at `00:01:00,000`, and does not
summarise or rewrite factual narration.

## Platform differences

All four packages keep the approved 9:16, 60-second master. They differ only in
controlled presentation:

| Platform | Caption shape | CTA style | Generic discovery tags |
|---|---|---|---|
| Xiaohongshu | title + approved hook + CTA | save and follow | craft story / handwork / maker |
| TikTok | approved hook + CTA | follow | craft story / made by hand / maker |
| Instagram Reels | title + approved hook + CTA | save | craft story / process / maker |
| YouTube Shorts | approved hook + source note + CTA | subscribe | craft story / made by hand / Shorts |

The platform templates are deterministic and bilingual. An English story master
produces English controls; a Chinese story master produces Chinese controls. Facts
are not translated at distribution time, so a translated version must be generated,
reviewed, and approved as its own story master.

## Demo path

1. Generate a Story Studio script from confirmed facts.
2. Pass Story Guardian.
3. Approve the script as the named maker or reviewer.
4. Open **Overseas multi-platform package**.
5. Switch between the four previews and inspect title, hook, caption, CTA, and
   hashtags.
6. Download the four-platform ZIP and open the SRT and metadata files.

## Verification

Coverage in `tests/test_story_distribution.py` verifies:

- the Guardian and human approval gate;
- four unique platform assets;
- one shared approved fact set;
- exclusion of pending credential and shipping claims;
- deterministic platform copy;
- a six-scene SRT ending exactly at 60 seconds;
- complete, machine-readable ZIP contents.
