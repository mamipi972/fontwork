# Texte Fontwork pour GIMP 3

Greffon Python pour GIMP 3.0 qui déforme du texte (arc, cercle, spirale, vague, entonnoir, etc.) et y ajoute un contour, un dégradé, une ombre portée et un relief 3D. Tout se règle depuis une seule fenêtre, avec un aperçu en direct. Aucun filtre natif de GIMP n'est utilisé.

<img width="1017" height="722" alt="image" src="https://github.com/user-attachments/assets/14fe8e66-1ae7-4477-a6e8-cf4799b7284c" />


## Installation

1. Copiez le dossier `fontwork` (qui contient `fontwork.py` et `fontwork_core.py`) dans le dossier des greffons de GIMP 3 :
   - **Windows** : `%APPDATA%\GIMP\3.0\plug-ins\`
   - **Linux** : `~/.config/GIMP/3.0/plug-ins/`
   - **Linux (Flatpak)** : `~/.var/app/org.gimp.GIMP/config/GIMP/3.0/plug-ins/`
   - **macOS** : `~/Library/Application Support/GIMP/3.0/plug-ins/`
2. Le nom du dossier doit rester `fontwork`, identique au nom du script `fontwork.py`.
3. Sous Linux et macOS, rendez le script exécutable : `chmod +x fontwork.py`.
4. Redémarrez GIMP. Le greffon se trouve dans le menu **Calque ▸ Texte Fontwork…**

## Utilisation

- **Style** : 15 styles prêts à l'emploi. Le bouton *Enregistrer le style…* garde vos propres réglages ; ils apparaissent ensuite dans la liste avec une ★.
- **Texte** : le texte (sur plusieurs lignes si besoin), la police, la taille en pixels, l'espacement des lettres, l'interligne, l'alignement et la largeur.
- **Forme** : 16 formes au choix (droit, arc haut, arc bas, cercle, spirale, vague, ondulation, gonflé, pincé, dôme, cuvette, entonnoir, pyramide, perspective, montée, chevron). Selon la forme, on règle l'intensité, le nombre de vagues, l'angle de l'arc et la rotation. Les réglages sans effet sur la forme choisie sont grisés.
- **Couleurs** : remplissage aucun, uni ou en dégradé (deux couleurs et un angle), épaisseur et couleur du contour.
- **Ombre** : décalage, flou, couleur et opacité.
- **Relief 3D** : profondeur, direction et couleur. Le relief est automatiquement assombri vers l'arrière.
- **Aperçu en direct sur l'image** : le calque se met à jour dans le canevas pendant que vous réglez. Ces essais n'entrent pas dans l'historique d'annulation.
- **Créer aussi un tracé** : crée en plus un chemin vectoriel du texte déformé, utile pour un détourage ou un tracé personnalisé.

Le texte est placé au centre de l'image, ou au centre de la sélection s'il y en a une.

### Modifier un texte existant

Les réglages sont enregistrés dans le calque (sous forme de parasite) et sont conservés dans le fichier XCF. Pour modifier un texte, sélectionnez son calque *Fontwork : …* puis relancez **Calque ▸ Texte Fontwork…** : le texte, la forme et les effets sont rechargés. Si vous avez déplacé le calque entre-temps, son nouvel emplacement est conservé.

## Remarques

- Les contours du texte sont produits par le moteur texte de GIMP : toutes les polices connues de GIMP sont disponibles, y compris celles de ses dossiers de polices.
- Le greffon fonctionne sur les images RVB et en niveaux de gris. Une image indexée doit d'abord être convertie : **Image ▸ Mode ▸ RVB**.
- L'entonnoir et la pyramide donnent de meilleurs résultats avec un texte sur 2 ou 3 lignes.
- Si le greffon n'apparaît pas dans le menu ou affiche une erreur `cairo`, lancez GIMP depuis un terminal pour lire le message. Le greffon a besoin de *pycairo*, fourni avec GIMP 3.
