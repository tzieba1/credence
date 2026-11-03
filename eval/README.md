# The evaluation set

Eighteen documents, each in its own directory under `cases/`:

```
eval/cases/<id>/document.pdf   the input
eval/cases/<id>/gold.json      what a correct extraction says
eval/cases/<id>/meta.json      where it came from and what makes it hard
```

Sixteen are certificates. Two are not, and the right answer for them is a record with every field null.

## Gold format

`gold.json` holds exactly the seven compared fields. Dates are ISO 8601. A field the document does not state is `null`, and a value the model invents for it counts as wrong. Text values are what the document prints, character for character; the runner normalises whitespace and case before comparing, so the gold does not have to anticipate that.

```json
{
  "issuer": "Northgate Certification Services Ltd",
  "holder": "Harwell Precision Engineering plc",
  "certificate_number": "NCS-QMS-2024-0417",
  "issue_date": "2024-03-14",
  "expiry_date": "2027-03-13",
  "scope": "Design and manufacture of machined aluminium housings for medical devices",
  "signatory": "Margaret Okonkwo"
}
```

The model's `notes` field has no gold value and is never compared.

## Sources

**Generated (all 18 so far).** The specifications live in `src/credence/synth/cases.py` and are rendered with reportlab, so every gold label is known by construction rather than labelled after the fact. Four layouts (a centred classic, a two-column grid, prose, and a landscape card with a logo), three fonts, three languages (English, Spanish, French), six date wordings, and distractors placed on purpose: letter dates that differ from the issue date, accreditation and registration numbers, batch numbers, cover letters signed by someone other than the signatory, annexes naming an auditor. Five cases are rasterised, tilted by up to a degree and a half, grained and blurred, then written back as image-only PDFs with no text layer. Every company, person and certificate number is invented.

Regenerate the set with:

```sh
uv run python -m credence.synth
```

The output is deterministic for the text-based cases. The scanned ones are deterministic on one machine; a different PDF rasteriser build can differ by a pixel, which is why the tests compare the committed files to the specifications rather than byte for byte to a fresh render.

**Public (none yet).** The plan calls for a handful of real, publicly available certificates labelled by hand. None are included yet: redistributing a third party's PDF in a public repository needs a licence check per document, and that decision is made by hand, not by the generator. When they are added, each will carry a `meta.json` with `"source": "public"`, the URL it was fetched from, and the licence.

## Cases

| id | layout | language | dates | pages | scanned | what makes it hard |
|---|---|---|---|---|---|---|
| `g01-classic-en-iso` | classic | en | iso | 1 | no | The baseline: clean layout, ISO dates, every field present. |
| `g02-classic-en-long` | classic | en | long | 1 | no | Dates written out in words; the signatory carries an honorific and a title. |
| `g03-table-en-us-numeric` | table | en | mdy | 1 | no | US month-first numeric dates, plus an accreditation registration number and a street number as distractors for the certificate number. |
| `g04-table-en-mixed-dates` | table | en | dmy + long | 1 | no | Two date formats on one page: day-first numeric for the issue date, words for the expiry. |
| `g05-letter-en-no-expiry` | letter | en | long_us | 1 | no | Prose layout with no expiry: the text says the certificate does not expire, so the gold is null and a guessed date is wrong. |
| `g06-letter-en-no-signatory` | letter | en | long | 1 | no | Prose layout with no signature block at all; the signatory is null. |
| `g07-classic-es-long` | classic | es | long | 1 | no | Spanish labels and dates in words; accented names must survive intact. |
| `g08-table-fr-long` | table | fr | long | 1 | no | French labels and dates; the signatory's name starts with an accented capital. |
| `g09-card-en-logo` | card | en | iso | 1 | no | Landscape card with a logo and a monospaced font; little text to go on. |
| `g10-classic-en-multipage` | classic | en | long | 3 | no | Three pages: a cover letter with its own date and reference, the certificate, and an annex of sites. The fields are on page two only. |
| `g11-scan-classic-en` | classic | en | long | 1 | yes | Image-only, slightly skewed. No text layer; the model reads pixels. |
| `g12-scan-table-es` | table | es | dmy | 1 | yes | Scanned Spanish table, skewed the other way, day-first numeric dates. |
| `g13-scan-letter-fr-no-signatory` | letter | fr | dmy | 2 | yes | Two scanned pages of French prose with no signature; the annex adds more names and numbers to ignore. |
| `g14-scan-card-en` | card | en | mdy | 1 | yes | Scanned landscape card with a logo and a one-year validity. |
| `g15-classic-en-dotted` | classic | en | dotted | 1 | no | Dotted European dates and an accreditation line that itself mentions a certificate number which is not this certificate's. |
| `g16-table-en-no-expiry-no-signatory` | table | en | iso | 1 | no | Both expiry and signatory absent on an otherwise complete grid; two nulls are correct, and a batch number is a distractor. |
| `n01-invoice-en` | invoice | en | iso | 1 | no | Not a certificate. An invoice with a number, dates and two company names; every field should be null. |
| `n02-scan-memo-es` | memo | es | long | 1 | yes | Not a certificate. A scanned Spanish internal memo that mentions an audit and a certificate by number; every field should still be null. |

Date wordings: `iso` 2024-03-14, `long` 14 March 2024 (or 14 de marzo de 2024, 14 mars 2024), `long_us` March 14, 2024, `dmy` 14/03/2024, `mdy` 03/14/2024, `dotted` 14.03.2024. Numeric dates in the set always have a day above twelve, so the ordering can be worked out from the page and the gold is never a coin toss.

## What the tests check

`tests/test_synth.py` renders every case and asserts that the text layer of each text-based PDF contains every gold value (and the "does not expire" or "valid without signature" sentence where a field is null), that scanned PDFs have no text layer at all, and that rendering is reproducible. `tests/test_eval_cases.py` asserts that the committed `gold.json`, `meta.json` and page counts under `eval/cases/` match the specifications, and that this file lists every case.
