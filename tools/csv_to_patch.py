#!/usr/bin/env python3
"""
csv_to_patch.py - Convertit un inventaire de textes annote (CSV point-virgule)
en commandes --patch pour fwpack_newfw.py.

Utilisation :
  1. Ouvrir docs/inventaire-textes-ui.csv dans un tableur (LibreOffice, Excel...)
  2. Remplir la colonne "nouveau_texte_meme_longueur" (OBLIGATOIREMENT la meme
     longueur que le texte d'origine ; completer avec des espaces si plus court)
  3. Sauvegarder en CSV puis :
       python3 csv_to_patch.py docs/inventaire-textes-ui.csv
  4. Copier la commande affichee, l'executer, puis VALIDER par re-deballage.
"""
import csv
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = Path(sys.argv[1])
    patches = []
    skipped = []
    with open(path, newline='', encoding='utf-8') as f:
        for i, row in enumerate(csv.DictReader(f, delimiter=';'), start=2):
            old = (row.get('texte') or '').strip()
            new = (row.get('nouveau_texte_meme_longueur') or '').strip()
            if not new:
                continue
            addr = (row.get('offset_flashbin_hex') or '').strip()
            if not addr.startswith('0x'):
                skipped.append(f'ligne {i}: offset invalide')
                continue
            if len(new) != len(old):
                skipped.append(
                    f'ligne {i}: "{new}" ({len(new)}) != "{old}" ({len(old)}) '
                    '-> meme longueur requise, completer avec des espaces')
                continue
            if not all(0x20 <= ord(c) <= 0x7E for c in new):
                skipped.append(f'ligne {i}: caracteres non ASCII imprimables')
                continue
            patches.append(f'{addr}:' + new.encode('ascii').hex())
    if skipped:
        print('# lignes ignorees :')
        for s in skipped:
            print(f'#   {s}')
    if not patches:
        print('# aucun patch valide')
        return 1
    print('# commande a executer :')
    print('python3 tools/fwpack_newfw.py firmware/RIDDIM_ROOTS_v0.3.0.fwsc \\')
    for p in patches:
        print(f'  --patch {p} \\')
    print(f'  --out firmware/RIDDIM_ROOTS_MOD.fwsc')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
