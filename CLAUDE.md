# CLAUDE.md — Règles du projet

Logiciel de bureau de **tri** et de **censure des yeux** sur des photos.
Ce fichier fait autorité pour toute contribution au code. Les références entre
crochets renvoient aux sections du cahier des charges
(`cahier_des_charges_photo_sorter.md`).

---

## 1. Nature du logiciel

Outil **personnel de bureau**, lancé à la main depuis un environnement de
développement (`python main.py`). Ce n'est ni un site web, ni une application
mobile, ni une application à installer via une boutique. [3]

Il rend deux services **successifs et bien distincts** [4] :

1. **Le tri** — les photos brutes défilent une par une en grand ; une touche du
   clavier range chaque photo dans l'un de **quatre** dossiers de tri.
2. **La censure des yeux** — plus tard, sur **un seul** dossier de tri choisi
   par l'utilisateur : un clic pose un bandeau noir sur les yeux d'une personne,
   la validation incruste les bandeaux et réenregistre la photo sur place.

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

## 3. Règle de style : la clarté prime [3]

- Le code doit être **simple, lisible et facile à suivre par une personne qui
  n'est pas experte**.
- **La simplicité et la clarté priment sur la concision** : mieux vaut un code
  un peu plus long mais compréhensible qu'un code court mais obscur.
- Éviter toute complexité inutile : pas d'abstraction anticipée, pas de
  métaprogrammation, pas de motif de conception introduit « au cas où ».
- Noms de variables et de fonctions explicites, en français ou en anglais mais
  de façon cohérente dans tout le projet.
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
  l'événement** [10].
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
  de débit et une panne possible, contre 0,06 s par photo en local.

Si le sujet est rouvert un jour, la seule piste à considérer serait un modèle
local plus lourd (InsightFace / SCRFD), **pas** une API distante.

## 5. Exclusions de périmètre [3]

Les éléments suivants **ne font pas partie du logiciel** et ne doivent pas être
implémentés :

- ❌ **Gestion multi-utilisateur** (comptes, profils, droits, authentification).
- ❌ **Traitement de plusieurs événements simultanés.**
- ❌ **Toute retouche d'image** autre que la pose de bandeaux noirs sur les yeux
  (pas de recadrage, de filtre, de correction de couleur, de compression
  volontaire, de flou, de pixellisation, de redimensionnement du fichier
  enregistré).
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
- **Zoom et rotation à l'étape de tri sont purement visuels** : ils ne modifient
  jamais le fichier, qui est déplacé tel quel. [8.1]
- **Renommage** : numérotation continue `1, 2, 3…` **sans zéros devant**,
  extension d'origine conservée, dans l'ordre de la **date de création** (à
  défaut, date de modification). Procéder **en deux passes** (noms temporaires
  puis noms définitifs) pour éviter les collisions. [7.2]
- **Dossiers `RAW/` et `Videos/` créés uniquement si de tels fichiers
  existent.** [7.1]
- **La préparation automatique ne se rejoue jamais** à la reprise d'un événement
  existant. [5, 10]
- **Rien n'est écrit sur le disque tant que la photo n'est pas validée** à
  l'étape de censure : les bandeaux sont provisoires à l'écran. [9.3]
- **Réenregistrement dans le format d'origine** : un JPEG reste JPEG, un PNG
  reste PNG, un HEIC reste HEIC ; le fichier existant est **remplacé sur
  place**, la photo n'est pas déplacée. [9.5]
- **Remettre la photo dans le bon sens (EXIF) avant** d'incruster les bandeaux,
  afin qu'ils soient enregistrés exactement là où l'utilisateur les a placés à
  l'écran. [9.5]
- **Le bandeau épouse l'inclinaison de la tête** : il s'aligne sur la ligne
  joignant les deux yeux, il n'est pas systématiquement horizontal. [9.3]
- **Comportement de bascule** : un second clic sur la même personne retire le
  bandeau. Chaque personne est indépendante des autres. [9.3]
- **Copie de sauvegarde avant modification** : à la censure, une copie intacte
  est conservée dans un dossier temporaire avant d'écrire, pour permettre
  l'annulation ; ce dossier est vidé à la fermeture. **Aucune photo d'origine ne
  doit être perdue en cours de session.** [9.6]
- **Le fichier de suivi est mis à jour à chaque action** de l'utilisateur
  (rangement, passage, pose de bandeau, annulation). [10]
- **Échap enregistre l'avancement puis ferme proprement.** [8.2, 9.5]

---

## 7. Fluidité [11.1]

Le passage d'une photo à l'autre doit être **instantané**. Les photos suivantes
sont **chargées à l'avance en arrière-plan** (lecture et redimensionnement)
pendant que l'utilisateur regarde la photo courante. Le même principe peut être
appliqué aux résultats de la détection de visages.

L'interface Tkinter ne doit **jamais être bloquée** par une lecture de fichier
ou une détection de visages.

---

## 8. Formats de fichiers [11.2]

| Type | Traitement |
|---|---|
| JPEG, PNG | Triés **et** censurés. |
| HEIC | Traités normalement : lus et réenregistrés dans leur format. |
| RAW (`.cr2`, `.nef`, `.arw`, `.dng`) | Mis de côté dans `RAW/`, jamais modifiés. |
| Vidéo (`.mp4`, `.mov`, `.avi`, `.mkv`) | Mis de côté dans `Videos/`, jamais traités. |

---

## 9. Livrables attendus [12]

1. Le programme complet, lançable par une commande simple.
2. `requirements.txt` avec les bibliothèques et leurs versions.
3. Un code en fichiers courts et lisibles, commentés aux endroits utiles.
4. Un document d'accompagnement : installation, lancement, et récapitulatif de
   **toutes les commandes clavier de chaque étape**.
