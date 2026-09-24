# Texte Fontwork — GIMP 3

**[Français](#français)** · **[English](#english)**

Licence / License : [GNU GPL v3 ou ultérieure / or later](#licence--license) — comme GIMP / same as GIMP.

---

## Français

Greffon Python pour GIMP 3 qui déforme du texte (arc, cercle, spirale, vague, entonnoir, etc.) et y ajoute un contour, un dégradé, une ombre portée et un relief 3D. Tout se règle depuis une seule fenêtre, avec un aperçu en direct. Aucun filtre natif de GIMP n'est utilisé.

### Installation

Le dossier doit s'appeler `fontwork`, comme le script `fontwork.py`. Il contient `fontwork.py`, `fontwork_core.py`, `README.md` et `LICENSE`.

#### Windows

1. Copiez le dossier `fontwork` dans `%APPDATA%\GIMP\3.0\plug-ins\`.
2. Redémarrez GIMP.

#### macOS

1. Copiez le dossier `fontwork` dans `~/Library/Application Support/GIMP/3.0/plug-ins/`.
2. Dans un terminal : `chmod +x ~/Library/Application\ Support/GIMP/3.0/plug-ins/fontwork/fontwork.py`
3. Redémarrez GIMP.

#### Linux Debian

**Debian 13 « Trixie » et versions suivantes** (GIMP 3 dans les dépôts officiels) :

```bash
# 1. GIMP 3 et les modules Python nécessaires au greffon
sudo apt update
sudo apt install gimp python3 python3-gi python3-gi-cairo python3-cairo gir1.2-gimp-3.0

# 2. Copie du greffon (depuis le dossier où vous avez décompressé l'archive)
mkdir -p ~/.config/GIMP/3.0/plug-ins
cp -r fontwork ~/.config/GIMP/3.0/plug-ins/
chmod +x ~/.config/GIMP/3.0/plug-ins/fontwork/fontwork.py
```

**Debian 12 « Bookworm »** : les dépôts officiels ne proposent que GIMP 2.10. Installez GIMP 3 avec Flatpak (Python et pycairo sont inclus) :

```bash
# 1. Flatpak et GIMP 3 depuis Flathub
sudo apt install flatpak
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.gimp.GIMP

# 2. Copie du greffon
mkdir -p ~/.var/app/org.gimp.GIMP/config/GIMP/3.0/plug-ins
cp -r fontwork ~/.var/app/org.gimp.GIMP/config/GIMP/3.0/plug-ins/
chmod +x ~/.var/app/org.gimp.GIMP/config/GIMP/3.0/plug-ins/fontwork/fontwork.py
```

**Vérifications**

- Version de GIMP : `gimp --version` (ou `flatpak run org.gimp.GIMP --version`). Il faut une version 3.x.
- Modules Python (paquets Debian) : `python3 -c "import gi, cairo; gi.require_version('Gimp', '3.0'); from gi.repository import Gimp; print('OK')"`
- Si le menu n'apparaît pas, lancez GIMP depuis un terminal (`gimp` ou `flatpak run org.gimp.GIMP`) pour lire les messages d'erreur.
- Si GIMP a été ouvert avant la copie, redémarrez-le.

Le greffon se trouve ensuite dans le menu **Calque ▸ Texte Fontwork…**

### Utilisation

- **Style** : 15 styles prêts à l'emploi. Le bouton *Enregistrer le style…* garde vos propres réglages ; ils apparaissent ensuite dans la liste avec une ★.
- **Texte** : le texte (sur plusieurs lignes si besoin), la police, la taille en pixels, l'espacement des lettres, l'interligne, l'alignement et la largeur.
- **Forme** : 16 formes au choix (droit, arc haut, arc bas, cercle, spirale, vague, ondulation, gonflé, pincé, dôme, cuvette, entonnoir, pyramide, perspective, montée, chevron). Selon la forme, on règle l'intensité, le nombre de vagues, l'angle de l'arc et la rotation. Les réglages sans effet sur la forme choisie sont grisés.
- **Couleurs** : remplissage aucun, uni ou en dégradé (deux couleurs et un angle), épaisseur et couleur du contour.
- **Ombre** : décalage, flou, couleur et opacité.
- **Relief 3D** : profondeur, direction et couleur. Le relief est automatiquement assombri vers l'arrière.
- **Aperçu en direct sur l'image** : le calque se met à jour dans le canevas pendant que vous réglez. Ces essais n'entrent pas dans l'historique d'annulation.
- **Créer aussi un tracé** : crée en plus un chemin vectoriel du texte déformé, utile pour un détourage ou un tracé personnalisé.
- **Fusionner avec le calque du dessous** : décochée par défaut. Cochée, le texte est fusionné dans le calque inférieur et n'est plus modifiable par le greffon.

Le texte est placé au centre de l'image, ou au centre de la sélection s'il y en a une.

### Modifier un texte existant (édition non destructive)

Les réglages sont enregistrés dans le calque (sous forme de parasite) et sont conservés dans le fichier XCF. Pour modifier un texte, sélectionnez son calque *Fontwork : …* puis relancez **Calque ▸ Texte Fontwork…** : le texte, la police, la forme et les effets sont rechargés.

- **Le calque est mis à jour sur place**, sans être recréé. Il garde ses filtres non destructifs GIMP (NDE), son masque, son opacité, son mode de fusion, son nom et sa place dans la pile. Vous pouvez donc ajouter à un calque Fontwork des filtres NDE de GIMP (flou, lueur, etc.) : ils restent actifs après chaque modification.
- **Versions précédentes** : à chaque validation, la version remplacée est ajoutée à l'historique du calque (15 versions au maximum, avec date, texte et forme). La liste *Version* en haut de la fenêtre permet de revenir à l'une d'elles ; elle est enregistrée dans le XCF.
- Si vous avez déplacé le calque, son nouvel emplacement est conservé.
- Une modification se défait en une seule étape avec **Édition ▸ Annuler**.
- Un calque dupliqué garde ses réglages : on peut le modifier indépendamment de l'original.

Ce qui fait perdre la possibilité de modification :

- la case *Fusionner avec le calque du dessous* ;
- une fusion ou un aplatissement faits ensuite dans GIMP ;
- la peinture directe sur le calque : elle est effacée lors de la modification suivante. Pour retoucher, peignez plutôt sur un calque séparé ou dans un masque de calque.

Le greffon n'est pas lui-même un filtre NDE : GIMP 3 réserve ce mécanisme aux opérations GEGL, et un greffon Python ne peut pas en créer. Le résultat est équivalent, mais il faut relancer le greffon pour modifier le texte au lieu de double-cliquer sur un filtre.

### Remarques

- Les contours du texte sont produits par le moteur texte de GIMP : toutes les polices connues de GIMP sont disponibles, y compris celles de ses dossiers de polices.
- Le greffon fonctionne sur les images RVB et en niveaux de gris. Une image indexée doit d'abord être convertie : **Image ▸ Mode ▸ RVB**.
- L'entonnoir et la pyramide donnent de meilleurs résultats avec un texte sur 2 ou 3 lignes.

### Greffons et outils similaires

Aucun greffon GIMP 3 trouvé ne réunit déformation par formes, effets et texte ré-éditable. Voici les outils les plus proches :

| | **Texte Fontwork** (ce greffon) | Texte le long d'un chemin (GIMP) | Filtres de distorsion GEGL (GIMP) | GEGL Effects (LinuxBeaver) | ofn-text-along-path (Ofnuts) | Arclayer (Akkana Peck) | Fontwork (LibreOffice) |
|---|---|---|---|---|---|---|---|
| Version de GIMP | 3.0 | 3.0 (intégré) | 3.0 (intégré) | 2.10 et 3.0 | 2.10 (Python 2) | 2.x (Python 2) | hors GIMP |
| Formes | 16 (arc, cercle, spirale, vague, entonnoir…) | suit un chemin tracé à la main | coordonnées polaires, ondes, etc., filtre par filtre | aucune | suit un chemin tracé à la main | arc uniquement | environ 40 |
| Méthode | déformation des contours vectoriels | contours vectoriels | déformation des pixels | styles de calque | contours vectoriels | déformation des pixels | vectoriel |
| Qualité quand la déformation est forte | nette | nette | flou, trous possibles | sans objet | nette | trous possibles | nette |
| Contour, dégradé, ombre | oui | non (à faire à la main) | non | oui, très complet (biseau, lueur…) | non | non | oui |
| Relief 3D | oui | non | non | non | non | non | oui |
| Aperçu en direct | oui (fenêtre et image) | non | oui | oui | non | non | oui |
| Texte modifiable après validation | oui (relancer le greffon) | non (produit un chemin) | réglages du filtre modifiables | oui | non | non | oui |
| Versions précédentes | oui (15) | non | non | non | non | non | non |
| Styles prêts à l'emploi et styles perso | oui | non | non | oui (préréglages) | non | non | galerie |
| Vrai filtre NDE GIMP | non (voir plus haut) | non | oui | oui | non | non | sans objet |

**En résumé :** GEGL Effects est le meilleur complément pour les styles (biseau, lueurs), et peut s'appliquer par-dessus un calque Fontwork. Le texte le long d'un chemin reste utile pour suivre une courbe libre. Texte Fontwork est le seul à proposer des formes toutes faites de qualité vectorielle avec texte modifiable dans GIMP 3.

---

## English

A Python plug-in for GIMP 3 that warps text (arc, circle, spiral, wave, funnel, etc.) and adds an outline, a gradient, a drop shadow and a 3D extrusion. Everything is set from a single window with a live preview. No built-in GIMP filter is used.

### Installation

The folder must be named `fontwork`, like the `fontwork.py` script. It contains `fontwork.py`, `fontwork_core.py`, `README.md` and `LICENSE`.

#### Windows

1. Copy the `fontwork` folder into `%APPDATA%\GIMP\3.0\plug-ins\`.
2. Restart GIMP.

#### macOS

1. Copy the `fontwork` folder into `~/Library/Application Support/GIMP/3.0/plug-ins/`.
2. In a terminal: `chmod +x ~/Library/Application\ Support/GIMP/3.0/plug-ins/fontwork/fontwork.py`
3. Restart GIMP.

#### Debian Linux

**Debian 13 "Trixie" and later** (GIMP 3 in the official repositories):

```bash
# 1. GIMP 3 and the Python modules the plug-in needs
sudo apt update
sudo apt install gimp python3 python3-gi python3-gi-cairo python3-cairo gir1.2-gimp-3.0

# 2. Copy the plug-in (from the folder where you extracted the archive)
mkdir -p ~/.config/GIMP/3.0/plug-ins
cp -r fontwork ~/.config/GIMP/3.0/plug-ins/
chmod +x ~/.config/GIMP/3.0/plug-ins/fontwork/fontwork.py
```

**Debian 12 "Bookworm"**: the official repositories only provide GIMP 2.10. Install GIMP 3 with Flatpak (Python and pycairo are included):

```bash
# 1. Flatpak and GIMP 3 from Flathub
sudo apt install flatpak
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.gimp.GIMP

# 2. Copy the plug-in
mkdir -p ~/.var/app/org.gimp.GIMP/config/GIMP/3.0/plug-ins
cp -r fontwork ~/.var/app/org.gimp.GIMP/config/GIMP/3.0/plug-ins/
chmod +x ~/.var/app/org.gimp.GIMP/config/GIMP/3.0/plug-ins/fontwork/fontwork.py
```

**Checks**

- GIMP version: `gimp --version` (or `flatpak run org.gimp.GIMP --version`). It must be 3.x.
- Python modules (Debian packages): `python3 -c "import gi, cairo; gi.require_version('Gimp', '3.0'); from gi.repository import Gimp; print('OK')"`
- If the menu entry does not appear, start GIMP from a terminal (`gimp` or `flatpak run org.gimp.GIMP`) to read the error messages.
- If GIMP was open before you copied the files, restart it.

The plug-in is then in the **Layer ▸ Texte Fontwork…** menu.

### Usage

The interface is in French. The main controls are:

- **Style**: 15 ready-made styles. The *Enregistrer le style…* (Save style) button keeps your own settings; they then appear in the list with a ★.
- **Texte** (Text): the text (multi-line if needed), font, size in pixels, letter spacing, line spacing, alignment and width.
- **Forme** (Shape): 16 shapes (straight, arc up, arc down, circle, spiral, wave, ripple, inflate, pinch, dome, bowl, funnel, pyramid, perspective, slant, chevron). Depending on the shape, you set the intensity, number of waves, arc angle and rotation. Settings that have no effect on the chosen shape are greyed out.
- **Couleurs** (Colours): no fill, solid or gradient fill (two colours and an angle), outline width and colour.
- **Ombre** (Shadow): offset, blur, colour and opacity.
- **Relief 3D** (3D extrusion): depth, direction and colour. The extrusion automatically gets darker towards the back.
- **Aperçu en direct sur l'image** (Live preview on the image): the layer updates on the canvas while you adjust. These tests do not go into the undo history.
- **Créer aussi un tracé** (Also create a path): also creates a vector path of the warped text, useful for selections or custom strokes.
- **Fusionner avec le calque du dessous** (Merge with the layer below): unchecked by default. When checked, the text is merged into the layer below and can no longer be edited by the plug-in.

The text is placed at the centre of the image, or at the centre of the selection if there is one.

### Editing existing text (non-destructive editing)

The settings are stored in the layer (as a parasite) and are kept in the XCF file. To edit a text, select its *Fontwork : …* layer and run **Layer ▸ Texte Fontwork…** again: the text, font, shape and effects are reloaded.

- **The layer is updated in place**, not recreated. It keeps its GIMP non-destructive filters (NDE), mask, opacity, blend mode, name and position in the stack. You can therefore add GIMP NDE filters (blur, glow, etc.) to a Fontwork layer: they stay active after every edit.
- **Previous versions**: each time you confirm, the replaced version is added to the layer's history (up to 15 versions, with date, text and shape). The *Version* list at the top of the window lets you go back to any of them; it is saved in the XCF file.
- If you moved the layer, its new position is kept.
- An edit can be undone in a single step with **Edit ▸ Undo**.
- A duplicated layer keeps its settings and can be edited independently of the original.

What makes the text no longer editable:

- the *Fusionner avec le calque du dessous* (merge) checkbox;
- a later merge or flatten in GIMP;
- painting directly on the layer: it is erased at the next edit. To retouch, paint on a separate layer or in a layer mask instead.

The plug-in is not itself an NDE filter: GIMP 3 reserves that mechanism for GEGL operations, and a Python plug-in cannot create one. The result is equivalent, but you run the plug-in again to edit the text instead of double-clicking a filter.

### Notes

- Text outlines are produced by GIMP's own text engine: every font GIMP knows is available, including fonts in GIMP's font folders.
- The plug-in works on RGB and greyscale images. Convert an indexed image first: **Image ▸ Mode ▸ RGB**.
- Funnel and pyramid look best with text on 2 or 3 lines.

### Similar plug-ins and tools

No GIMP 3 plug-in found combines shape warping, effects and re-editable text. The closest tools are:

| | **Texte Fontwork** (this plug-in) | Text along Path (GIMP) | GEGL distort filters (GIMP) | GEGL Effects (LinuxBeaver) | ofn-text-along-path (Ofnuts) | Arclayer (Akkana Peck) | Fontwork (LibreOffice) |
|---|---|---|---|---|---|---|---|
| GIMP version | 3.0 | 3.0 (built in) | 3.0 (built in) | 2.10 and 3.0 | 2.10 (Python 2) | 2.x (Python 2) | outside GIMP |
| Shapes | 16 (arc, circle, spiral, wave, funnel…) | follows a hand-drawn path | polar coordinates, waves, etc., one filter at a time | none | follows a hand-drawn path | arc only | about 40 |
| Method | warps vector outlines | vector outlines | warps pixels | layer styles | vector outlines | warps pixels | vector |
| Quality under strong warping | sharp | sharp | blurry, possible holes | n/a | sharp | possible holes | sharp |
| Outline, gradient, shadow | yes | no (manual) | no | yes, very complete (bevel, glow…) | no | no | yes |
| 3D extrusion | yes | no | no | no | no | no | yes |
| Live preview | yes (window and image) | no | yes | yes | no | no | yes |
| Text editable after confirming | yes (run the plug-in again) | no (produces a path) | filter settings editable | yes | no | no | yes |
| Previous versions | yes (15) | no | no | no | no | no | no |
| Ready-made and custom styles | yes | no | no | yes (presets) | no | no | gallery |
| True GIMP NDE filter | no (see above) | no | yes | yes | no | no | n/a |

**In short:** GEGL Effects is the best companion for styling (bevel, glows) and can be applied on top of a Fontwork layer. Text along Path remains useful for following a free-form curve. Texte Fontwork is the only one offering ready-made vector-quality shapes with editable text in GIMP 3.

---

## Sources

[GIMP 3.2 release notes](https://www.gimp.org/release-notes/gimp-3.2.html) · [GEGL Effects](https://github.com/LinuxBeaver/Gimp_Layer_Effects_Text_Styler_Plugin_GEGL_Effects) · [Ofnuts' path tools](https://sourceforge.net/projects/gimp-path-tools/) · [ofn-text-along-path discussion](https://www.gimp-forum.net/Thread-ofn-text-along-path-issues) · [Arclayer](https://www.shallowsky.com/software/arclayer/) · [Debian: gir1.2-gimp-3.0](https://packages.debian.org/trixie/gir1.2-gimp-3.0)

---

## Licence / License

Copyright © 2026 Miguel

**FR —** Ce programme est un logiciel libre ; vous pouvez le redistribuer et/ou le modifier selon les termes de la Licence publique générale GNU (GNU GPL) publiée par la Free Software Foundation, soit la version 3 de la licence, soit (à votre choix) toute version ultérieure. C'est la même licence que GIMP. Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE, sans même la garantie implicite de QUALITÉ MARCHANDE ou d'ADÉQUATION À UN USAGE PARTICULIER. Le texte complet de la licence (en anglais, seule version officielle) se trouve dans le fichier `LICENSE`.

**EN —** This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This is the same license as GIMP. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. The full license text is in the `LICENSE` file.

SPDX-License-Identifier: `GPL-3.0-or-later`
