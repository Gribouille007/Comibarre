"""
Les dossiers de tri : ceux proposes la toute premiere fois, les regles que
doivent respecter leurs noms et leurs touches, et le choix d'une touche libre.

Leur nombre est libre, de 1 a NOMBRE_MAXIMAL (decision de l'utilisateur,
26 octobre 2026 ; il en fallait exactement quatre auparavant).

Ce module ne connait pas Tkinter. Il sert a l'ecran de configuration d'un
nouvel evenement, a la creation d'un dossier pendant le tri (touche N) et a la
gestion des dossiers depuis le menu : les trois appliquent ainsi exactement
les memes regles.
"""

import os

import touches
from dossiers import contient_des_fichiers, probleme_du_nom
from preparation import NOM_DOSSIER_RAW, NOM_DOSSIER_VIDEOS
from retouches import DOSSIER_SANS_BARRE
from suivi import NOM_DOSSIER_TEMPORAIRE

# Proposes tant que l'utilisateur n'a encore configure aucun evenement. Ensuite,
# ce sont ses propres dossiers qui sont proposes (voir preferences.py).
DOSSIERS_PAR_DEFAUT = [
    {"nom": "A garder", "touche": "1"},
    {"nom": "Ratees", "touche": "2"},
    {"nom": "A revoir", "touche": "3"},
    {"nom": "A supprimer", "touche": "4"},
]

# Au-dela, le rappel des touches ne tiendrait plus en bas de la fenetre de tri,
# ni l'ecran de configuration sur un petit ecran.
NOMBRE_MAXIMAL = 12

# Dossiers que le logiciel cree lui-meme a cote des dossiers de tri. Un dossier
# de tri du meme nom melangerait les photos triees avec les fichiers RAW, les
# videos, les versions sans bandeaux ou les copies de sauvegarde.
NOMS_RESERVES = (NOM_DOSSIER_RAW, NOM_DOSSIER_VIDEOS, DOSSIER_SANS_BARRE,
                 NOM_DOSSIER_TEMPORAIRE)

# Ordre dans lequel les touches libres sont proposees : les chiffres d'abord,
# puis les lettres. Les touches reservees (R, C, N) sont sautees.
ORDRE_DES_TOUCHES = "1234567890abdefghijklmopqstuvwxyz"


def erreurs_des_dossiers(dossiers):
    """Liste des problemes d'une liste de dossiers de tri, vide si tout va bien.

    `dossiers` est une liste de dictionnaires {"nom", "touche"}. Chaque sorte
    de probleme n'est signalee qu'une fois, meme si plusieurs lignes la
    presentent : la liste reste courte et lisible.
    """
    if not dossiers:
        return ["Il faut au moins un dossier de tri."]
    erreurs = []
    if len(dossiers) > NOMBRE_MAXIMAL:
        erreurs.append("Il ne peut pas y avoir plus de %d dossiers de tri." % NOMBRE_MAXIMAL)

    noms = [dossier["nom"].strip() for dossier in dossiers]
    if any(not nom for nom in noms):
        erreurs.append("Chaque dossier de tri doit avoir un nom.")
    for nom in noms:
        probleme = probleme_du_nom(nom) if nom else None
        if probleme is not None:
            erreurs.append("Dossier « %s » : %s." % (nom, probleme))
            break
    reserves = [nom for nom in noms if nom.lower() in {r.lower() for r in NOMS_RESERVES}]
    if reserves:
        erreurs.append("Le nom « %s » est reserve aux dossiers que cree le logiciel."
                       % reserves[0])
    noms_remplis = [nom.lower() for nom in noms if nom]
    if len(set(noms_remplis)) != len(noms_remplis):
        erreurs.append("Deux dossiers de tri ne peuvent pas porter le meme nom.")

    touches_choisies = [dossier["touche"].strip() for dossier in dossiers]
    if any(not touche for touche in touches_choisies):
        erreurs.append("Chaque dossier de tri doit avoir une touche.")
    for touche in touches_choisies:
        probleme = touches.probleme_de_touche(touche) if touche else None
        if probleme is not None:
            erreurs.append("Touche « %s » : %s." % (touche, probleme))
            break
    touches_remplies = [touche.lower() for touche in touches_choisies if touche]
    if len(set(touches_remplies)) != len(touches_remplies):
        erreurs.append("Une meme touche ne peut pas servir a deux dossiers.")

    return erreurs


def erreurs_sur_le_disque(dossiers, dossier_evenement):
    """Problemes que poserait la creation de ces dossiers dans le dossier de l'evenement.

    Un dossier de tri ne peut pas prendre la place d'un fichier, ni celle d'un
    dossier deja present qui contient des fichiers : une copie faite depuis le
    menu, ou un dossier que l'utilisateur avait lui-meme range la. Ses photos
    se melangeraient aux photos triees. Un dossier vide, lui, est simplement
    repris.

    La cle facultative "origine" donne le nom actuel d'un dossier de tri qui
    existe deja (gestion depuis le menu) : le garder, ou le renommer, n'est pas
    un conflit avec lui-meme.
    """
    erreurs = []
    for dossier in dossiers:
        nom = dossier["nom"].strip()
        chemin = os.path.join(dossier_evenement, nom)
        if not nom or not os.path.exists(chemin):
            continue
        origine = dossier.get("origine")
        if origine is not None:
            chemin_origine = os.path.join(dossier_evenement, origine)
            # samefile reconnait le meme dossier, meme change de majuscules.
            if os.path.exists(chemin_origine) and os.path.samefile(chemin, chemin_origine):
                continue
        if not os.path.isdir(chemin):
            erreurs.append("Un fichier nomme « %s » occupe deja la place de ce dossier." % nom)
        elif contient_des_fichiers(chemin):
            erreurs.append("Un dossier « %s » existe deja et contient des fichiers : "
                           "choisissez un autre nom." % nom)
    return erreurs


def erreurs_avec_les_copies(dossiers, noms_des_copies):
    """Refuse a un dossier de tri, nouveau ou renomme, le nom d'une copie de l'evenement.

    Une copie reste notee dans le suivi, meme vide ou effacee du disque : un
    dossier de tri du meme nom apparaissait alors deux fois au menu. Un
    dossier qui garde son nom n'est pas verifie, pour ne pas bloquer un
    evenement plus ancien.
    """
    copies = {nom.lower() for nom in noms_des_copies}
    erreurs = []
    for dossier in dossiers:
        nom = dossier["nom"].strip()
        origine = dossier.get("origine")
        if origine is not None and origine.lower() == nom.lower():
            continue
        if nom.lower() in copies:
            erreurs.append("« %s » est deja le nom d'une copie de l'evenement : "
                           "choisissez un autre nom." % nom)
    return erreurs


def touche_libre(dossiers):
    """Premiere touche qu'aucun de ces dossiers n'utilise, ou "" s'il n'y en a plus."""
    prises = {dossier["touche"].strip().lower() for dossier in dossiers}
    for touche in ORDRE_DES_TOUCHES:
        if touche not in prises and touches.probleme_de_touche(touche) is None:
            return touche
    return ""
