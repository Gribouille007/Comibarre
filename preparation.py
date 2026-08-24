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


def date_de_creation(chemin):
    """Date servant a ordonner les photos (section 7.2).

    On utilise la date de creation du fichier ; si elle n'est pas disponible,
    on se rabat sur la date de derniere modification.
    """
    informations = os.stat(chemin)

    # st_birthtime est la vraie date de creation quand le systeme la fournit.
    # Sous Windows, c'est st_ctime qui joue ce role. En dernier recours, on
    # utilise la date de derniere modification, comme prevu par la section 7.2.
    for attribut in ("st_birthtime", "st_ctime"):
        date = getattr(informations, attribut, None)
        if date:
            return date
    return informations.st_mtime


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
        os.makedirs(suivi.chemin_dossier_tri(nom), exist_ok=True)
    if avec_raw:
        os.makedirs(os.path.join(suivi.dossier_evenement, NOM_DOSSIER_RAW),
                    exist_ok=True)
    if avec_video:
        os.makedirs(os.path.join(suivi.dossier_evenement, NOM_DOSSIER_VIDEOS),
                    exist_ok=True)


def renommer_photos(dossier_source, noms):
    """Renomme tous les fichiers en 1, 2, 3... par date de creation (section 7.2).

    Le renommage se fait en deux passes. Sans cela, renommer un fichier en
    « 3.jpg » alors qu'un autre fichier porte deja ce nom ecraserait ce dernier.
    La premiere passe donne a chacun un nom temporaire, forcement libre ; la
    seconde attribue les noms definitifs, en toute securite.

    Renvoie la liste ordonnee des nouveaux noms.
    """
    chemins = [os.path.join(dossier_source, nom) for nom in noms]
    chemins.sort(key=date_de_creation)

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
