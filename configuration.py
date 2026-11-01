"""
Ecran de configuration d'un nouvel evenement (section 6).

L'utilisateur y choisit le dossier de ses photos, donne un nom a l'evenement,
et definit ses dossiers de tri avec la touche associee a chacun : autant qu'il
le souhaite, de 1 a 12 (dossiers_tri.py). La liste proposee est celle de la
derniere fois (preferences.py).

Le dossier des photos devient le dossier de l'evenement : il sera renomme du
nom de l'evenement, et les dossiers de tri seront crees directement dedans
(decision de l'utilisateur, 26 octobre 2026). L'ecran annonce ce renommage
avant qu'il ait lieu.

L'ecran ne laisse passer a la suite que si toutes les conditions sont
remplies ; sinon il explique ce qui manque.
"""

import os
import tkinter as tk
from tkinter import ttk

import dossiers_tri
import preferences
import theme
from dossiers import choisir_dossier, probleme_du_nom
from editeur_dossiers import EditeurDossiers
from suivi import Suivi
from synchronisation import service_de_synchronisation


class EcranConfiguration:
    """Fenetre de saisie de la configuration d'un nouvel evenement."""

    def __init__(self, racine, parent=None):
        self.resultat = None

        self.racine = racine
        self.fenetre = tk.Toplevel(racine)
        self.fenetre.title("Nouvel evenement - configuration")
        self.fenetre.resizable(False, False)
        if parent is not None:
            self.fenetre.transient(parent)
        theme.habiller(self.fenetre)

        self.variable_dossier = tk.StringVar()
        self.variable_nom = tk.StringVar()

        self._construire()
        self.variable_dossier.trace_add("write", lambda *_: self._annoncer())
        self.variable_nom.trace_add("write", lambda *_: self._annoncer())
        self.fenetre.protocol("WM_DELETE_WINDOW", self._annuler)
        self.fenetre.bind("<Escape>", lambda evenement: self._annuler())
        theme.centrer(self.fenetre, parent or racine)
        # Fenetre modale : un clic sur l'ecran d'accueil, reste accessible,
        # ouvrait une seconde configuration, ou reprenait un evenement par-dessous.
        self.fenetre.grab_set()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _construire(self):
        cadre = ttk.Frame(self.fenetre, padding=theme.MARGE)
        cadre.grid(row=0, column=0, sticky="nsew")

        ttk.Label(cadre, text="Configuration d'un nouvel evenement",
                  style="Titre.TLabel").grid(row=0, column=0, columnspan=3,
                                             sticky="w", pady=(0, 16))

        # -- dossier des photos --
        ttk.Label(cadre, text="Dossier des photos :").grid(row=1, column=0, sticky="w")
        ttk.Entry(cadre, textvariable=self.variable_dossier, width=48,
                  state="readonly").grid(row=1, column=1, sticky="we", padx=6)
        ttk.Button(cadre, text="Choisir...",
                   command=self._choisir_dossier).grid(row=1, column=2)

        # -- nom de l'evenement --
        ttk.Label(cadre, text="Nom de l'evenement :").grid(row=2, column=0,
                                                           sticky="w", pady=(10, 0))
        ttk.Entry(cadre, textvariable=self.variable_nom, width=48).grid(
            row=2, column=1, sticky="we", padx=6, pady=(10, 0))

        # Ce qui va arriver au dossier : renomme ou non, synchronise ou non.
        self.etiquette_annonce = ttk.Label(cadre, text="", style="Doux.TLabel",
                                           wraplength=560, justify="left")
        self.etiquette_annonce.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # -- les dossiers de tri --
        ttk.Label(cadre, text="Dossiers de tri (nom et touche associee) :").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(16, 6))
        dossiers = preferences.dossiers_de_tri() or dossiers_tri.DOSSIERS_PAR_DEFAUT
        self.editeur = EditeurDossiers(cadre, dossiers)
        self.editeur.cadre.grid(row=5, column=0, columnspan=3, sticky="w")
        ttk.Label(cadre, text="Ces dossiers vous seront proposes de nouveau la prochaine "
                              "fois. Touches reservees : R, C et N.",
                  style="Doux.TLabel").grid(row=6, column=0, columnspan=3, sticky="w",
                                            pady=(8, 0))

        # -- message d'erreur --
        self.etiquette_erreur = ttk.Label(cadre, text="", style="Alerte.TLabel",
                                          wraplength=560, justify="left")
        self.etiquette_erreur.grid(row=7, column=0, columnspan=3, sticky="w",
                                   pady=(14, 0))

        # -- boutons --
        boutons = ttk.Frame(cadre)
        boutons.grid(row=8, column=0, columnspan=3, sticky="e", pady=(18, 0))
        ttk.Button(boutons, text="Annuler", width=14,
                   command=self._annuler).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(boutons, text="Continuer", width=14, style="Accent.TButton",
                   command=self._valider).grid(row=0, column=1)

    def _choisir_dossier(self):
        dossier = choisir_dossier("Choisir le dossier contenant les photos", self.fenetre,
                                  preferences.dossier_des_photos())
        if not dossier:
            return
        self.variable_dossier.set(dossier)
        # Le nom du dossier est propose comme nom de l'evenement : s'il convient,
        # le dossier n'a pas a etre renomme.
        if not self.variable_nom.get().strip():
            self.variable_nom.set(os.path.basename(dossier))

    def _annoncer(self):
        """Dit ce qui va arriver au dossier : renomme ou non, et s'il est synchronise."""
        dossier = self.variable_dossier.get()
        nom = self.variable_nom.get().strip()
        lignes = []
        if dossier and nom and dans_un_autre_evenement(dossier):
            lignes.append("Ce dossier appartient a un autre evenement : il gardera son nom, "
                          "pour ne pas desorganiser cet evenement. Les dossiers de tri "
                          "seront crees dedans.")
        elif dossier and nom and os.path.basename(dossier) != nom:
            lignes.append("Le dossier « %s » sera renomme « %s », et les dossiers de tri "
                          "seront crees dedans." % (os.path.basename(dossier), nom))
        elif dossier and nom:
            lignes.append("Les dossiers de tri seront crees dans ce dossier.")
        service = service_de_synchronisation(dossier) if dossier else None
        if service:
            lignes.append("Attention : ce dossier est synchronise par %s, qui peut remettre "
                          "des photos rangees dans le dossier source. Suspendez la "
                          "synchronisation pendant le tri." % service)
        self.etiquette_annonce.config(text="\n".join(lignes))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _erreurs(self):
        """Renvoie la liste des conditions qui ne sont pas remplies."""
        erreurs = []

        dossier = self.variable_dossier.get()
        if not dossier:
            erreurs.append("Choisissez le dossier des photos.")
        elif not os.path.isdir(dossier):
            erreurs.append("Le dossier des photos n'existe pas.")
        elif Suivi.existe(dossier) or contient_un_ancien_evenement(dossier):
            erreurs.append("Ce dossier contient deja un evenement : reprenez-le depuis "
                           "l'ecran d'accueil.")
        elif not any(os.path.isfile(os.path.join(dossier, nom))
                     for nom in os.listdir(dossier)):
            erreurs.append("Le dossier des photos ne contient aucun fichier.")

        nom_evenement = self.variable_nom.get().strip()
        probleme = probleme_du_nom(nom_evenement) if nom_evenement else None
        if not nom_evenement:
            erreurs.append("Donnez un nom a l'evenement.")
        elif probleme is not None:
            erreurs.append("Nom de l'evenement : %s." % probleme)
        elif dossier and os.path.isdir(dossier) and not dans_un_autre_evenement(dossier):
            voisin = os.path.join(os.path.dirname(dossier), nom_evenement)
            if os.path.exists(voisin) and not os.path.samefile(voisin, dossier):
                erreurs.append("Un dossier « %s » existe deja a cote du dossier des photos : "
                               "choisissez un autre nom d'evenement." % nom_evenement)

        dossiers = self.editeur.dossiers()
        erreurs += dossiers_tri.erreurs_des_dossiers(dossiers)
        if dossier and os.path.isdir(dossier):
            erreurs += dossiers_tri.erreurs_sur_le_disque(dossiers, dossier)
        return erreurs

    def _valider(self):
        erreurs = self._erreurs()
        if erreurs:
            self.etiquette_erreur.config(text="\n".join("- " + e for e in erreurs))
            return

        self.resultat = {
            "dossier_source": self.variable_dossier.get(),
            "nom_evenement": self.variable_nom.get().strip(),
            "dossiers_tri": [{"nom": dossier["nom"], "touche": dossier["touche"]}
                             for dossier in self.editeur.dossiers()],
        }
        self.fenetre.destroy()

    def _annuler(self):
        self.resultat = None
        self.fenetre.destroy()


def dans_un_autre_evenement(dossier):
    """Le dossier est-il un dossier d'un autre evenement (un de ses dossiers de tri) ?

    On peut vouloir retrier finement les photos d'un dossier de tri, en en
    faisant un nouvel evenement. Mais le renommer desorganiserait l'evenement
    dont il fait partie, qui le designe par son nom : il garde donc son nom.
    """
    return Suivi.existe(os.path.dirname(dossier))


def contient_un_ancien_evenement(dossier):
    """Le dossier contient-il un evenement de l'ancienne organisation (version 1) ?

    Avant le 26 octobre 2026, l'evenement vivait dans un sous-dossier du
    dossier des photos. Demarrer un nouvel evenement sur ce meme dossier
    ferait trier les memes photos par deux evenements a la fois.
    """
    try:
        noms = os.listdir(dossier)
    except OSError:
        return False
    return any(Suivi.existe(os.path.join(dossier, nom)) for nom in noms)


def demander_configuration(racine, parent=None):
    """Affiche l'ecran et attend sa fermeture. Renvoie la configuration ou None."""
    ecran = EcranConfiguration(racine, parent)
    racine.wait_window(ecran.fenetre)
    return ecran.resultat
