# Original UI baseline

Verified 2026-10-17: origin/main `7f8922cad8adb7e73a5f95ecfbf5b1a73e5bd46f`;
feature/visual-mentor `245b686c916f0fcb0aff50b305e27f399c32910d`;
deployment PR branch `c59fcf7495bbb6a59f45fd7e2f06c48e594547e1`.
New development starts from main, not either donor branch. Prior branches remain unchanged.

Protected: Library landing and three-column thumbnail cards, 1280px maximum content width,
24px gutters, system sans typography, dark #0d0d0d page / #1a1a19 surfaces,
#3987e5 accent; Nav/NavLinks, Controls, SegmentCard, ClipPlayer,
Search single/dim/view comparisons, Ask citation buttons and history,
Experiments Recharts/heatmap and query table, Architecture diagram,
video details with transcript and segment timeline. Mobile refinements may wrap controls.

Baseline screenshots use deterministic synthetic sample metadata and actual generated playable media.
Provider responses in browser fixtures are mocked, including experimental scores;
these are UI regression data, never inference/evaluation evidence.
Capture sizes: 1440×1000, 1280×900, 768×1024, 390×844.
No authenticated HF credentials are configured; no openweb screenshot comparison is claimed.

Initial capture gate: 5 browser tests passed (27.4s), including all 24 screenshots
and clip/citation interactions. Moving video pixels are masked for deterministic
image comparisons; video playback is checked separately. Main's Google font request
is unavailable here; Next used its documented fallback. No UI layout was changed.
