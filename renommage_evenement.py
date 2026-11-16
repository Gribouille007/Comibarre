"""
Renommage des photos d'un evenement deja commence (menu « Renommer les photos »).

Sert surtout aux evenements numerotes 1, 2, 3 : reunir deux tris faits
separement y donnerait deux « 12.jpg » differents. Renommes par date, leurs
fichiers ne se rencontrent plus (voir renommage.py).

Toutes les photos de l'evenement sont concernees, ou qu'elles soient : encore
a trier, rangees dans un dossier de tri ou dans une copie, mises de cote dans
RAW et Videos, ou gardees dans un dossier « Sans-barre ». Une photo, sa
version sans barre et ses copies portent le meme nom : elles recoivent donc le
meme nouveau nom, et restent ensemble.

Ce module ne touche jamais a l'interface : il peut tourner sur un fil
d'arriere-plan (voir attente.py).
"""

import errno
import os

import renommage
from images import est_une_image
from preparation import (NOM_DOSSIER_RAW, NOM_DOSSIER_VIDEOS, date_de_prise_de_vue_exif,
                         date_du_fichier, est_pris_en_charge)
from retouches import DOSSIER_SANS_BARRE


def fichiers_de_l_evenement(suivi):
    """Chemins de toutes les photos, RAW et videos de l'evenement.

    Le dossier des copies de sauvegarde n'en fait pas partie : ses fichiers
    gardent leur nom, sous lequel l'historique d'annulation les designe.
    """
    dossiers = [suivi.dossier_source]
    noms = list(suivi.noms_dossiers_tri) + list(suivi.dossiers_dupliques)
    noms += [NOM_DOSSIER_RAW, NOM_DOSSIER_VIDEOS]
    for nom in noms:
        chemin = suivi.chemin_dossier(nom)
        if chemin not in dossiers:
            dossiers.append(chemin)
    dossiers += [os.path.join(dossier, DOSSIER_SANS_BARRE) for dossier in dossiers]

    chemins = []
    for dossier in dossiers:
        if not os.path.isdir(dossier):
            continue
        with os.scandir(dossier) as entrees:
            chemins += [entree.path for entree in entrees
                        if entree.is_file() and est_pris_en_charge(entree.name)]
    return chemins


def _representant(membres):
    """Le fichier d'une prise de vue dont la date et le contenu donnent le nom.

    De preference la version sans barre, copie de la photo telle que l'appareil
    l'a ecrite : son code est alors le meme que sur un autre ordinateur ou la
    photo n'aurait pas ete barree. A defaut une photo, a defaut le premier fichier.
    """
    def rang(chemin):
        sans_barre = os.path.basename(os.path.dirname(chemin)) == DOSSIER_SANS_BARRE
        image = est_une_image(os.path.basename(chemin))
        return (not (sans_barre and image), not image, chemin.lower())
    return sorted(membres, key=rang)[0]


def _date_de_la_prise(membres, representant):
    """Date de prise de vue du groupe ; a defaut, la plus ancienne date de ses fichiers.

    Une photo barree ou rognee a ete reenregistree : la date de son fichier
    est celle de la modification. Les donnees EXIF, elles, ont ete gardees.
    """
    for chemin in [representant] + [autre for autre in membres if autre != representant]:
        if est_une_image(os.path.basename(chemin)):
            date = date_de_prise_de_vue_exif(chemin)
            if date is not None:
                return date
    return min(date_du_fichier(chemin) for chemin in membres)


def renommer_evenement(suivi, nom_format, avancement=None):
    """Donne aux photos de l'evenement les noms du format choisi. Renvoie leur nombre.

    Le suivi est mis a jour partout ou il cite une photo par son nom
    (rangements, historique d'annulation, listes du tri et de la revue), puis
    enregistre. Leve OSError si un fichier ne peut pas etre renomme : tout ce
    qui avait deja change de nom reprend alors son ancien nom.
    """
    chemins = fichiers_de_l_evenement(suivi)
    groupes = {}
    for chemin in chemins:
        identite = renommage.identite(os.path.basename(chemin), nom_format)
        groupes.setdefault(identite, []).append(chemin)

    prises = []
    for numero, (identite, membres) in enumerate(groupes.items(), start=1):
        representant = _representant(membres)
        prises.append({"identite": identite, "date": _date_de_la_prise(membres, representant),
                       "nom": os.path.basename(representant), "chemin": representant})
        if avancement is not None:
            avancement("Lecture des dates de prise de vue : %d sur %d" % (numero, len(groupes)))
    if avancement is not None:
        avancement("Calcul des nouveaux noms...")
    bases = renommage.calculer_les_noms(prises, nom_format, suivi.nom_evenement)

    renommages = []
    nouveaux_noms = {}          # ancien nom de fichier -> nouveau nom
    for chemin in chemins:
        ancien_nom = os.path.basename(chemin)
        nouveau_nom = (bases[renommage.identite(ancien_nom, nom_format)]
                       + os.path.splitext(ancien_nom)[1])
        nouveaux_noms[ancien_nom] = nouveau_nom
        if nouveau_nom != ancien_nom:
            renommages.append((chemin, os.path.join(os.path.dirname(chemin), nouveau_nom)))

    # Un fichier que le logiciel ne renomme pas, ou un sous-dossier, qui
    # porterait deja l'un des nouveaux noms : on le dit avant de commencer.
    anciens = {os.path.normcase(chemin) for chemin in chemins}
    for _, nouveau in renommages:
        if os.path.exists(nouveau) and os.path.normcase(nouveau) not in anciens:
            raise FileExistsError(
                errno.EEXIST, "Le nom « %s » est deja pris dans le dossier « %s » : "
                "renommez ce fichier, puis recommencez"
                % (os.path.basename(nouveau), os.path.basename(os.path.dirname(nouveau))))

    renommage.renommer_en_deux_passes(renommages, avancement)

    def nouveau(nom):
        return nouveaux_noms.get(nom, nom)

    suivi.donnees["rangements"] = {nouveau(nom): dossier
                                   for nom, dossier in suivi.rangements.items()}
    for action in suivi.historique:
        action["fichier"] = nouveau(action["fichier"])
    for etape in (suivi.tri, suivi.revue):
        etape["photos"] = [nouveau(nom) for nom in etape["photos"]]
    suivi.renommage = nom_format
    suivi.enregistrer()
    return len(chemins)
