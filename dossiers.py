"""
Operations sur les dossiers : choix, nommage et duplication.

Ce module regroupe trois besoins qui portent tous sur des dossiers :

1. verifier qu'un nom peut servir de nom de dossier ;
2. demander un dossier a l'utilisateur sans que le programme « s'y installe » ;
3. dupliquer un dossier de l'evenement, avec un decompte d'avancement.

La duplication sert surtout a garder les originaux intacts : on copie un dossier
de tri avant de censurer l'un des deux exemplaires.
"""

import os
import shutil
import tkinter as tk
from tkinter import filedialog, ttk

# Caracteres interdits dans un nom de dossier sous Windows.
CARACTERES_INTERDITS = set('\\/:*?"<>|')


def nom_de_dossier_valide(nom):
    """Le nom peut-il servir de nom de dossier ?"""
    if not nom or nom.strip() != nom:
        return False
    if any(caractere in CARACTERES_INTERDITS for caractere in nom):
        return False
    # Un nom termine par un point ou un espace pose probleme sous Windows.
    return not nom.endswith(".")


def choisir_dossier(titre, parent):
    """Demande un dossier a l'utilisateur, sans deplacer le dossier courant.

    Sous Windows, le dossier courant d'un programme en cours d'execution est
    considere comme « ouvert » : il ne peut plus etre deplace, renomme ni
    supprime, et l'explorateur repond qu'un fichier ou un dossier est ouvert.
    Or la boite de dialogue de choix de dossier peut, selon les versions de
    Windows, deplacer le dossier courant vers le dossier choisi. On note donc
    le dossier courant avant d'ouvrir la boite, et on le remet apres.

    Renvoie le chemin choisi, ou une chaine vide si l'utilisateur a annule.
    """
    dossier_courant = os.getcwd()
    try:
        choisi = filedialog.askdirectory(title=titre, parent=parent)
    finally:
        os.chdir(dossier_courant)

    return os.path.normpath(choisi) if choisi else ""


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
    return sorted(nom for nom in os.listdir(chemin_dossier)
                  if os.path.isfile(os.path.join(chemin_dossier, nom)))


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
    attente.grab_set()
    attente.protocol("WM_DELETE_WINDOW", lambda: None)   # on ne ferme pas en pleine copie

    cadre = ttk.Frame(attente, padding=24)
    cadre.grid(row=0, column=0)
    ttk.Label(cadre, text="Copie de « %s » vers « %s »" % (nom_source, nom_destination),
              font=("Segoe UI", 10, "bold")).grid(row=0, column=0)
    etiquette = ttk.Label(cadre, text="Preparation...")
    etiquette.grid(row=1, column=0, pady=(8, 0))
    attente.update()

    try:
        os.makedirs(chemin_destination)
        for numero, nom in enumerate(noms, start=1):
            shutil.copy2(os.path.join(chemin_source, nom),
                         os.path.join(chemin_destination, nom))
            # Rafraichir l'affichage a chaque fichier couterait plus cher que la
            # copie elle-meme sur les petites photos : une fois sur dix suffit.
            if numero % 10 == 0 or numero == len(noms):
                etiquette.config(text="%d fichier(s) sur %d" % (numero, len(noms)))
                attente.update()
    finally:
        attente.grab_release()
        attente.destroy()

    return len(noms)
