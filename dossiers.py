"""
Operations sur les dossiers : choix, nommage, contenu et duplication.

Ce module regroupe quatre besoins qui portent tous sur des dossiers :

1. verifier qu'un nom peut servir de nom de dossier ;
2. demander un dossier a l'utilisateur sans que le programme « s'y installe » ;
3. lister les photos d'un dossier dans l'ordre de leurs numeros ;
4. dupliquer un dossier de l'evenement, avec un decompte d'avancement.

La duplication sert surtout a garder les originaux intacts : on copie un dossier
de tri avant de censurer l'un des deux exemplaires.
"""

import os
import shutil
import tkinter as tk
from tkinter import filedialog, ttk

import theme
from images import est_une_image
from polices import police

# Caracteres interdits dans un nom de dossier sous Windows. Ils sont refuses
# sur les trois systemes, pour qu'un evenement reste lisible partout.
CARACTERES_INTERDITS = set('\\/:*?"<>|')

# Noms que Windows reserve a ses peripheriques : un dossier ne peut pas les
# porter, meme suivis d'une extension (« CON.txt »).
NOMS_RESERVES_PAR_WINDOWS = ({"con", "prn", "aux", "nul"}
                             | {"com%d" % numero for numero in range(1, 10)}
                             | {"lpt%d" % numero for numero in range(1, 10)})

# Au-dela, les chemins des photos rangees risquent de depasser la longueur
# qu'accepte Windows (260 caracteres).
LONGUEUR_MAXIMALE_NOM = 100


def probleme_du_nom(nom):
    """Explique pourquoi `nom` ne peut pas servir de nom de dossier, ou renvoie None."""
    if not nom:
        return "le nom est vide"
    if nom.strip() != nom:
        return "le nom commence ou finit par un espace"
    if any(caractere in CARACTERES_INTERDITS for caractere in nom):
        return "caracteres interdits : " + " ".join(sorted(CARACTERES_INTERDITS))
    if any(not caractere.isprintable() for caractere in nom):
        return "le nom contient un caractere invisible"
    if nom.endswith("."):
        return "un nom de dossier ne peut pas finir par un point"
    if nom in (".", "..") or nom.split(".")[0].strip().lower() in NOMS_RESERVES_PAR_WINDOWS:
        return "« %s » est un nom reserve par Windows" % nom
    if len(nom) > LONGUEUR_MAXIMALE_NOM:
        return "le nom est trop long (%d caracteres au plus)" % LONGUEUR_MAXIMALE_NOM
    return None


def nom_de_dossier_valide(nom):
    """Le nom peut-il servir de nom de dossier ?"""
    return probleme_du_nom(nom) is None


def choisir_dossier(titre, parent, dossier_initial=None):
    """Demande un dossier a l'utilisateur, sans deplacer le dossier courant.

    Sous Windows, le dossier courant d'un programme en cours d'execution est
    considere comme « ouvert » : il ne peut plus etre deplace, renomme ni
    supprime, et l'explorateur repond qu'un fichier ou un dossier est ouvert.
    Or la boite de dialogue de choix de dossier peut, selon les versions de
    Windows, deplacer le dossier courant vers le dossier choisi. On note donc
    le dossier courant avant d'ouvrir la boite, et on le remet apres.

    `dossier_initial` : dossier ou la boite s'ouvre, s'il existe encore.

    Renvoie le chemin choisi, ou une chaine vide si l'utilisateur a annule.
    """
    options = {"title": titre, "parent": parent}
    if dossier_initial and os.path.isdir(dossier_initial):
        options["initialdir"] = dossier_initial

    dossier_courant = os.getcwd()
    try:
        choisi = filedialog.askdirectory(**options)
    finally:
        os.chdir(dossier_courant)

    return os.path.normpath(choisi) if choisi else ""


def photos_du_dossier(chemin_dossier):
    """Liste les images d'un dossier de tri, ordonnees par leur numero.

    Sans ce tri par numero, « 10.jpg » passerait avant « 2.jpg ».

    `os.scandir` sait deja, pour chaque entree, s'il s'agit d'un fichier :
    `os.path.isfile` interrogeait le disque une fois par photo, soit 0,18 s
    pour 3 000 photos, a chaque ouverture du tri et du menu (0,005 s ainsi).
    """
    if not os.path.isdir(chemin_dossier):
        return []
    with os.scandir(chemin_dossier) as entrees:
        noms = [entree.name for entree in entrees
                if entree.is_file() and est_une_image(entree.name)]

    def numero(nom):
        base = os.path.splitext(nom)[0]
        return (0, int(base)) if base.isdigit() else (1, 0)

    return sorted(noms, key=lambda nom: (numero(nom), nom))


def contient_des_fichiers(chemin_dossier):
    """Le dossier contient-il au moins un fichier, a sa racine ou dans un sous-dossier ?"""
    for _, _, fichiers in os.walk(chemin_dossier):
        if fichiers:
            return True
    return False


def supprimer_dossier_vide(chemin_dossier):
    """Supprime un dossier qui ne contient aucun fichier, sous-dossiers vides compris.

    `os.rmdir` refuse de supprimer un dossier qui n'est pas vide : meme
    appelee par erreur sur un dossier contenant une photo, cette fonction ne
    peut donc rien effacer d'autre que des dossiers vides. `topdown=False`
    parcourt les sous-dossiers du plus profond au moins profond : chacun est
    deja vide quand vient son tour.
    """
    for dossier, _, _ in os.walk(chemin_dossier, topdown=False):
        os.rmdir(dossier)


def nom_de_copie_disponible(dossier_evenement, nom_dossier):
    """Propose « X - copie », puis « X - copie 2 »... tant que le nom est pris."""
    candidat = "%s - copie" % nom_dossier
    numero = 2
    while os.path.exists(os.path.join(dossier_evenement, candidat)):
        candidat = "%s - copie %d" % (nom_dossier, numero)
        numero += 1
    return candidat


def fichiers_a_copier(chemin_dossier):
    """Fichiers poses directement dans le dossier ; les sous-dossiers sont ignores."""
    if not os.path.isdir(chemin_dossier):
        return []
    with os.scandir(chemin_dossier) as entrees:
        return sorted(entree.name for entree in entrees if entree.is_file())


def dupliquer_dossier(parent, dossier_evenement, nom_source, nom_destination):
    """Copie un dossier de l'evenement sous un nouveau nom, en montrant l'avancement.

    La copie se fait fichier par fichier plutot qu'en un seul appel : c'est le
    seul moyen d'afficher un decompte, ce qui est indispensable quand le dossier
    contient plusieurs milliers de photos et que la copie dure plusieurs
    minutes. `copy2` conserve les dates des fichiers, dont depend l'ordre des
    photos.

    Renvoie le nombre de fichiers copies.
    """
    chemin_source = os.path.join(dossier_evenement, nom_source)
    chemin_destination = os.path.join(dossier_evenement, nom_destination)
    noms = fichiers_a_copier(chemin_source)

    attente = tk.Toplevel(parent)
    attente.title("Duplication")
    attente.resizable(False, False)
    attente.transient(parent)
    attente.protocol("WM_DELETE_WINDOW", lambda: None)   # on ne ferme pas en pleine copie
    theme.habiller(attente)

    cadre = ttk.Frame(attente, padding=theme.MARGE)
    cadre.grid(row=0, column=0)
    ttk.Label(cadre, text="Copie de « %s » vers « %s »" % (nom_source, nom_destination),
              font=police(11, gras=True)).grid(row=0, column=0)
    etiquette = ttk.Label(cadre, text="Preparation...", style="Doux.TLabel")
    etiquette.grid(row=1, column=0, pady=(10, 0))
    theme.centrer(attente, parent)
    attente.grab_set()
    attente.update()

    try:
        os.makedirs(chemin_destination)
        try:
            for numero, nom in enumerate(noms, start=1):
                shutil.copy2(os.path.join(chemin_source, nom),
                             os.path.join(chemin_destination, nom))
                # Rafraichir l'affichage a chaque fichier couterait plus cher que
                # la copie elle-meme sur les petites photos : une fois sur dix suffit.
                if numero % 10 == 0 or numero == len(noms):
                    etiquette.config(text="%d fichier(s) sur %d" % (numero, len(noms)))
                    attente.update()
        except OSError:
            # Copie interrompue (fichier occupe, disque plein) : le dossier a
            # moitie rempli, que l'on vient de creer, ne contient que des
            # copies. Laisse en place, il n'etait ni note dans l'evenement ni
            # propose a la revue, et son nom restait pris.
            shutil.rmtree(chemin_destination, ignore_errors=True)
            raise
    finally:
        attente.grab_release()
        attente.destroy()

    return len(noms)
