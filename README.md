# Tri et censure de photos

Logiciel de bureau permettant de **trier rapidement un grand nombre de photos**
au clavier, puis de **masquer les yeux** de certaines personnes pour préserver
leur anonymat avant de partager les images.

Il fonctionne sur les fichiers de votre ordinateur, pour un seul utilisateur et
un seul événement à la fois. Aucun serveur, aucune base de données, aucune
connexion internet nécessaire.

---

## 1. Installation

### Ce qu'il vous faut

- **Python 3.11 ou supérieur** (développé et vérifié sous Python 3.14).
  Tkinter, l'interface graphique, est fourni d'origine avec Python.

### Les commandes

Dans un terminal, placez-vous dans le dossier du programme, puis :

**Windows**

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux**

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Trois bibliothèques sont installées :

| Bibliothèque | Rôle |
|---|---|
| `pillow` | Ouvrir, redimensionner et enregistrer les images, dessiner les bandeaux |
| `pillow-heif` | Lire et enregistrer les photos HEIC des iPhone |
| `opencv-contrib-python` | Détecter les visages et la position des yeux |

Le modèle de détection (`modeles/face_detection_yunet_2023mar.onnx`, 227 Ko) est
livré avec le programme. **Rien n'est téléchargé au lancement.**

### Vérifier que tout fonctionne

Avant de traiter de vraies photos, lancez une fois :

```
python verifier_installation.py
```

Ce script contrôle en quelques secondes que Python, les quatre bibliothèques et
le modèle de détection sont en place, que les formats JPEG, PNG et HEIC sont bien
lus **et** réenregistrés, et que les bandeaux s'inclinent correctement. Il
fabrique ses propres images de test et **ne touche à aucun de vos fichiers**.

---

## 2. Lancement

```
python main.py
```

Au démarrage, deux possibilités :

- **Démarrer un nouvel événement** — vous remplissez l'écran de configuration,
  puis le logiciel prépare tout seul les dossiers et les photos.
- **Reprendre un événement existant** — vous désignez le dossier de l'événement
  créé lors d'une session précédente, et vous repartez exactement là où vous
  vous étiez arrêté.

> Pour reprendre un événement, choisissez le dossier **portant le nom de
> l'événement**, celui qui a été créé *à l'intérieur* de votre dossier de
> photos — et non le dossier de photos lui-même.

---

## 3. Déroulé complet

### Étape A — Configuration (nouvel événement seulement)

Vous renseignez :

1. le **dossier source**, celui où sont vos photos ;
2. le **nom de l'événement** (par exemple « Mariage Julie et Marc ») ;
3. **quatre dossiers de tri**, chacun avec un nom et une touche du clavier.

Le bouton « Continuer » ne s'active que si tout est correct : dossier existant et
non vide, nom utilisable comme nom de dossier, quatre noms et quatre touches
renseignés, et aucune touche utilisée deux fois. Les touches **R** et **C** sont
réservées (pivoter et rogner) et ne peuvent pas servir de touche de tri.

### Étape B — Préparation automatique

Elle s'exécute une seule fois, sans rien vous demander :

```
VotreDossierPhotos/
├── (vos photos, renommées 1.jpg, 2.jpg, 3.jpg…)
└── Mariage Julie et Marc/
    ├── À garder/
    ├── Ratées/
    ├── À revoir/
    ├── À supprimer/
    ├── RAW/          (créé seulement s'il y a des fichiers RAW)
    ├── Videos/       (créé seulement s'il y a des vidéos)
    └── suivi.json    (votre avancement)
```

- Les photos sont **renommées `1`, `2`, `3`…**, sans zéros devant, extension
  d'origine conservée, dans l'ordre **chronologique de prise de vue** : `1` est
  la photo la plus ancienne (date et heure), le dernier numéro la plus récente.
  La date est lue dans la photo elle-même (EXIF) ; à défaut, on prend la plus
  ancienne des dates du fichier.
- Les fichiers **RAW** (`.cr2`, `.nef`, `.arw`, `.dng`…) et les **vidéos**
  (`.mp4`, `.mov`, `.avi`, `.mkv`…) sont **mis de côté** et ne sont plus jamais
  touchés ensuite.

> À noter : la numérotation porte sur **tous** les fichiers de la racine. Comme
> les RAW et les vidéos reçoivent eux aussi un numéro avant d'être déplacés, la
> suite des numéros des photos peut comporter des trous (1, 2, 3, 6, 8…). C'est
> normal.

### Étape C — Menu principal

Cinq choix : lancer le tri, lancer la censure, lancer le **mode revue**,
**dupliquer un dossier**, ou quitter. Le menu rappelle votre avancement et le nombre de photos dans chaque
dossier, copies comprises.

---

## 4. Étape 1 — Le tri

Les photos défilent une par une en grand, **toujours dans le bon sens** (le
logiciel lit l'orientation enregistrée par l'appareil). L'avancement est affiché
en permanence, sous la forme « Photo 12 sur 340 ».

### Commandes du tri

| Touche ou action | Effet |
|---|---|
| **Vos 4 touches de tri** | Déplacer la photo vers le dossier correspondant, puis afficher la suivante |
| **Barre d'espace** ou **flèche droite** | Passer à la photo suivante **sans** la ranger (elle reste dans le dossier source) |
| **Flèche gauche** | Revenir à la photo précédente, sans rien déplacer |
| **Retour arrière** | Annuler la dernière action (rangement ou rognage) : la photo revient à sa place et se réaffiche. Plusieurs annulations de suite sont possibles |
| **R** | Faire pivoter l'affichage d'un quart de tour |
| **C** | Rogner la photo (voir ci-dessous) |
| **Molette de la souris** | Agrandir ou réduire la vue (zoom) |
| **Cliquer-glisser** | Déplacer la vue lorsque la photo est agrandie |
| **Échap** | Enregistrer l'avancement et fermer |

> Le zoom et la rotation **ne modifient jamais le fichier**. Ils servent
> uniquement à mieux examiner la photo avant de la ranger ; elle est déplacée
> telle quelle.

**Revenir sur une photo déjà rangée.** Les flèches font circuler librement d'une
photo à l'autre sans rien déplacer. Une photo déjà rangée s'affiche depuis le
dossier où elle se trouve, indiqué dans la barre du bas ; une touche de tri la
déplace alors de ce dossier vers le nouveau.

### Rogner une photo

1. Appuyez sur **C** : la photo s'affiche en entier.
2. **Cliquez-glissez** pour tracer le cadre à garder ; ce qui sera coupé est
   assombri. Pour corriger, tracez simplement un nouveau cadre.
3. **Entrée** rogne la photo et l'enregistre à sa place, dans son format
   d'origine. **Échap** ou **C** abandonne sans rien modifier.

- Si vous avez pivoté l'affichage avec R, tracez le cadre sur la photo telle
  que vous la voyez : le rognage tombe au bon endroit, et la photo est ensuite
  enregistrée dans son sens d'origine (la rotation reste purement visuelle).
- Une copie intacte est gardée avant chaque rognage : **Retour arrière** la
  remet en place. Ces copies sont effacées à la fermeture de la fenêtre ;
  l'annulation d'un rognage n'est donc possible que tant qu'elle est ouverte.

L'étape est terminée lorsque toutes les photos ont été soit rangées, soit
passées. Les photos passées restent dans le dossier source et pourront être
traitées plus tard.

---

## 5. Mode revue — reclasser un dossier trié

Pour corriger un rangement après coup. Depuis le menu, choisissez **« Mode
revue »**, puis l'un des quatre dossiers de tri : ses photos défilent une par
une, comme au tri.

Par exemple, en revoyant « À garder », vous tombez sur une photo ratée : appuyez
sur la touche de « Ratées », elle y est **déplacée immédiatement** et la photo
suivante s'affiche.

| Touche ou action | Effet |
|---|---|
| **Touche d'un autre dossier** | Déplacer la photo vers ce dossier, puis afficher la suivante |
| **Touche du dossier revu** | Laisser la photo où elle est et passer à la suivante |
| **Barre d'espace** ou **flèche droite** | Passer à la photo suivante sans la déplacer |
| **Flèche gauche** | Revenir à la photo précédente, sans rien déplacer |
| **Retour arrière** | Annuler le dernier déplacement ou rognage |
| **R**, **C**, molette, cliquer-glisser | Comme au tri : pivoter, rogner, zoomer, déplacer la vue |
| **Échap** | Enregistrer l'avancement et fermer |

Ce qu'il faut savoir :

- Seuls les quatre dossiers de tri peuvent être revus, et ce sont les seules
  destinations possibles. Les copies (section 8) n'ont pas de touche.
- Si le dossier de destination contient déjà un fichier du même nom, **rien
  n'est déplacé** et un message vous prévient : aucune photo n'est jamais
  écrasée.
- En revenant sur une photo déjà déplacée (flèche gauche), la barre du bas
  indique le dossier où elle se trouve maintenant.
- Rouvrir le même dossier reprend à la photo où vous vous étiez arrêté ; les
  photos rangées entre-temps dans ce dossier sont ajoutées à la fin. Une fois le
  dossier revu en entier, le rouvrir repart du début.

---

## 6. Étape 2 — La censure des yeux

Lancée depuis le menu, à tout moment après le tri. Vous choisissez **un seul**
dossier à passer en revue : l'un des quatre dossiers de tri, ou l'une des copies
faites depuis le menu (section 7).

Pour chaque photo, le logiciel **détecte automatiquement les visages** et la
position des deux yeux.

### Poser un bandeau

- **Cliquez sur la tête d'une personne** : un bandeau noir apparaît sur ses yeux.
- **Cliquez à nouveau sur la même personne** : le bandeau disparaît.

Chaque personne est indépendante : vous pouvez masquer certains visages et en
laisser d'autres visibles. Le bandeau **épouse l'inclinaison de la tête** : il
s'aligne sur la ligne qui joint les deux yeux. Ses bords sont lissés : même
incliné, il ne présente pas de marches d'escalier, à l'écran comme dans le
fichier enregistré.

### Quand la détection échoue

Si une personne n'a pas été détectée (visage de profil, lunettes de soleil, yeux
fermés…), **cliquez à l'endroit de ses yeux** : un bandeau de taille standard
apparaît, entouré de poignées bleues.

| Manipulation | Effet |
|---|---|
| Glisser le **centre** du bandeau | Le déplacer |
| Glisser la poignée **carrée de droite** | Modifier sa longueur |
| Glisser la poignée **carrée du bas** | Modifier son épaisseur |
| Glisser la poignée **ronde du dessus** | Le faire pivoter |
| **Cliquer dessus sans le déplacer** | Le retirer |

### Commandes de la censure

| Touche ou action | Effet |
|---|---|
| **Clic gauche** | Poser ou retirer un bandeau |
| **Entrée** | Incruster les bandeaux, enregistrer la photo sur place, passer à la suivante |
| **Barre d'espace** ou **flèche droite** | Passer à la photo suivante sans la modifier |
| **Flèche gauche** | Revenir à la photo précédente sans rien enregistrer (les bandeaux non validés sont abandonnés) |
| **Retour arrière** | Annuler la dernière validation : la photo d'origine est restaurée et réaffichée |
| **Échap** | Enregistrer l'avancement, vider le dossier temporaire et fermer |

### Ce qui est enregistré, et quand

- **Tant que vous n'appuyez pas sur Entrée, rien n'est écrit sur le disque.**
  Les bandeaux ne sont que des dessins provisoires à l'écran.
- À la validation, la photo est **réenregistrée dans son format d'origine** (un
  JPEG reste JPEG, un PNG reste PNG, un HEIC reste HEIC) **par-dessus le fichier
  existant**, dans le même dossier. Elle n'est pas déplacée.
- Si vous validez une photo **sans aucun bandeau**, le fichier n'est pas réécrit
  du tout : cela éviterait une recompression inutile qui dégraderait la photo
  sans rien y apporter.

### Filet de sécurité

Avant de modifier une photo, le logiciel en conserve une **copie intacte** dans
un dossier temporaire. La touche Retour arrière restaure cette copie.

> Ce dossier temporaire est **vidé à la fermeture du logiciel**. L'annulation
> n'est donc possible que **pendant la session en cours**.

---

## 7. Dupliquer un dossier

Depuis le menu principal, le bouton **« Dupliquer un dossier »** fait une copie
complète de l'un de vos dossiers, à côté de l'original.

C'est utile parce que **la censure réécrit les photos sur place** : une fois les
bandeaux validés, la version sans bandeaux n'existe plus. En dupliquant d'abord,
vous gardez les deux versions.

Le déroulé :

1. Vous choisissez le dossier à copier (les quatre dossiers de tri, ainsi que
   les copies déjà faites).
2. Le logiciel propose un nom, « Nom du dossier - copie », que vous pouvez
   changer. Un nom déjà pris ou impossible est refusé, et vous êtes invité à en
   saisir un autre.
3. La copie s'effectue en affichant son avancement. Sur plusieurs milliers de
   photos, comptez quelques minutes.

Ce qu'il faut savoir :

- Une copie **n'est pas un cinquième dossier de tri** : le tri en compte
  toujours quatre, chacun avec sa touche. La copie ne reçoit donc pas de touche.
- Une copie **peut être censurée** comme n'importe quel dossier : elle apparaît
  dans la liste proposée à l'étape 2.
- La copie ne concerne que les fichiers posés directement dans le dossier.
- Les dossiers `RAW/` et `Videos/` ne sont pas proposés : leur contenu ne doit
  jamais être modifié, une copie n'aurait donc pas d'objet.

Utilisation typique : dupliquer « À garder » en « À garder - censuré », puis
censurer la copie. Les originaux restent intacts.

---

## 8. Reprise de session

Vous pouvez fermer le logiciel à n'importe quel moment. Votre avancement est
enregistré dans `suivi.json`, à l'intérieur du dossier de l'événement, et mis à
jour **après chaque action**.

À la réouverture, choisissez « Reprendre un événement existant » : la préparation
automatique n'est pas rejouée, et chaque étape repart exactement là où vous vous
étiez arrêté, même après plusieurs centaines de photos.

---

## 9. Formats de fichiers

| Type | Traitement |
|---|---|
| JPEG, PNG | Triés **et** censurés |
| HEIC (iPhone) | Triés et censurés, lus et réenregistrés dans leur format |
| RAW (`.cr2`, `.nef`, `.arw`, `.dng`…) | Mis de côté dans `RAW/`, jamais modifiés |
| Vidéo (`.mp4`, `.mov`, `.avi`, `.mkv`…) | Mis de côté dans `Videos/`, jamais traités |

---

## 10. Organisation du code

| Fichier | Responsabilité |
|---|---|
| `main.py` | Lancement, gestion des sessions, menu principal |
| `configuration.py` | Écran de configuration d'un nouvel événement |
| `preparation.py` | Création des dossiers, renommage, mise à l'écart RAW/vidéo |
| `tri.py` | Étape 1 : lance la fenêtre de rangement sur le dossier source |
| `revue.py` | Mode revue : lance la fenêtre de rangement sur un dossier de tri |
| `rangement.py` | Fenêtre commune au tri et à la revue : clavier, déplacements, navigation, annulation |
| `visionneuse.py` | Affichage d'une photo : zoom, vue, rotation, cadre de rognage |
| `rognage.py` | Écriture d'une photo rognée sur le disque |
| `censure.py` | Étape 2 : affichage, clics, validation, annulation |
| `bandeaux.py` | Géométrie du bandeau : inclinaison, poignées, dessin aux bords lisses |
| `visages.py` | Détection des visages et des yeux |
| `images.py` | Lecture, orientation, enregistrement, chargement anticipé |
| `suivi.py` | Fichier de suivi : enregistrement et reprise |
| `dossiers.py` | Choix d'un dossier, noms valides, liste des photos, duplication |
| `modeles/` | Modèle de détection livré avec le programme |
| `verifier_installation.py` | Contrôle que l'installation est fonctionnelle |

Les règles de conception du projet sont consignées dans `CLAUDE.md`.

---

## 11. Questions courantes

**Le passage d'une photo à l'autre est-il rapide ?**
Oui. Pendant que vous regardez une photo, les suivantes sont déjà lues en
arrière-plan, et leurs visages déjà détectés. Le logiciel est prévu pour environ
3 000 photos par session.

**Une personne au fond n'est pas détectée.**
Cliquez simplement à l'endroit de ses yeux : un bandeau manuel apparaît, que vous
pouvez déplacer, redimensionner et incliner.

**J'ai validé une photo par erreur.**
Appuyez sur Retour arrière : la photo d'origine est restaurée. Attention, cela
n'est possible que tant que le logiciel n'a pas été fermé.

**Windows refuse de déplacer mon dossier : « un fichier ou dossier est ouvert ».**
Cela veut dire que le logiciel tourne encore. Tant qu'il lit des photos en
arrière-plan, Windows considère le dossier comme ouvert. Fermez le logiciel par
le bouton **Quitter** du menu (ou par Échap) : le programme relâche alors tous
les fichiers et se termine pour de bon. Si un message d'erreur inattendu
apparaît, fermez-le puis quittez normalement — le menu revient toujours à
l'écran, même après une erreur.

**Puis-je récupérer une photo mise dans « À supprimer » ?**
Oui : le logiciel ne supprime jamais aucun fichier. Il ne fait que les déplacer.
Le dossier « À supprimer » est un dossier comme les autres, que vous videz
vous-même si vous le souhaitez.
