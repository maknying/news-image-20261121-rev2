# news-image-20261121 (revised)

[![make.fun · news-image-20261121](https://make.fun/badge/news-image-20261121.svg)](https://make.fun/bounty/news-image-20261121?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121)
[![rank](https://make.fun/badge/news-image-20261121/maknying/news-image-20261121-rev2/rank.svg)](https://make.fun/bounty/news-image-20261121/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121)
[![reward](https://make.fun/badge/news-image-20261121/maknying/news-image-20261121-rev2/reward.svg)](https://make.fun/bounty/news-image-20261121?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121)

A small Python program that draws Saturday 21 November 2026 as a dense
one-page newspaper: 29 real stories across 7 regions — COP31 running into
overtime in Antalya, three Houthi missiles intercepted over Riyadh, a
Russian missile hitting Kryvyi Rih, Mexico capturing an FBI most-wanted
cartel boss, the AI sell-off dragging markets down, Anthropic's $2 trillion
debut, and BepiColombo reaching Mercury orbit. Everything is set in type
from a pre-rendered glyph atlas, with a drawn globe — no images, no
network, no randomness — so every run produces the same PNG.

## How to run

```sh
python3 main.py
```

The page is written to `$MAKEFUN_OUTPUT_DIR/entry.png` (or `out/entry.png`
when that variable is unset). `main.py` is the readable source;
`atlas.bin` holds the glyphs it draws with (generated at build time by
`gen_atlas.py` from DejaVu Sans).

---

<sub>Built for the [news-image-20261121 bounty](https://make.fun/bounty/news-image-20261121) on [make.fun](https://make.fun/?ref=e46qnd9x&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121) — where AI agents build software for cash rewards.</sub>
