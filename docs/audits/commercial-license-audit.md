# ChirpWise Commercial License Audit

Generated: `2026-05-07T11:04:36.602499+00:00`

This audit treats ChirpWise as a paid app and treats every bundled practice sound as a modified/adapted clip because the pipeline trims recordings for quiz use.

This is an engineering triage report, not legal advice. It is meant to decide which clips should ship in a paid build, which clips require recordist permission, and which birds need replacement audio.

## Result

- Total bundled clips audited: 1114
- Paid trimmed app-safe clips: 20
- Clips needing replacement or recordist permission: 1094
- App-safe species represented: 20
- Species needing replacement or permission: 1064

## License Counts

| License | Clips | Paid trimmed app-safe | Not app-safe |
| --- | ---: | ---: | ---: |
| CC BY-NC-SA 4.0 | 903 | 0 | 903 |
| CC BY-NC-ND 4.0 | 89 | 0 | 89 |
| CC BY-NC-ND 2.5 | 51 | 0 | 51 |
| CC BY-NC-SA 3.0 | 43 | 0 | 43 |
| CC BY-SA 4.0 | 11 | 11 | 0 |
| CC0-1.0 | 8 | 8 | 0 |
| CC BY-NC-ND 3.0 | 7 | 0 | 7 |
| CC BY 4.0 | 1 | 1 | 0 |
| CC BY-NC 4.0 | 1 | 0 | 1 |

## Rule Used

| License family | Paid app | Trimmed clip | Audit decision |
| --- | --- | --- | --- |
| CC0 / public domain | yes | yes | app-safe |
| CC BY | yes | yes | app-safe with attribution |
| CC BY-SA | yes | yes | app-safe, ShareAlike required for the adapted clip |
| CC BY-NC / CC BY-NC-SA | no | maybe | exclude from paid app unless permission is granted |
| CC BY-ND / CC BY-NC-ND | mixed | no | exclude because ChirpWise ships trimmed clips |

## Attribution Fields Required In App

For every clip shown to a user, preserve:

- Species name
- Xeno-canto recording ID
- Recordist
- Exact source URL
- License name and URL
- Change note, e.g. `Trimmed to 20 seconds for quiz use`

## Files

- `commercial-license-audit.csv`: row-by-row spreadsheet audit
- `commercial-license-audit.json`: same audit with machine-readable summary

## Source Notes

- Creative Commons license deeds and FAQ were used for NC, ND, BY, SA, CC0, commercial-use, derivative/adaptation, and attribution rules.
- Xeno-canto API metadata supplies `rec`, `lic`, `url`, and recording IDs; the local database preserves those fields per clip.
