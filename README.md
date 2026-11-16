# Tri et censure de photos

Logiciel de bureau permettant de **trier rapidement un grand nombre de photos**
au clavier, puis de **masquer les yeux** de certaines personnes pour préserver
leur anonymat avant de partager les images.

Il fonctionne sur les fichiers de votre ordinateur, pour un seul utilisateur et
un seul événement à la fois. Aucun serveur, aucune base de données, aucune
connexion internet nécessaire.

---

## 1. Installation et lancement

Le logiciel fonctionne sur **Windows, macOS et Linux**.

### La manière simple : un double-clic

| Système | Fichier à double-cliquer |
|---|---|
| **Windows** | `lancer.bat` |
| **macOS** | `lancer.command` |
| **Linux** | `lancer.sh` |

Au **premier** lancement, une fenêtre de terminal s'ouvre et le programme
s'installe tout seul : il vérifie que Python est présent, crée son
environnement isolé (le dossier `venv/`), télécharge les trois bibliothèques
nécessaires, puis ouvre la fenêtre du logiciel. Comptez une minute.

Aux lancements suivants, la fenêtre s'ouvre directement : rien n'est
réinstallé, et le lanceur passe la main sans attendre au Python du logiciel.
L'écran d'accueil s'affiche d'abord ; le reste (lecture des photos, détection
des visages) se charge pendant que vous choisissez votre événement.

> **Si Python manque**, le script vous le dit et propose de l'installer :
> par Homebrew sous macOS, par `winget` sous Windows, par le gestionnaire de
> paquets de votre distribution sous Linux. Vous pouvez aussi refuser et
> l'installer vous-même depuis <https://www.python.org/downloads/>.
> Sous Linux, si le Python de la distribution est trop ancien (Ubuntu 22.04
> fournit 3.10), le script propose `python3.11` ; si votre distribution ne
> le fournit pas, installez une version récente vous-même.
>
> **Après une mise à jour de Python**, l'environnement isolé est refait tout
> seul au lancement suivant, s'il ne fonctionne plus.
>
> **Sous macOS et Linux**, si le double-clic ne fait rien, il faut autoriser
> une seule fois l'exécution, depuis un terminal placé dans le dossier :
> `chmod +x lancer.sh lancer.command`

### La manière manuelle

Si vous préférez tout faire à la main, ou si vous travaillez déjà dans un
terminal :

**Windows**

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**macOS / Linux**

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Il existe aussi un intermédiaire, qui installe ce qu'il faut puis lance le
logiciel, sans passer par les fichiers `lancer.*` :

```
python demarrer.py
```

### Ce qu'il vous faut

- **Python 3.11 ou supérieur** (développé et vérifié sous Python 3.14).
  Tkinter, l'interface graphique, est fourni d'origine avec Python — sauf sur
  certaines distributions Linux, où il faut ajouter `python3-tk`. Le programme
  vous le signale clairement le cas échéant.

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
python demarrer.py --verifier
```

Ce script contrôle en quelques secondes que Python, les bibliothèques et
le modèle de détection sont en place, que les formats JPEG, PNG et HEIC sont bien
lus **et** réenregistrés, et que les bandeaux s'inclinent correctement. Il
fabrique ses propres images de test et **ne touche à aucun de vos fichiers**.

Un second jeu de tests vérifie la **géométrie du bandeau** — couvre-t-il bien
les yeux, sans monter inutilement sur le front ?

```
python tester_bandeau.py
```

Un troisième vérifie la **géométrie du cadre de rognage** — tirer un bord
déplace-t-il le bon côté, y compris quand la photo a été pivotée à l'écran ?

```
python tester_rognage.py
```

Deux derniers vérifient ce qui arrive aux fichiers : le **rangement**
(préparation, tri, annulation, fichiers bloqués, photos revenues, gestion des
dossiers) et le **réenregistrement des formats** (transparence, WEBP sans perte,
HEIC très détaillé, formats refusés).

```
python tester_rangement.py
python tester_formats.py
```

### En cas de problème

```
python demarrer.py --reinstaller
```

efface le dossier `venv/` et refait l'installation depuis zéro. Vos photos et
votre avancement ne sont pas touchés.

---

## 2. Démarrage d'une session

Au démarrage, trois possibilités :

- **Démarrer un nouvel événement** — vous remplissez l'écran de configuration,
  puis le logiciel prépare tout seul les dossiers et les photos.
- **Reprendre « … »** — reprend en un clic le dernier événement ouvert.
- **Reprendre un événement existant…** — vous désignez le dossier d'un
  événement, et vous reprenez votre travail (section 8).

> Pour reprendre un événement, choisissez **le dossier de l'événement** : votre
> dossier de photos, renommé du nom de l'événement, celui qui contient les
> dossiers de tri. Pour un événement créé avant le 26 octobre 2026, qui vivait
> dans un sous-dossier de votre dossier de photos, choisir le dossier de photos
> suffit : le logiciel trouve l'événement à l'intérieur.

---

## 3. Déroulé complet

### Étape A — Configuration (nouvel événement seulement)

Vous renseignez :

1. le **dossier des photos** ;
2. le **nom de l'événement** (par exemple « Mariage Julie et Marc ») — le nom
   du dossier est proposé d'office ;
3. vos **dossiers de tri**, chacun avec un nom et une touche du clavier ;
4. le **nom donné aux photos** (voir ci-dessous).

**Votre dossier de photos devient le dossier de l'événement** : il est renommé
du nom de l'événement, et les dossiers de tri sont créés directement dedans. Il
n'y a plus de sous-dossier supplémentaire. L'écran annonce ce renommage avant
qu'il ait lieu. S'il est impossible (un fichier du dossier est ouvert dans un
autre programme, synchronisation en cours, racine d'une carte mémoire), le tri
se fait dans le dossier sous son nom actuel, et un message le signale. Si le
nom est déjà pris par un dossier voisin, l'écran demande un autre nom.

**Les dossiers de tri sont libres** : de 1 à 12. Le bouton **« + Ajouter un
dossier »** en ajoute un (une touche libre est proposée), le bouton
**« Retirer »** en enlève un. **La liste est retenue** : la prochaine fois, vous
retrouvez vos dossiers tels que vous les avez laissés — noms, nombre et touches.

Le bouton « Continuer » n'aboutit que si tout est correct : dossier existant et
non vide, nom utilisable comme nom de dossier, chaque dossier de tri avec un nom
et une touche, aucun nom ni aucune touche utilisés deux fois. Les touches **R**,
**C** et **N** sont réservées (pivoter, rogner, nouveau dossier), et les noms
`RAW`, `Videos`, `Sans-barre` et `_sauvegardes_temporaires` aussi : le logiciel
s'en sert lui-même.

> Si le dossier est synchronisé par **OneDrive** (ou Google Drive, Dropbox,
> iCloud), l'écran vous le signale : voir la section 9 bis.

#### Le nom donné aux photos

Cinq formats au choix ; un exemple s'affiche sous la liste, et votre choix est
retenu pour la prochaine fois. Dans tous, l'ordre est celui des prises de
vue : **classer les fichiers par nom les donne de la plus ancienne à la plus
récente.**

| Format | Exemple | À savoir |
|---|---|---|
| **Date, heure et code** (par défaut) | `2026-08-24_14-03-27_K7F2.jpg` | Le code de 4 caractères vient du contenu de la photo. **Deux tris faits sur deux ordinateurs se réunissent sans qu'aucun nom se répète**, même pour des photos prises dans la même seconde ; et une même photo reçoit partout le même nom, ce qui fait reconnaître les vrais doublons |
| **Date et heure** | `2026-08-24_14-03-27.jpg` | Plus court, mais deux appareils qui déclenchent dans la même seconde donnent le même nom |
| **Numéros** | `1.jpg`, `2.jpg`, `3.jpg` | Le format d'origine, sans zéros devant. Deux tris faits séparément ont les mêmes noms |
| **Nom de l'événement et numéro** | `Mariage_0001.jpg` | Numéros complétés par des zéros |
| **Ne pas renommer** | `IMG_4012.jpg` | Les fichiers gardent le nom donné par l'appareil |

Dans les deux formats par date, les photos d'une même seconde (rafale) sont
numérotées dans leur ordre (`…_14-03-27-1_…`, `…_14-03-27-2_…`), et les
fichiers d'une même prise de vue portent le même nom : `IMG_12.JPG` et
`IMG_12.CR2` deviennent `2026-…_K7F2.JPG` et `2026-…_K7F2.CR2`. L'heure est
celle de l'ordinateur pour l'instant de la prise de vue.

Le format se change aussi après coup : bouton **« Renommer les photos »** du
menu (étape C).

### Étape B — Préparation automatique

Elle s'exécute une seule fois, sans rien vous demander :

```
Mariage Julie et Marc/        (votre dossier de photos, renommé)
├── 2026-08-24_14-03-27_K7F2.jpg…   (les photos à trier, renommées)
├── A garder/                 (vos dossiers de tri : ici, ceux proposés
├── Ratees/                    d'office, que vous pouvez renommer à votre
├── A revoir/                  goût, accents compris)
├── A supprimer/
├── RAW/          (créé seulement s'il y a des fichiers RAW)
├── Videos/       (créé seulement s'il y a des vidéos)
└── suivi.json    (votre avancement)
```

- Les photos sont **renommées selon le format choisi** à l'étape A (ou pas du
  tout, si vous avez choisi « Ne pas renommer »), extension d'origine
  conservée, dans l'ordre **chronologique de prise de vue** : le premier nom
  revient à la photo la plus ancienne (date et heure), le dernier à la plus
  récente. La date est lue dans la photo elle-même (EXIF) : la date de prise de vue, ou
  à défaut celle inscrite par l'appareil, avec son fuseau horaire quand
  l'appareil l'indique (photos prises à l'étranger, nuit du changement
  d'heure). Sans date lisible, on prend la plus ancienne des dates du fichier.
- Les fichiers **RAW** (`.cr2`, `.nef`, `.arw`, `.dng`…) et les **vidéos**
  (`.mp4`, `.mov`, `.avi`, `.mkv`…) sont **mis de côté** et ne sont plus jamais
  touchés ensuite. Si un dossier `RAW/` ou `Videos/` existait déjà et contient un
  fichier du même nom, ou si le fichier est occupé par un autre programme, il
  reste à la racine et le compte rendu le signale : rien n'est jamais écrasé.
- Les autres fichiers (textes, PDF…) ne sont ni renommés ni déplacés, pas plus
  que les fichiers `._…` que macOS ajoute sur les clés et les cartes mémoire.
- Un **sous-dossier** ou un autre fichier qui porterait le nom que doit
  recevoir une photo (un dossier nommé `2.jpg`) est signalé avant tout
  renommage : renommez-le, puis recommencez. Un renommage qui échoue en route
  rend leur ancien nom à tous les fichiers.
- Si la préparation est interrompue (fichier bloqué, coupure de courant), la
  reprise de l'événement propose de la terminer.

> À noter, au format « Numéros » : la numérotation porte sur **tous** les fichiers de la racine. Comme
> les RAW et les vidéos reçoivent eux aussi un numéro avant d'être déplacés, la
> suite des numéros des photos peut comporter des trous (1, 2, 3, 6, 8…). C'est
> normal.

### Étape C — Menu principal

Sept choix : **trier** les photos du dossier source, **revoir un dossier**
(reclasser, barrer des yeux), **gérer les dossiers de tri** (section 5 bis),
**dupliquer un dossier**, **renommer les photos**, **terminer la session**, ou
quitter. Le menu rappelle votre avancement et le
nombre de photos dans chaque dossier, copies comprises. Il signale aussi, en
rouge, les photos rangées qui seraient revenues dans le dossier source, et un
dossier synchronisé par OneDrive (section 9 bis).

Le tri, la revue et la censure des yeux se font **dans la même fenêtre** : la
censure n'est plus une étape à part, c'est le **mode barrer**, que la touche
**Tab** active ou désactive (section 6).

**Renommer les photos** applique un autre format de nom à **toutes** les photos
de l'événement, où qu'elles soient : à trier, rangées, copiées, mises de côté
(`RAW`, `Videos`) ou gardées sans barre. Une photo, sa version sans barre et
ses copies reçoivent le même nouveau nom. C'est ce qui permet de réunir deux
tris déjà faits au format « Numéros » : renommez-les d'abord « Date, heure et
code ». Les annulations en attente restent possibles après le renommage.

**Terminer la session** rend le tri **définitif**. Jusque-là, rien ne l'est :
vous pouvez quitter, revenir, et défaire ce que vous avez fait à n'importe
quelle photo (voir « Annuler », section 4). Le bouton, après confirmation :

- efface les copies intactes gardées pour l'annulation (le menu indique la
  place qu'elles occupent) : plus rien ne peut être annulé ;
- **supprime les dossiers vides** (dossiers de tri, `RAW`, `Videos`). Ils
  restent dans la liste de l'événement : si vous y rangez une photo plus tard,
  le dossier est recréé tout seul.

Les photos rangées et les versions sans barre ne sont pas touchées. Vous
pouvez rouvrir l'événement ensuite : ce que vous y ferez sera de nouveau
annulable, jusqu'à la prochaine fin de session.

---

## 4. Étape 1 — Le tri

Les photos défilent une par une en grand, **toujours dans le bon sens** (le
logiciel lit l'orientation enregistrée par l'appareil). L'avancement est affiché
en permanence, sous la forme « Photo 12 sur 340 ».

**Statistiques en temps réel**, en bas de la fenêtre :

```
A trier : 118   |   Rangees : 59 sur 177 (33 %)   |   Cette session : 24   |   Rythme : 9 photos/min   |   Temps restant : environ 13 min   |   31 action(s) annulable(s)
[1] A garder (41)   [2] Ratees (12)   [3] A revoir (6)      [N] nouveau dossier
```

Le nombre de photos de chaque dossier suit sa touche. Le rythme et le temps
restant apparaissent après quelques photos ; une pause n'est comptée que pour
une minute, pour ne pas les fausser.

### Commandes du tri

| Touche ou action | Effet |
|---|---|
| **Vos touches de tri** | Enregistrer les retouches en attente (rotation, bandeaux), déplacer la photo vers le dossier correspondant, puis afficher la suivante |
| **N** | Créer un **nouveau dossier de tri** sans quitter le tri : une petite fenêtre demande son nom et sa touche (une touche libre est proposée). La photo affichée ne bouge pas : appuyez ensuite sur la touche du nouveau dossier pour l'y ranger. Le dossier est retenu pour vos prochains événements |
| **Entrée** | Enregistrer les retouches en attente dans la photo, sans la déplacer, puis afficher la suivante |
| **Barre d'espace** ou **flèche droite** | Passer à la photo suivante **sans** la ranger ni enregistrer ses retouches |
| **Flèche gauche** | Revenir à la photo précédente, sans rien déplacer ni enregistrer |
| **Retour arrière** | **Annuler** : la photo revient à sa place, dans son état d'avant, et se réaffiche. Sans avoir bougé, c'est la dernière action qui est annulée, et plusieurs appuis remontent les actions une à une. **Revenu sur une ancienne photo avec les flèches, c'est ce qu'on a fait à cette photo-là qui est annulé**, même si d'autres ont été modifiées depuis. Le rappel des touches dit toujours ce qui sera annulé (voir ci-dessous) |
| **R** | Faire pivoter la photo d'un quart de tour (enregistré par Entrée ou une touche de tri) |
| **C** | Rogner la photo en réduisant ses bords (voir ci-dessous) |
| **Tab** | Activer ou désactiver le **mode barrer** les yeux (section 6) |
| **Molette de la souris** | Agrandir ou réduire la vue (zoom) |
| **Cliquer-glisser** | Déplacer la vue lorsque la photo est agrandie |
| **Échap** | Enregistrer l'avancement et fermer |

Pendant le **rognage**, seules trois touches agissent : **Entrée** (rogner),
**Échap** et **C** (abandonner). Toutes les autres sont inertes.

> **Clavier AZERTY.** Sur un clavier français ou belge, la rangée des chiffres
> donne `& é " ' (`… sans la touche Majuscule. Si vous avez choisi les touches
> `1`, `2`, `3`…, inutile d'appuyer sur Majuscule : la touche marquée 1 range
> dans le dossier de la touche 1, avec ou sans Majuscule, comme le pavé
> numérique.

La fenêtre s'ouvre agrandie la première fois, puis reprend la taille et la
position que vous lui avez laissées.

Une photo au format **BMP, GIF ou TIFF**, ou une image animée, se trie
normalement, mais ne peut être ni rognée ni barrée : son format ne se
réenregistre pas sans perte. La barre du bas l'indique dès l'affichage,
« format non modifiable : tri seulement ».

> **Fichier occupé.** Une photo ouverte dans un autre programme (OneDrive qui
> l'envoie en ligne, antivirus…) ne peut pas être déplacée : le logiciel
> réessaie deux secondes, puis vous prévient. Rien n'est perdu : rappuyez sur
> la touche. Il en va de même pour Retour arrière : une annulation qui échoue
> reste à faire, et un nouvel appui la reprend là où elle s'était arrêtée.
>
> **Enregistrement en cours.** Une photo HEIC met quelques secondes à
> s'enregistrer. Si vous la rangez, l'annulez ou fermez la fenêtre juste
> après l'avoir validée, la barre du bas affiche « Enregistrement en cours, un
> instant... » : la fenêtre ne se fige pas, et l'action se fait dès que
> l'enregistrement est fini. Les autres touches sont ignorées d'ici là.
>
> **Enregistrement raté.** Si une photo n'a pas pu être enregistrée (disque
> plein, fichier bloqué), un message le dit et elle se réaffiche telle qu'elle
> est sur le disque : le fichier d'origine est intact.
>
> **Chargement.** Une touche de tri pressée pendant que la barre affiche
> « Chargement... » est ignorée : on ne range pas une photo qu'on n'a pas
> vue. Attendez qu'elle apparaisse, puis rappuyez.

### Retouches : ce qui est enregistré, et quand

La rotation (R) et les bandeaux (mode barrer) sont d'abord **provisoires** :
la barre du bas les signale en orange, « À enregistrer : rotation 90°,
2 bandeau(x) ». Ils sont écrits dans la photo :

- par **Entrée**, qui enregistre et passe à la suivante ;
- par **une touche de tri**, qui enregistre puis range la photo.

**Espace**, les **flèches** et **Échap** les abandonnent : la photo reste
intacte. Le zoom, lui, n'est jamais enregistré.

Quand une photo est enregistrée **avec des bandeaux**, sa version sans bandeaux
est gardée dans un sous-dossier **`Sans-barre`** du dossier où va la photo
(par exemple `Dossier 1/Sans-barre/12.jpg`). Elle suit la photo si on la range
ailleurs, et disparaît si l'on annule (Retour arrière).

La photo est réenregistrée dans son format d'origine, en gardant sa date de
prise de vue et ses autres informations (EXIF), ainsi que son profil de
couleurs. Une photo sans retouche n'est jamais réécrite.

**Revenir sur une photo déjà rangée.** Les flèches font circuler librement d'une
photo à l'autre sans rien déplacer. Une photo déjà rangée s'affiche depuis le
dossier où elle se trouve, indiqué dans la barre du bas ; une touche de tri la
déplace alors de ce dossier vers le nouveau.

### Rogner une photo

Le rognage se fait **en réduisant les bords de la photo**, comme sur un
téléphone. Il n'y a pas de rectangle à tracer.

1. Appuyez sur **C** : la photo s'affiche en entier, entourée d'un cadre blanc
   posé sur ses quatre bords.
2. **Tirez un bord** pour n'enlever qu'un côté, **un coin** pour en régler deux
   d'un seul geste, ou **glissez à l'intérieur** du cadre pour le déplacer sans
   changer sa taille. Ce qui sera coupé s'assombrit à mesure, et les dimensions
   de ce que vous gardez s'affichent dans la barre du bas.
3. **Entrée** rogne la photo et l'enregistre à sa place, dans son format
   d'origine. **Échap** ou **C** abandonne sans rien modifier.

Repères utiles :

- La forme du pointeur dit ce que vous allez saisir : double flèche sur un
  bord, flèche d'angle sur un coin, croix de déplacement à l'intérieur.
- Une **grille des tiers** apparaît pendant que vous ajustez, pour vous aider à
  placer le sujet, et disparaît dès que vous relâchez.
- Si vous validez sans avoir bougé aucun bord, **rien n'est réenregistré** : le
  logiciel sort simplement du mode, sans recompresser la photo pour rien.
- Pendant le rognage, **seules Entrée, Échap et C agissent**. Les autres
  touches, la molette et le mode barrer sont volontairement inertes, pour que
  rien ne puisse déplacer ni modifier la photo tant que le cadre est à l'écran.
- Si vous avez pivoté la photo avec R, réglez le cadre sur la photo telle que
  vous la voyez : le rognage tombe au bon endroit. La rotation reste ensuite
  en attente, comme avant le rognage, et les bandeaux déjà posés suivent le
  nouveau cadrage.
- Une copie intacte est gardée avant chaque rognage et chaque retouche :
  **Retour arrière** la remet en place, même lors d'une session suivante.

### Annuler, même une ancienne photo

Tout ce que vous faites à une photo reste annulable — rangement, bandeaux,
rotation, rognage — **jusqu'à ce que vous cliquiez sur « Terminer la session »**
dans le menu. Vous pouvez fermer le logiciel et y revenir entre-temps.

- **Vous venez de faire une erreur** : appuyez sur Retour arrière. La dernière
  action est annulée ; appuyez encore pour remonter aux précédentes.
- **Vous voulez défaire ce que vous avez fait à une photo plus ancienne** :
  revenez dessus avec la flèche gauche (ou ouvrez son dossier en mode revue),
  puis appuyez sur Retour arrière. Seule cette photo est concernée, les
  autres gardent leurs modifications. Appuyez de nouveau pour défaire, une à
  une, les actions plus anciennes de cette même photo.

Le rappel des touches annonce à tout moment ce que fera la touche :
« [Retour arrière] annuler le rognage de 2026-08-24_14-03-27_K7F2.jpg », ou
« rien à annuler ».

L'étape est terminée lorsque toutes les photos ont été soit rangées, soit
passées. Les photos passées restent dans le dossier source, et **l'écran de fin
indique combien il en reste** : appuyez sur **Entrée** pour les repasser
aussitôt, sans revenir au menu.

**Chaque ouverture du tri ne montre que les photos encore dans le dossier
source**, c'est-à-dire pas encore rangées, à partir de la première. Les photos
déjà rangées n'y reviennent pas ; pendant la session, la flèche gauche permet
toutefois de revenir sur une photo que l'on vient de ranger.

Le logiciel retient dans quel dossier vous avez rangé chaque photo. Si une
photo rangée se retrouve plus tard dans le dossier source — c'est ce que fait
parfois OneDrive, voir la section 9 bis —, il vous le dit à l'ouverture du tri
et propose de la remettre dans son dossier.

---

## 5. Revoir un dossier — reclasser ou censurer

Pour corriger un rangement après coup, ou pour barrer des yeux. Depuis le menu,
choisissez **« Revoir un dossier »**, puis l'un des dossiers de tri ou l'une des
copies (section 7) : ses photos défilent une par une, dans la même fenêtre
qu'au tri.

Par exemple, en revoyant « À garder », vous tombez sur une photo ratée : appuyez
sur la touche de « Ratées », elle y est **déplacée immédiatement** et la photo
suivante s'affiche.

| Touche ou action | Effet |
|---|---|
| **Touche d'un autre dossier** | Enregistrer les retouches, déplacer la photo vers ce dossier, puis afficher la suivante |
| **Touche du dossier revu** | Enregistrer les retouches, laisser la photo où elle est et passer à la suivante |
| **Entrée** | Enregistrer les retouches et passer à la suivante |
| **Barre d'espace** ou **flèche droite** | Passer à la photo suivante sans la déplacer ni l'enregistrer |
| **Flèche gauche** | Revenir à la photo précédente, sans rien déplacer |
| **Retour arrière** | Annuler, comme au tri : la dernière action, ou, revenu sur une photo avec les flèches, ce qui a été fait à cette photo (même lors d'une session précédente, même pendant le tri) |
| **R**, **C**, **N**, **Tab**, molette, cliquer-glisser | Comme au tri : pivoter, rogner, nouveau dossier, mode barrer, zoomer, déplacer la vue |
| **Échap** | Enregistrer l'avancement et fermer |

Ce qu'il faut savoir :

- Les dossiers de tri sont les seules destinations possibles. Dans une
  **copie** (section 7), les touches de tri sont sans effet : ses photos n'en
  sortent pas, on n'y fait que retoucher et barrer des yeux.
- Si le dossier de destination contient déjà un fichier du même nom, **rien
  n'est déplacé** et un message vous prévient : aucune photo n'est jamais
  écrasée.
- En revenant sur une photo déjà déplacée (flèche gauche), la barre du bas
  indique le dossier où elle se trouve maintenant.
- Rouvrir le même dossier reprend à la photo où vous vous étiez arrêté ; les
  photos rangées entre-temps dans ce dossier sont ajoutées à la fin. Une fois le
  dossier revu en entier, le rouvrir repart du début.
- Une photo que la synchronisation aurait remise dans le dossier source est
  montrée depuis celui-ci (la barre du bas l'indique) : une touche de tri la
  range de nouveau.

---

## 5 bis. Gérer les dossiers de tri

Depuis le menu, **« Gérer les dossiers de tri »** ouvre la liste des dossiers de
tri de l'événement, avec le nombre de photos de chacun. Vous pouvez :

- **renommer** un dossier — il est renommé sur le disque, ses photos avec lui ;
- **changer sa touche** ;
- **ajouter** un dossier (bouton « + Ajouter un dossier ») ;
- **retirer** un dossier, **seulement s'il est vide** : un dossier qui contient
  encore des fichiers ne peut pas être retiré, pour qu'aucune photo ne soit
  perdue ou déplacée par mégarde. Videz-le d'abord, par exemple en reclassant
  ses photos en mode revue. Un dossier retiré, vide, est supprimé du disque.

Rien n'est modifié avant « Enregistrer ». La nouvelle liste est aussi retenue
pour vos prochains événements. Pour échanger les noms de deux dossiers, passez
par un nom provisoire, en deux fois.

---

## 6. Le mode barrer — la censure des yeux

Il n'y a plus d'étape de censure à part. Dans la fenêtre du tri ou de la revue,
appuyez sur **Tab** : le mode barrer s'active, une pastille rouge « MODE
BARRER » le signale en bas à droite. Il **reste actif** d'une photo à l'autre,
et même d'une session à l'autre, jusqu'à ce que vous rappuyiez sur Tab.

Vous pouvez donc trier et censurer en un seul passage : poser les bandeaux, puis
appuyer sur la touche de tri, qui enregistre les bandeaux et range la photo. Ou
bien, pour censurer sans ranger, revoir un dossier (ou une copie) et valider
chaque photo par Entrée.

Pour chaque photo, le logiciel **détecte automatiquement les visages** et la
position des deux yeux ; leur nombre s'affiche à côté de la pastille.

### Poser un bandeau

- **Cliquez sur la tête d'une personne** : un bandeau noir apparaît sur ses
  yeux, entouré de ses poignées. Le clic est rattaché au visage détecté dont
  la tête (un peu élargie, cheveux et oreilles compris) le contient ; si
  plusieurs têtes se chevauchent, à celui dont les yeux sont les plus proches
  du clic.
- **Double-cliquez sur un bandeau** : il disparaît.

Chaque personne est indépendante : vous pouvez masquer certains visages et en
laisser d'autres visibles. Le bandeau **épouse l'inclinaison de la tête** : il
s'aligne sur la ligne qui joint les deux yeux, **même sur une tête très
penchée**. Pour cela, chaque visage détecté est redressé puis examiné de
nouveau, et la photo est aussi parcourue inclinée à 45°, dans un sens puis
dans l'autre, pour trouver les têtes couchées. Ses bords sont lissés : même
incliné, il ne présente pas de marches d'escalier, à l'écran comme dans le
fichier enregistré.

Son épaisseur est calculée pour **couvrir entièrement les yeux sans monter sur
le front**. C'est la plus petite épaisseur qui convienne à toutes les
morphologies : elle est mesurée, et le calcul est refait à chaque fois que vous
lancez `python tester_bandeau.py`.

### Quand la détection échoue

Si une personne n'a pas été détectée (visage de profil, lunettes de soleil, yeux
fermés…), **cliquez à l'endroit de ses yeux** : un bandeau de taille standard
apparaît au même endroit, horizontal à l'écran — même si vous avez pivoté la
photo avec R, et même si elle est collée à une personne détectée. Un clic
dans la bande sombre autour de la photo ne pose rien.

### Retoucher un bandeau

**Tous** les bandeaux se retouchent, qu'ils aient été posés à la main ou par la
détection. Un clic sur un bandeau le **choisit** : son contour blanc et ses
cinq poignées apparaissent.

| Manipulation | Effet |
|---|---|
| **Cliquer** sur un bandeau | Le choisir, sans rien changer d'autre |
| **Glisser** le corps du bandeau | Le déplacer |
| Glisser une poignée **de gauche ou de droite** | Modifier sa longueur |
| Glisser une poignée **du haut ou du bas** | Modifier son épaisseur |
| Glisser la poignée **bleue, au bout du fil** | Le faire pivoter |
| **Double-cliquer** sur un bandeau | Le retirer |
| **Cliquer-glisser** à côté des bandeaux | Déplacer la vue (photo agrandie) |

Les poignées vont par paires, une de chaque côté : prenez celle qui tombe sous
votre souris. La forme du pointeur indique ce que vous vous apprêtez à saisir,
et la poignée survolée se met en avant. Sur un bandeau fin à l'écran, l'intérieur
sert à le déplacer : son épaisseur se tire juste au-dessus ou au-dessous.

> Un bandeau se retire **uniquement** par un double-clic sur lui. Un simple
> clic ne l'efface jamais, pas plus qu'un double-clic sur une poignée (deux
> retouches rapides de suite) : c'est ce qui permet d'attraper une poignée, ou
> de déplacer un bandeau, sans risquer de le faire disparaître par mégarde.

Le zoom et la rotation restent disponibles : les bandeaux suivent la photo
quand vous la pivotez, et s'enregistrent exactement là où vous les voyez.

### Ce qui est enregistré, et quand

- **Tant que vous n'appuyez pas sur Entrée ou sur une touche de tri, rien
  n'est écrit sur le disque.** Les bandeaux ne sont que des dessins provisoires
  à l'écran ; passer à une autre photo (Espace, flèches) les abandonne.
- À la validation, la photo est **réenregistrée dans son format d'origine** (un
  JPEG reste JPEG, un PNG reste PNG, un HEIC reste HEIC) **par-dessus le fichier
  existant**. Avec Entrée elle reste dans son dossier ; avec une touche de tri,
  elle est rangée en même temps.
- Désactiver le mode barrer (Tab) abandonne les bandeaux non enregistrés de la
  photo affichée.

### Filet de sécurité

Avant de modifier une photo, le logiciel en conserve une **copie intacte** dans
le dossier `_sauvegardes_temporaires` de l'événement. La touche Retour arrière
restaure cette copie.

> Ces copies sont gardées **d'une session à l'autre**, jusqu'à ce que vous
> cliquiez sur **« Terminer la session »** dans le menu, qui les efface et rend
> le tri définitif. D'ici là, elles occupent la place des photos modifiées ;
> le menu indique combien.

---

## 7. Dupliquer un dossier

Depuis le menu principal, le bouton **« Dupliquer un dossier »** fait une copie
complète de l'un de vos dossiers, à côté de l'original.

C'est utile parce que **la censure réécrit les photos sur place**. Le
sous-dossier `Sans-barre` garde bien une version sans bandeaux de chaque photo
barrée (section 4), mais dupliquer le dossier avant de le censurer reste le
moyen le plus simple de garder tous les originaux ensemble, barrés ou non.

Le déroulé :

1. Vous choisissez le dossier à copier (les dossiers de tri, ainsi que les
   copies déjà faites).
2. Le logiciel propose un nom, « Nom du dossier - copie », que vous pouvez
   changer. Un nom déjà pris (même par un dossier de l'événement disparu du
   disque), impossible, ou réservé au logiciel (`RAW`, `Videos`,
   `Sans-barre`, `_sauvegardes_temporaires`) est refusé, et vous êtes invité
   à en saisir un autre.
3. La copie s'effectue en affichant son avancement. Sur plusieurs milliers de
   photos, comptez quelques minutes. Si elle échoue en cours de route (disque
   plein, fichier occupé), le dossier à moitié copié est effacé.

Ce qu'il faut savoir :

- Une copie **n'est pas un dossier de tri** : elle ne reçoit pas de touche, et
  le tri n'y range rien. Pour un dossier de tri supplémentaire, utilisez
  « Gérer les dossiers de tri » (section 5 bis) ou la touche N pendant le tri.
- Une copie **peut être censurée** comme n'importe quel dossier : elle apparaît
  dans la liste proposée par « Revoir un dossier ».
- La copie ne concerne que les fichiers posés directement dans le dossier.
- Les dossiers `RAW/` et `Videos/` ne sont pas proposés : leur contenu ne doit
  jamais être modifié, une copie n'aurait donc pas d'objet.

Utilisation typique : dupliquer « À garder » en « À garder - censuré », puis
revoir la copie en mode barrer. Les originaux restent intacts.

---

## 8. Reprise de session

Vous pouvez fermer le logiciel à n'importe quel moment. Votre avancement est
enregistré dans `suivi.json`, à l'intérieur du dossier de l'événement, et mis à
jour **après chaque action**.

À la réouverture, un bouton reprend directement le dernier événement ouvert ;
pour un autre, choisissez « Reprendre un événement existant… ». La préparation
automatique n'est pas rejouée. Le tri reprend avec les photos encore dans le
dossier source (celles passées avec Espace comprises, à partir de la
première), et la revue d'un dossier à la photo où vous l'aviez laissée. Seule
exception : une préparation qui avait été interrompue est proposée à la
reprise, pour être terminée.

Tout ce que vous avez fait reste **annulable** à la reprise, tant que la
session n'a pas été terminée depuis le menu (étape C).

Le logiciel retient aussi, d'une ouverture à l'autre, vos dossiers de tri, le
format de nom des photos, le dernier événement ouvert, le dossier où vous
allez chercher vos photos et la taille de la fenêtre de tri. Ces préférences sont dans le fichier
`preferences.json`, à côté du programme ; le supprimer revient simplement aux
valeurs par défaut.

---

## 9. Formats de fichiers

| Type | Traitement |
|---|---|
| JPEG, PNG, WEBP | Triés **et** censurés. Un WEBP sans perte le reste ; la transparence d'un PNG est conservée |
| HEIC (iPhone) | Triés et censurés, lus et réenregistrés dans leur format. Une photo très détaillée est enregistrée un peu plus compressée s'il le faut, pour rester lisible (voir ci-dessous) |
| BMP, GIF, TIFF, images animées | **Triés seulement** : le rognage et les bandeaux sont refusés avec un message, ces formats ne se réenregistrant pas sans perte. Le contenu du fichier compte, pas seulement son extension : un GIF nommé `.jpg` est reconnu |
| RAW (`.cr2`, `.nef`, `.arw`, `.dng`…) | Mis de côté dans `RAW/`, jamais modifiés |
| Vidéo (`.mp4`, `.mov`, `.avi`, `.mkv`…) | Mis de côté dans `Videos/`, jamais traités |

Une image de plus de 8 bits par couleur (PNG 16 bits, HEIC 10 bits) s'affiche
et se censure normalement, et s'enregistre en 8 bits : la différence ne se voit
pas à l'écran.

**HEIC très détaillé.** Le décodeur HEIC installé avec le logiciel ne relit pas
un fichier HEIC dont l'image compressée dépasse 16 Mo. Une photo de 24 ou
48 Mpx très détaillée, réenregistrée en haute qualité, pouvait y arriver, et
devenait « illisible » dans le logiciel (Windows, lui, la lisait). Un gros
fichier est donc relu avant de remplacer l'original, et réenregistré un peu
plus compressé tant qu'il ne se relit pas.

---

## 9 bis. OneDrive et les autres services de synchronisation

Un dossier synchronisé (OneDrive, Google Drive, Dropbox, iCloud) peut **défaire
après coup le rangement d'une photo** : le déplacement réussit, puis, quelques
secondes ou minutes plus tard, le service remet la photo dans le dossier source.
C'est ce qui explique des photos « triées » retrouvées dans le dossier source
après un tri complet, sans aucun message d'erreur.

Le logiciel ne peut pas l'empêcher, mais :

- il vous **prévient** dès l'écran de configuration, à la fin de la
  préparation, et dans le menu, quand le dossier est synchronisé ;
- il **retient dans quel dossier vous avez rangé chaque photo**. À l'ouverture
  du tri, et quand vous repassez les photos restantes depuis l'écran de fin, il
  repère les photos revenues dans le dossier source, vous en donne la liste, et
  propose de les **remettre dans leur dossier** (« Non » les laisse à trier) ;
- une photo présente en double, identique, dans le dossier source et dans son
  dossier de tri, est dédoublonnée sans perte ; si les deux fichiers diffèrent,
  rien n'est touché.

**Le plus sûr est de suspendre la synchronisation le temps du tri** : icône
OneDrive dans la barre des tâches → roue dentée → « Suspendre la
synchronisation ». Ou de trier dans un dossier non synchronisé, puis de
déplacer le résultat dans OneDrive.

---

## 10. Organisation du code

| Fichier | Responsabilité |
|---|---|
| `main.py` | Lancement, écran d'accueil, chargement du reste en arrière-plan |
| `menu.py` | Menu principal d'un événement |
| `renommage.py` | Formats de nom des photos, renommage en deux passes |
| `renommage_evenement.py` | Renommage des photos d'un événement déjà commencé |
| `choix_renommage.py` | Liste des formats de nom, avec exemple |
| `fin_de_session.py` | Fin de la session : tri définitif, dossiers vides supprimés |
| `attente.py` | Fenêtre d'attente des travaux longs (préparation, renommage) |
| `statistiques.py` | Statistiques de la fenêtre de tri : compteurs, rythme, temps restant |
| `configuration.py` | Écran de configuration d'un nouvel événement |
| `dossiers_tri.py` | Dossiers de tri : valeurs par défaut, règles des noms et des touches |
| `editeur_dossiers.py` | Saisie des dossiers de tri (lignes nom + touche), boîte de la touche N |
| `gestion_dossiers.py` | Gestion des dossiers de tri d'un événement commencé |
| `preferences.py` | Ce qui est retenu d'une ouverture à l'autre |
| `preparation.py` | Création des dossiers, renommage, mise à l'écart RAW/vidéo |
| `tri.py` | Tri : lance la fenêtre de rangement sur le dossier source |
| `remise_en_place.py` | Photos rangées revenues dans le dossier source |
| `synchronisation.py` | Reconnaît un dossier OneDrive, Google Drive, Dropbox, iCloud |
| `touches.py` | Touches réservées, touches de tri sur un clavier AZERTY |
| `fichiers.py` | Déplacer, renommer, remplacer, en réessayant quand Windows refuse |
| `ecritures.py` | Enregistrement des photos modifiées en arrière-plan |
| `revue.py` | Revue : lance la fenêtre de rangement sur un dossier de tri ou une copie |
| `rangement.py` | La fenêtre unique : clavier, déplacements, retouches, mode barrer, navigation, annulation |
| `visionneuse.py` | Affichage d'une photo : zoom, vue, rotation, cadre de rognage par les bords, relais des clics |
| `rognage.py` | Écriture d'une photo rognée sur le disque |
| `retouches.py` | Écriture des bandeaux et de la rotation dans la photo |
| `censure.py` | Mode barrer : pose et retouche des bandeaux à la souris |
| `bandeaux.py` | Géométrie du bandeau : inclinaison, poignées, dessin aux bords lisses |
| `selection.py` | Habillage du bandeau choisi : contour et poignées, tracés lissés |
| `visages.py` | Détection des visages et des yeux |
| `images.py` | Lecture, orientation, enregistrement, chargement anticipé |
| `suivi.py` | Fichier de suivi : enregistrement et reprise |
| `dossiers.py` | Choix d'un dossier, noms valides, liste des photos, duplication |
| `polices.py` | Police de caractères du système, la même partout |
| `theme.py` | Couleurs et styles communs à toutes les fenêtres |
| `modeles/` | Modèle de détection livré avec le programme |
| `demarrer.py` | Installation automatique des bibliothèques, puis lancement |
| `lancer.bat`, `lancer.command`, `lancer.sh` | Lancement par double-clic sous Windows, macOS et Linux |
| `verifier_installation.py` | Contrôle que l'installation est fonctionnelle |
| `tester_bandeau.py` | Vérifie que le bandeau couvre les yeux, et rien de plus |
| `tester_rognage.py` | Vérifie la géométrie du cadre de rognage, rotations comprises |
| `tester_rangement.py` | Vérifie la préparation, les formats de nom, le tri, l'annulation photo par photo, les statistiques, la fin de session, les fichiers bloqués, les bandeaux à la souris |
| `tester_formats.py` | Vérifie le réenregistrement de chaque format d'image |

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

**J'ai pivoté une photo, mais le fichier n'a pas changé.**
La rotation n'est enregistrée que par **Entrée** ou par une **touche de tri**.
Espace et les flèches l'abandonnent, pour qu'une rotation faite seulement pour
mieux voir ne modifie pas la photo.

**J'ai validé une photo par erreur.**
Appuyez sur Retour arrière : la photo d'origine est restaurée. Si vous êtes
déjà passé à autre chose, revenez sur la photo avec la flèche gauche (ou en
mode revue), puis appuyez sur Retour arrière. C'est possible même après avoir
fermé le logiciel, tant que vous n'avez pas cliqué sur « Terminer la session ».

**Je veux réunir les photos triées sur deux ordinateurs.**
Au format « Date, heure et code » (le format par défaut), aucun nom ne se
répète : copiez simplement les dossiers de l'un dans ceux de l'autre. Pour des
événements déjà triés au format « Numéros », cliquez d'abord sur « Renommer les
photos » dans le menu de chacun, et choisissez « Date, heure et code ».

**Le logiciel met longtemps à s'ouvrir.**
Passez par `lancer.bat`, `lancer.command` ou `lancer.sh` : une fois
l'installation faite, ils ouvrent directement le logiciel. Le tout premier
lancement après un redémarrage de l'ordinateur reste un peu plus long, le
temps que le système relise les bibliothèques sur le disque.

**Windows refuse de déplacer mon dossier : « un fichier ou dossier est ouvert ».**
Cela veut dire que le logiciel tourne encore. Tant qu'il lit des photos en
arrière-plan, Windows considère le dossier comme ouvert. Fermez le logiciel par
le bouton **Quitter** du menu (ou sa croix de fermeture) : le programme relâche
alors tous les fichiers et se termine pour de bon. Si un message d'erreur
inattendu apparaît, fermez-le puis quittez normalement : le menu revient à
l'écran.

**Le bandeau ne suit pas une tête très penchée.**
C'était un défaut de la détection, corrigé : sur les petits visages surtout,
elle plaçait les yeux presque à l'horizontale quelle que soit la tête.
Mesuré sur de vraies photos, les yeux sont désormais entièrement couverts dans
94 à 95 % des cas jusqu'à 70° d'inclinaison, contre 0 à 36 % auparavant. Pour
les cas restants, tirez la poignée bleue pour incliner le bandeau.

**Le bandeau disparaît quand j'essaie de le retoucher.**
C'était un défaut, corrigé : un simple clic ne retire plus jamais un bandeau,
il le choisit. Seul le **double-clic** en retire un.

**Le bandeau laisse voir un bout d'œil sur certaines photos.**
Son épaisseur est au plus juste, pour ne pas couvrir le front. Cliquez sur le
bandeau, puis tirez la poignée du haut ou du bas pour l'épaissir sur cette
photo-là. Si le cas se répète, la valeur générale se règle dans `bandeaux.py`
(`FACTEUR_EPAISSEUR`) ; `python tester_bandeau.py` dit aussitôt si la nouvelle
valeur couvre encore tous les yeux.

**Des photos que j'avais triées sont revenues dans le dossier source.**
C'est presque toujours la synchronisation (OneDrive…) qui a défait leur
déplacement : voir la section 9 bis. Ouvrez « Trier » : le logiciel les
repère et propose de les remettre dans leur dossier. Pour l'éviter, suspendez
la synchronisation pendant le tri.

**Mes touches 1, 2, 3 ne rangent rien.**
Sur un clavier AZERTY, elles fonctionnent désormais avec ou sans Majuscule. Si
le problème persiste, vérifiez que la fenêtre de tri a bien le clavier (cliquez
une fois sur la photo) et que la touche est bien celle d'un dossier de tri : la
barre du bas les rappelle.

**Puis-je récupérer une photo mise dans « À supprimer » ?**
Oui : le logiciel ne supprime jamais aucun fichier. Il ne fait que les déplacer.
Le dossier « À supprimer » est un dossier comme les autres, que vous videz
vous-même si vous le souhaitez.
