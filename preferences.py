"""
Preferences retenues d'une ouverture du logiciel a l'autre (decision de
l'utilisateur, 26 octobre 2026).

A la configuration d'un nouvel evenement, l'utilisateur retrouve ses dossiers
de tri tels qu'il les avait laisses la derniere fois : leurs noms, leur nombre
et leurs touches, y compris ceux crees pendant le tri avec la touche N. Sont
aussi retenus le dernier evenement ouvert, pour le reprendre en un clic, le
dossier ou l'on va chercher ses photos, le format des noms donnes aux photos,
et la taille de la fenetre de tri.

Tout tient dans un petit fichier JSON place a cote du programme. Il n'est
jamais indispensable : s'il manque ou s'il est illisible, le logiciel repart
des valeurs par defaut ; s'il ne peut pas etre ecrit, seule cette commodite
est perdue.
"""

import os

from fichiers import ecrire_json, lire_json

CHEMIN_PREFERENCES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "preferences.json")


def _lire():
    try:
        donnees = lire_json(CHEMIN_PREFERENCES)
    except (OSError, ValueError):
        return {}
    return donnees if isinstance(donnees, dict) else {}


def _retenir(cle, valeur):
    donnees = _lire()
    donnees[cle] = valeur
    try:
        ecrire_json(CHEMIN_PREFERENCES, donnees)
    except OSError:
        pass        # simple commodite : le logiciel s'en passe tres bien


def _texte(cle):
    """Valeur texte d'une preference, ou None si elle manque ou n'est pas du texte."""
    valeur = _lire().get(cle)
    return valeur if isinstance(valeur, str) and valeur else None


# --- Dossiers de tri --------------------------------------------------------

def dossiers_de_tri():
    """Dossiers de tri de la derniere fois, [{"nom", "touche"}...], ou None.

    Les entrees abimees (fichier modifie a la main) sont ecartees. Leur
    validite (noms, touches) n'est pas verifiee ici : l'ecran de configuration
    le fait, et explique ce qui ne va pas.
    """
    dossiers = _lire().get("dossiers_tri")
    if not isinstance(dossiers, list):
        return None
    propres = [{"nom": dossier["nom"], "touche": dossier["touche"]}
               for dossier in dossiers
               if isinstance(dossier, dict)
               and isinstance(dossier.get("nom"), str)
               and isinstance(dossier.get("touche"), str)]
    return propres or None


def retenir_dossiers_de_tri(dossiers):
    _retenir("dossiers_tri", [{"nom": dossier["nom"], "touche": dossier["touche"]}
                              for dossier in dossiers])


# --- Nom des photos ---------------------------------------------------------

def format_de_renommage():
    """Format de nom choisi la derniere fois (voir renommage.py), ou None."""
    return _texte("format_de_renommage")


def retenir_format_de_renommage(nom_format):
    _retenir("format_de_renommage", nom_format)


# --- Emplacements -----------------------------------------------------------

def dernier_evenement():
    """Dossier du dernier evenement ouvert, ou None."""
    return _texte("dernier_evenement")


def retenir_dernier_evenement(chemin):
    _retenir("dernier_evenement", chemin)


def dossier_des_photos():
    """Dossier ou ouvrir le choix du dossier source, ou None."""
    return _texte("dossier_des_photos")


def retenir_dossier_des_photos(chemin):
    _retenir("dossier_des_photos", chemin)


# --- Fenetre de tri ---------------------------------------------------------

def fenetre_de_tri():
    """Taille et etat de la fenetre de tri : {"geometrie": "1200x800+40+30", "agrandie": bool}.

    Par defaut, la fenetre s'ouvre agrandie : une photo se juge mieux en grand.
    """
    retenue = _lire().get("fenetre_de_tri")
    fenetre = {"geometrie": "1200x800", "agrandie": True}
    if isinstance(retenue, dict):
        if isinstance(retenue.get("geometrie"), str):
            fenetre["geometrie"] = retenue["geometrie"]
        if isinstance(retenue.get("agrandie"), bool):
            fenetre["agrandie"] = retenue["agrandie"]
    return fenetre


def retenir_fenetre_de_tri(geometrie, agrandie):
    _retenir("fenetre_de_tri", {"geometrie": geometrie, "agrandie": agrandie})
