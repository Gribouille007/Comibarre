"""
Saisie des dossiers de tri : la liste modifiable de l'ecran de configuration
et de la gestion des dossiers, et la petite boite qui cree un dossier pendant
le tri (touche N).

Chaque dossier occupe une ligne : son nom, sa touche, et un bouton pour le
retirer ; un bouton en dessous en ajoute un. Les regles (noms valides, touches
uniques...) sont celles de dossiers_tri.py, communes a tout le logiciel.
"""

import tkinter as tk
from tkinter import messagebox, ttk

import dossiers_tri
import theme


def limiter_a_un_caractere(variable):
    """Une touche ne fait qu'un caractere : le dernier tape remplace le precedent."""
    valeur = variable.get()
    if len(valeur) > 1:
        variable.set(valeur[-1])


class EditeurDossiers:
    """Liste de dossiers de tri modifiable : un nom et une touche par ligne."""

    def __init__(self, parent, dossiers, peut_retirer=None, information=None):
        """
        parent       : widget dans lequel la liste est placee (voir `cadre`).
        dossiers     : [{"nom", "touche"}] pour remplir les premieres lignes. La
                       cle facultative "origine" garde le nom d'un dossier qui
                       existe deja sur le disque (gestion depuis le menu).
        peut_retirer : facultatif, (origine) -> message expliquant pourquoi ce
                       dossier existant ne peut pas etre retire, ou None.
        information  : facultatif, (origine) -> court texte affiche en bout de
                       ligne, comme le nombre de photos du dossier.
        """
        self.peut_retirer = peut_retirer
        self.information = information
        self.lignes = []

        self.cadre = ttk.Frame(parent)
        entetes = ttk.Frame(self.cadre)
        entetes.grid(row=0, column=0, sticky="w")
        ttk.Label(entetes, text="", width=3).grid(row=0, column=0)
        ttk.Label(entetes, text="Nom du dossier", style="Doux.TLabel",
                  width=32).grid(row=0, column=1, sticky="w")
        ttk.Label(entetes, text="Touche", style="Doux.TLabel").grid(row=0, column=2, sticky="w")

        self.cadre_lignes = ttk.Frame(self.cadre)
        self.cadre_lignes.grid(row=1, column=0, sticky="w")
        self.bouton_ajouter = ttk.Button(self.cadre, text="+  Ajouter un dossier",
                                         command=self.ajouter)
        self.bouton_ajouter.grid(row=2, column=0, sticky="w", pady=(8, 0))

        for dossier in dossiers:
            self._creer_ligne(dossier["nom"], dossier["touche"], dossier.get("origine"))
        self._replacer_les_lignes()

    # ------------------------------------------------------------------

    def dossiers(self):
        """Contenu actuel : [{"nom", "touche", "origine"}], dans l'ordre des lignes."""
        return [{"nom": ligne["nom"].get().strip(),
                 "touche": ligne["touche"].get().strip(),
                 "origine": ligne["origine"]}
                for ligne in self.lignes]

    def ajouter(self):
        """Ajoute une ligne vide, avec une touche libre deja proposee."""
        if len(self.lignes) >= dossiers_tri.NOMBRE_MAXIMAL:
            return
        ligne = self._creer_ligne("", dossiers_tri.touche_libre(self.dossiers()), None)
        self._replacer_les_lignes()
        ligne["champ_nom"].focus_set()

    def _creer_ligne(self, nom, touche, origine):
        ligne = {"nom": tk.StringVar(value=nom),
                 "touche": tk.StringVar(value=touche),
                 "origine": origine}
        ligne["numero"] = ttk.Label(self.cadre_lignes, width=3)
        ligne["champ_nom"] = ttk.Entry(self.cadre_lignes, textvariable=ligne["nom"], width=32)
        ligne["champ_touche"] = ttk.Entry(self.cadre_lignes, textvariable=ligne["touche"],
                                          width=6, justify="center")
        texte = ""
        if self.information is not None and origine is not None:
            texte = self.information(origine)
        ligne["info"] = ttk.Label(self.cadre_lignes, text=texte, style="Doux.TLabel", width=12)
        ligne["bouton"] = ttk.Button(self.cadre_lignes, text="Retirer", width=9,
                                     command=lambda: self._retirer(ligne))
        ligne["touche"].trace_add(
            "write", lambda *_: limiter_a_un_caractere(ligne["touche"]))
        self.lignes.append(ligne)
        return ligne

    def _retirer(self, ligne):
        """Retire une ligne, sauf s'il n'en resterait aucune, ou si son dossier est refuse."""
        if len(self.lignes) <= 1:
            messagebox.showinfo("Dossier de tri", "Il faut garder au moins un dossier de tri.",
                                parent=self.cadre.winfo_toplevel())
            return
        if ligne["origine"] is not None and self.peut_retirer is not None:
            refus = self.peut_retirer(ligne["origine"])
            if refus:
                messagebox.showwarning("Dossier non vide", refus,
                                       parent=self.cadre.winfo_toplevel())
                return
        for cle in ("numero", "champ_nom", "champ_touche", "info", "bouton"):
            ligne[cle].destroy()
        self.lignes.remove(ligne)
        self._replacer_les_lignes()

    def _replacer_les_lignes(self):
        """Renumerote les lignes et les replace les unes sous les autres."""
        for rang, ligne in enumerate(self.lignes):
            ligne["numero"].config(text="%d." % (rang + 1))
            ligne["numero"].grid(row=rang, column=0, pady=2)
            ligne["champ_nom"].grid(row=rang, column=1, pady=2)
            ligne["champ_touche"].grid(row=rang, column=2, padx=(10, 0), pady=2)
            ligne["info"].grid(row=rang, column=3, padx=(10, 0), pady=2, sticky="w")
            ligne["bouton"].grid(row=rang, column=4, padx=(6, 0), pady=2)
        etat = "normal" if len(self.lignes) < dossiers_tri.NOMBRE_MAXIMAL else "disabled"
        self.bouton_ajouter.config(state=etat)


def demander_nouveau_dossier(parent, suivi):
    """Boite de creation d'un dossier de tri pendant le tri (touche N).

    Demande le nom et la touche du nouveau dossier, avec une touche libre deja
    proposee. Les memes regles qu'a la configuration s'appliquent ; tant
    qu'elles ne sont pas respectees, la boite reste ouverte et dit pourquoi.

    Renvoie {"nom", "touche"}, ou None si l'utilisateur renonce.
    """
    boite = tk.Toplevel(parent)
    boite.title("Nouveau dossier de tri")
    boite.resizable(False, False)
    boite.transient(parent)
    theme.habiller(boite)

    nom = tk.StringVar()
    touche = tk.StringVar(value=dossiers_tri.touche_libre(suivi.dossiers_tri))
    touche.trace_add("write", lambda *_: limiter_a_un_caractere(touche))
    reponse = {"dossier": None}

    cadre = ttk.Frame(boite, padding=theme.MARGE)
    cadre.grid(row=0, column=0)
    ttk.Label(cadre, text="Nouveau dossier de tri", style="Titre.TLabel").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))
    ttk.Label(cadre, text="Nom du dossier :").grid(row=1, column=0, sticky="w")
    champ_nom = ttk.Entry(cadre, textvariable=nom, width=32)
    champ_nom.grid(row=1, column=1, sticky="w", padx=(8, 0))
    ttk.Label(cadre, text="Touche :").grid(row=2, column=0, sticky="w", pady=(8, 0))
    ttk.Entry(cadre, textvariable=touche, width=6, justify="center").grid(
        row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
    ttk.Label(cadre, text="Il sera aussi propose pour vos prochains evenements.",
              style="Doux.TLabel").grid(row=3, column=0, columnspan=2, sticky="w",
                                        pady=(12, 0))
    etiquette_erreur = ttk.Label(cadre, text="", style="Alerte.TLabel",
                                 wraplength=380, justify="left")
    etiquette_erreur.grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def valider():
        nouveau = {"nom": nom.get().strip(), "touche": touche.get().strip()}
        erreurs = (dossiers_tri.erreurs_des_dossiers(suivi.dossiers_tri + [nouveau])
                   + dossiers_tri.erreurs_sur_le_disque([nouveau], suivi.dossier_evenement)
                   + dossiers_tri.erreurs_avec_les_copies([nouveau],
                                                          suivi.dossiers_dupliques))
        if erreurs:
            etiquette_erreur.config(text="\n".join(erreurs))
            return
        reponse["dossier"] = nouveau
        boite.destroy()

    boutons = ttk.Frame(cadre)
    boutons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(16, 0))
    ttk.Button(boutons, text="Annuler", width=12,
               command=boite.destroy).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(boutons, text="Creer", width=12, style="Accent.TButton",
               command=valider).grid(row=0, column=1)

    boite.bind("<Return>", lambda evenement: valider())
    boite.bind("<KP_Enter>", lambda evenement: valider())
    boite.bind("<Escape>", lambda evenement: boite.destroy())

    # Le placement doit preceder la capture du clavier, sinon on voit la boite
    # sauter sous les yeux de l'utilisateur.
    theme.centrer(boite, parent)
    champ_nom.focus_set()
    boite.grab_set()
    parent.wait_window(boite)
    return reponse["dossier"]
