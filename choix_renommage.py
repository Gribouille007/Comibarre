"""
Choix du format des noms des photos (voir renommage.py).

Le meme petit bloc sert a l'ecran de configuration d'un nouvel evenement et a
la boite « Renommer les photos » du menu : une ligne par format, et sous la
liste un exemple des noms que donnera le format choisi.
"""

import tkinter as tk
from tkinter import ttk

import renommage


class ChoixDuRenommage:
    """Liste des formats de noms, avec un exemple du format choisi."""

    def __init__(self, parent, format_initial, nom_evenement="", formats=None):
        """
        formats : formats proposes, tous par defaut. Le menu n'en propose pas
                  « aucun » : on ne peut pas rendre leur nom d'origine a des
                  photos deja renommees.
        """
        self.cadre = ttk.Frame(parent)
        self.nom_evenement = nom_evenement
        proposes = formats or [nom_format for nom_format, _ in renommage.FORMATS]
        if format_initial not in proposes:
            format_initial = proposes[0]
        self.variable = tk.StringVar(value=format_initial)

        for rang, nom_format in enumerate(proposes):
            ttk.Radiobutton(self.cadre, text=renommage.libelle(nom_format),
                            value=nom_format, variable=self.variable,
                            command=self._montrer_l_exemple).grid(
                row=rang, column=0, sticky="w", pady=1)

        self.etiquette_exemple = ttk.Label(self.cadre, text="", style="Doux.TLabel",
                                           wraplength=560, justify="left")
        self.etiquette_exemple.grid(row=len(proposes), column=0, sticky="w", pady=(6, 0))
        self._montrer_l_exemple()

    def nom_format(self):
        return self.variable.get()

    def changer_nom_evenement(self, nom_evenement):
        """L'exemple du format « evenement » suit le nom saisi."""
        self.nom_evenement = nom_evenement
        self._montrer_l_exemple()

    def _montrer_l_exemple(self):
        self.etiquette_exemple.config(
            text="Exemple : " + renommage.exemple(self.variable.get(), self.nom_evenement))
