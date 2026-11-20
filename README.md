# RIDDIM BOX — firmware & émulateur pour le M-VAVE FM-1

**[Jouer l'émulateur](https://altessproduction.github.io/RIDDIM-BOX/)** ·
[Les firmwares](firmware/) · [L'analyse B36014](docs/04-b36014-uc25hq80.md) ·
[L'outillage .fwsc](tools/) · [Les sources](sources/)

Ce dépôt réunit deux choses autour du synthétiseur de poche **M-VAVE FM-1** :

1. **un émulateur web qui exécute le vrai firmware** — la même architecture que
   l'émulateur [Sloop-DUB](https://altessproduction.github.io/sloop-dub-fm1/dub/) :
   les sources du firmware compilées en WebAssembly, tournant dans un
   AudioWorklet, derrière une faceplate FM-1 ;
2. **le firmware et l'outillage** pour le modifier, l'installer et le rendre
   compatible avec la **nouvelle puce flash B36014 (UC25HQ80)** des unités
   récentes.

---

## L'émulateur — le vrai firmware dans le navigateur

La page d'accueil de ce dépôt **est** la machine :

- **aucune ré-implémentation du son** : c'est le code du firmware lui-même
  (moteurs de synthèse, séquenceur 64 pas, module DUB — filtre bipolaire, sirène,
  tape delay —, isolateur 4 bandes, 27 riddims, presets et kits) compilé en
  `riddim.wasm` et exécuté dans un AudioWorklet à 44,1 kHz en virgule fixe ;
- **l'écran LCD est émulé au niveau du protocole du panneau** (CASET/RASET/RAMWR
  d'un ST7789) : chaque pixel est dessiné par le `lcd.c`/`gfx.c` du firmware ;
- **les entrées** vont directement dans l'état `fm1_in` débrayé que lit le
  firmware (boutons, encodeurs, clavier) ;
- **la flash est une image navigateur** (IndexedDB) : autosave, slots de projet
  et réglages survivent au rechargement ;
- **le menu du firmware est la seule surface de contrôle** — maintiens HOME puis
  SELECT / KNOB 1–4 / OCT± exactement comme sur la machine.

### Contrôles

- rangée du milieu du clavier = touches blanches depuis C4, rangée du haut =
  touches noires ; `Z`/`X` = OCT−/OCT+ ;
- `1`–`0` = FX SCL ENV LFO EDIT GLO HOME SAVE ARP SEQ, `Espace` = PLAY, `R` = REC,
  `↑↓` = SELECT, `←→` = ALGORITHM, `[` `\` = PRESETS ;
- boutons/knobs : clic, glisser, molette, tactile (multi-touch OK) ;
- un clavier MIDI branché joue (canaux 1–3 synths, 10 drums) ;
- la page est installable comme application (PWA).

## Le firmware RIDDIM ROOTS

Le build de ce dépôt provient de la lignée libre du FM-1 :
**Felucca** (Hügelton Instruments) → **SLOOP** (isod89) → **Sloop-DUB**,
sous **GPL-3.0** — sources complètes dans [`sources/`](sources/), avec le
support **deux puces flash** déjà en place :

```c
/* sources/firmware/hal/fm1_flash_id.h */
#define FL_JEDEC_OK(id) ((id) == 0x856014u || (id) == 0xB36014u)
/*  0x856014  Puya P25Q80, le FM-1 d'origine
    0xB36014  UC25HQ80, les FM-1 vendus depuis fin 2026  */
```

- **émulateur** : `riddim.wasm` à la racine = ces sources compilées
  (`sources/reference_emu/build.sh`), version embarquée **RIDDIM ROOTS 0.4.0** ;
- **build appareil** : le `.fwsc` à flasher se produit avec le toolchain JieLi
  (pi32v2) — procédure complète dans [`sources/BUILDING.md`](sources/BUILDING.md).

### Le binaire communautaire 0.3.0

[`firmware/RIDDIM_ROOTS_v0.3.0.fwsc`](firmware/RIDDIM_ROOTS_v0.3.0.fwsc) est le
firmware communautaire « RIDDIM ROOTS 0.3.0 DUB EVOLUTION » **dans son binaire
d'origine** (auteur communautaire, sources indisponibles), accompagné de la
démo de patch [`RIDDIM_ROOTS_v0.3.1_MOD_DEMO.fwsc`](firmware/RIDDIM_ROOTS_v0.3.1_MOD_DEMO.fwsc)
(chaînes de version 0.3.0 → 0.3.1, 2 octets, chaîne CRC revalidée).

**B36014 sur ce binaire 0.3.0** : l'analyse complète (app.bin, image flash
déchiffrée, chargeur ota.bin) ne révèle **aucun verrou JEDEC** — la compatibilité
UC25HQ80 n'est ni bloquée explicitement, ni garantie. Détails et recommandations :
[docs/04-b36014-uc25hq80.md](docs/04-b36014-uc25hq80.md).

## Modifier un `.fwsc` (textes UI, paramètres)

L'outillage de ce dépôt a prouvé le cycle complet **sur le 0.3.0 précisément** :
déballage, repackaging **octet-pour-octet identique**, patch réel, re-déballage
de contrôle.

```bash
# 0. aller-retour de sanité (doit être identique octet pour octet)
python3 tools/fwpack_newfw.py firmware/RIDDIM_ROOTS_v0.3.0.fwsc --check

# 1. annoter les textes (764 chaînes UI) dans docs/inventaire-textes-ui.csv
#    puis convertir les annotations en commandes :
python3 tools/csv_to_patch.py docs/inventaire-textes-ui.csv

# 2. appliquer + recalcule toute la chaîne de CRC automatiquement
python3 tools/fwpack_newfw.py firmware/RIDDIM_ROOTS_v0.3.0.fwsc \
  --patch 0x2A4F1:302E332E31 --out firmware/mon-build.fwsc

# 3. TOUJOURS valider par re-déballage
python3 tools/fwpack_newfw.py firmware/mon-build.fwsc --check
```

Les patches sont de **taille strictement identique** : renommer un texte de même
longueur OK, rallonger non. Voir [docs/02-guide-modification.md](docs/02-guide-modification.md).

## Flasher (Windows + M-UPGRADE)

Procédure et check-list de sécurité : [docs/03-flash-mupgrade.md](docs/03-flash-mupgrade.md).

**À lire avant tout flash** : la flash est **mono-banc, sans rollback** ; garde
toujours une sauvegarde du firmware qui tourne sur ta machine ; ne teste qu'un
petit changement à la fois ; batterie chargée, ne débranche jamais pendant
l'écriture.

## Arborescence

```
index.html, emu.js, worklet.js, riddim.wasm   l'émulateur (la racine = la page)
firmware/                                     les .fwsc (0.3.0 original + démo 0.3.1)
docs/
  01-analyse-format-fwsc.md                   format .fwsc / flash.bin (CRC, chiffrements)
  02-guide-modification.md                    workflow pas-à-pas
  03-flash-mupgrade.md                        flash Windows + sécurité
  04-b36014-uc25hq80.md                       la nouvelle puce flash : analyse
  inventaire-textes-ui.csv                    5 300+ chaînes de app.bin (764 UI)
tools/                                        repacker .fwsc + conversion CSV → patch
sources/                                      sources GPL complètes de la lignée
                                              (Felucca → SLOOP → Sloop-DUB, build
                                              RIDDIM ROOTS 0.4.0) + BUILDING.md
```

## Crédits & licences

- **Felucca** — Leo Kuroshita (@kurogedelic) / Hügelton Instruments — GPL-3.0 ;
- **SLOOP** — [isod89/sloop-fm1](https://github.com/isod89/sloop-fm1) — GPL-3.0 ;
- **Sloop-DUB** et son émulateur — [altessproduction/sloop-dub-fm1](https://github.com/altessproduction/sloop-dub-fm1) — GPL-3.0
  (l'émulateur de ce dépôt en dérive directement, commit source `d6114f7`) ;
- [kagaimiq/jl-misctools](https://github.com/kagaimiq/jl-misctools) — déballage et
  primitives JieLi (`jltech`) ; [AL-255/FM-1-RE](https://github.com/AL-255/FM-1-RE) —
  architecture et sécurité du FM-1 ;
- échantillons CC0 et polices — voir [`sources/LICENSING.md`](sources/LICENSING.md)
  pour le tableau complet des licences tierces ;
- « M-VAVE », « FM-1 » — marques de leurs propriétaires, sans affiliation ;
  l'outil officiel M-UPGRADE appartient à M-VAVE/Cuvave.

Le code de ce dépôt est sous **GPL-3.0-only**, comme les sources qu'il embarque.
