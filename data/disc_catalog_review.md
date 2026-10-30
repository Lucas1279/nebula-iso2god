# Xbox 360 disc catalogue build review

- Redump DAT snapshot: 2026-10-30; source lists 3733 media entries.
- CSV source rows parsed: 4047; exact Title ID + Media ID records: 2577.
- Redump games with explicit role terms: 51.
- Automatically joined role records: 31; conflicting role identities: 0.
- Labeled Redump entries not joined: 4.

## Automatic role assignments (review before shipping)

| Title ID | Media ID | Game-list name | Region(s) | Disc | Role | Redump label(s) |
|---|---|---|---|---:|---|---|
| 415608FC | 3CC5A411 | Call of Duty: Ghosts (Disc 1) | RF | 1 | playable | Call of Duty - Ghosts (Japan) (Disc 1) (Game Disc) (Fukikaeban); Call of Duty - Ghosts (Japan) (Disc 1) (Game Disc) (Jimakuban); Call of Duty - Ghosts (USA, Europe) (Disc 1) (Game Disc) |
| 415608FC | 56374F6E | Call of Duty: Ghosts (Disc 2) | NTSC/J (Excludes China) | 2 | install | Call of Duty - Ghosts (Japan) (Disc 2) (Install Disc); Call of Duty - Ghosts (USA, Europe) (En,Fr,De,Es,It,Pt,Pl,Ru) (Disc 2) (Install Disc) |
| 415608FC | 5C90116D | Call of Duty: Ghosts (Disc 1) | PAL | 1 | playable | Call of Duty - Ghosts (Japan) (Disc 1) (Game Disc) (Fukikaeban); Call of Duty - Ghosts (Japan) (Disc 1) (Game Disc) (Jimakuban); Call of Duty - Ghosts (USA, Europe) (Disc 1) (Game Disc) |
| 415608FC | 6E412B07 | Call of Duty: Ghosts (Disc 2) | RF | 2 | install | Call of Duty - Ghosts (Japan) (Disc 2) (Install Disc); Call of Duty - Ghosts (USA, Europe) (En,Fr,De,Es,It,Pt,Pl,Ru) (Disc 2) (Install Disc) |
| 41560920 | 4A135223 | Guitar Hero Live (Disc 2) | RF | 2 | install | Guitar Hero Live (USA, Europe) (En,Fr,De,Es,It) (Disc 2) (Install Disc) |
| 41560920 | 7B22125D | Guitar Hero Live (Disc 1) | RF | 1 | playable | Guitar Hero Live (USA, Europe) (En,Fr,De,Es,It) (Disc 1) (Game Disc) |
| 43430814 | 0F61AFF2 | Dragon's Dogma: Dark Arisen (Disc 1) | RF | 1 | playable | Dragon's Dogma - Dark Arisen (World) (En,Ja,Fr,De,Es,It) (Disc 1) (Game Disc) |
| 43430814 | 596DD4A7 | Dragon's Dogma: Dark Arisen (Disc 2) | RF | 2 | install | Dragon's Dogma - Dark Arisen (World) (Disc 2) (Install Disc) |
| 43430819 | 4EA1CC2E | Resident Evil 6 (Disc 1) | RF | 1 | playable | Resident Evil 6 (Germany) (En,Fr,De,Es,It,Pt,Pl,Ru) (Disc 1) (Game Disc); Resident Evil 6 (World) (En,Ja,Fr,De,Es,It,Pt,Pl,Ru) (Disc 1) (Game) |
| 45410949 | 7C44607E | Dragon Age: Origins Ultimate Edition (Disc 2) (Unofficial DB Name) | PAL | 2 | install | Dragon Age - Origins - Ultimate Edition (USA, Europe) (Disc 2) (Additional Content Packs Install Disc) |
| 45410950 | 511536A8 | Battlefield 3 (Disc 2) | PAL, NTSC/U | 2 | playable | Battlefield 3 (Japan, Korea) (En,Ja,Zh,Ko) (Disc 2) (Single-Play) |
| 454109E0 | 2B4E0DEA | Battlefield Hardline (Disc 1) | RF | 1 | install | Battlefield Hardline (World) (En,Ja,Fr,De,Es,It,Pt,Zh,Ko,Pl,Ru,Cs) (Disc 1) (Install-Multiplayer) |
| 4D53084D | 04DEF72C | Forza Motorsport 3 (Disc 1) | NTSC/J (Excludes China) | 1 | playable | Forza Motorsport 3 (Europe, Australia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc); Forza Motorsport 3 (Japan, Asia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc); Forza Motorsport 3 (USA) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc) |
| 4D53084D | 0670AEF8 | Forza Motorsport 3 (Disc 2) | PAL | 2 | install | Forza Motorsport 3 (Europe, Australia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc); Forza Motorsport 3 (Japan, Asia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc); Forza Motorsport 3 (USA) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc) |
| 4D53084D | 0CC8C158 | Forza Motorsport 3 (Disc 1) | NTSC/U | 1 | playable | Forza Motorsport 3 (Europe, Australia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc); Forza Motorsport 3 (Japan, Asia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc); Forza Motorsport 3 (USA) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc) |
| 4D53084D | 1235FA6A | Forza Motorsport 3 (Disc 2) | NTSC/U | 2 | install | Forza Motorsport 3 (Europe, Australia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc); Forza Motorsport 3 (Japan, Asia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc); Forza Motorsport 3 (USA) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc) |
| 4D53084D | 4BE13908 | Forza Motorsport 3: Ultimate Collection (Disc 1) | PAL | 1 | playable | Forza Motorsport 3 - Ultimate Collection (Europe, Australia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc); Forza Motorsport 3 - Ultimate Collection (USA) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc) |
| 4D53084D | 5DD89BE4 | Forza Motorsport 3 (Disc 1) | PAL | 1 | playable | Forza Motorsport 3 (Europe, Australia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc); Forza Motorsport 3 (Japan, Asia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc); Forza Motorsport 3 (USA) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc) |
| 4D53084D | 706E78F1 | Forza Motorsport 3 (Disc 2) | NTSC/J (Excludes China) | 2 | install | Forza Motorsport 3 (Europe, Australia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc); Forza Motorsport 3 (Japan, Asia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc); Forza Motorsport 3 (USA) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc) |
| 4D53084D | 79276431 | Forza Motorsport 3: Ultimate Collection (Disc 2) | PAL | 2 | install | Forza Motorsport 3 - Ultimate Collection (Europe, Australia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc); Forza Motorsport 3 - Ultimate Collection (USA) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc) |
| 4D530910 | 0F5C87F9 | Forza Motorsport 4 (Disc 2) | NTSC/U | 2 | install | Forza Motorsport 4 (Europe) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc) (Rev 1); Forza Motorsport 4 (Europe, Australia) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc); Forza Motorsport 4 (Japan, Asia) (Disc 2) (Content Install Disc); Forza Motorsport 4 (USA) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc); Forza Motorsport 4 (USA) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc) (Rev 1) |
| 4D530910 | 26FF1101 | Forza Motorsport 4 (Disc 1) | NTSC/U | 1 | playable | Forza Motorsport 4 (Europe) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc) (Rev 1); Forza Motorsport 4 (Europe, Australia) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc); Forza Motorsport 4 (Japan, Asia) (Disc 1) (Play Disc); Forza Motorsport 4 (USA) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc); Forza Motorsport 4 (USA) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc) (Rev 1) |
| 4D530910 | 527B075C | Forza Motorsport 4 (Disc 2) | PAL | 2 | install | Forza Motorsport 4 (Europe) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc) (Rev 1); Forza Motorsport 4 (Europe, Australia) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc); Forza Motorsport 4 (Japan, Asia) (Disc 2) (Content Install Disc); Forza Motorsport 4 (USA) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc); Forza Motorsport 4 (USA) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc) (Rev 1) |
| 4D530910 | 61D62D9F | Forza Motorsport 4 (Disc 1) | PAL | 1 | playable | Forza Motorsport 4 (Europe) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc) (Rev 1); Forza Motorsport 4 (Europe, Australia) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc); Forza Motorsport 4 (Japan, Asia) (Disc 1) (Play Disc); Forza Motorsport 4 (USA) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc); Forza Motorsport 4 (USA) (En,Ja,Fr,De,Es,It,Nl,Pt,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc) (Rev 1) |
| 5345085E | 6C4728D7 | Alien: Isolation (Disc 1) | RF | 1 | install | Alien - Isolation (USA, Europe) (En,Fr,De,Es,It,Pt,Pl,Ru) (Disc 1) (Installation Disc) |
| 5454082B | 26302E11 | Red Dead Redemption -- Game of the Year Edition (Disc 2) | RF | 2 | playable | Red Dead Redemption - Game of the Year Edition (USA, Europe) (En,Fr,De,Es,It) (Disc 2) (Undead Nightmare and Multiplayer) |
| 5454082B | 3EE87B76 | Red Dead Redemption -- Game of the Year Edition (Disc 1) | RF | 1 | playable | Red Dead Redemption - Game of the Year Edition (USA, Europe) (En,Fr,De,Es,It) (Disc 1) (Red Dead Redemption Single Player) |
| 545408A7 | 0C48794E | Grand Theft Auto V (Disc 1) | RF | 1 | install | Grand Theft Auto V (Japan) (En,Ja) (Disc 1) (Install); Grand Theft Auto V (Japan) (En,Ja) (Disc 1) (Install) (Rev 1); Grand Theft Auto V (World) (En,Fr,De,Es,It,Pt,Zh,Ko,Pl,Ru) (Disc 1) (Install) |
| 545408A7 | 79E465C5 | Grand Theft Auto V (Disc 2) | RF | 2 | playable | Grand Theft Auto V (Japan) (En,Ja) (Disc 2) (Play); Grand Theft Auto V (Japan) (En,Ja) (Disc 2) (Play) (Rev 1); Grand Theft Auto V (World) (En,Fr,De,Es,It,Pt,Zh,Ko,Pl,Ru) (Disc 2) (Play) |
| 555308B7 | 1DEB466B | Watch_Dogs (Disc 1) | RF | 1 | install | Watch_Dogs (USA, Europe) (En,Fr,De,Es,It,Nl,Pt,Sv,No,Da,Fi) (Disc 1) (Installation Disc); Watch_Dogs (World) (En,Pt) (Disc 1) (Installation Disc) |
| 555308B7 | 54A95DF1 | Watch_Dogs (Disc 2) | RF | 2 | playable | Watch_Dogs (USA, Europe) (En,Fr,De,Es,It,Nl,Pt,Sv,No,Da,Fi) (Disc 2) (Game Disc); Watch_Dogs (World) (En,Pt) (Disc 2) (Game Disc) |

## Conflicts (must remain unknown)

| Key | Name | Candidate roles | Source labels |
|---|---|---|---|

## Unmatched Redump role-labeled entries

| Label | Role | Reason |
|---|---|---|
| Forza Motorsport 3 - Ultimate Edition (Japan, Asia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 1) (Play Disc) | playable | no exact title/disc crosswalk |
| Forza Motorsport 3 - Ultimate Edition (Japan, Asia) (En,Ja,Fr,De,Es,It,Zh,Ko,Pl,Ru,Cs,Hu) (Disc 2) (Content Install Disc) | install | no exact title/disc crosswalk |
| Saints Row - The Third - The Full Package (Japan) (Disc 2) (Install Disc) | install | no exact title/disc crosswalk |
| Saints Row IV - National Treasure Edition (USA, Europe) (En,Fr,De,Es,It) (Disc 1) (Installation Disc) | install | no exact title/disc crosswalk |
