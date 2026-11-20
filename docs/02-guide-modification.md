# 02 — Guide de modification pas-à-pas

Toutes les commandes ci-dessous ont été exécutées avec succès sur
`RIDDIM_ROOTS_v0.3.0.fwsc`. Le résultat validé est livré dans
`firmware/RIDDIM_ROOTS_v0.3.1_MOD_DEMO.fwsc`.

## 0. Règles d'or

1. **Un changement à la fois**, validé à chaque étape.
2. **Taille strictement identique** : remplacer du texte par du texte de même
   longueur (compléter avec des espaces si plus court). Ne jamais rallonger,
   déplacer ou supprimer des octets.
3. **Toujours valider** le build par un re-déballage
   (`fwunpack_newfw.py`) avant d'envisager un flash.
4. Garder le `.fwsc` d'origine intact : le repacker part toujours de lui.

## 1. Sanité de l'outillage (à refaire à chaque session)

```bash
# vérifie le modèle CRC sur l'original
python3 tools/fwpack_newfw.py firmware/RIDDIM_ROOTS_v0.3.0.fwsc --check

# aller-retour : doit être octet-pour-octet identique
python3 tools/fwpack_newfw.py firmware/RIDDIM_ROOTS_v0.3.0.fwsc --out /tmp/rt.fwsc
cmp /tmp/rt.fwsc firmware/RIDDIM_ROOTS_v0.3.0.fwsc && echo OK
```

## 2. Choisir les modifications : le CSV annotable

`docs/inventaire-textes-ui.csv` liste 5 300+ chaînes de `app.bin` avec :

- `offset_appbin_hex` — adresse dans le fichier `app.bin` déballé ;
- `offset_flashbin_hex` — la même, exprimée en coordonnées `decrypted.bin`
  (= +0x4120) : **c'est cette adresse que `--patch` attend** ;
- `region` — « UI probable » (764 lignes : menus, kits, effets) ou bruit de code ;
- `nouveau_texte_meme_longueur` — **colonne à remplir**.

Exemples de lignes UI réelles trouvées : `808 KIT`, `ROOTS KIT`, `SKA KIT`,
`NOISE KIT`, `TAP TEMPO`, `TAPE ECHO`, `BASS DROP`, `KIT SETTINGS`,
`RIDDIM ROOTS 0.3.0 DUB EVOLUTION`…

Astuce : filtrer `region = UI probable` dans le tableur, ne toucher qu'à cela.

## 3. Convertir le CSV en commande

```bash
python3 tools/csv_to_patch.py docs/inventaire-textes-ui.csv
```

Le script vérifie longueurs et caractères, et affiche la commande `--patch`
prête à copier (hexadécimal ASCII du nouveau texte, ex. `0.3.1` → `302E332E31`).

## 4. Appliquer et repackager

```bash
python3 tools/fwpack_newfw.py firmware/RIDDIM_ROOTS_v0.3.0.fwsc \
  --patch 0x2A4F1:302E332E31 \
  --patch 0x2A786:302E332E31 \
  --out firmware/RIDDIM_ROOTS_v0.3.1_MOD_DEMO.fwsc
```

Le repacker enchaîne automatiquement : déchiffrement de la zone app (chipkey
0x980F extrait d'`isd_config.ini`), application des patches, recalcul des CRC
(`app.bin`, `app_area_head`, flash.bin, listcrc, hdrcrc), rechiffrement,
émission, puis auto-vérification des CRC du fichier produit.

Fichiers entiers (même taille) également supportés :

```bash
--app-bin files/app.bin        # app.bin édité par ailleurs
--cfg-tool files/cfg_tool.bin
--isd-config top/isd_config.ini
```

## 5. Validation externe (obligatoire)

Avec l'outil communautaire (dépendance : `pip install pyyaml`) :

```bash
python3 jl-misctools/firmware/fwunpack_newfw.py firmware/RIDDIM_ROOTS_v0.3.1_MOD_DEMO.fwsc
strings files/app.bin | grep "RIDDIM ROOTS"
# attendu :
#   RIDDIM ROOTS 0.3.1
#   RIDDIM ROOTS 0.3.1 DUB EVOLUTION
```

Contrôle de diff : `cmp -l` entre l'`app.bin` d'origine et le nouveau ne doit
montrer **que vos octets** (2 sur la démo).

## 6. Exemple complet déjà exécuté (la démo)

- cibles : `RIDDIM ROOTS 0.3.0` @0x2A4E4 et `RIDDIM ROOTS 0.3.0 DUB EVOLUTION`
  @0x2A779 ; sous-chaîne `0.3.0` à +13 → offsets flashbin `0x2A4F1` et
  `0x2A786` ;
- contenu : `30 2E 33 2E 31` (« 0.3.1 ») ;
- recalculs : edcrc app.bin `3CD5`, app_area_head `2E87`, flash `EF74` ;
- résultat : re-déballage OK, point d'entrée intact `0x2000120`, exactement
  2 octets modifiés.

## 7. Au-delà des textes (réglages numériques)

Les constantes (limites BPM, temps d'écho…) sont dans `app.bin` mais sans nom.
Méthode : charger `app.bin` dans Ghidra à l'adresse base 0x02000000
(architecture pi32v2 — voir le loader de FM-1-RE), repérer les comparaisons
autour des menus ciblés, puis patcher les mêmes adresses via `--patch`.
Toute valeur doit être testée prudemment : une constante farfelue peut bloquer
au boot même si les CRC sont bons.
