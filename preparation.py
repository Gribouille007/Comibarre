"""
Preparation automatique (section 7).

Cette phase s'execute une seule fois, juste apres la configuration, sans aucune
action de l'utilisateur :

1. creation des dossiers de rangement ;
2. renommage de toutes les photos en 1, 2, 3... ;
3. mise a l'ecart des fichiers RAW et video.

Elle n'est jamais rejouee lors de la reprise d'un evenement (sections 5 et 10).
"""

import errno
import os
import time
from datetime import datetime

from PIL import ExifTags, Image

from fichiers import deplacer_fichier
# Importer `images` enregistre aussi le format HEIC aupres de Pillow, ce qui
# permet de lire la date de prise de vue des photos d'iPhone.
from images import est_une_image
from suivi import NOM_FICHIER_SUIVI

# Fichiers bruts des appareils photo reflex et hybrides. Ils ne sont jamais
# modifies : on se contente de les ranger a part.
EXTENSIONS_RAW = {
    ".cr2", ".cr3", ".nef", ".nrw", ".arw", ".srf", ".sr2",
    ".dng", ".orf", ".raf", ".rw2", ".pef", ".raw",
}

EXTENSIONS_VIDEO = {
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".mts", ".m2ts", ".wmv", ".3gp",
}

NOM_DOSSIER_RAW = "RAW"
NOM_DOSSIER_VIDEOS = "Videos"

# Prefixe des noms temporaires utilises pendant le renommage.
PREFIXE_TEMPORAIRE = "_renommage_temporaire_"


def date_de_prise_de_vue_exif(chemin):
    """Date et heure de prise de vue inscrites dans la photo, ou None.

    Les appareils photo et les telephones inscrivent dans chaque photo (donnees
    EXIF) l'instant exact du declenchement, sous la forme « 2026:08:24 14:03:27 ».
    C'est la seule date fiable : elle voyage avec la photo et ne change pas
    quand le fichier est copie d'une carte memoire ou d'un telephone.

    On prend, dans cet ordre :
    - DateTimeOriginal (0x9003) : l'instant du declenchement ;
    - DateTime (0x0132) : a defaut, la date inscrite par l'appareil ou le
      logiciel. Elle prend aussi le relais d'une DateTimeOriginal illisible
      (« 0000:00:00 00:00:00 », que certains appareils inscrivent faute de mieux).
    Chacune peut etre accompagnee de son ecart au temps universel
    (OffsetTimeOriginal, 0x9011, et OffsetTime, 0x9010) : voir _en_secondes.
    Les fractions de seconde (SubSecTimeOriginal, 0x9291), quand elles existent,
    departagent les photos prises en rafale dans la meme seconde.

    Renvoie un nombre de secondes, comparable a une date de fichier, ou None si
    le fichier n'a pas de date lisible (PNG, video, RAW non reconnu...).
    """
    try:
        with Image.open(chemin) as image:
            # Un PNG peut ranger ses donnees EXIF apres l'image : pour les y
            # chercher, Pillow decode alors toute l'image (0,12 s pour un PNG
            # de 12 Mpx, des minutes pour un dossier entier de PNG). On s'en
            # tient a celles placees avant, comme le font les appareils ; a
            # defaut, ce sont les dates du fichier qui servent.
            if image.format == "PNG" and "exif" not in image.info:
                return None
            exif = image.getexif()
            details = exif.get_ifd(ExifTags.IFD.Exif)
            originale = _en_secondes(details.get(0x9003), details.get(0x9011))
            inscrite = _en_secondes(exif.get(0x0132), details.get(0x9010))
            fraction = details.get(0x9291)
    except Exception:
        # Fichier que Pillow ne sait pas ouvrir : ce n'est pas une erreur, on
        # se rabattra simplement sur les dates du fichier.
        return None

    if originale is None:
        return inscrite
    if fraction and str(fraction).strip("\x00 ").isdigit():
        originale += float("0." + str(fraction).strip("\x00 "))
    return originale


def _en_secondes(texte, decalage):
    """« 2026:08:24 14:03:27 » -> nombre de secondes, ou None si la date est inutilisable.

    L'heure EXIF est celle de la montre de l'appareil, sans fuseau horaire.
    Quand l'appareil a inscrit son ecart au temps universel (« +02:00 »), on
    s'en sert : on obtient l'instant exact, comparable sans erreur aux dates
    des fichiers (celles des videos, notamment), meme pour des photos prises
    a l'etranger ou la nuit du changement d'heure. Sinon, l'heure est lue
    comme une heure de l'ordinateur.

    Une date fantaisiste (« 0000:00:00 00:00:00 ») donne None, de meme qu'une
    date anterieure au 2 janvier 1970 (horloge d'appareil remise a zero,
    photo scannee) : sous Windows, Python ne sait pas la convertir.
    """
    if not texte:
        return None
    texte = str(texte).strip("\x00 ")
    decalage = str(decalage or "").strip("\x00 ")
    try:
        try:
            date = datetime.strptime(texte + decalage, "%Y:%m:%d %H:%M:%S%z")
        except ValueError:
            # Pas d'ecart inscrit, ou un ecart illisible (« :  ») : heure locale.
            date = datetime.strptime(texte, "%Y:%m:%d %H:%M:%S")
        secondes = date.timestamp()
    except (ValueError, OSError, OverflowError):
        return None
    # Avec un ecart inscrit, une date d'avant 1970 se convertirait, elle :
    # on l'ecarte aussi, pour que des photos scannees soient toutes classees
    # de la meme facon, par la date de leur fichier.
    if secondes < 86400:
        return None
    return secondes


def date_du_fichier(chemin):
    """Date la plus ancienne connue du fichier, a defaut de date de prise de vue.

    Sous Windows, la « date de creation » d'un fichier est la date a laquelle il
    a ete copie sur ce disque : apres une copie depuis une carte memoire, elle
    ne dit rien de la prise de vue. La date de modification, elle, est conservee
    par la copie et correspond en general a la prise de vue. On retient donc la
    plus ancienne des deux, qui est la plus proche de l'instant reel.
    """
    informations = os.stat(chemin)
    dates = [informations.st_mtime]

    # st_birthtime est la vraie date de creation quand le systeme la fournit.
    # Sur les anciennes versions de Python sous Windows, c'est st_ctime qui joue
    # ce role (ailleurs, st_ctime signifie autre chose et n'est pas utilise).
    if getattr(informations, "st_birthtime", None):
        dates.append(informations.st_birthtime)
    elif os.name == "nt":
        dates.append(informations.st_ctime)

    return min(dates)


def ordre_chronologique(chemin):
    """Cle de tri : de la photo la plus ancienne a la plus recente (section 7.2).

    La date de prise de vue passe avant tout ; les dates du fichier ne servent
    que si la photo n'en contient pas. En cas d'egalite parfaite, le nom
    d'origine departage : les appareils numerotent leurs photos dans l'ordre
    ou ils les prennent (IMG_0001, IMG_0002...). Ainsi l'ordre obtenu est
    toujours le meme, quel que soit l'ordre dans lequel Windows liste les
    fichiers.
    """
    date = date_de_prise_de_vue_exif(chemin)
    if date is None:
        date = date_du_fichier(chemin)
    return (date, os.path.basename(chemin).lower())


def fichiers_a_la_racine(dossier_source):
    """Liste les fichiers poses directement dans le dossier source.

    Les sous-dossiers sont ignores : seules les photos brutes, deposees a la
    racine, sont concernees par la preparation.
    """
    noms = []
    for nom in os.listdir(dossier_source):
        chemin = os.path.join(dossier_source, nom)
        if os.path.isfile(chemin):
            noms.append(nom)
    return noms


def est_pris_en_charge(nom_fichier):
    """Le fichier fait-il partie de ce que la preparation traite ?

    Seules les photos, les fichiers RAW et les videos sont pris en charge. Tout
    autre fichier pose a la racine du dossier source (un texte, un PDF, un
    fichier de l'appareil) est laisse strictement intact : il n'est ni renomme,
    ni deplace, ni compte dans la numerotation.

    Auparavant, le renommage prenait tous les fichiers sans distinction : un
    « notes.txt » devenait « 7.txt », alors que le code affirmait quelques
    lignes plus loin le laisser ou il etait, sans y toucher.

    « ._IMG_0001.JPG » est un fichier que macOS ajoute a cote de chaque
    fichier copie sur une cle ou une carte memoire : il porte l'extension de
    la photo, mais ne contient que des informations du Mac. Pris pour une
    photo, il recevait un numero et apparaissait au tri, illisible.
    """
    if nom_fichier.startswith("._"):
        return False
    extension = os.path.splitext(nom_fichier)[1].lower()
    return (est_une_image(nom_fichier)
            or extension in EXTENSIONS_RAW
            or extension in EXTENSIONS_VIDEO)


def creer_dossiers(suivi, avec_raw, avec_video):
    """Cree l'arborescence de rangement (section 7.1).

    Les dossiers RAW et Videos ne sont crees que si de tels fichiers existent.
    """
    os.makedirs(suivi.dossier_evenement, exist_ok=True)
    for nom in suivi.noms_dossiers_tri:
        os.makedirs(suivi.chemin_dossier(nom), exist_ok=True)
    if avec_raw:
        os.makedirs(os.path.join(suivi.dossier_evenement, NOM_DOSSIER_RAW),
                    exist_ok=True)
    if avec_video:
        os.makedirs(os.path.join(suivi.dossier_evenement, NOM_DOSSIER_VIDEOS),
                    exist_ok=True)


def _signaler(avancement, texte):
    """Transmet ou en est la preparation, si l'appelant l'a demande (voir preparer)."""
    if avancement is not None:
        avancement(texte)


def renommer_photos(dossier_source, noms, avancement=None):
    """Renomme tous les fichiers en 1, 2, 3... du plus ancien au plus recent (section 7.2).

    Le numero 1 revient a la photo prise la premiere, le dernier numero a la
    photo prise la derniere, d'apres la date et l'heure de prise de vue.

    Le renommage se fait en deux passes. Sans cela, renommer un fichier en
    « 3.jpg » alors qu'un autre fichier porte deja ce nom ecraserait ce dernier.
    La premiere passe donne a chacun un nom temporaire, forcement libre ; la
    seconde attribue les noms definitifs, en toute securite.

    Les noms temporaires portent la date et l'heure du renommage : si une
    preparation precedente avait ete interrompue en laissant des noms
    temporaires, ceux de la nouvelle ne peuvent pas les rencontrer. Chaque
    renommage reessaie un instant si un fichier est occupe (OneDrive qui
    l'envoie en ligne, l'explorateur qui fabrique sa vignette...), et aucun
    n'ecrase jamais un fichier existant (voir fichiers.deplacer_fichier).

    Renvoie la liste ordonnee des nouveaux noms.
    """
    chemins = [os.path.join(dossier_source, nom) for nom in noms]
    total = len(chemins)

    # La date de chaque photo est lue une seule fois, avant le classement :
    # c'est l'etape la plus longue, chaque photo devant etre ouverte (et, dans
    # un dossier OneDrive, parfois d'abord telechargee). On peut ainsi en
    # annoncer l'avancement.
    cles = {}
    for numero, chemin in enumerate(chemins, start=1):
        cles[chemin] = ordre_chronologique(chemin)
        _signaler(avancement, "Lecture des dates de prise de vue : %d sur %d" % (numero, total))
    chemins.sort(key=lambda chemin: cles[chemin])
    prefixe = "%s%s_" % (PREFIXE_TEMPORAIRE, time.strftime("%Y%m%d%H%M%S"))

    # Un sous-dossier qui porterait l'un des noms definitifs (un dossier
    # « 2.jpg ») arreterait la seconde passe a mi-chemin, et de nouveau a
    # chaque reprise. On le signale avant d'avoir renomme quoi que ce soit.
    for numero, chemin in enumerate(chemins, start=1):
        nom_final = "%d%s" % (numero, os.path.splitext(chemin)[1])
        if os.path.isdir(os.path.join(dossier_source, nom_final)):
            raise FileExistsError(
                errno.EEXIST, "Un sous-dossier porte le nom « %s », que doit recevoir "
                "une photo : renommez ce sous-dossier, puis recommencez" % nom_final)

    # Premiere passe : noms temporaires.
    chemins_temporaires = []
    for numero, chemin in enumerate(chemins, start=1):
        extension = os.path.splitext(chemin)[1]
        temporaire = os.path.join(dossier_source, "%s%d%s" % (prefixe, numero, extension))
        deplacer_fichier(chemin, temporaire)
        chemins_temporaires.append(temporaire)
        _signaler(avancement, "Renommage : %d sur %d" % (numero, 2 * total))

    # Seconde passe : noms definitifs, sans zeros devant les nombres.
    nouveaux_noms = []
    for numero, temporaire in enumerate(chemins_temporaires, start=1):
        extension = os.path.splitext(temporaire)[1]
        nom_final = "%d%s" % (numero, extension)
        deplacer_fichier(temporaire, os.path.join(dossier_source, nom_final))
        nouveaux_noms.append(nom_final)
        _signaler(avancement, "Renommage : %d sur %d" % (total + numero, 2 * total))

    return nouveaux_noms


def mettre_a_ecart(suivi, noms):
    """Deplace les fichiers RAW et video dans leurs dossiers (section 7.3).

    Le dossier source pouvant deja contenir des dossiers RAW ou Videos, un
    fichier du meme nom peut s'y trouver : le fichier est alors laisse a la
    racine plutot que d'ecraser l'autre (avec `shutil.move`, qui se rabat sur
    une copie, il l'aurait remplace). Un fichier occupe trop longtemps
    (OneDrive, antivirus) reste lui aussi a la racine : la preparation va
    jusqu'au bout, car relancee, elle renumeroterait tout.

    Renvoie (photos restantes, fichiers laisses a la racine).
    Les photos restantes sont celles qui seront effectivement triees.
    """
    dossier_source = suivi.dossier_source
    restants = []
    laisses = []

    for nom in noms:
        extension = os.path.splitext(nom)[1].lower()
        if extension in EXTENSIONS_RAW:
            destination = os.path.join(suivi.dossier_evenement, NOM_DOSSIER_RAW)
        elif extension in EXTENSIONS_VIDEO:
            destination = os.path.join(suivi.dossier_evenement, NOM_DOSSIER_VIDEOS)
        else:
            # Ne restent ici que des images : les fichiers d'un autre genre ont
            # ete ecartes avant le renommage (voir est_pris_en_charge).
            restants.append(nom)
            continue

        try:
            os.makedirs(destination, exist_ok=True)
            deplacer_fichier(os.path.join(dossier_source, nom), os.path.join(destination, nom))
        except OSError:
            laisses.append(nom)

    return restants, laisses


def ordonner_photos(noms):
    """Trie les photos par leur numero, et non par ordre alphabetique.

    Sans cela, « 10.jpg » passerait avant « 2.jpg ».
    """
    def numero(nom):
        base = os.path.splitext(nom)[0]
        return int(base) if base.isdigit() else 0

    return sorted(noms, key=numero)


def preparer(suivi, avancement=None):
    """Execute toute la preparation automatique et met a jour le suivi.

    `avancement`, facultatif, est appele de temps en temps avec un court texte
    disant ou en est la preparation (« Renommage : 120 sur 600 »). Cette
    fonction ne touche jamais a l'interface : elle peut tourner sur un fil
    d'arriere-plan (voir main.EcranDemarrage._preparer_avec_attente).

    Renvoie un petit compte rendu, affiche ensuite a l'utilisateur.
    """
    dossier_source = suivi.dossier_source
    # Le fichier de suivi, ecrit juste avant dans ce meme dossier, n'est pas
    # un fichier de l'utilisateur : il n'a pas a figurer parmi les ignores.
    tous_les_fichiers = [nom for nom in fichiers_a_la_racine(dossier_source)
                         if not nom.startswith(NOM_FICHIER_SUIVI)]
    noms = [nom for nom in tous_les_fichiers if est_pris_en_charge(nom)]

    extensions = {os.path.splitext(nom)[1].lower() for nom in noms}
    avec_raw = bool(extensions & EXTENSIONS_RAW)
    avec_video = bool(extensions & EXTENSIONS_VIDEO)

    creer_dossiers(suivi, avec_raw, avec_video)
    nouveaux_noms = renommer_photos(dossier_source, noms, avancement)
    _signaler(avancement, "Mise de cote des fichiers RAW et des videos...")
    restants, laisses = mettre_a_ecart(suivi, nouveaux_noms)
    photos = ordonner_photos(restants)

    suivi.tri["photos"] = photos
    suivi.tri["position"] = 0
    suivi.tri["historique"] = []
    suivi.tri["terminee"] = False
    suivi.donnees["preparation_faite"] = True
    suivi.enregistrer()

    pas_bouges = set(restants) | set(laisses)
    mis_de_cote = [nom for nom in nouveaux_noms if nom not in pas_bouges]
    return {
        "photos": len(photos),
        "raw": sum(1 for n in mis_de_cote
                   if os.path.splitext(n)[1].lower() in EXTENSIONS_RAW),
        "videos": sum(1 for n in mis_de_cote
                      if os.path.splitext(n)[1].lower() in EXTENSIONS_VIDEO),
        "laisses": laisses,
        "ignores": len(tous_les_fichiers) - len(noms),
    }
