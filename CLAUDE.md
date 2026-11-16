# CLAUDE.md — Règles du projet

Logiciel de bureau de **tri** et de **censure des yeux** sur des photos.
Ce fichier fait autorité pour toute contribution au code. Les références entre
crochets renvoient aux sections du cahier des charges
(`cahier_des_charges_photo_sorter.md`).

---

## 1. Nature du logiciel

Outil **personnel de bureau**, lancé par un double-clic sur `lancer.bat`
(Windows), `lancer.command` (macOS) ou `lancer.sh` (Linux) — ou à la main par
`python demarrer.py`, voire `python main.py` quand tout est déjà installé. Ce
n'est ni un site web, ni une application mobile, ni une application à installer
via une boutique. [3]

Il rend deux services [4] :

1. **Le tri** — les photos brutes défilent une par une en grand ; une touche du
   clavier range chaque photo dans l'un des dossiers de tri. **Leur nombre est
   libre, de 1 à 12** (décision de l'utilisateur, 26 octobre 2026 ; il en
   fallait exactement quatre auparavant).
2. **La censure des yeux** — un clic pose un bandeau noir sur les yeux d'une
   personne, la validation incruste les bandeaux et réenregistre la photo.

S'y ajoute un **mode revue** (ajouté par décision de l'utilisateur, 13 septembre
2026) : on repasse les photos de l'un des dossiers de tri, et la touche d'un
autre dossier y déplace aussitôt une photo mal rangée.

**Le dossier des photos devient le dossier de l'événement** (décision de
l'utilisateur, 26 octobre 2026) : il est renommé du nom de l'événement, et les
dossiers de tri, `RAW/`, `Videos/` et `suivi.json` sont créés directement
dedans. Auparavant, l'événement était un sous-dossier supplémentaire, à son
nom, placé dans le dossier des photos ; ces événements (suivi « version 1 »)
se reprennent toujours, sans changer d'organisation (`Suivi.dossier_source`).

**Une seule fenêtre pour tout** (décision de l'utilisateur, 5 octobre 2026) : le
cahier des charges séparait le tri et la censure en deux étapes successives ;
ils sont désormais réunis dans `rangement.py`. La censure est le **mode
barrer**, activé et désactivé par la touche **Tab**, et **retenu** d'une photo
et d'une session à l'autre (`mode_barrer` dans le suivi). Tri et revue ne
diffèrent que par le dossier d'origine ; une copie faite depuis le menu se
revoit aussi, mais sans touches de tri (ses photos n'en sortent pas). Le menu
de l'événement est dans `menu.py`.

**Le rognage se fait en réduisant les bords** (décision de l'utilisateur,
16 octobre 2026), comme sur un téléphone : à l'ouverture, le cadre épouse la
photo entière, et l'on tire l'un de ses quatre bords, l'un de ses quatre coins,
ou le cadre entier. Il fallait auparavant tracer un rectangle à la souris, ce
qui obligeait à tout recommencer dès qu'on le plaçait mal, et ne permettait pas
de ne retirer qu'une bande d'un seul côté.

**Cinq décisions de l'utilisateur, 16 novembre 2026 :**

1. **Le nom des photos se choisit** (`renommage.py`) : « date, heure et code »
   par défaut (`2026-08-24_14-03-27_K7F2.jpg`), « date et heure », « numéros »
   (le seul format auparavant), « nom de l'événement et numéro », ou **aucun
   renommage**. But : que deux tris faits sur deux ordinateurs se réunissent
   sans qu'un nom se répète, tout en restant classés de la plus ancienne à la
   plus récente quand on trie par nom. Le format se change après coup depuis
   le menu (`renommage_evenement.py`).
2. **Tout reste annulable jusqu'à « Terminer la session »** (`fin_de_session.py`) :
   l'historique et les copies intactes sont gardés d'une session à l'autre.
   Le bouton du menu rend le tri définitif.
3. **Retour arrière annule ce qu'on a fait à la photo sur laquelle on est
   revenu**, et plus seulement la dernière action (`rangement._action_a_annuler`).
4. **Les dossiers vides sont supprimés quand la session est terminée**, et
   seulement alors.
5. **Statistiques en temps réel** au bas de la fenêtre de tri, et **démarrage
   rapide** (section 7).

Volume visé : jusqu'à environ **3 000 photos** par session, sans perte de
fluidité. [1]

---

## 2. Pile technique

| Besoin | Bibliothèque |
|---|---|
| Langage | **Python 3.11 ou supérieur** (vérifié sous 3.14.6) |
| Interface graphique | **Tkinter** (fourni d'origine avec Python) |
| Manipulation des images | **Pillow** |
| Lecture/écriture HEIC | **pillow-heif** |
| Détection visages et yeux | **OpenCV — `cv2.FaceDetectorYN` (YuNet)** |

Ne pas introduire d'autre dépendance sans nécessité démontrée.

### Détection de visages : YuNet remplace mediapipe

Le cahier des charges recommandait mediapipe [11.3], tout en autorisant « une
bibliothèque équivalente si elle offre le même résultat et la même simplicité ».
**YuNet a été retenu à sa place, sur la base de mesures.**

Deux raisons, dans cet ordre :

**1. mediapipe ne voit pas les visages éloignés.** Son détecteur (BlazeFace
*short range*) est conçu pour des visages proches, type selfie. Mesures sur des
photos de groupe réelles (1920 px de large) :

| Photo | mediapipe BlazeFace | mediapipe FaceLandmarker | **YuNet** |
|---|---|---|---|
| Foule, visages au fond | **0** | **0** | **62** |
| Réunion, personnes en arrière-plan | **0** | **0** | **29** |
| Groupe rapproché (4 personnes) | 4 | 3 | 4 |

Sur les photos de groupe, mediapipe ne détecte **rien du tout**. YuNet descend
jusqu'à des visages de **10 à 25 px de large**, et conserve 45 détections sur 52
sur une version fortement sous-exposée de la même photo.

**2. mediapipe 1.x a supprimé l'API `mp.solutions`.** Seule subsiste l'API
`mediapipe.tasks`, plus lourde à mettre en œuvre. Vérifié également en
mediapipe 0.10.35 et en Python 3.12 : l'ancienne API a disparu partout.

YuNet est par ailleurs plus léger : **modèle de 233 Ko** (contre 3,7 Mo), et
OpenCV suffit là où mediapipe imposait 17 paquets supplémentaires.

### Règles d'usage de YuNet

- Le modèle `modeles/face_detection_yunet_2023mar.onnx` est **versionné dans le
  dépôt** et chargé depuis le disque.
- **Seuil de confiance : 0,5.** Choix délibérément bas. Une détection en trop ne
  coûte rien — **rien n'est dessiné tant que l'utilisateur n'a pas cliqué**
  [9.3] — alors qu'un visage manqué oblige à poser un bandeau à la main [9.4].
  Dans ce logiciel, **mieux vaut trop détecter que pas assez.**
- `FaceDetectorYN` exige que la **taille d'entrée corresponde à celle de
  l'image** (`setInputSize`) : la redéfinir à chaque changement de photo.
- YuNet renvoie par visage : boîte (4 valeurs), puis **5 points — œil droit, œil
  gauche, nez, coin droit et coin gauche de la bouche** — puis le score. Les
  deux premiers points donnent directement l'axe du bandeau.
- **Ne pas appliquer de CLAHE ni de correction de luminosité avant détection** :
  mesuré, le gain est nul voire négatif.
- **YuNet place mal les yeux d'une tête penchée** (constaté par l'utilisateur,
  octobre 2026) : il les met presque à l'horizontale, d'autant plus que le
  visage est petit (il ne rend que 20 % de l'inclinaison réelle sous 100 px de
  haut), et ne voit plus du tout une tête penchée au-delà d'environ 40°.
  `visages.py` y remédie en deux temps, sans changer le seuil :
  1. **passes tournées** : la photo est aussi parcourue tournée de ±45°, à
     demi-résolution ; un visage trouvé seulement ainsi n'est gardé que si
     YuNet le retrouve une fois la tête redressée ;
  2. **redressement** : chaque visage d'au moins 12 px entre les yeux est
     découpé, mis à 80 px entre les yeux et tourné pour que la tête soit
     droite, puis détecté de nouveau (au plus 3 fois, jusqu'à moins de 1°).
  Mesuré sur 23 photos réelles (98 visages de référence, tournées de −90° à
  +90°) : yeux entièrement couverts dans 94 à 95 % des cas de 0 à 70°, 81 %
  au-delà (contre 0 à 36 % et 0 % avant), aucun visage perdu sur des foules
  de 126 et 424 personnes. Coût : 0,15 s par photo en médiane (0,05 s avant),
  en arrière-plan. Les visages de la photo droite ne s'éliminent jamais entre
  eux.
- **Rattachement d'un clic à un visage** (`visage_le_plus_proche`) : sont
  candidats les visages dont la boîte, élargie d'un quart, contient le clic ;
  on retient celui dont le milieu des yeux est le plus proche, en tailles de
  visage. Hors de tout candidat, bandeau manuel. L'ancienne règle (le plus
  petit visage contenant le clic, ou tout visage à moins d'une taille de son
  centre) posait le bandeau sur le mauvais visage, ou sur une voisine
  détectée quand on visait une personne non détectée. Un visage retrouvé sur
  une image tournée garde une boîte droite **de sa taille propre**, centrée au
  même endroit : le rectangle englobant la boîte penchée, 1,4 fois plus grand
  à 45°, captait les clics autour de la tête.

## 3. Règle de style : la clarté prime [3]

- Le code doit être **simple, lisible et facile à suivre par une personne qui
  n'est pas experte**.
- **La simplicité et la clarté priment sur la concision** : mieux vaut un code
  un peu plus long mais compréhensible qu'un code court mais obscur.
- Éviter toute complexité inutile : pas d'abstraction anticipée, pas de
  métaprogrammation, pas de motif de conception introduit « au cas où ».
- Noms de variables et de fonctions explicites, en français ou en anglais mais
  de façon cohérente dans tout le projet.
- **Pas d'accents dans les fichiers `.py`**, y compris dans les textes affichés
  (`« Preparation terminee »`) ; les guillemets `« »` et le degré `°` sont en
  revanche admis. Convention suivie par tout le projet depuis l'origine.
- **Toutes les couleurs sont dans `theme.py`**, et nulle part ailleurs. Une
  couleur écrite en dur dans un module d'interface est une erreur : c'est ce
  qui avait fait diverger la fenêtre de tri, sombre, des écrans d'accueil et de
  configuration, restés au gris clair de Tkinter.
- **Commenter obligatoirement les passages non évidents** [11.4] :
  - le rattachement d'un clic au bon visage,
  - le calcul de l'inclinaison et de la forme des bandeaux,
  - la remise des photos dans le bon sens (données d'orientation EXIF).
- Fichiers **courts**, chacun avec **une responsabilité claire**. [11.4]

---

## 4. Contraintes d'architecture [3]

- **Contrainte « hors ligne » levée** par décision de l'utilisateur
  (24 août 2026), au profit de la précision de détection. **En pratique le
  logiciel reste néanmoins 100 % local** : voir section 4 bis, la détection
  locale s'est révélée à la fois plus précise et la seule réellement gratuite au
  volume visé. Aucun appel réseau n'est donc nécessaire à l'exécution.
- **Aucun serveur.** Pas de Flask, FastAPI, Django, ni aucun processus qui
  écoute sur un port.
- **Aucune base de données.** Pas de SQLite, pas d'ORM. L'avancement est
  conservé dans un simple **fichier de suivi placé dans le dossier de
  l'événement** [10]. Ce que le logiciel retient d'une ouverture à l'autre
  (dossiers de tri, format de nom des photos, dernier événement, dossier des
  photos, taille de la fenêtre de tri) tient dans `preferences.json`, à côté du programme
  (`preferences.py`) : jamais indispensable, ignoré s'il est illisible.
- **Un seul utilisateur**, **un seul événement traité à la fois**. Aucune notion
  de compte, de session partagée ou de concurrence entre utilisateurs.

---

## 4 bis. Pourquoi aucune API de reconnaissance en ligne

La question a été tranchée sur mesures et sur tarifs, pas par principe :

- **Ce n'est pas gratuit au volume visé.** Google Cloud Vision offre 1 000
  unités par mois, puis facture 1,50 $ les 1 000 : une session de 3 000 photos
  coûte environ 3 $. Le palier gratuit d'AWS Rekognition est limité aux
  12 premiers mois et aux nouveaux comptes.
- **Ce serait contraire au but du logiciel.** L'objet même de l'outil est la
  **protection de la vie privée** [1]. Téléverser chez un tiers les photos que
  l'on cherche précisément à anonymiser irait à l'encontre du résultat visé.
- **Ce n'est pas plus précis.** YuNet, en local, détecte déjà des visages de
  10 px et fonctionne en photo sous-exposée.
- **Ce serait plus lent et plus fragile** : 3 000 requêtes réseau, des limites
  de débit et une panne possible, contre 0,15 s par photo en local (têtes
  penchées comprises, voir section 2), en arrière-plan.

Si le sujet est rouvert un jour, la seule piste à considérer serait un modèle
local plus lourd (InsightFace / SCRFD), **pas** une API distante.

## 4 ter. Windows, macOS et Linux

Le logiciel doit fonctionner **à l'identique sur les trois systèmes**. Décision
de l'utilisateur (16 septembre 2026). Les règles qui en découlent :

- **Aucun chemin écrit à la main** : toujours `os.path.join`, jamais de `\` ni
  de `/` en dur.
- **Aucune police nommée en dur.** `Segoe UI` n'existe que sous Windows. On
  passe par `polices.police(taille, gras)`, qui reprend la police normale du
  système, quelle qu'elle soit.
- **La molette de la souris** se signale par `<MouseWheel>` sous Windows et
  macOS, mais par les boutons 4 et 5 sous X11 (donc sous Linux) : les trois
  événements doivent être branchés.
- **Les formes de pointeur** ne sont pas toutes connues partout : entourer
  `canvas.config(cursor=...)` d'un `try` et retomber sur le pointeur ordinaire.
- **Le lissage des tracés** ne doit pas dépendre de Tkinter, qui n'en fait pas :
  ce qui doit être lisse est dessiné avec Pillow (voir `selection.py`), donc
  rendu de la même façon partout.
- **L'installation doit être automatique** : `demarrer.py` ne se sert que de ce
  que Python fournit d'origine, de façon à pouvoir s'exécuter avant toute
  installation. Il crée l'environnement, installe les bibliothèques, et
  réessaie sans versions figées si celles-ci n'existent pas pour la plateforme.
- Les fichiers `lancer.*` ne font qu'une chose : trouver un Python assez
  récent, proposer de l'installer s'il n'y en a pas, puis appeler `demarrer.py`.

---

## 5. Exclusions de périmètre [3]

Les éléments suivants **ne font pas partie du logiciel** et ne doivent pas être
implémentés :

- ❌ **Gestion multi-utilisateur** (comptes, profils, droits, authentification).
- ❌ **Traitement de plusieurs événements simultanés.**
- ❌ **Toute retouche d'image** autre que la pose de bandeaux noirs sur les yeux
  et le **rognage** (pas de filtre, de correction de couleur, de compression
  volontaire, de flou, de pixellisation, de redimensionnement du fichier
  enregistré). Le rognage, exclu par le cahier des charges, a été **ajouté par
  décision de l'utilisateur** (13 septembre 2026), à l'étape de tri et en mode
  revue uniquement.
- ❌ **Tout traitement des fichiers RAW ou vidéo** autre que leur mise à l'écart
  dans les dossiers `RAW/` et `Videos/`. Une fois déplacés, le logiciel n'y
  touche plus.
- ❌ **Toute fonction de partage ou d'envoi** : réseaux sociaux, cloud, courriel,
  export vers un service tiers.

---

## 6. Règles métier à ne pas enfreindre

- **Le tri déplace, il ne copie pas.** La photo rangée quitte la racine du
  dossier source. [8.2]
- **La barre d'espace ne range rien** : la photo passée reste dans le dossier
  source. [8.2]
- **On ne range pas une photo qu'on n'a pas vue** : une touche de tri pressée
  pendant « Chargement... » est ignorée. Une touche maintenue enfoncée, ou un
  disque lent, rangeaient sinon des photos jamais affichées.
- **Le zoom est purement visuel**. **La rotation peut être enregistrée**
  (décision de l'utilisateur, 5 octobre 2026, à la place de la règle [8.1]) :
  comme les bandeaux, elle reste provisoire jusqu'à **Entrée** (enregistrer
  puis suivante) ou une **touche de tri** (enregistrer puis ranger). Espace,
  flèches et Échap l'abandonnent. Les bandeaux sont mémorisés dans le repère de
  la photo non pivotée : ils sont incrustés d'abord, la photo est pivotée
  ensuite (`retouches.py`), par quart de tour exact, sans recalcul de pixels.
- **Le tri ne présente que les photos encore dans le dossier source**
  (décision de l'utilisateur, 16 octobre 2026) : la liste est refaite à chaque
  ouverture à partir de la racine du dossier source (`tri.preparer_tri`). Les
  photos rangées pendant la session restent dans la liste, pour la flèche
  gauche ; celles d'une session précédente se retrouvent en mode revue.
- **Annulation** (décision de l'utilisateur, 16 novembre 2026). Un seul
  historique pour le tri et la revue (`Suivi.historique`), gardé d'une session
  à l'autre. Retour arrière choisit son action ainsi (`_action_a_annuler`) :
  si l'utilisateur est **arrivé de lui-même** sur la photo affichée (flèches,
  ouverture de la fenêtre) et qu'elle a des actions, la plus récente de
  **cette photo** ; sinon la dernière action **de la session**. Ne pas
  simplifier en « toujours la photo affichée » : après un rangement fait par
  erreur, la photo suivante est à l'écran, et Retour arrière retirerait les
  bandeaux qu'elle a reçus la veille au lieu de ramener la photo rangée. Le
  rappel des touches dit toujours ce qui sera annulé. Une action désigne sa
  photo par son **nom**, jamais par sa position dans la liste, et sa copie
  intacte par le **nom du fichier de sauvegarde**, jamais par un chemin
  complet (le dossier de l'événement peut être déplacé entre deux sessions).
  Les retouches d'une copie faite depuis le menu ne se mélangent pas à celles
  de la photo d'origine, qui porte le même nom.
- **Fin de session** (`fin_de_session.py`) : seul le bouton « Terminer la
  session » du menu efface les copies intactes et vide l'historique, après
  confirmation ; **rien d'autre ne doit le faire**, pas même la fermeture. Il
  supprime aussi les dossiers vides (tri, `RAW`, `Videos`), qui restent dans
  la liste de l'événement et sont recréés au premier rangement. Un dossier
  qui ne contient que `.DS_Store`, `Thumbs.db`, `desktop.ini` ou des `._…`
  est vide ; la suppression passe par `os.rmdir`, qui ne peut rien effacer
  d'autre.
- **Statistiques** au bas de la fenêtre (`statistiques.py`) : à trier, rangées (nombre et
  pourcentage), nombre de photos de chaque dossier à côté de sa touche,
  rythme et temps restant après cinq rangements (une pause compte pour une
  minute au plus), actions annulables. Les compteurs sont lus sur le disque à
  l'ouverture, à la touche N et à l'écran de fin, et suivent chaque
  rangement entre-temps : relire les dossiers à chaque touche ralentirait le
  tri sur un disque lent.
- **Aucun objet Tkinter ne doit être détruit hors du fil principal.** Tkinter
  n'obéit qu'au fil principal : un fil d'arrière-plan qui détruit une image ou
  une variable Tkinter (via le ramasse-miettes) reste bloqué plus d'une
  seconde, et, s'il lisait une photo, la garde ouverte, ce qui empêche Windows
  de la déplacer (mesuré : deux collectes automatiques sur sept tombaient sur
  un fil d'arrière-plan, et une boîte de saisie fermée suffisait à faire
  échouer un rangement). D'où **le ramasse-miettes automatique coupé au
  démarrage** (`gc.disable()` dans `main.main`) et remplacé par une collecte
  toutes les deux secondes sur le fil principal (`ramasser_les_miettes`),
  ainsi que la libération des images dans `Visionneuse.arreter`. Ne jamais
  réactiver le ramasse-miettes automatique. Les déplacements passent par
  `fichiers.deplacer_fichier` (simple renommage), jamais par `shutil.move`, qui
  laissait la photo en double quand le déplacement échouait à mi-chemin.
  Toutes les opérations de `fichiers.py` réessaient deux secondes quand
  Windows refuse (fichier lu par un autre fil, l'antivirus, OneDrive), et
  `deplacer_fichier` refuse une destination déjà prise **sur les trois
  systèmes** (`os.rename` écrase sans rien dire sous macOS et Linux).
- **Photos revenues dans le dossier source** (problème constaté sur un dossier
  OneDrive, octobre 2026 : des photos rangées se retrouvaient dans le dossier
  source, sans aucune erreur ; la synchronisation avait défait leur
  déplacement après coup). Le suivi retient le dossier choisi pour chaque photo
  (`Suivi.rangements`, mis à jour à chaque rangement et annulation) ; une photo
  rangée retrouvée à la racine du dossier source est signalée à l'ouverture du
  tri et à l'écran de fin, avec la proposition de la remettre en place
  (`remise_en_place.py`). Un dossier synchronisé est signalé à la
  configuration, à la fin de la préparation et dans le menu
  (`synchronisation.py`), avec le conseil de suspendre la synchronisation.
- **L'écran de fin du tri dit combien de photos restent** dans le dossier
  source ; Entrée les fait repasser aussitôt (une nouvelle fenêtre s'ouvre sur
  la liste refaite, voir `tri.lancer_tri`).
- **Un fichier bloqué n'interrompt jamais une action à mi-chemin** (fichiers
  tenus par OneDrive ou l'antivirus, constaté par les essais) :
  - le suivi qui ne s'enregistre pas ne fait que prévenir, une fois
    (`_noter_avancement`) ; l'écran est mis à jour avant l'enregistrement.
    Auparavant, l'erreur laissait l'écran sur une photo alors que la position
    désignait la suivante, et la touche d'après rangeait une photo jamais vue :
    l'un des chemins qui laissaient des photos dans le dossier source ;
  - **l'annulation ne retire l'action de l'historique qu'une fois faite** ;
    un échec prévient et laisse l'action en place, et un nouvel appui reprend
    où l'on s'était arrêté (`ramenee`). La copie intacte est remise avant
    d'effacer la version sans barre. Après un échec à mi-chemin, l'écran et le
    suivi sont remis à jour, et fermer la fenêtre termine l'annulation tant
    que la copie intacte existe ;
  - **un enregistrement en arrière-plan raté fait reprendre la photo
    affichée telle qu'elle est sur le disque** (`_traiter_les_echecs`) : après
    un rognage raté, l'écran gardait la photo rognée, et un bandeau posé sur
    des yeux tombait à côté d'eux dans le fichier. L'action qui attendait cet
    enregistrement est abandonnée ;
  - un rangement est inscrit dans l'historique dès que la photo a bougé ;
    une copie de sauvegarde ou une version sans barre impossible à faire
    prévient sans laisser d'état à moitié fait ;
  - Échap ferme la fenêtre même si le suivi ne s'enregistre pas, et une
    fenêtre à moitié construite est refermée avec ses fils.
- **La fenêtre ne se fige jamais en attendant un enregistrement** : ranger,
  annuler, rogner ou valider une photo encore en cours d'enregistrement (un
  HEIC prend 3 à 4 s), ou fermer la fenêtre, revient voir toutes les 50 ms
  (`_attendre_les_enregistrements`, `_finir_de_quitter`) ; les touches sont
  ignorées d'ici là. N'appeler `ecritures.attendre()` depuis la fenêtre que
  pour une attente forcément brève.
- **Les flèches gauche et droite ne font que naviguer**, dans toutes les étapes :
  elles ne déplacent, ne modifient ni n'enregistrent aucune photo (seule la
  position est notée dans le suivi). Au tri et en revue, une photo déjà rangée
  est montrée depuis le dossier où elle se trouve ; une touche de tri la déplace
  de là vers le nouveau dossier.
- **Rognage** : rien n'est écrit avant la validation (Entrée). Le cadre **part
  des quatre bords de la photo** et se réduit en tirant un bord, un coin ou le
  cadre entier ; tant qu'il n'a pas bougé, Entrée ne réenregistre rien et sort
  simplement du mode. Il s'applique à la photo remise dans le bon sens (EXIF)
  puis éventuellement pivotée ; le rognage est enregistré dans le sens
  d'origine, et la rotation reste en attente, comme les bandeaux, qui suivent le
  nouveau cadrage. Mêmes garanties qu'à la censure : copie de sauvegarde,
  réenregistrement dans le format d'origine, annulation par Retour arrière.
  Pendant le rognage, **seules Entrée, Échap et C agissent** ; la photo est
  montrée entière, avec une marge tout autour pour que ses bords restent
  saisissables à la souris.
- **Mode revue** : ne revoit et ne déplace que vers les dossiers de tri ;
  la touche du dossier revu laisse la photo en place. **Aucun déplacement
  n'écrase un fichier** portant déjà le même nom.
- **Dossiers de tri** (décision de l'utilisateur, 26 octobre 2026) : de 1 à 12,
  ajoutés ou retirés à la configuration (`editeur_dossiers.py`), avec les
  mêmes règles partout (`dossiers_tri.py`) : noms valides sur les trois
  systèmes (pas de `CON`, `NUL`… ni de point final), distincts, différents des
  dossiers du logiciel (`RAW`, `Videos`, `Sans-barre`,
  `_sauvegardes_temporaires`) ; touches d'un caractère, distinctes, différentes
  des touches réservées **R, C et N**. **La liste est retenue** d'une ouverture à
  l'autre (`preferences.py`).
- **Touche N pendant le tri et la revue** : crée un nouveau dossier de tri (nom
  et touche demandés), ajouté à l'événement et retenu pour les prochains. La
  photo affichée **ne bouge pas** : on la range ensuite avec la touche du
  nouveau dossier (choix de l'utilisateur). Un événement plus ancien dont un
  dossier se range par N garde ce comportement.
- **Gestion des dossiers depuis le menu** : renommer (sur le disque, et partout
  où le suivi cite le dossier), changer de touche, ajouter, retirer. **Un
  dossier qui contient encore des fichiers ne peut pas être retiré** (choix de
  l'utilisateur) ; retiré, un dossier vide est supprimé du disque. Échanger
  deux noms d'un coup est refusé : il faut passer par un nom provisoire.
- **Touches de tri sur un clavier AZERTY** : la rangée des chiffres donne
  `& é " '…` sans Majuscule. Une touche de tri « 1 » répond aussi à la touche
  marquée 1 sans Majuscule (`touches.py`) ; le caractère exact reste
  prioritaire.
- **Bords du bandeau lissés** (suréchantillonnage ×4 puis réduction) : un bandeau
  incliné ne doit pas présenter de marches d'escalier. L'intérieur reste
  entièrement noir, et le rendu à l'écran est identique à celui du fichier.
- **Renommage** : selon le format choisi (`renommage.py`), extension
  d'origine conservée, dans l'**ordre chronologique strict** : le premier nom
  = le fichier le plus ancien par date et heure, le dernier = le plus récent,
  et aucun autre ordre. **Classer par nom doit toujours donner cet ordre** :
  dates écrites année-mois-jour-heure, numéros du format « événement »
  complétés par des zéros, photos d'une même seconde numérotées `-1`, `-2`
  **avant** le code (sans quoi c'est le code qui les classerait). Le format
  « numéros » reste `1, 2, 3…` **sans zéros devant** (règle d'origine [7.2]).
  **Le code** (4 caractères, base32) est tiré de la taille du fichier et de
  ses 64 premiers Ko : identique pour une même photo sur deux ordinateurs,
  différent pour deux photos de la même seconde ; lire le fichier entier
  prendrait des minutes sur 3 000 photos. Dans les formats par date, les
  fichiers d'une même prise de vue (même nom sans l'extension : photo et
  RAW, photo et vidéo) reçoivent le même nom, d'après la date de la photo.
  Un renommage qui échoue en route rend leur ancien nom à tous les fichiers
  (`renommer_en_deux_passes`). « Aucun renommage » saute cette étape ; les
  RAW et vidéos sont quand même mis de côté. Un événement créé avant le choix
  du format est « numéros » (`Suivi.renommage`).
  La date retenue est celle de **prise de vue (EXIF `DateTimeOriginal`)**,
  puis `DateTime` si la première manque ou est illisible (« 0000:00:00… ») ;
  avec son écart au temps universel (`OffsetTimeOriginal`, `OffsetTime`) quand
  l'appareil l'inscrit, pour comparer sans erreur photos et vidéos prises à
  l'étranger ou la nuit du changement d'heure. Une date d'avant 1970, que
  Windows ne sait pas convertir, est ignorée au lieu de bloquer la
  préparation. À défaut seulement, la plus ancienne des dates du fichier (sous
  Windows, la « date de création » est celle de la copie sur le disque et ne
  reflète pas la prise de vue). Égalité : nom d'origine. Procéder **en deux
  passes** (noms temporaires puis noms définitifs) pour éviter les collisions ;
  un sous-dossier qui porterait un nom définitif est signalé avant toute
  passe. [7.2]

  **La numérotation porte sur l'ensemble photos + RAW + vidéos**, et les photos
  à trier gardent donc des trous une fois les RAW et les vidéos mis à l'écart
  (décision de l'utilisateur, 16 octobre 2026, à la place de la numérotation
  continue initialement prévue). C'est voulu : le numéro dit **quand** le
  fichier a été pris, et `2.cr2` se situe ainsi entre `1.jpg` et `3.jpg`, ce
  qui permet de retrouver à quel moment un RAW a été déclenché.

  **Un fichier qui n'est ni une photo, ni un RAW, ni une vidéo n'est jamais
  touché** : il n'est ni renommé, ni déplacé, ni compté dans la numérotation.
  Les fichiers `._…` que macOS ajoute sur les clés et les cartes en font
  partie, malgré leur extension de photo.
- **Dossiers `RAW/` et `Videos/` créés uniquement si de tels fichiers
  existent.** [7.1] S'ils existaient déjà et contiennent un fichier du même
  nom, ou si le fichier est occupé, il reste à la racine et figure au compte
  rendu : rien n'est écrasé, et la préparation va jusqu'au bout.
- **La préparation automatique ne se rejoue jamais** à la reprise d'un événement
  existant. [5, 10] Le suivi est toutefois écrit **avant** elle : une
  préparation interrompue (fichier bloqué, coupure) n'a jamais eu lieu en
  entier, et la reprise propose de la terminer.
- **Renommage du dossier des photos** : s'il est impossible (fichier ouvert,
  synchronisation, racine d'une carte), le tri se fait dans le dossier sous
  son nom actuel, avec un message (choix de l'utilisateur). Un nom déjà pris
  par un dossier voisin est refusé dès l'écran de configuration. Un dossier
  qui appartient à un autre événement (un de ses dossiers de tri) n'est jamais
  renommé, pour ne pas désorganiser cet événement.
- **Rien n'est écrit sur le disque tant que la photo n'est pas validée** (Entrée
  ou touche de tri) : bandeaux et rotation sont provisoires à l'écran. [9.3]
- **Réenregistrement dans le format d'origine** : un JPEG reste JPEG, un PNG
  reste PNG, un HEIC reste HEIC ; le fichier existant est **remplacé sur
  place**. [9.5] Les **données EXIF** (date de prise de vue…) et le **profil de
  couleurs** sont réécrits avec la photo : Pillow les perd sinon. L'étiquette
  d'orientation, elle, a été retirée à la lecture, la photo étant enregistrée
  droite.
- **Remettre la photo dans le bon sens (EXIF) avant** d'incruster les bandeaux,
  afin qu'ils soient enregistrés exactement là où l'utilisateur les a placés à
  l'écran. [9.5]
- **Le bandeau épouse l'inclinaison de la tête** : il s'aligne sur la ligne
  joignant les deux yeux, il n'est pas systématiquement horizontal. [9.3]
- **L'épaisseur du bandeau vaut 0,40 fois l'écart des deux yeux**, et cette
  valeur est justifiée par mesure, non choisie à vue : c'est la plus petite qui
  couvre entièrement les yeux de toutes les morphologies examinées, avec une
  marge d'erreur de repérage de 8 %. Elle valait 0,8, ce qui couvrait
  systématiquement les sourcils et une partie du front. **Toute modification de
  ce facteur doit être accompagnée du résultat de `tester_bandeau.py`**, qui
  échoue si la nouvelle valeur laisse un œil visible ou si une valeur plus
  faible suffirait.
- **Un simple clic ne retire jamais un bandeau.** Il en pose un s'il n'y en a
  pas, sinon il choisit celui qui se trouve sous le pointeur. Seul le
  **double-clic** retire un bandeau. Règle posée par décision de l'utilisateur
  (16 septembre 2026) : le comportement de bascule précédent faisait
  disparaître un bandeau dès qu'on effleurait une de ses poignées, celles-ci
  étant posées sur son bord. Chaque personne reste indépendante des autres.
  [9.3]
- **Tous les bandeaux se retouchent de la même façon**, qu'ils viennent de la
  détection ou d'un clic dans le vide : mêmes poignées, même déplacement, même
  retrait. Le logiciel ne doit jamais traiter les uns autrement que les autres.
- **Un bandeau ne peut pas sortir de la photo** : son centre est ramené dans le
  cadre à chaque déplacement, faute de quoi il disparaîtrait de l'écran sans
  avoir été retiré.
- **Copie de sauvegarde avant modification** : à la censure et au rognage, une
  copie intacte est conservée dans `_sauvegardes_temporaires` avant d'écrire,
  pour permettre l'annulation ; ce dossier n'est vidé que par « Terminer la
  session » (il l'était à chaque fermeture avant le 16 novembre 2026, d'où
  son nom, gardé pour les événements déjà commencés). Chaque copie
  porte un numéro unique, pour qu'une photo modifiée deux fois n'écrase jamais
  sa sauvegarde précédente. **Aucune photo d'origine ne
  doit être perdue en cours de session.** [9.6]
- **Version sans barre** (décision de l'utilisateur, 5 octobre 2026) : quand
  une photo est validée avec des bandeaux, une copie sans bandeaux (même
  rotation) est rangée dans un sous-dossier `Sans-barre/` du dossier où va la
  photo. Elle suit la photo à chaque déplacement, disparaît si l'on annule, et
  n'est jamais écrasée si la photo est barrée de nouveau.
- **Le fichier de suivi est mis à jour à chaque action** de l'utilisateur
  (rangement, passage, validation, rognage, annulation, mode barrer). [10]
  Les bandeaux posés, eux, ne sont que provisoires : rien n'est écrit tant
  que la photo n'est pas validée.
- **Clics et gestes sur les bandeaux** : un clic hors de la photo ne pose
  rien ; un clic fait avant l'arrivée des visages (détection encore en cours)
  pose aussitôt un bandeau manuel, remplacé par celui du visage dès qu'ils
  arrivent (`recevoir_visages`) : une photo validée dans la foulée n'est
  jamais sans bandeau, et le bandeau finit par suivre la tête, sauf si
  l'utilisateur l'a retouché entre-temps, auquel cas il reste où il est ; sur un
  bandeau fin à l'écran (moins de deux fois la zone d'une poignée), sa moitié
  centrale le déplace au lieu de tirer une poignée d'épaisseur, qui
  l'amincissait jusqu'à découvrir les yeux ; un double-clic sur une
  poignée ne retire rien (deux saisies rapides forment un double-clic pour
  Tk) et vaut un appui simple ; un appui en cours est oublié au changement de
  photo ; un rognage oublie les visages sortis du cadre.
- **Échap enregistre l'avancement puis ferme proprement.** [8.2, 9.5]

---

## 7. Fluidité [11.1]

Le passage d'une photo à l'autre doit être **instantané**. Les photos suivantes
sont **chargées à l'avance en arrière-plan** (lecture et redimensionnement)
pendant que l'utilisateur regarde la photo courante. Le même principe peut être
appliqué aux résultats de la détection de visages.

L'interface Tkinter ne doit **jamais être bloquée** par une lecture de fichier
ou une détection de visages.

Mise en œuvre :

- Le chargeur prépare pour chaque photo un **aperçu à la taille de l'écran** ;
  l'affichage part toujours de la plus petite version assez détaillée (aperçu,
  puis photo réduite de moitié en moitié quand on zoome), jamais de la photo
  entière pour une vue d'ensemble.
- Une photo pas encore chargée n'est **pas lue sur le fil principal** : la
  fenêtre affiche « Chargement... » et revient voir quelques millisecondes plus
  tard.
- Les dessins passent par `after_idle` : plusieurs mouvements de souris
  rapprochés ne donnent qu'un seul dessin.
- Les photos modifiées (censure, rognage) sont **enregistrées en arrière-plan**
  (`ecritures.py`). Règle : avant de déplacer, copier ou restaurer un fichier
  depuis la fenêtre, attendre son enregistrement en cours, sans figer la
  fenêtre (voir section 6) ; à la fermeture, attendre tous les
  enregistrements.
- **Démarrage** (demande de l'utilisateur, 16 novembre 2026 : « beaucoup trop
  lent »). Un lancement démarrait Python quatre fois, dont deux chargeaient
  OpenCV. Désormais : les `lancer.*` appellent `demarrer.py` avec le Python de
  `venv/` s'il existe, qui ouvre le logiciel **dans le même processus** ; les
  bibliothèques ne sont plus essayées qu'après un échec (code de sortie 3 =
  environnement à réparer). **`main.py` n'importe en tête que des modules
  légers** (mesuré : 0,04 s au lieu de 0,14 à 0,54 s) : ni Pillow ni OpenCV.
  Le reste est importé par un fil d'arrière-plan une fois l'écran d'accueil
  dessiné, et par des `import` placés dans les fonctions de `main.py`,
  exception assumée à l'usage du projet. Ne pas ajouter d'import lourd en
  tête de `main.py`, `suivi.py`, `preferences.py`, `renommage.py` ou
  `theme.py`.
- **Le chargeur ne relit jamais une photo en cours d'enregistrement** : il
  attend la fin de son écriture (`attendre_ecriture`), sans quoi une photo
  pivotée, sortie du cache puis revue, revenait sans sa rotation. Chaque
  photo a un **numéro de version**, augmenté quand elle est remplacée,
  oubliée ou déplacée : une lecture commencée avant est jetée.
- **Le cache ne garde que ce que le chargeur prépare** : la photo précédente,
  la courante et les trois suivantes. Dix photos entières montaient à 3 Go
  avec des photos de 48 Mpx.
- Une photo est **lue d'un bloc en mémoire** avant d'être décodée : le fichier
  n'est ouvert que 2 ms au lieu de 110 ms, autant de temps pendant lequel
  Windows refusait de le déplacer.
- Les dossiers sont listés avec `os.scandir` : interroger le disque photo par
  photo prenait 0,2 s pour 3 000 photos, à chaque ouverture du tri et du menu.

---

## 8. Formats de fichiers [11.2]

| Type | Traitement |
|---|---|
| JPEG, PNG, WEBP | Triés **et** censurés. |
| HEIC | Traités normalement : lus et réenregistrés dans leur format. |
| BMP, GIF, TIFF | **Triés seulement.** Rognage et bandeaux refusés avec un message. |
| RAW (`.cr2`, `.nef`, `.arw`, `.dng`) | Mis de côté dans `RAW/`, jamais modifiés. |
| Vidéo (`.mp4`, `.mov`, `.avi`, `.mkv`) | Mis de côté dans `Videos/`, jamais traités. |

**Pourquoi BMP, GIF et TIFF sont triés mais pas modifiés** (décision de
l'utilisateur, 16 octobre 2026) : les trier ne touche pas au fichier, donc ne
risque rien ; les réenregistrer les dégraderait, un GIF ne retenant que
256 couleurs et ni l'un ni l'autre ne conservant ses données EXIF à la
réécriture. Plutôt que d'abîmer la photo en silence, le logiciel refuse de la
modifier et le dit. La liste fait foi dans `images.EXTENSIONS_MODIFIABLES`.

`images.est_modifiable` regarde aussi **le contenu** du fichier (son en-tête
seul) : un GIF animé ou un TIFF nommés `.jpg` perdaient, rognés, leurs images
suivantes ou leur date. Les PNG et WEBP animés sont refusés de même. Si le
fichier ne s'ouvre pas à cet instant, l'extension décide. Il n'est appelé
qu'au moment de modifier la photo ; à l'affichage, seule l'extension compte
(`extension_modifiable`) : ouvrir le fichier sur le fil principal forcerait le
téléchargement d'une photo OneDrive « à la demande » et figerait la fenêtre.

Règles du réenregistrement (`images.py`), toutes constatées par les essais :

- **Transparence** : une image avec canal alpha ou couleur transparente
  (PNG à palette, `tRNS`) est travaillée en RGBA. En RGB, une couleur-clé
  noire rendait transparents les bandeaux noirs.
- **Plus de 8 bits par couleur** (PNG 16 bits, HEIC 10 bits) : ramené en
  8 bits, valeurs divisées par 256 ; converti tel quel, un PNG gris 16 bits
  devenait blanc. Choix assumé : la différence ne se voit pas, et la censure
  prime.
- **Profil de couleurs** : celui d'une image CMJN ou en niveaux de gris est
  retiré une fois l'image passée en RGB, qu'il ne décrit plus.
- **WEBP** : sans perte s'il l'était (morceau `VP8L`), qualité 95 sinon ;
  Pillow reencodait tout WEBP avec perte, en qualité 80.
- **MPO** (JPEG à plusieurs vues) : toujours réenregistré en JPEG, première
  vue seulement.
- **HEIC** : le décodeur livré avec pillow-heif (libde265) ne relit pas une
  image compressée de plus de 16 Mio. Un fichier de plus de 15 Mio est donc
  relu avant de remplacer l'original, et réenregistré en qualité 85, 75, 60
  puis 40 tant qu'il ne se relit pas ; sinon l'enregistrement échoue et
  l'original reste intact.

---

## 9. Livrables attendus [12]

1. Le programme complet, lançable par une commande simple.
2. `requirements.txt` avec les bibliothèques et leurs versions.
3. Un code en fichiers courts et lisibles, commentés aux endroits utiles.
4. Un document d'accompagnement : installation, lancement, et récapitulatif de
   **toutes les commandes clavier de chaque étape**.
5. Des lanceurs pour les trois systèmes, et une installation qui se fait seule.
6. Des tests exécutables : `verifier_installation.py` pour l'installation,
   `tester_bandeau.py` pour la géométrie du bandeau, `tester_rognage.py` pour
   celle du cadre de rognage, `tester_rangement.py` pour ce que deviennent
   les fichiers (préparation, formats de nom, tri, annulation photo par
   photo, statistiques, fin de session, fichiers bloqués, chargement,
   bandeaux à la souris, gestion des dossiers) et `tester_formats.py` pour le
   réenregistrement de chaque format. Tous doivent passer avant de livrer.
