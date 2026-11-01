"""
Gestion des dossiers de tri d'un evenement deja commence (menu principal).

On peut y ajouter un dossier, en renommer un, changer sa touche, ou retirer un
dossier. Un dossier qui contient encore des fichiers ne peut pas etre retire
(decision de l'utilisateur, 26 octobre 2026) : aucune photo ne risque ainsi
d'etre deplacee ou perdue par megarde. Le dossier retire, vide, est supprime
du disque.

Les changements sont appliques d'un coup, a la validation, sur le disque puis
dans le fichier de suivi ; la nouvelle liste est aussi retenue pour les
prochains evenements (preferences.py).
"""

import os
import tkinter as tk
from tkinter import messagebox, ttk

import dossiers_tri
import preferences
import theme
from dossiers import contient_des_fichiers, photos_du_dossier, supprimer_dossier_vide
from editeur_dossiers import EditeurDossiers
from fichiers import renommer_dossier


def gerer_les_dossiers(parent, suivi):
    """Ouvre la fenetre de gestion et attend sa fermeture. Renvoie True si l'on a enregistre."""
    fenetre = FenetreGestionDossiers(parent, suivi)
    parent.wait_window(fenetre.fenetre)
    return fenetre.modifie


class FenetreGestionDossiers:
    """Boite modale listant les dossiers de tri de l'evenement, modifiables."""

    def __init__(self, parent, suivi):
        self.suivi = suivi
        self.modifie = False

        self.fenetre = tk.Toplevel(parent)
        self.fenetre.title("Dossiers de tri - %s" % suivi.nom_evenement)
        self.fenetre.resizable(False, False)
        self.fenetre.transient(parent)
        theme.habiller(self.fenetre)

        cadre = ttk.Frame(self.fenetre, padding=theme.MARGE)
        cadre.grid(row=0, column=0)
        ttk.Label(cadre, text="Dossiers de tri", style="Titre.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(cadre, text="Renommez un dossier, changez sa touche, ajoutez-en ou "
                              "retirez-en. Seul un dossier vide peut etre retire.",
                  style="Doux.TLabel", wraplength=560, justify="left").grid(
            row=1, column=0, sticky="w", pady=(0, 14))

        lignes = [{"nom": dossier["nom"], "touche": dossier["touche"],
                   "origine": dossier["nom"]} for dossier in suivi.dossiers_tri]
        self.editeur = EditeurDossiers(cadre, lignes, peut_retirer=self._refus_de_retrait,
                                       information=self._nombre_de_photos)
        self.editeur.cadre.grid(row=2, column=0, sticky="w")

        self.etiquette_erreur = ttk.Label(cadre, text="", style="Alerte.TLabel",
                                          wraplength=560, justify="left")
        self.etiquette_erreur.grid(row=3, column=0, sticky="w", pady=(14, 0))

        boutons = ttk.Frame(cadre)
        boutons.grid(row=4, column=0, sticky="e", pady=(18, 0))
        ttk.Button(boutons, text="Annuler", width=14,
                   command=self.fenetre.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(boutons, text="Enregistrer", width=14, style="Accent.TButton",
                   command=self._valider).grid(row=0, column=1)

        self.fenetre.bind("<Escape>", lambda evenement: self.fenetre.destroy())
        theme.centrer(self.fenetre, parent)
        self.fenetre.grab_set()

    def _nombre_de_photos(self, nom_dossier):
        nombre = len(photos_du_dossier(self.suivi.chemin_dossier(nom_dossier)))
        return "%d photo(s)" % nombre

    def _refus_de_retrait(self, nom_dossier):
        """Message expliquant pourquoi ce dossier ne peut pas etre retire, ou None."""
        chemin = self.suivi.chemin_dossier(nom_dossier)
        if os.path.isdir(chemin) and contient_des_fichiers(chemin):
            return ("Le dossier « %s » contient encore des fichiers : il ne peut pas etre "
                    "retire.\n\nVidez-le d'abord, par exemple en reclassant ses photos "
                    "en mode revue." % nom_dossier)
        return None

    def _valider(self):
        dossiers = self.editeur.dossiers()
        erreurs = (dossiers_tri.erreurs_des_dossiers(dossiers)
                   + dossiers_tri.erreurs_sur_le_disque(dossiers, self.suivi.dossier_evenement)
                   + dossiers_tri.erreurs_avec_les_copies(dossiers,
                                                          self.suivi.dossiers_dupliques)
                   + _erreurs_d_echange(dossiers))
        if erreurs:
            self.etiquette_erreur.config(text="\n".join("- " + e for e in erreurs))
            return
        try:
            appliquer(self.suivi, dossiers)
        except OSError as erreur:
            messagebox.showerror("Modification impossible",
                                 "Les dossiers n'ont pas pu etre tous modifies :\n%s\n\n"
                                 "Ce qui a deja ete fait a ete enregistre." % erreur,
                                 parent=self.fenetre)
        try:
            self.suivi.enregistrer()
        except OSError as erreur:
            # Les dossiers sont deja modifies sur le disque, et le suivi en
            # memoire les decrit : il sera reecrit a la prochaine action, ou en
            # quittant le menu. Rester ouvert ferait refuser un second essai,
            # les dossiers ayant deja leur nouveau nom.
            messagebox.showwarning("Suivi non enregistre",
                                   "Le fichier de suivi n'a pas pu etre enregistre :\n%s\n\n"
                                   "Il le sera a la prochaine action." % erreur,
                                   parent=self.fenetre)
        preferences.retenir_dossiers_de_tri(self.suivi.dossiers_tri)
        self.modifie = True
        self.fenetre.destroy()


def _erreurs_d_echange(dossiers):
    """Refuse de donner a un dossier le nom actuel d'un autre dossier de tri.

    Echanger deux noms d'un coup (A devient B, B devient A) demanderait un nom
    intermediaire : au moment de renommer A en B, B existe encore. Plutot que
    de compliquer l'operation pour un cas aussi rare, on demande de le faire
    en deux fois.
    """
    origines = {dossier["origine"].lower() for dossier in dossiers if dossier["origine"]}
    for dossier in dossiers:
        origine = dossier["origine"]
        if (origine and dossier["nom"].lower() != origine.lower()
                and dossier["nom"].lower() in origines):
            return ["« %s » est encore le nom d'un autre dossier de tri : pour echanger "
                    "deux noms, renommez d'abord l'un des deux sous un nom provisoire, "
                    "enregistrez, puis recommencez." % dossier["nom"]]
    return []


def appliquer(suivi, dossiers):
    """Applique la nouvelle liste de dossiers de tri, sur le disque et dans le suivi.

    `dossiers` : [{"nom", "touche", "origine"}], deja verifiee. "origine" est
    le nom actuel d'un dossier existant, ou None pour un dossier a creer.

    Ordre des operations : retraits, puis renommages, puis creations. Chaque
    etape met le suivi a jour aussitot : si l'une echoue, le suivi decrit
    exactement ce qui a deja ete fait.
    """
    gardes = {dossier["origine"] for dossier in dossiers if dossier["origine"] is not None}

    # 1. Retraits. Le dossier est verifie vide une derniere fois : il a pu
    #    recevoir des fichiers depuis l'ouverture de la fenetre.
    for nom in [nom for nom in suivi.noms_dossiers_tri if nom not in gardes]:
        chemin = suivi.chemin_dossier(nom)
        if os.path.isdir(chemin):
            if contient_des_fichiers(chemin):
                raise OSError("le dossier « %s » n'est pas vide" % nom)
            supprimer_dossier_vide(chemin)
        suivi.retirer_dossier_tri(nom)

    # 2. Renommages, sur le disque puis dans le suivi. Un dossier vide qui
    #    porterait deja le nouveau nom (la verification l'accepte) est d'abord
    #    supprime, sans quoi le renommage serait refuse.
    for dossier in dossiers:
        origine = dossier["origine"]
        if origine is None or origine == dossier["nom"]:
            continue
        chemin = suivi.chemin_dossier(origine)
        cible = suivi.chemin_dossier(dossier["nom"])
        if os.path.isdir(chemin):
            if (os.path.isdir(cible) and not os.path.samefile(chemin, cible)
                    and not contient_des_fichiers(cible)):
                supprimer_dossier_vide(cible)
            renommer_dossier(chemin, dossier["nom"])
        suivi.renommer_dossier_tri(origine, dossier["nom"])

    # 3. Creations, puis la liste definitive, dans l'ordre et avec les touches choisies.
    for dossier in dossiers:
        os.makedirs(suivi.chemin_dossier(dossier["nom"]), exist_ok=True)
    suivi.ordonner_dossiers_tri(dossiers)
