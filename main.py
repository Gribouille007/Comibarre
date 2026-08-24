"""
Programme principal : lancement, gestion des sessions et menu (sections 4 et 5).

Se lance simplement par :

    python main.py

Le deroule est toujours le meme : on demarre un nouvel evenement ou l'on reprend
un evenement existant, puis le menu principal propose le tri, la censure, ou de
quitter.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import preparation
from censure import lancer_censure, photos_du_dossier
from configuration import demander_configuration
from suivi import Suivi
from tri import lancer_tri


class EcranDemarrage:
    """Premiere fenetre : nouvel evenement ou reprise (section 5)."""

    def __init__(self, racine):
        self.racine = racine
        self.suivi = None

        self.fenetre = tk.Toplevel(racine)
        self.fenetre.title("Tri et censure de photos")
        self.fenetre.resizable(False, False)
        self.fenetre.protocol("WM_DELETE_WINDOW", self.fenetre.destroy)

        cadre = ttk.Frame(self.fenetre, padding=24)
        cadre.grid(row=0, column=0)

        ttk.Label(cadre, text="Tri et censure de photos",
                  font=("Segoe UI", 14, "bold")).grid(row=0, column=0, pady=(0, 4))
        ttk.Label(cadre, text="Que voulez-vous faire ?",
                  foreground="#555555").grid(row=1, column=0, pady=(0, 16))

        ttk.Button(cadre, text="Demarrer un nouvel evenement", width=34,
                   command=self._nouveau).grid(row=2, column=0, pady=4)
        ttk.Button(cadre, text="Reprendre un evenement existant", width=34,
                   command=self._reprendre).grid(row=3, column=0, pady=4)
        ttk.Button(cadre, text="Quitter", width=34,
                   command=self.fenetre.destroy).grid(row=4, column=0, pady=(16, 0))

    def _nouveau(self):
        configuration = demander_configuration(self.racine)
        if configuration is None:
            return

        dossier_evenement = os.path.join(configuration["dossier_source"],
                                         configuration["nom_evenement"])
        if Suivi.existe(dossier_evenement):
            messagebox.showerror(
                "Evenement deja existant",
                "Un evenement porte deja ce nom dans ce dossier.\n"
                "Choisissez un autre nom, ou reprenez l'evenement existant.",
                parent=self.fenetre)
            return

        suivi = Suivi.creer(configuration["dossier_source"],
                            configuration["nom_evenement"],
                            configuration["dossiers_tri"])

        rapport = self._preparer_avec_attente(suivi)
        if rapport is None:
            return

        messagebox.showinfo(
            "Preparation terminee",
            "Photos a trier : %d\n"
            "Fichiers RAW mis de cote : %d\n"
            "Videos mises de cote : %d"
            % (rapport["photos"], rapport["raw"], rapport["videos"]),
            parent=self.fenetre)

        self.suivi = suivi
        self.fenetre.destroy()

    def _preparer_avec_attente(self, suivi):
        """Lance la preparation automatique en affichant un message d'attente."""
        attente = tk.Toplevel(self.fenetre)
        attente.title("Preparation")
        attente.resizable(False, False)
        ttk.Label(attente, text="Preparation en cours...\n"
                                "Creation des dossiers, renommage des photos.",
                  padding=24, justify="center").grid(row=0, column=0)
        attente.update()

        try:
            rapport = preparation.preparer(suivi)
        except OSError as erreur:
            attente.destroy()
            messagebox.showerror("Erreur pendant la preparation", str(erreur),
                                 parent=self.fenetre)
            return None

        attente.destroy()
        return rapport

    def _reprendre(self):
        dossier = filedialog.askdirectory(
            title="Choisir le dossier de l'evenement a reprendre",
            parent=self.fenetre)
        if not dossier:
            return

        dossier = os.path.normpath(dossier)
        if not Suivi.existe(dossier):
            messagebox.showerror(
                "Evenement introuvable",
                "Ce dossier ne contient pas de fichier de suivi.\n\n"
                "Choisissez le dossier portant le nom de l'evenement, "
                "celui qui a ete cree a l'interieur du dossier source.",
                parent=self.fenetre)
            return

        try:
            self.suivi = Suivi.charger(dossier)
        except (OSError, ValueError) as erreur:
            messagebox.showerror("Fichier de suivi illisible", str(erreur),
                                 parent=self.fenetre)
            return

        self.fenetre.destroy()


class MenuPrincipal:
    """Menu propose apres la preparation ou la reprise (section 4)."""

    def __init__(self, racine, suivi):
        self.racine = racine
        self.suivi = suivi

        self.fenetre = tk.Toplevel(racine)
        self.fenetre.title("Menu - %s" % suivi.nom_evenement)
        self.fenetre.resizable(False, False)
        self.fenetre.protocol("WM_DELETE_WINDOW", self.quitter)

        cadre = ttk.Frame(self.fenetre, padding=24)
        cadre.grid(row=0, column=0)

        ttk.Label(cadre, text=suivi.nom_evenement,
                  font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        self.etiquette_etat = ttk.Label(cadre, text="", foreground="#555555",
                                        justify="left")
        self.etiquette_etat.grid(row=1, column=0, sticky="w", pady=(4, 16))

        ttk.Button(cadre, text="Etape 1  -  Trier les photos", width=38,
                   command=self._trier).grid(row=2, column=0, pady=4)
        ttk.Button(cadre, text="Etape 2  -  Censurer les yeux", width=38,
                   command=self._censurer).grid(row=3, column=0, pady=4)
        ttk.Button(cadre, text="Quitter", width=38,
                   command=self.quitter).grid(row=4, column=0, pady=(16, 0))

        self._rafraichir()

    def _rafraichir(self):
        """Met a jour le resume de l'avancement affiche dans le menu."""
        tri = self.suivi.tri
        total = len(tri["photos"])
        restantes = max(0, total - tri["position"])

        lignes = ["Dossier : %s" % self.suivi.dossier_evenement]
        if total:
            lignes.append("Tri : %d photo(s) sur %d parcourue(s), %d restante(s)."
                          % (tri["position"], total, restantes))
        else:
            lignes.append("Tri : aucune photo a trier.")

        for dossier in self.suivi.dossiers_tri:
            nombre = len(photos_du_dossier(self.suivi.chemin_dossier_tri(dossier["nom"])))
            lignes.append("   %s (%s) : %d photo(s)" % (dossier["nom"], dossier["touche"],
                                                        nombre))
        self.etiquette_etat.config(text="\n".join(lignes))

    def _trier(self):
        if not self.suivi.tri["photos"]:
            messagebox.showinfo("Rien a trier",
                                "Aucune photo n'est presente a la racine du dossier source.",
                                parent=self.fenetre)
            return
        self.fenetre.withdraw()
        lancer_tri(self.racine, self.suivi)
        self.fenetre.deiconify()
        self._rafraichir()

    def _censurer(self):
        nom_dossier = self._choisir_dossier_a_censurer()
        if nom_dossier is None:
            return

        self.fenetre.withdraw()
        nombre = lancer_censure(self.racine, self.suivi, nom_dossier)
        self.fenetre.deiconify()
        if nombre == 0:
            messagebox.showinfo("Dossier vide",
                                "Le dossier « %s » ne contient aucune photo." % nom_dossier,
                                parent=self.fenetre)
        self._rafraichir()

    def _choisir_dossier_a_censurer(self):
        """Demande lequel des quatre dossiers de tri doit etre passe en revue (section 9.1)."""
        boite = tk.Toplevel(self.fenetre)
        boite.title("Choisir le dossier a censurer")
        boite.resizable(False, False)
        boite.transient(self.fenetre)
        boite.grab_set()

        choix = {"dossier": None}

        cadre = ttk.Frame(boite, padding=20)
        cadre.grid(row=0, column=0)
        ttk.Label(cadre, text="Quel dossier voulez-vous passer en revue ?",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, pady=(0, 12))

        def choisir(nom):
            choix["dossier"] = nom
            boite.destroy()

        for numero, dossier in enumerate(self.suivi.dossiers_tri):
            nom = dossier["nom"]
            nombre = len(photos_du_dossier(self.suivi.chemin_dossier_tri(nom)))
            ttk.Button(cadre, text="%s  (%d photo(s))" % (nom, nombre), width=34,
                       command=lambda n=nom: choisir(n)).grid(row=1 + numero, column=0,
                                                              pady=3)

        ttk.Button(cadre, text="Annuler", width=34,
                   command=boite.destroy).grid(row=6, column=0, pady=(14, 0))

        self.racine.wait_window(boite)
        return choix["dossier"]

    def quitter(self):
        self.suivi.enregistrer()
        self.fenetre.destroy()


def main():
    # Certaines consoles Windows n'acceptent pas les caracteres accentues ;
    # on evite ainsi qu'un simple message d'information fasse echouer le programme.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    racine = tk.Tk()
    racine.withdraw()

    demarrage = EcranDemarrage(racine)
    racine.wait_window(demarrage.fenetre)

    if demarrage.suivi is not None:
        menu = MenuPrincipal(racine, demarrage.suivi)
        racine.wait_window(menu.fenetre)

    racine.destroy()


if __name__ == "__main__":
    main()
