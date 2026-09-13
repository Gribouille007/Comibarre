"""
Preparation automatique (section 7).

Cette phase s'execute une seule fois, juste apres la configuration, sans aucune
action de l'utilisateur :

1. creation des dossiers de rangement ;
2. renommage de toutes les photos en 1, 2, 3... ;
3. mise a l'ecart des fichiers RAW et video.

Elle n'est jamais rejouee lors de la reprise d'un evenement (sections 5 et 10).
"""

import os
import shutil
from datetime import datetime

from PIL import ExifTags, Image

# Importer `images` enregistre aussi le format HEIC aupres de Pillow, ce qui
# permet de lire la date de prise de vue des photos d'iPhone.
from images import EXTENSIONS_IMAGE, est_une_image

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
    - DateTime (0x0132) : a defaut, la date inscrite par l'appareil ou le logiciel.
    Les fractions de seconde (SubSecTimeOriginal, 0x9291), quand elles existent,
    departagent les photos prises en rafale dans la meme seconde.

    Renvoie un nombre de secondes, comparable a une date de fichier, ou None si
    le fichier n'a pas de date lisible (PNG, video, RAW non reconnu...).
    """
    try:
        with Image.open(chemin) as image:
            exif = image.getexif()
            details = exif.get_ifd(ExifTags.IFD.Exif)
            texte = details.get(0x9003) or exif.get(0x0132)
            fraction = details.get(0x9291)
    except Exception:
        # Fichier que Pillow ne sait pas ouvrir : ce n'est pas une erreur, on
        # se rabattra simplement sur les dates du fichier.
        return None

    if not texte:
        return None
    try:
        date = datetime.strptime(str(texte).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        # Date absente ou fantaisiste, par exemple « 0000:00:00 00:00:00 ».
        return None

    secondes = date.timestamp()
    if fraction and str(fraction).strip("\x00 ").isdigit():
        secondes += float("0." + str(fraction).strip("\x00 "))
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


def renommer_photos(dossier_source, noms):
    """Renomme tous les fichiers en 1, 2, 3... du plus ancien au plus recent (section 7.2).

    Le numero 1 revient a la photo prise la premiere, le dernier numero a la
    photo prise la derniere, d'apres la date et l'heure de prise de vue.

    Le renommage se fait en deux passes. Sans cela, renommer un fichier en
    « 3.jpg » alors qu'un autre fichier porte deja ce nom ecraserait ce dernier.
    La premiere passe donne a chacun un nom temporaire, forcement libre ; la
    seconde attribue les noms definitifs, en toute securite.

    Renvoie la liste ordonnee des nouveaux noms.
    """
    chemins = [os.path.join(dossier_source, nom) for nom in noms]
    chemins.sort(key=ordre_chronologique)

    # Premiere passe : noms temporaires.
    chemins_temporaires = []
    for numero, chemin in enumerate(chemins, start=1):
        extension = os.path.splitext(chemin)[1]
        temporaire = os.path.join(dossier_source,
                                  "%s%d%s" % (PREFIXE_TEMPORAIRE, numero, extension))
        os.rename(chemin, temporaire)
        chemins_temporaires.append(temporaire)

    # Seconde passe : noms definitifs, sans zeros devant les nombres.
    nouveaux_noms = []
    for numero, temporaire in enumerate(chemins_temporaires, start=1):
        extension = os.path.splitext(temporaire)[1]
        nom_final = "%d%s" % (numero, extension)
        os.rename(temporaire, os.path.join(dossier_source, nom_final))
        nouveaux_noms.append(nom_final)

    return nouveaux_noms


def mettre_a_ecart(suivi, noms):
    """Deplace les fichiers RAW et video dans leurs dossiers (section 7.3).

    Renvoie la liste des noms restants, c'est-a-dire les photos qui seront
    effectivement triees puis censurees.
    """
    dossier_source = suivi.dossier_source
    restants = []

    for nom in noms:
        extension = os.path.splitext(nom)[1].lower()
        if extension in EXTENSIONS_RAW:
            destination = os.path.join(suivi.dossier_evenement, NOM_DOSSIER_RAW)
        elif extension in EXTENSIONS_VIDEO:
            destination = os.path.join(suivi.dossier_evenement, NOM_DOSSIER_VIDEOS)
        else:
            if est_une_image(nom):
                restants.append(nom)
            # Un fichier qui n'est ni une image, ni un RAW, ni une video (un
            # fichier texte par exemple) est laisse ou il est, sans y toucher.
            continue

        os.makedirs(destination, exist_ok=True)
        shutil.move(os.path.join(dossier_source, nom),
                    os.path.join(destination, nom))

    return restants


def ordonner_photos(noms):
    """Trie les photos par leur numero, et non par ordre alphabetique.

    Sans cela, « 10.jpg » passerait avant « 2.jpg ».
    """
    def numero(nom):
        base = os.path.splitext(nom)[0]
        return int(base) if base.isdigit() else 0

    return sorted(noms, key=numero)


def preparer(suivi):
    """Execute toute la preparation automatique et met a jour le suivi.

    Renvoie un petit compte rendu, affiche ensuite a l'utilisateur.
    """
    dossier_source = suivi.dossier_source
    noms = fichiers_a_la_racine(dossier_source)

    extensions = {os.path.splitext(nom)[1].lower() for nom in noms}
    avec_raw = bool(extensions & EXTENSIONS_RAW)
    avec_video = bool(extensions & EXTENSIONS_VIDEO)

    creer_dossiers(suivi, avec_raw, avec_video)
    nouveaux_noms = renommer_photos(dossier_source, noms)
    photos = ordonner_photos(mettre_a_ecart(suivi, nouveaux_noms))

    suivi.tri["photos"] = photos
    suivi.tri["position"] = 0
    suivi.tri["historique"] = []
    suivi.tri["terminee"] = False
    suivi.donnees["preparation_faite"] = True
    suivi.enregistrer()

    return {
        "photos": len(photos),
        "raw": sum(1 for n in nouveaux_noms
                   if os.path.splitext(n)[1].lower() in EXTENSIONS_RAW),
        "videos": sum(1 for n in nouveaux_noms
                      if os.path.splitext(n)[1].lower() in EXTENSIONS_VIDEO),
        "ignores": sum(1 for n in nouveaux_noms
                       if os.path.splitext(n)[1].lower() not in EXTENSIONS_RAW
                       and os.path.splitext(n)[1].lower() not in EXTENSIONS_VIDEO
                       and os.path.splitext(n)[1].lower() not in EXTENSIONS_IMAGE),
    }
