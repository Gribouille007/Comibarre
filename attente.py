"""
Fenetre d'attente pour les travaux longs (preparation, renommage).

Lire la date de 3 000 photos puis les renommer peut durer plusieurs minutes,
plus encore dans un dossier OneDrive dont les photos doivent d'abord etre
telechargees. Fait sur le fil principal, ce travail figeait la fenetre, que
Windows declarait alors « ne repond pas ». Il tourne donc sur un fil separe,
qui ne touche jamais a l'interface ; la fenetre d'attente est rafraichie ici,
sur le fil principal, avec le dernier etat annonce par le travail.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk

import theme
from polices import police


def executer_avec_attente(parent, titre, travail):
    """Execute travail(avancement) en arriere-plan, en montrant ou il en est.

    `travail` recoit une fonction `avancement(texte)`, qu'il appelle de temps
    en temps avec un court texte (« Renommage : 120 sur 600 »).

    Renvoie (resultat, erreur) : `erreur` vaut None si tout s'est bien passe,
    sinon l'exception levee par le travail, et le resultat vaut alors None.
    """
    attente = tk.Toplevel(parent)
    attente.title(titre)
    attente.resizable(False, False)
    attente.transient(parent)
    # On n'interrompt pas un renommage en cours.
    attente.protocol("WM_DELETE_WINDOW", lambda: None)
    theme.habiller(attente)
    cadre = ttk.Frame(attente, padding=theme.MARGE)
    cadre.grid(row=0, column=0)
    ttk.Label(cadre, text="%s en cours..." % titre, font=police(11, gras=True)).grid(
        row=0, column=0)
    etiquette = ttk.Label(cadre, text="", style="Doux.TLabel", width=46, anchor="center")
    etiquette.grid(row=1, column=0, pady=(10, 0))
    theme.centrer(attente, parent)
    attente.grab_set()

    etat = {"texte": "", "resultat": None, "erreur": None, "fini": False}

    def travailler():
        try:
            etat["resultat"] = travail(lambda texte: etat.update(texte=texte))
        except Exception as erreur:
            etat["erreur"] = erreur
        etat["fini"] = True

    fil = threading.Thread(target=travailler, daemon=True)
    fil.start()
    while not etat["fini"]:
        etiquette.config(text=etat["texte"])
        attente.update()
        time.sleep(0.05)
    fil.join()
    attente.grab_release()
    attente.destroy()
    return etat["resultat"], etat["erreur"]
