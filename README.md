# Qumran

Transcriptions of the Dead Sea Scrolls, and the pipeline that turns them into
TEI, a reading edition, and release bundles.

| Folder | Contents |
|---|---|
| `original/` | `dss.txt`, and `scroll/*.txt` split out of it — the source transcriptions |
| `scripts/` | The pipeline |
| `tei/` | Generated TEI P5, one file per scroll |
| `STATS.md` | Generated corpus statistics |

Reading edition: **https://kmpenner.github.io/Qumran/**

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
| `ẋ` (U+0307) | probable letter | `<unclear cert="high">` |
| `x֯` (U+05AF) | possible letter | `<unclear cert="low">` |
| `◌` | unreadable letter | `<gap reason="illegible">` |
| `〚word〛` | scribal erasure | `<del rend="erasure">` |
| `{word}` | scribal deletion | `<del rend="dots">` |
| `^word^` | supralinear insertion | `<add place="above">` |
| `<word>` | editorial correction | `<corr>` |
| `(word)` | editorial addition | `<supplied reason="omitted">` |

## Pipeline

```
original/dss.txt  ◄──────────┐
      │                      │  sync-dss.yml, both directions
      └──────────────────────┘
                  │
   original/scroll/*.txt ──► lint.yml   fails on malformed lines
      │                                 and unbalanced brackets
      ├──► build-tei.yml ──► tei/*.xml + STATS.md
      ├──► pages.yml     ──► reading edition on GitHub Pages
      └──► release.yml   ──► TEI, TSV, transcription and site bundles (on a v* tag)
```

### Keeping the two shapes in step

`dss.txt` and `original/scroll/*.txt` hold the same content, and an edit can
land on either side. `sync-dss.yml` works out which side changed and propagates
it. If both changed in one push it fails rather than guessing which wins.

Writing back into `dss.txt` is a splice, not a regeneration: only the byte
ranges of changed scrolls are replaced, so untouched blocks keep their exact
bytes and a one-line edit stays a one-line diff.

```bash
python3 scripts/sync_dss.py check      # report drift
python3 scripts/sync_dss.py from-dss   # dss.txt wins
python3 scripts/sync_dss.py to-dss     # scroll files win
```

All the workflows that commit share the `commit-to-main` concurrency group, so
they queue instead of racing each other to push.

## Running the pipeline locally

```bash
python3 scripts/lint_transcriptions.py
python3 scripts/build_tei.py
python3 scripts/corpus_stats.py
python3 scripts/build_site.py --out site
python3 -m http.server -d site
```

## Known issues

`lint.yml` fails on six unbalanced-bracket defects. All six are real: a bracket
is opened and never closed, or closed without being opened, which corrupts the
`<supplied>` nesting in the generated TEI.

| File | Line | Brackets |
|---|---|---|
| `4Q320.txt` | 13 | 2 open, 1 close |
| `11Q19.txt` | 180 | 7 open, 8 close |
| `11Q19.txt` | 443 | 2 open, 1 close |
| `11Q19.txt` | 976 | 13 open, 14 close |
| `1QHa.txt` | 360 | 2 open, 0 close |
| `1QHa.txt` | 909 | 3 open, 2 close |

Five of the six are in `11Q19` and `1QHa`, which only entered `scroll/` when
the sync was first run — they had been sitting unchecked inside `dss.txt`.
