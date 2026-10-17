# UI parity review

[Open desktop/mobile screenshot comparison](v2-evidence/ui-comparison.html).
Baseline images are immutable snapshots from main before feature work;
current images live in committed Playwright screenshot directories. Main has no
Live or Models routes, so their comparison explicitly says no baseline exists.
All screenshot data is synthetic, not a live provider demonstration.

| Original workflow | v2 evidence / intentional differences |
| --- | --- |
| Library landing, dense thumbnail grid and summary cards | Same Library component and tokens; import disclosure and private-library access added; labeled synthetic teaching slides replace test bars |
| Search query/deep links, single/dim/view comparisons | Same SearchView/cards; only actual indexed capabilities selectable; remote text/keyword sample distinction explicit |
| Ask cited evidence/history, inline clip modal | Original citation renderer and player retained; keyframe wording and missing token usage corrected |
| Experiments metric chart, heatmap, query table | Original Recharts/heatmap preserved; model/provenance label replaces false live benchmark claims |
| Architecture flow diagram | Same diagram components; current topology remote CPU, historical multimodal/MRL diagrams explicitly labeled |
| Video details, transcript, timeline and seeking | Original detail layout; graceful errors; authenticated media and public synthetic sample path |
| Keyboard and narrow navigation | Focus indicators and wrapped nav/control groups; 390px, 768px, 1280px and 1440px screenshots |
| Live addition | Original card/control tokens, fluid local previews, exact-still overlays, explicit capture/transfer, timeline and guidance |
| Models addition | Original dark palette/cards, native route matrix and form builder, YAML review/apply, synthetic trace and admin backup status |

Automated gate before feature work: 24 original screenshots + clip/citation
interactions passed. Current suite compares the intentional new baseline and
retains original screenshots for human review. It does not claim pixel equality
with main after adding navigation, safety copy, import and access controls.
Screenshots include Next dev's cache-disabled badge; it is absent from the
production Docker build. Font download was unavailable for main capture; v2 uses
the same system sans and a local monospace fallback without runtime font egress.

A physical browser/hardware and final user visual approval remain staging gates.
No screenshots of inaccessible private openweb were invented.
