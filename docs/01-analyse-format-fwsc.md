# 01 — Analyse du format `.fwsc` (RIDDIM ROOTS 0.3.0)

Document établi par analyse et vérification empirique sur le fichier
`RIDDIM_ROOTS_v0.3.0.fwsc` (483 892 octets). Toutes les valeurs citées ont été
re-vérifiées par calcul ; le repacker `fwpack_newfw.py` reproduit le fichier
original octet pour octet en mode aller-retour, ce qui prouve le modèle.

## 1. Vue d'ensemble

Le `.fwsc` est un package de mise à jour JieLi « new firmware » (famille UFW).
Sa particularité : son en-tête est transporté dans **20 blocs de 0x30 octets**
dont seul le contenu utile (0x2F octets) est pris en compte — le 32e octet de
chaque bloc est du remplissage ignoré par le chargeur.

```
0x00000  en-tête UFW brouillé (20 x 0x30 = 960 o ; 940 o utiles + 20 "junk")
0x003C0  padding (84 o, conservé tel quel)
0x00414  flash.bin   (462 848 o, CRC16 stocké 0x2EA1)
0x71414  ota.bin     (19 969 o, CRC16 stocké 0xA1C9) — chargeur USB-HID, non modifié
0x76215  fin
```

En-tête UFW (après reconstruction et déchiffrement XOR 0xFFFF) :

| champ | taille | valeur observée |
|---|---|---|
| hdrcrc | 2 | 0x60D6 — CRC16 des octets **déchiffrés** [2:0x40] |
| listcrc | 2 | 0xA49E — CRC16 des octets **chiffrés** [0x40:0xE0] |
| imgsize | 4 | 0x76220 (= taille fichier − 20) |
| numents | 2 | 2 (`flash.bin`, `ota.bin`) |
| chip | 48 | « AC791N » |

Entrées (0x50 o chacune, déchiffrées XOR 0xFFFF) : `type`(2) `index`(2)
`edcrc`(2, CRC16 des données stockées) `resv`(2) `eoffset`(4, coordonnées
« dé-brouillées ») `esize`(4) `esize2`(4) `resv`(44) `name`(16).

Le flash.bin occupe les offsets 0x400..0x71000 en coordonnées dé-brouillées ;
le décalage fichier (offskew) vaut 20 (les 20 octets junk).

## 2. flash.bin — carte mémoire

| offset flash.bin | contenu |
|---|---|
| 0x0000 | en-tête flash (burner/VID « 0.01 », PID « AC791N_STORY », flash 0xFF000) — XOR 0xFFFF |
| 0x0020 | 4 entrées JLFS top (32 o chacune, XOR 0xFFFF) : `uboot.boot`, `isd_config.ini`, `app_dir_head`, `key_mac` |
| 0x00A0 | SPL `uboot.boot` (14 488 o) — bankcb-scramblé + XOR 0xFFFF |
| 0x3938 | `isd_config.ini` (755 o, **en clair**) — contient la chipkey encodée : **0x980F** |
| 0x4000 | **zone applicative** (462 848 o) — chiffrée chipkey, voir §3 |
| 0x71000 | fin du flash.bin du package |

Note : le package ne couvre que les 0x71000 premiers octets de la flash de
1 Mo. Les régions VM (0x75000), BTIF (0x7F000), key_mac (0xFF000) ne sont
**pas** incluses — une mise à jour partielle qui préserve réglages et patches.

## 3. Zone applicative (0x4000–0x71000)

Chiffrée avec la chipkey via le chiffrement « sfc » : par blocs de 32 octets,
clé de bloc = `chipkey ^ ((offset_bloc − 0x4000) >> 2)` appliquée à la même
LFSR que le XOR 0xFFFF (`jl_enc_cipher`). Symétrique : déchiffrer = rechiffrer.

Contenu déchiffré (coordonnées = celles de `decrypted.bin`) :

| offset | entrée | détail |
|---|---|---|
| 0x4000 | `app_area_head` | off = point d'entrée **0x2000120**, size = 443 879 (data = 443 847), edcrc = CRC16 sur [0x4020, 0x705E7) |
| 0x4020 | `app.bin` | données à 0x4120, **443 208 o**, edcrc 0x7C71 |
| 0x4040 | `cfg_tool.bin` | données à 0x70468, 383 o, edcrc 0x2E75 |
| 0x4060 | `VM` | descripteur zone réservée (flags 0x12) |
| 0x4080 | `PRCT` | descripteur zone protégée (flags 0x92) |
| 0x40A0 | `BTIF` | descripteur zone réservée (flags 0x92) |
| 0x4120–0x70468 | données app.bin | code + rodata pi32v2 (XIP à 0x02000000) |
| 0x70468–0x705E7 | données cfg_tool.bin | |
| 0x705E7 | `EXT_RESERVED` | 32 o de données, en fin de zone |

Entrée JLFS (32 o) : `hcrc`(2) `edcrc`(2) `off`(4) `size`(4) `flags`(1)
`resvd`(1) `index`(2) `name`(16). Attention : **edcrc fait 2 octets** (le
format exact est `<HIIBBH16s` sur les 30 octets qui suivent hcrc) — l'écrire
en 32 bits écrase le pointeur `off` et rend l'image non amorçable.

## 4. Conventions CRC vérifiées (CRC-16/CCITT poly 0x1021, init 0)

| CRC | couverture |
|---|---|
| UFW hdrcrc | octets déchiffrés [2:0x40] de l'en-tête |
| UFW listcrc | octets **chiffrés** [0x40:0xE0] (vérifiés par le chargeur avant déchiffrement) |
| UFW edcrc flash.bin / ota.bin | données **telles que stockées** (chiffrées) |
| JLFS hcrc (toutes entrées) | 30 octets d'en-tête après hcrc |
| JLFS edcrc isd_config | données stockées (clair) |
| JLFS edcrc uboot | données **débrouillées** (bankcb inversé) |
| JLFS edcrc app.bin / cfg_tool | données finales |
| JLFS edcrc app_area_head | toute la data qui suit son en-tête ([0x4020, 0x705E7), 443 847 o) |

## 5. Implications pratiques

- Tout patch de **même taille** dans app.bin est possible : il faut recalculer
  l'edcrc de l'entrée modifiée, celui de `app_area_head`, puis l'edcrc du
  flash.bin dans l'en-tête UFW, puis `listcrc` (sur chiffré) puis `hdrcrc`
  (le listcrc étant couvert par le hdrcrc, il faut l'écrire d'abord) — c'est
  exactement ce que fait `fwpack_newfw.py`.
- Grandir ou rétrécir app.bin nécessite de déplacer `cfg_tool.bin`, les
  descripteurs et les tailles — non supporté, non nécessaire tant que la
  marge interne (~140 Ko de gain vs firmware stock V13) n'est pas saturée.
- L'ISA du CPU est **pi32v2** (dérivée Blackfin, instructions 16 bits) :
  pour la modification de code, utiliser Ghidra + les bases de fonctions
  publiées par FM-1-RE, ou recompiler depuis les sources.
