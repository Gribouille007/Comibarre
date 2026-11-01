"""
Reconnaitre un dossier synchronise par un service en ligne (OneDrive...).

Un service de synchronisation peut annuler apres coup le deplacement d'une
photo et la remettre a son ancienne place. Constate par l'utilisateur sur un
dossier OneDrive (octobre 2026) : apres un tri complet, des photos rangees se
trouvaient de nouveau dans le dossier source, et plus dans leur dossier de
tri, sans qu'aucune erreur ait ete signalee. Le deplacement avait pourtant
reussi : c'est la synchronisation qui l'a defait ensuite.

Le logiciel ne peut pas l'empecher. Il previent donc avant le tri, puis
repere et propose de remettre en place les photos revenues (voir
remise_en_place.py).
"""

import os

# Debuts de noms de dossiers propres a chaque service. Ils servent quand le
# service ne declare pas son emplacement : sous macOS, par exemple, les
# services ranges dans ~/Library/CloudStorage s'appellent « OneDrive-... »,
# « GoogleDrive-... », « Dropbox »...
DEBUTS_DE_NOMS = (
    ("onedrive", "OneDrive"),
    ("dropbox", "Dropbox"),
    ("google drive", "Google Drive"),
    ("googledrive", "Google Drive"),
    ("my drive", "Google Drive"),
    ("mon drive", "Google Drive"),
    ("icloud", "iCloud"),
    ("mobile documents", "iCloud"),
)


def service_de_synchronisation(chemin):
    """Nom du service qui synchronise ce dossier (« OneDrive »...), ou None."""
    chemin = os.path.abspath(chemin)

    # Sous Windows, OneDrive declare ses dossiers dans des variables
    # d'environnement : c'est le moyen le plus sur de les reconnaitre, y
    # compris quand Windows y a place les dossiers Images ou Bureau.
    for variable in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        racine = os.environ.get(variable)
        if racine and _est_dans(chemin, racine):
            return "OneDrive"

    for morceau in chemin.split(os.sep):
        morceau = morceau.lower()
        for debut, service in DEBUTS_DE_NOMS:
            if morceau.startswith(debut):
                return service
    return None


def _est_dans(chemin, dossier):
    """Le chemin est-il ce dossier, ou se trouve-t-il a l'interieur ?"""
    chemin = os.path.normcase(os.path.abspath(chemin))
    dossier = os.path.normcase(os.path.abspath(dossier))
    try:
        return os.path.commonpath([chemin, dossier]) == dossier
    except ValueError:
        return False        # deux lecteurs differents, sous Windows
