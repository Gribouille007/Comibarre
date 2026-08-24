"""
Ecran de configuration d'un nouvel evenement (section 6).

L'utilisateur y choisit le dossier source, donne un nom a l'evenement, et
definit ses quatre dossiers de tri avec la touche associee a chacun.

L'ecran ne laisse passer a la suite que si toutes les conditions de la section 6
sont remplies ; sinon il explique ce qui manque.
"""

import os
import tkinter as tk
from tkinter import ttk

from dossiers import choisir_dossier, nom_de_dossier_valide

# Valeurs proposees par defaut, que l'utilisateur peut modifier librement.
DOSSIERS_PAR_DEFAUT = [
    ("A garder", "1"),
    ("Ratees", "2"),
    ("A revoir", "3"),
    ("A supprimer", "4"),
]


class EcranConfiguration:
    """Fenetre de saisie de la configuration d'un nouvel evenement."""

    def __init__(self, racine):
        self.resultat = None

        self.fenetre = tk.Toplevel(racine)
        self.fenetre.title("Nouvel evenement - configuration")
        self.fenetre.resizable(False, False)

        self.variable_dossier = tk.StringVar()
        self.variable_nom = tk.StringVar()
        self.variables_noms = []
        self.variables_touches = []

        self._construire()
        self.fenetre.protocol("WM_DELETE_WINDOW", self._annuler)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _construire(self):
        cadre = ttk.Frame(self.fenetre, padding=16)
        cadre.grid(row=0, column=0, sticky="nsew")

        ttk.Label(cadre, text="Configuration d'un nouvel evenement",
                  font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=3,
                                                      sticky="w", pady=(0, 12))

        # -- dossier source --
        ttk.Label(cadre, text="Dossier source :").grid(row=1, column=0, sticky="w")
        ttk.Entry(cadre, textvariable=self.variable_dossier, width=44,
                  state="readonly").grid(row=1, column=1, sticky="we", padx=6)
        ttk.Button(cadre, text="Choisir...",
                   command=self._choisir_dossier).grid(row=1, column=2)

        # -- nom de l'evenement --
        ttk.Label(cadre, text="Nom de l'evenement :").grid(row=2, column=0,
                                                           sticky="w", pady=(10, 0))
        ttk.Entry(cadre, textvariable=self.variable_nom, width=44).grid(
            row=2, column=1, sticky="we", padx=6, pady=(10, 0))

        # -- les quatre dossiers de tri --
        ttk.Label(cadre, text="Dossiers de tri (nom et touche associee) :").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(16, 4))

        entetes = ttk.Frame(cadre)
        entetes.grid(row=4, column=0, columnspan=3, sticky="we")
        ttk.Label(entetes, text="Nom du dossier", width=34).grid(row=0, column=1)
        ttk.Label(entetes, text="Touche", width=8).grid(row=0, column=2)

        for numero, (nom_defaut, touche_defaut) in enumerate(DOSSIERS_PAR_DEFAUT):
            variable_nom = tk.StringVar(value=nom_defaut)
            variable_touche = tk.StringVar(value=touche_defaut)
            self.variables_noms.append(variable_nom)
            self.variables_touches.append(variable_touche)

            ligne = ttk.Frame(cadre)
            ligne.grid(row=5 + numero, column=0, columnspan=3, sticky="we", pady=2)
            ttk.Label(ligne, text="%d." % (numero + 1), width=3).grid(row=0, column=0)
            ttk.Entry(ligne, textvariable=variable_nom, width=34).grid(row=0, column=1)
            champ_touche = ttk.Entry(ligne, textvariable=variable_touche, width=6,
                                     justify="center")
            champ_touche.grid(row=0, column=2, padx=(10, 0))
            # Une touche ne fait qu'un seul caractere : on tronque a la saisie.
            variable_touche.trace_add(
                "write",
                lambda *_, variable=variable_touche: self._limiter_a_un_caractere(variable))

        # -- message d'erreur --
        self.etiquette_erreur = ttk.Label(cadre, text="", foreground="#b00020",
                                          wraplength=460, justify="left")
        self.etiquette_erreur.grid(row=10, column=0, columnspan=3, sticky="w",
                                   pady=(14, 0))

        # -- boutons --
        boutons = ttk.Frame(cadre)
        boutons.grid(row=11, column=0, columnspan=3, sticky="e", pady=(16, 0))
        ttk.Button(boutons, text="Annuler", command=self._annuler).grid(row=0, column=0,
                                                                       padx=(0, 8))
        ttk.Button(boutons, text="Continuer", command=self._valider).grid(row=0, column=1)

    @staticmethod
    def _limiter_a_un_caractere(variable):
        valeur = variable.get()
        if len(valeur) > 1:
            variable.set(valeur[-1])

    def _choisir_dossier(self):
        dossier = choisir_dossier("Choisir le dossier contenant les photos",
                                  self.fenetre)
        if dossier:
            self.variable_dossier.set(dossier)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _erreurs(self):
        """Renvoie la liste des conditions de la section 6 qui ne sont pas remplies."""
        erreurs = []

        dossier = self.variable_dossier.get()
        if not dossier:
            erreurs.append("Choisissez un dossier source.")
        elif not os.path.isdir(dossier):
            erreurs.append("Le dossier source n'existe pas.")
        elif not any(os.path.isfile(os.path.join(dossier, nom))
                     for nom in os.listdir(dossier)):
            erreurs.append("Le dossier source ne contient aucun fichier.")

        nom_evenement = self.variable_nom.get().strip()
        if not nom_evenement:
            erreurs.append("Donnez un nom a l'evenement.")
        elif not nom_de_dossier_valide(nom_evenement):
            erreurs.append("Le nom de l'evenement ne peut pas servir de nom de "
                           "dossier (caracteres interdits : \\ / : * ? \" < > |).")

        noms = [variable.get().strip() for variable in self.variables_noms]
        touches = [variable.get().strip() for variable in self.variables_touches]

        if any(not nom for nom in noms):
            erreurs.append("Les quatre dossiers de tri doivent avoir un nom.")
        elif any(not nom_de_dossier_valide(nom) for nom in noms):
            erreurs.append("Un nom de dossier de tri contient un caractere interdit.")
        elif len({nom.lower() for nom in noms}) != 4:
            erreurs.append("Les quatre dossiers de tri doivent avoir des noms differents.")

        if any(not touche for touche in touches):
            erreurs.append("Les quatre touches doivent etre renseignees.")
        elif len({touche.lower() for touche in touches}) != 4:
            erreurs.append("Une meme touche ne peut pas servir deux fois.")

        return erreurs

    def _valider(self):
        erreurs = self._erreurs()
        if erreurs:
            self.etiquette_erreur.config(text="\n".join("- " + e for e in erreurs))
            return

        self.resultat = {
            "dossier_source": self.variable_dossier.get(),
            "nom_evenement": self.variable_nom.get().strip(),
            "dossiers_tri": [
                {"nom": nom.get().strip(), "touche": touche.get().strip()}
                for nom, touche in zip(self.variables_noms, self.variables_touches)
            ],
        }
        self.fenetre.destroy()

    def _annuler(self):
        self.resultat = None
        self.fenetre.destroy()


def demander_configuration(racine):
    """Affiche l'ecran et attend sa fermeture. Renvoie la configuration ou None."""
    ecran = EcranConfiguration(racine)
    racine.wait_window(ecran.fenetre)
    return ecran.resultat
