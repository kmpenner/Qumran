# Qumran

Transcriptions of the Dead Sea Scrolls, and the pipeline that turns them into
TEI, a reading edition, and release bundles.

| Folder | Contents |
|---|---|
| `English Translation/original/` | `dss.txt`, and `scroll/*.txt` split out of it — the source transcriptions |
| `English Translation/scripts/` | The pipeline |
| `English Translation/tei/` | Generated TEI P5, one file per scroll |
| `English Translation/STATS.md` | Generated corpus statistics |

The English translation of the scrolls is **not** here; it lives in the private
`LexhamEnglishDSS` repository.

## Transcription format

One line per manuscript line:

```
<siglum> <column>:<line, left-justified in 7 columns><text>
1Q19 f1:1      [ -- ][וי]ה̇י הו א֯[ -- ]
```

Markup alphabet, taken from a census of the corpus:

| Notation | Meaning | TEI |
|---|---|---|
| `[word]` | reconstructed | `<supplied reason="lost">` |
| `--` | lacuna | `<gap reason="lost">` |
| `ẋ` (U+0307) | probable letter | `<unclear cert="high">` |
| `x֯` (U+05AF) | possible letter | `<unclear cert="low">` |
| `◌` | unreadable letter | `<gap reason="illegible">` |
| `〚word〛` | scribal erasure | `<del rend="erasure">` |
| `{word}` | scribal deletion | `<del rend="dots">` |
| `^word^` | supralinear insertion | `<add place="above">` |
| `<word>` | editorial correction | `<corr>` |
| `(word)` | editorial addition | `<supplied reason="omitted">` |

## Pipeline

```
original/dss.txt
      │  splitdss.yml
      ▼
original/scroll/*.txt ──► lint.yml            fails the build on malformed
      │                                        lines and unbalanced brackets
      ├──► build-tei.yml ──► tei/*.xml + STATS.md
      ├──► pages.yml     ──► reading edition + concordance on GitHub Pages
      └──► release.yml   ──► TEI, TSV, transcription and site bundles (on a v* tag)
```

`convert_txt_to_xml.yml` is the older, shallower converter — it emits `<cb>`,
`<lb>` and `<s>` only, and drops the reconstruction markup. `build_tei.py`
supersedes it; retire it once nothing depends on its output.

All the workflows that commit share the `commit-to-main` concurrency group, so
they queue instead of racing each other to push.

## Enabling the reading edition

GitHub Pages has to be switched on once by hand:
**Settings → Pages → Build and deployment → Source: GitHub Actions.**
Until then `pages.yml` fails at "Configure Pages".

## Running the pipeline locally

```bash
python3 "English Translation/scripts/lint_transcriptions.py"
python3 "English Translation/scripts/build_tei.py"
python3 "English Translation/scripts/corpus_stats.py"
python3 "English Translation/scripts/build_site.py" --out site
python3 -m http.server -d site
```

## Known issues

- `4Q320.txt` line 13 has unbalanced brackets (2 open, 1 close); `lint.yml`
  fails on it until it is fixed.
- 14 scrolls named in `dss.txt` have no file in `original/scroll/` — `1QS`,
  `1QM`, `1QHa`, `CD`, `11Q19`, `1Q20`, `11Q10`, `4Q176`, `4Q249`, `4Q249z`,
  `4Q266`, `4Q299`, `4Q317`, `4Q364`. They are the long scrolls, handled
  elsewhere as multi-part files; confirm whether that is deliberate.
- `dss.txt` and `scroll/*.txt` are both committed, and the second is generated
  from the first. Editing a scroll file directly will be overwritten the next
  time `dss.txt` changes. Pick one as the source of truth.
