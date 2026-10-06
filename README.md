# Texte Fontwork — GIMP 3

**[Français](#français)** · **[English](#english)** · Version française seule : [LISEZMOI.md](LISEZMOI.md)

Licence / License : [GNU GPL v3 ou ultérieure / or later](#licence--license) — comme GIMP / same as GIMP.

<img width="1012" height="727" alt="Fenêtre du greffon Texte Fontwork / Texte Fontwork plug-in window" src="https://github.com/user-attachments/assets/1b771d6b-d664-4e14-a104-1408a389a1e8" />

<img width="1140" alt="Les 23 modèles de badges / The 23 badge templates" src="captures/badges.png" />

---

## Français

Greffon Python pour GIMP 3 qui met en forme du texte de quatre façons : texte déformé (arc, cercle, spirale, vague, entonnoir…), texte qui suit le contour d'une forme, texte mis en page à l'intérieur d'une forme (cœur, étoile, bulle…) ou autour d'elle et badges circulaires. Contour, dégradé, métal, biseau, ombre portée et relief 3D s'ajoutent au texte. Tout se règle depuis une seule fenêtre, avec un aperçu en direct, et le texte reste modifiable. Aucun filtre natif de GIMP n'est utilisé.

### Installation

Les chemins ci-dessous sont ceux de GIMP 3.0. Avec une version plus récente (3.2…), le dossier peut porter un autre numéro : le chemin exact est indiqué dans GIMP, menu **Édition ▸ Préférences ▸ Dossiers ▸ Greffons**.

Le dossier doit s'appeler `fontwork`, comme le script `fontwork.py`. Il contient `fontwork.py`, `fontwork_core.py`, le dossier `formes` (formes SVG fournies), le dossier `captures` (images du README), `README.md`, `LISEZMOI.md` et `LICENSE`.

#### Windows

1. Copiez le dossier `fontwork` dans `%APPDATA%\GIMP\3.0\plug-ins\` (ou `3.2`, selon votre version de GIMP).
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

Le greffon a quatre modes, choisis en haut de la fenêtre : **Texte déformé**, **Texte sur chemin**, **Texte dans ou hors d'une forme** et **Badge / sceau**. Chaque mode propose des **modèles** de départ ; tout reste ensuite modifiable (textes, couleurs, tailles, rayons…). Le bouton *Enregistrer…* garde vos propres réglages comme modèle personnel ; ils apparaissent ensuite dans la liste avec une ★.

Le bouton **Galerie…** affiche tous les modèles du mode en cours sous forme de vignettes, calculées avec vos textes : un clic applique le modèle. Les vignettes sont gardées dans le dossier `fontwork-vignettes` du profil GIMP, ce qui rend les ouvertures suivantes immédiates ; ce dossier peut être supprimé sans risque.

#### Mode Texte déformé

- **Modèles** : 19 modèles, dont *Cercle orange*, *Bloc 3D*, *Double arche* et *Or estampé*.
- **Texte** : le texte (sur plusieurs lignes si besoin), la police, la taille en pixels, l'espacement des lettres, l'interligne, l'alignement et la largeur. L'option *Déformer chaque ligne séparément* applique la forme à chaque ligne (par exemple deux arches superposées), avec un écart réglable.
- **Forme** : 16 formes au choix (droit, arc haut, arc bas, cercle, spirale, vague, ondulation, gonflé, pincé, dôme, cuvette, entonnoir, pyramide, perspective, montée, chevron). Selon la forme, on règle l'intensité, le nombre de vagues, l'angle de l'arc et la rotation. Les réglages sans effet sur la forme choisie sont grisés. *Grossir au centre* et *Grossir vers la droite* font varier la taille des lettres, en plus de la forme.
- **Couleurs** : remplissage aucun, uni, dégradé à 2 ou 3 couleurs, ou métal (or, argent, bronze), avec l'angle du dégradé ; épaisseur et couleur du contour.
- **Biseau** : relief bombé ou gravé sur le remplissage, avec profondeur, douceur, direction de la lumière, éclat et ombre.
- **Ombre** : décalage, flou, couleur et opacité.
- **3D** : relief (extrusion) avec profondeur, direction et couleur, automatiquement assombri vers l'arrière ; rotation 3D (basculer, pivoter) avec perspective réglable.

#### Mode Texte sur chemin

Une phrase qui suit le contour d'une forme : étoile, cœur, flèche, maison, fleur, spirale, croix, cercle, ovale, vague, arche, bulle… Les onglets Texte, Couleurs, Biseau, Ombre et 3D sont les mêmes que pour le texte déformé (police, taille, espacement, largeur, dégradé, métal, contour…). L'onglet **Chemin** remplace l'onglet Forme.

- **Modèles** : *Étoile dorée*, *Cœur tendre*, *Flèche*, *Maison*, *Fleur*, *Spirale*, *Croix étoilée*, *Cercle continu*, *Vague*. Les styles de lettres du mode texte sont aussi proposés (« Lettres : … ») : ils changent l'apparence sans changer la forme.
- **Chemin suivi** : une forme SVG de la bibliothèque, ou le **tracé sélectionné dans l'image** (dessiné avec l'outil Chemins) ; dans ce cas le texte se place exactement sur le tracé.
- **Vos propres formes** : bouton *Ajouter un SVG…*, qui copie le fichier dans votre bibliothèque (`fontwork-formes` dans le dossier de profil GIMP, chemin affiché dans l'onglet). Vous pouvez aussi y déposer des SVG directement. Sont lus : chemins (`path`, y compris courbes et arcs), polygones, polylignes, rectangles, cercles, ellipses, lignes et transformations. Le texte et les images intégrés dans un SVG sont ignorés.
- **Forme** : taille, rotation, et contour suivi quand le SVG en contient plusieurs (0 = le plus long).
- **Texte sur le chemin** : position le long du chemin, côté (au-dessus / centré / en dessous, c'est-à-dire à l'extérieur ou à l'intérieur d'une forme fermée), écart, inversion du sens, *Remplir le chemin* (répartit le texte sur x % de la longueur), *Répéter le texte tout autour* avec un séparateur (•, ♥, ✿…), lettres rigides ou courbées.
- **Dessiner la forme** : fond, trait et épaisseur, ou forme invisible pour ne garder que le texte.

Conseil : sur les angles rentrants (creux du cœur, pétales de la fleur), les lettres peuvent se toucher ; augmentez l'écart, l'espacement, ou décochez *Lettres rigides*.

#### Mode Texte dans ou hors d'une forme

Le texte est mis en page **à l'intérieur** d'une forme (chaque ligne prend la largeur disponible à sa hauteur, comme un paragraphe qui épouse le contour d'un cœur) ou **à l'extérieur** : le texte remplit alors un cadre et contourne la forme, comme dans un magazine où le texte habille une image. Les formes sont les mêmes que pour le texte sur chemin (bibliothèque, vos SVG, ou tracé fermé de l'image). Les onglets Texte, Couleurs, Biseau, Ombre et 3D restent disponibles ; l'onglet **Forme SVG** contient la forme et la mise en page.

- **Modèles** : à l'intérieur, *Cœur*, *Étoile*, *Maison*, *Bulle*, *Cercle*, *Fleur*, *Texte seul* (forme invisible : seul le texte dessine la silhouette) ; à l'extérieur, *Autour d'un cœur* et *Autour d'une étoile*. Les styles de lettres (« Lettres : … ») sont aussi proposés.
- **Placer le texte** : à l'intérieur de la forme, ou à l'extérieur. À l'extérieur, **Largeur du cadre** et **Hauteur du cadre** (en % de la taille de la forme) fixent la zone de texte autour de la forme ; la forme est au centre du cadre.
- **Ajuster la taille pour remplir la forme** : la taille du texte est calculée pour occuper au mieux la place disponible ; la taille obtenue est affichée sous l'aperçu. Décochée, la taille choisie dans l'onglet Texte est utilisée, et un avertissement indique les mots qui ne tiennent pas.
- **Alignement** : à gauche, centré, à droite ou justifié. **Position verticale** : en haut ou centrée.
- **Marge intérieure** : distance entre le texte et le bord de la forme.
- **Zones utilisées sur chaque ligne** : *toutes* (le texte passe des deux côtés de la forme, ou dans les deux lobes du haut d'un cœur), *la plus large*, *à gauche seulement* ou *à droite seulement*. À l'extérieur, *à gauche seulement* donne une colonne de texte qui habille le côté gauche de la forme.
- **Retours à la ligne** : *texte continu* (par défaut : un retour simple devient une espace, seule une ligne vide commence un nouveau paragraphe ; idéal pour remplir la forme) ou *respecter chaque retour à la ligne* (un vers par ligne, pour la poésie). L'interligne se règle dans l'onglet Texte.
- **Justifié** : l'espace ajouté entre deux mots est limité, pour éviter les grands blancs ; une ligne trop courte reste alignée à gauche, comme la dernière ligne d'un paragraphe.

Conseil : les formes étroites (branches d'étoile, pointe du cœur) donnent un texte plus petit à l'intérieur ; à l'extérieur, un cadre trop étroit laisse des lignes vides à hauteur de la partie la plus large de la forme : élargissez le cadre ou réduisez la marge.

#### Mode Badge / sceau

Pour les logos ronds, médailles, tampons et citations en cercle.

- **Modèles** : *Club (deux anneaux)*, *Citation sur photo*, *Médaille d'or*, *Tampon encreur*, *Écusson bleu et or*, *Sceau de cire rouge*, *Badge bleu institutionnel*, *Médaille d'or prestige*, *Vintage brasserie*, *Moderne & tech*, *Champion (humour)*, *Gravure blanche*, *Industriel cuivre*, *Bijouterie luxe*, *Éco vert & rouge*, *Institutionnel à ruban*, *Sport & performance*, *Tampon éco*, et cinq variantes humoristiques du Champion (*reine de la gaffe*, *mauvaise foi garantie*, *expert en cafouillage*, *sorcier de la caféine*, *grand maître du bazar*). La case *Garder mes textes en changeant de modèle* permet d'essayer plusieurs modèles sans retaper ses textes.
- **Anneaux** : diamètre et rotation du badge ; forme du bord extérieur (lisse, festonné comme un sceau de cire, dentelé comme une capsule, cranté comme un engrenage, ébréché), avec nombre et profondeur ; jusqu'à 4 anneaux, chacun avec rayon, couleur de fond (transparente possible), trait (épaisseur, couleur) et choix d'appliquer ou non la teinte métal au fond (pour garder, par exemple, une bande bleue entre des anneaux dorés).
- **Textes** : un texte en haut (lettres vers l'extérieur) et un texte en bas (lisible à l'endroit), chacun avec police, taille, couleur, rayon, contour et espacement. *Étaler sur* répartit le texte sur l'angle voulu (par exemple 335° pour un texte qui fait presque tout le tour). Un texte central sur plusieurs lignes, avec décalage vertical.
- **Décors** : filets en arc qui relient les deux textes ; couronne de motifs répétés (★, •, ✦… nombre, rayon, taille, couleur, angle de départ, orientation) ; cordelette torsadée ; guillochage (hachures ondulées dans un anneau) ; couronne de lauriers ; couronne de perles, rivets ou diamants ; bandeau sous le texte central (ruban à pointes fourchues, courbé ou droit, ou plaque avec rivets) ; forme SVG au centre (étoile, bouclier coché, vos propres SVG…), placée automatiquement au-dessus du texte central s'il y en a un ; petite mention en bas (« GIMP-FONTWORK »…) ; zone centrale circulaire pour placer une photo ou un logo (voir ci-dessous).
- **Effets** : finition métal (or, argent, bronze, cuivre), texture (métal brossé, cire, patine, rouille) avec son intensité, biseau (sur les textes ou sur tout le badge) et ombre portée. Les illustrations (personnage, animal, blason) ne sont pas dessinées par le greffon : placez votre image dans la zone centrale.

Le badge est centré sur l'image, ou sur la sélection s'il y en a une : faites d'abord une sélection sur votre photo pour y placer le badge.

**Zone centrale.** Par défaut, elle est enregistrée comme **canal** dans l'onglet *Canaux* (nommé « Fontwork : zone centrale – … »), sans laisser de sélection active : on ne risque pas de peindre ou d'effacer seulement le centre par erreur. Votre sélection éventuelle est remise telle qu'elle était. Pour utiliser la zone : clic droit sur le canal ▸ **Canal vers sélection**, puis par exemple **Édition ▸ Coller dans la sélection** pour y mettre une photo. Le choix *Sélection active* reste possible dans l'onglet *Décors*. Quand le badge est modifié, son canal est mis à jour.

#### Options communes

- **Aperçu en direct sur l'image** : le calque se met à jour dans le canevas pendant que vous réglez. Ces essais n'entrent pas dans l'historique d'annulation.
- **Créer aussi un tracé** : crée en plus un chemin vectoriel du texte, utile pour un détourage ou un tracé personnalisé.
- **Fusionner avec le calque du dessous** : décochée par défaut. Cochée, le texte est fusionné dans le calque inférieur et n'est plus modifiable par le greffon.

Le texte est placé au centre de l'image, ou au centre de la sélection s'il y en a une.

### Réinitialiser (réglages d'origine)

Le bouton **Réinitialiser**, à côté de la liste des modèles, remet tous les réglages du mode en cours à leurs valeurs d'origine. Deux options : *Garder mes textes*, et *Supprimer aussi mes modèles personnels (★)*. Les réglages remis à zéro ne s'appliquent au calque qu'après **Valider**.

Réinitialisation manuelle, GIMP fermé : supprimez `fontwork-last.json` (derniers réglages utilisés) et, si vous le souhaitez, `fontwork-styles.json` (vos modèles ★), dans le dossier de profil GIMP (`%APPDATA%\GIMP\3.0\` sous Windows, `~/.config/GIMP/3.0/` sous Linux  ; le numéro peut être `3.2` selon votre version).

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
- En cas d'erreur, le détail est écrit dans le fichier `fontwork-erreurs.log` du dossier de profil GIMP (`%APPDATA%\GIMP\3.0\` sous Windows, `~/.config/GIMP/3.0/` sous Linux  ; le numéro peut être `3.2` selon votre version). Joignez-le si vous signalez un problème.

### Greffons et outils similaires

Aucun greffon GIMP 3 trouvé ne réunit déformation par formes, effets et texte ré-éditable. Voici les outils les plus proches :

Légende : <span style="color:#1a7f37">vert = oui</span> · <span style="color:#cf222e">rouge = non</span> · <span style="color:#d97706">orange = ni l'un ni l'autre</span>

| | **Texte Fontwork** (ce greffon) | Texte le long d'un chemin (GIMP) | Filtres de distorsion GEGL (GIMP) | GEGL Effects (LinuxBeaver) | ofn-text-along-path (Ofnuts) | Arclayer (Akkana Peck) | Fontwork (LibreOffice) |
|---|---|---|---|---|---|---|---|
| Version de GIMP | <span style="color:#d97706">3.0</span> | <span style="color:#d97706">3.0 (intégré)</span> | <span style="color:#d97706">3.0 (intégré)</span> | <span style="color:#d97706">2.10 et 3.0</span> | <span style="color:#d97706">2.10 (Python 2)</span> | <span style="color:#d97706">2.x (Python 2)</span> | <span style="color:#d97706">hors GIMP</span> |
| Formes | <span style="color:#d97706">16 (arc, cercle, spirale, vague, entonnoir…) + badges</span> | <span style="color:#d97706">suit un chemin tracé à la main</span> | <span style="color:#d97706">coordonnées polaires, ondes, etc., filtre par filtre</span> | <span style="color:#d97706">aucune</span> | <span style="color:#d97706">suit un chemin tracé à la main</span> | <span style="color:#d97706">arc uniquement</span> | <span style="color:#d97706">environ 40</span> |
| Méthode | <span style="color:#d97706">déformation des contours vectoriels</span> | <span style="color:#d97706">contours vectoriels</span> | <span style="color:#d97706">déformation des pixels</span> | <span style="color:#d97706">styles de calque</span> | <span style="color:#d97706">contours vectoriels</span> | <span style="color:#d97706">déformation des pixels</span> | <span style="color:#d97706">vectoriel</span> |
| Qualité quand la déformation est forte | <span style="color:#d97706">nette</span> | <span style="color:#d97706">nette</span> | <span style="color:#d97706">flou, trous possibles</span> | <span style="color:#d97706">sans objet</span> | <span style="color:#d97706">nette</span> | <span style="color:#d97706">trous possibles</span> | <span style="color:#d97706">nette</span> |
| Contour, dégradé, ombre | <span style="color:#1a7f37">oui</span> | <span style="color:#cf222e">non (à faire à la main)</span> | <span style="color:#cf222e">non</span> | <span style="color:#1a7f37">oui, très complet (biseau, lueur…)</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#1a7f37">oui</span> |
| Texte le long d'une forme SVG ou d'un tracé | <span style="color:#1a7f37">oui (12 formes, vos SVG, tracés)</span> | <span style="color:#d97706">tracé seulement</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#d97706">tracé seulement</span> | <span style="color:#cf222e">non</span> | <span style="color:#d97706">quelques formes</span> |
| Texte mis en page dans ou autour d'une forme | <span style="color:#1a7f37">oui (ajustement automatique)</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> |
| Badges (textes haut/bas, anneaux, motifs) | <span style="color:#1a7f37">oui</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> |
| Biseau, finition métal | <span style="color:#1a7f37">oui</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#1a7f37">oui</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> |
| Rotation 3D en perspective | <span style="color:#1a7f37">oui</span> | <span style="color:#cf222e">non</span> | <span style="color:#d97706">filtre séparé (perspective)</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#1a7f37">oui</span> |
| Relief 3D | <span style="color:#1a7f37">oui</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#1a7f37">oui</span> |
| Aperçu en direct | <span style="color:#1a7f37">oui (fenêtre et image)</span> | <span style="color:#cf222e">non</span> | <span style="color:#1a7f37">oui</span> | <span style="color:#1a7f37">oui</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#1a7f37">oui</span> |
| Texte modifiable après validation | <span style="color:#1a7f37">oui (relancer le greffon)</span> | <span style="color:#cf222e">non (produit un chemin)</span> | <span style="color:#d97706">réglages du filtre modifiables</span> | <span style="color:#1a7f37">oui</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#1a7f37">oui</span> |
| Versions précédentes | <span style="color:#1a7f37">oui (15)</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> |
| Styles prêts à l'emploi et styles perso | <span style="color:#1a7f37">oui</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#1a7f37">oui (préréglages)</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#d97706">galerie</span> |
| Vrai filtre NDE GIMP | <span style="color:#cf222e">non (voir plus haut)</span> | <span style="color:#cf222e">non</span> | <span style="color:#1a7f37">oui</span> | <span style="color:#1a7f37">oui</span> | <span style="color:#cf222e">non</span> | <span style="color:#cf222e">non</span> | <span style="color:#d97706">sans objet</span> |

**En résumé :** GEGL Effects est le meilleur complément pour les styles (biseau, lueurs), et peut s'appliquer par-dessus un calque Fontwork. Le texte le long d'un chemin reste utile pour suivre une courbe libre. Texte Fontwork est le seul à réunir, dans GIMP 3, formes toutes faites, texte sur, dans ou autour d'une forme et badges, en qualité vectorielle et avec un texte qui reste modifiable.

---

## English

A Python plug-in for GIMP 3 that lays out text in four ways: warped text (arc, circle, spiral, wave, funnel…), text following the outline of a shape, text laid out inside a shape (heart, star, speech bubble…) or around it and circular badges. Outline, gradient, metal, bevel, drop shadow and 3D extrusion can be added to the text. Everything is set from a single window with a live preview, and the text stays editable. No built-in GIMP filter is used.

### Installation

The paths below are for GIMP 3.0. With a newer version (3.2…), the folder may have a different number: GIMP shows the exact path in **Edit ▸ Preferences ▸ Folders ▸ Plug-ins**.

The folder must be named `fontwork`, like the `fontwork.py` script. It contains `fontwork.py`, `fontwork_core.py`, the `formes` folder (bundled SVG shapes), the `captures` folder (README images), `README.md`, `LISEZMOI.md` and `LICENSE`.

#### Windows

1. Copy the `fontwork` folder into `%APPDATA%\GIMP\3.0\plug-ins\` (or `3.2`, depending on your GIMP version).
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

The interface is in French. The plug-in has four modes, chosen at the top of the window: **Texte déformé** (Warped text), **Texte sur chemin** (Text on path), **Texte dans ou hors d'une forme** (Text inside or around a shape) and **Badge / sceau** (Badge / seal). Each mode offers starting **templates** (*Modèle*); everything stays editable afterwards (texts, colours, sizes, radii…). The *Enregistrer…* (Save) button keeps your own settings as a personal template; they then appear in the list with a ★.

The **Galerie…** (Gallery) button shows every template of the current mode as thumbnails, rendered with your texts: one click applies the template. Thumbnails are kept in the `fontwork-vignettes` folder of the GIMP profile, so later openings are instant; this folder can be deleted safely.

#### Warped text mode

- **Templates**: 19 templates, including *Cercle orange* (orange circle), *Bloc 3D* (3D block), *Double arche* (double arch) and *Or estampé* (embossed gold).
- **Texte** (Text): the text (multi-line if needed), font, size in pixels, letter spacing, line spacing, alignment and width. *Déformer chaque ligne séparément* (Warp each line separately) applies the shape to each line (for example two stacked arches), with an adjustable gap.
- **Forme** (Shape): 16 shapes (straight, arc up, arc down, circle, spiral, wave, ripple, inflate, pinch, dome, bowl, funnel, pyramid, perspective, slant, chevron). Depending on the shape, you set the intensity, number of waves, arc angle and rotation. Settings that have no effect on the chosen shape are greyed out. *Grossir au centre* (Grow in the centre) and *Grossir vers la droite* (Grow to the right) vary the letter size on top of the shape.
- **Couleurs** (Colours): no fill, solid, 2- or 3-colour gradient, or metal (gold, silver, bronze), with the gradient angle; outline width and colour.
- **Biseau** (Bevel): raised or engraved bevel on the fill, with depth, softness, light direction, highlight and shade.
- **Ombre** (Shadow): offset, blur, colour and opacity.
- **3D**: extrusion with depth, direction and colour, automatically darker towards the back; 3D rotation (tilt, turn) with adjustable perspective.

#### Text on path mode

A sentence that follows the outline of a shape: star, heart, arrow, house, flower, spiral, cross, circle, oval, wave, arch, speech bubble… The Texte, Couleurs, Biseau, Ombre and 3D tabs are the same as in warped text mode (font, size, spacing, width, gradient, metal, outline…). The **Chemin** (Path) tab replaces the Forme tab.

- **Templates**: *Étoile dorée* (golden star), *Cœur tendre* (heart), *Flèche* (arrow), *Maison* (house), *Fleur* (flower), *Spirale* (spiral), *Croix étoilée* (four-point star), *Cercle continu* (endless circle), *Vague* (wave). The letter styles of text mode are also offered ("Lettres : …"): they change the look without changing the shape.
- **Chemin suivi** (Path followed): an SVG shape from the library, or the **path selected in the image** (drawn with the Paths tool); in that case the text is placed exactly on the path.
- **Your own shapes**: the *Ajouter un SVG…* (Add an SVG) button copies the file into your library (`fontwork-formes` in the GIMP profile folder, path shown in the tab). You can also drop SVG files there directly. Supported: paths (`path`, including curves and arcs), polygons, polylines, rectangles, circles, ellipses, lines and transforms. Text and embedded images in an SVG are ignored.
- **Forme** (Shape): size, rotation, and which outline to follow when the SVG has several (0 = the longest).
- **Texte sur le chemin** (Text on the path): position along the path, side (above / centred / below, i.e. outside or inside a closed shape), gap, reverse direction, *Remplir le chemin* (spread the text over x % of the length), *Répéter le texte tout autour* (repeat all the way round) with a separator (•, ♥, ✿…), rigid or bent letters.
- **Dessiner la forme** (Draw the shape): fill, stroke and width, or an invisible shape to keep only the text.

Tip: on inward corners (the dip of the heart, flower petals) letters may touch; increase the gap or spacing, or untick *Lettres rigides*.

#### Text inside or around a shape mode

The text is laid out **inside** a shape (each line takes the width available at its height, like a paragraph that follows the outline of a heart) or **outside** it: the text then fills a frame and flows around the shape, like magazine text wrapping around a picture. The shapes are the same as for text on path (library, your SVGs, or a closed path in the image). The Texte, Couleurs, Biseau, Ombre and 3D tabs are still available; the **Forme SVG** tab holds the shape and the layout settings.

- **Templates**: inside, *Cœur* (heart), *Étoile* (star), *Maison* (house), *Bulle* (speech bubble), *Cercle* (circle), *Fleur* (flower), *Texte seul* (text only: the shape is hidden and the text alone draws the silhouette); outside, *Autour d'un cœur* (around a heart) and *Autour d'une étoile* (around a star). The letter styles ("Lettres : …") are also offered.
- **Placer le texte** (Place the text): inside the shape, or outside it. Outside, **Largeur du cadre** and **Hauteur du cadre** (frame width and height, in % of the shape size) set the text area around the shape; the shape sits in the centre of the frame.
- **Ajuster la taille pour remplir la forme** (Fit the size to fill the shape): the text size is computed to fill the available space as well as possible; the resulting size is shown under the preview. When unticked, the size set in the Texte tab is used, and a warning shows how many words do not fit.
- **Alignement** (Alignment): left, centred, right or justified. **Position verticale** (Vertical position): top or centred.
- **Marge intérieure** (Margin): distance between the text and the edge of the shape.
- **Zones utilisées sur chaque ligne** (Areas used on each line): *toutes* (all: the text goes on both sides of the shape, or into both lobes at the top of a heart), *la plus large* (the widest), *à gauche seulement* (left only) or *à droite seulement* (right only). Outside, *left only* gives a column of text wrapping the left side of the shape.
- **Retours à la ligne** (Line breaks): *texte continu* (continuous text, the default: a single line break becomes a space and only an empty line starts a new paragraph; best for filling the shape) or *respecter chaque retour à la ligne* (keep every line break: one verse per line, for poetry). Line spacing is set in the Texte tab.
- **Justifié** (Justified): the space added between two words is limited to avoid large gaps; a line that is too short stays left-aligned, like the last line of a paragraph.

Tip: narrow shapes (star arms, the tip of a heart) give smaller text inside; outside, a frame that is too narrow leaves empty lines level with the widest part of the shape: widen the frame or reduce the margin.

#### Badge / seal mode

For round logos, medals, stamps and quotes in a circle.

- **Templates**: *Club (deux anneaux)* (two-ring club), *Citation sur photo* (quote on a photo), *Médaille d'or* (gold medal), *Tampon encreur* (rubber stamp), *Écusson bleu et or* (blue and gold crest), *Sceau de cire rouge* (red wax seal), *Badge bleu institutionnel* (blue institutional badge), *Médaille d'or prestige* (prestige gold medal), *Vintage brasserie* (vintage brewery), *Moderne & tech* (modern & tech), *Champion (humour)* (humorous champion), *Gravure blanche* (white engraving), *Industriel cuivre* (industrial copper), *Bijouterie luxe* (luxury jewellery), *Éco vert & rouge* (eco green & red), *Institutionnel à ruban* (institutional with ribbon), *Sport & performance*, *Tampon éco* (eco stamp), and five humorous Champion variants (*reine de la gaffe*, *mauvaise foi garantie*, *expert en cafouillage*, *sorcier de la caféine*, *grand maître du bazar*). The *Garder mes textes en changeant de modèle* (Keep my texts when changing template) box lets you try several templates without retyping your texts.
- **Anneaux** (Rings): badge diameter and rotation; shape of the outer edge (smooth, scalloped like a wax seal, serrated like a bottle cap, notched like a gear, chipped), with count and depth; up to 4 rings, each with radius, background colour (can be transparent), stroke (width, colour) and whether the metal tint applies to the background (for example to keep a blue band between golden rings).
- **Textes** (Texts): a top text (letters facing outwards) and a bottom text (upright and readable), each with font, size, colour, radius, outline and spacing. *Étaler sur* (Spread over) distributes the text over the chosen angle (for example 335° for text running almost all the way round). A multi-line centre text with vertical offset.
- **Décors** (Decorations): arc lines joining the two texts; a ring of repeated symbols (★, •, ✦… count, radius, size, colour, start angle, orientation); twisted rope; guilloche (wavy hatching in a ring); laurel wreath; ring of pearls, rivets or diamonds; banner behind the centre text (forked ribbon, curved or straight, or plate with rivets); SVG shape in the centre (star, checked shield, your own SVGs…), automatically placed above the centre text if there is one; small note at the bottom ("GIMP-FONTWORK"…); a circular centre area to place a photo or logo (see below).
- **Effets** (Effects): metal finish (gold, silver, bronze, copper), texture (brushed metal, wax, patina, rust) with its strength, bevel (on the texts or the whole badge) and drop shadow. Illustrations (character, animal, coat of arms) are not drawn by the plug-in: place your own picture in the centre area.

The badge is centred on the image, or on the selection if there is one: make a selection on your photo first to place the badge there.

**Centre area.** By default it is saved as a **channel** in the *Channels* tab (named "Fontwork : zone centrale – …"), without leaving an active selection, so you cannot accidentally paint or erase only the centre. Any selection you had is restored as it was. To use the area: right-click the channel ▸ **Channel to Selection**, then for example **Edit ▸ Paste Into** to put a photo in it. The *Sélection active* (Active selection) option is still available in the *Décors* tab. When the badge is edited, its channel is updated.

#### Common options

- **Aperçu en direct sur l'image** (Live preview on the image): the layer updates on the canvas while you adjust. These tests do not go into the undo history.
- **Créer aussi un tracé** (Also create a path): also creates a vector path of the text, useful for selections or custom strokes.
- **Fusionner avec le calque du dessous** (Merge with the layer below): unchecked by default. When checked, the text is merged into the layer below and can no longer be edited by the plug-in.

The text is placed at the centre of the image, or at the centre of the selection if there is one.

### Reset (factory settings)

The **Réinitialiser** (Reset) button, next to the template list, restores every setting of the current mode to its original value. Two options: *Garder mes textes* (Keep my texts) and *Supprimer aussi mes modèles personnels (★)* (Also delete my personal templates). The reset settings only apply to the layer after **Valider** (OK).

Manual reset, with GIMP closed: delete `fontwork-last.json` (last used settings) and, if you wish, `fontwork-styles.json` (your ★ templates) in the GIMP profile folder (`%APPDATA%\GIMP\3.0\` on Windows, `~/.config/GIMP/3.0/` on Linux; the number may be `3.2` depending on your version).

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
- If an error occurs, the details are written to `fontwork-erreurs.log` in the GIMP profile folder (`%APPDATA%\GIMP\3.0\` on Windows, `~/.config/GIMP/3.0/` on Linux; the number may be `3.2` depending on your version). Attach it when reporting a problem.

### Similar plug-ins and tools

No GIMP 3 plug-in found combines shape warping, effects and re-editable text. The closest tools are:

Key: <span style="color:#1a7f37">green = yes</span> · <span style="color:#cf222e">red = no</span> · <span style="color:#d97706">orange = neither</span>

| | **Texte Fontwork** (this plug-in) | Text along Path (GIMP) | GEGL distort filters (GIMP) | GEGL Effects (LinuxBeaver) | ofn-text-along-path (Ofnuts) | Arclayer (Akkana Peck) | Fontwork (LibreOffice) |
|---|---|---|---|---|---|---|---|
| GIMP version | <span style="color:#d97706">3.0</span> | <span style="color:#d97706">3.0 (built in)</span> | <span style="color:#d97706">3.0 (built in)</span> | <span style="color:#d97706">2.10 and 3.0</span> | <span style="color:#d97706">2.10 (Python 2)</span> | <span style="color:#d97706">2.x (Python 2)</span> | <span style="color:#d97706">outside GIMP</span> |
| Shapes | <span style="color:#d97706">16 (arc, circle, spiral, wave, funnel…) + badges</span> | <span style="color:#d97706">follows a hand-drawn path</span> | <span style="color:#d97706">polar coordinates, waves, etc., one filter at a time</span> | <span style="color:#d97706">none</span> | <span style="color:#d97706">follows a hand-drawn path</span> | <span style="color:#d97706">arc only</span> | <span style="color:#d97706">about 40</span> |
| Method | <span style="color:#d97706">warps vector outlines</span> | <span style="color:#d97706">vector outlines</span> | <span style="color:#d97706">warps pixels</span> | <span style="color:#d97706">layer styles</span> | <span style="color:#d97706">vector outlines</span> | <span style="color:#d97706">warps pixels</span> | <span style="color:#d97706">vector</span> |
| Quality under strong warping | <span style="color:#d97706">sharp</span> | <span style="color:#d97706">sharp</span> | <span style="color:#d97706">blurry, possible holes</span> | <span style="color:#d97706">n/a</span> | <span style="color:#d97706">sharp</span> | <span style="color:#d97706">possible holes</span> | <span style="color:#d97706">sharp</span> |
| Outline, gradient, shadow | <span style="color:#1a7f37">yes</span> | <span style="color:#cf222e">no (manual)</span> | <span style="color:#cf222e">no</span> | <span style="color:#1a7f37">yes, very complete (bevel, glow…)</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#1a7f37">yes</span> |
| Text along an SVG shape or a path | <span style="color:#1a7f37">yes (12 shapes, your SVGs, paths)</span> | <span style="color:#d97706">path only</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#d97706">path only</span> | <span style="color:#cf222e">no</span> | <span style="color:#d97706">a few shapes</span> |
| Text laid out inside or around a shape | <span style="color:#1a7f37">yes (automatic fit)</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> |
| Badges (top/bottom texts, rings, symbols) | <span style="color:#1a7f37">yes</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> |
| Bevel, metal finish | <span style="color:#1a7f37">yes</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#1a7f37">yes</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> |
| 3D rotation with perspective | <span style="color:#1a7f37">yes</span> | <span style="color:#cf222e">no</span> | <span style="color:#d97706">separate filter (perspective)</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#1a7f37">yes</span> |
| 3D extrusion | <span style="color:#1a7f37">yes</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#1a7f37">yes</span> |
| Live preview | <span style="color:#1a7f37">yes (window and image)</span> | <span style="color:#cf222e">no</span> | <span style="color:#1a7f37">yes</span> | <span style="color:#1a7f37">yes</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#1a7f37">yes</span> |
| Text editable after confirming | <span style="color:#1a7f37">yes (run the plug-in again)</span> | <span style="color:#cf222e">no (produces a path)</span> | <span style="color:#d97706">filter settings editable</span> | <span style="color:#1a7f37">yes</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#1a7f37">yes</span> |
| Previous versions | <span style="color:#1a7f37">yes (15)</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> |
| Ready-made and custom styles | <span style="color:#1a7f37">yes</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#1a7f37">yes (presets)</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#d97706">gallery</span> |
| True GIMP NDE filter | <span style="color:#cf222e">no (see above)</span> | <span style="color:#cf222e">no</span> | <span style="color:#1a7f37">yes</span> | <span style="color:#1a7f37">yes</span> | <span style="color:#cf222e">no</span> | <span style="color:#cf222e">no</span> | <span style="color:#d97706">n/a</span> |

**In short:** GEGL Effects is the best companion for styling (bevel, glows) and can be applied on top of a Fontwork layer. Text along Path remains useful for following a free-form curve. Texte Fontwork is the only one in GIMP 3 to combine ready-made shapes, text on, inside or around a shape, and badges, in vector quality and with text that stays editable.

---

## Sources

[GIMP 3.2 release notes](https://www.gimp.org/release-notes/gimp-3.2.html) · [GEGL Effects](https://github.com/LinuxBeaver/Gimp_Layer_Effects_Text_Styler_Plugin_GEGL_Effects) · [Ofnuts' path tools](https://sourceforge.net/projects/gimp-path-tools/) · [ofn-text-along-path discussion](https://www.gimp-forum.net/Thread-ofn-text-along-path-issues) · [Arclayer](https://www.shallowsky.com/software/arclayer/) · [Debian: gir1.2-gimp-3.0](https://packages.debian.org/trixie/gir1.2-gimp-3.0)

---

## Licence / License

Copyright © 2026 Miguel

**FR —** Ce programme est un logiciel libre ; vous pouvez le redistribuer et/ou le modifier selon les termes de la Licence publique générale GNU (GNU GPL) publiée par la Free Software Foundation, soit la version 3 de la licence, soit (à votre choix) toute version ultérieure. C'est la même licence que GIMP. Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE, sans même la garantie implicite de QUALITÉ MARCHANDE ou d'ADÉQUATION À UN USAGE PARTICULIER. Le texte complet de la licence (en anglais, seule version officielle) se trouve dans le fichier `LICENSE`.

**EN —** This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This is the same license as GIMP. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. The full license text is in the `LICENSE` file.

SPDX-License-Identifier: `GPL-3.0-or-later`
