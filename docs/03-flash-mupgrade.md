# 03 — Flasher avec M-UPGRADE (Windows) et rester en vie

## 1. Avant le premier flash — check-list

- [ ] **Sauvegardes hors de l'ordinateur** : le firmware qui tourne actuellement
      sur votre FM-1 (si vous en disposez) et votre firmware de secours, chacun
      avec sa somme de contrôle notée.
- [ ] Vous savez que la flash est **mono-banc sans rollback** : si un flash
      interrompu ou une image invalide passe, l'appareil peut rester noir. Le
      protocole n'offre pas de récupération démontrée (analyse FM-1-RE).
- [ ] Batterie **chargée**, câble USB USB correct, poste Windows stable
      (désactiver la mise en veille pendant l'opération).
- [ ] Premier essai = le build de **démonstration cosmétique**
      (`RIDDIM_ROOTS_v0.3.1_MOD_DEMO.fwsc`, 2 octets de différence), jamais un
      gros changement d'un coup.
- [ ] Savoir revenir en arrière : si le test échoue, reflasher immédiatement
      le firmware de secours.

## 2. Procédure avec l'outil officiel M-UPGRADE

1. Installer l'utilitaire M-UPGRADE fourni par M-VAVE (page produit FM-1 /
   tutoriel vidéo officiel d'installation de firmware).
2. Connecter la FM-1 par USB. Elle doit être reconnue (périphérique MIDI
   « FM-1 » ; le firmware embarque un chargeur USB-HID de mise à jour).
3. Lancer M-UPGRADE, choisir le fichier `.fwsc` à flasher (le sélectionner tel
   quel — le package contient lui-même la structure attendue par le chargeur).
4. Démarrer la mise à jour et **ne toucher à rien** jusqu'à la fin (le device
   écrit sa flash en plusieurs étapes, y compris la zone applicative chiffrée).
5. Redémarrer la FM-1 et vérifier le changement attendu (sur la démo : la
   mention de version doit afficher 0.3.1 sur l'écran d'accueil/menu correspondant).

Remarques :

- Le package `.fwsc` transporte aussi `ota.bin` (chargeur USB-HID), identique
  dans nos builds — seuls les octets modifiés changent.
- Si M-UPGRADE refuse un fichier (« CRC », « taille »), **ne forcez pas** :
  refaites la validation locale (re-déballage + `cmp`) pour trouver l'écart.
- Alternative avancée : le protocole USB-MIDI SysEx (magic vendeur
  `F0 35 59 F7`) a été documenté par FM-1-RE avec un client Linux ; utile pour
  l'analyse, mais l'outil officiel reste le chemin le plus sûr sous Windows.

## 3. En cas de problème

| symptôme | action |
|---|---|
| M-UPGRADE ne voit pas l'appareil | changer de port USB/câble, vérifier le gestionnaire de périphériques, relancer Windows |
| flash qui échoue à mi-parcours | ne débrancher qu'à la fin du message d'erreur, puis tenter immédiatement le reflash du firmware de secours |
| appareil allumé mais écran noir après flash | tenter un reflash du firmware précédent (le chargeur USB-HID peut rester amorçable) ; au pire, la puce reste flashable par un outil SPI externe en atelier |
| le boot boucle ou se fige | c'est un problème de contenu (constante farfelue, donnée corrompue) : reflasher le build précédent validé |

## 4. Après chaque flash réussi

- noter la date, le nom du build et son empreinte (ex. `sha256sum`) ;
- garder le `.fwsc` exact qui tourne sur la machine dans votre archive
  personnelle : c'est votre nouveau point de retour.
- consigner les changements dans ce dépôt (un fichier `CHANGELOG.md` par
  exemple) pour tracer ce qui a été testé sur matériel réel.
