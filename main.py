"""
Programme principal : lancement, gestion des sessions et menu (sections 4 et 5).

Se lance simplement par :

    python main.py

Le deroule est toujours le meme : on demarre un nouvel evenement ou l'on reprend
un evenement existant, puis le menu principal propose le tri, la censure, la
duplication d'un dossier, ou de quitter.
"""

import os
import sys
import traceback
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import dossiers
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
        dossier = dossiers.choisir_dossier(
            "Choisir le dossier de l'evenement a reprendre", self.fenetre)
        if not dossier:
            return

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
        ttk.Button(cadre, text="Dupliquer un dossier", width=38,
                   command=self._dupliquer).grid(row=4, column=0, pady=(12, 4))
        ttk.Button(cadre, text="Quitter", width=38,
                   command=self.quitter).grid(row=5, column=0, pady=(16, 0))

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
            nombre = self._nombre_de_photos(dossier["nom"])
            lignes.append("   %s (%s) : %d photo(s)" % (dossier["nom"], dossier["touche"],
                                                        nombre))

        # Les copies faites depuis le menu apparaissent a la suite, sans touche
        # de clavier : elles ne servent pas au tri, seulement a la censure.
        for nom in self.suivi.dossiers_dupliques:
            if os.path.isdir(self.suivi.chemin_dossier(nom)):
                lignes.append("   %s (copie) : %d photo(s)"
                              % (nom, self._nombre_de_photos(nom)))

        self.etiquette_etat.config(text="\n".join(lignes))

    def _nombre_de_photos(self, nom_dossier):
        return len(photos_du_dossier(self.suivi.chemin_dossier(nom_dossier)))

    def _trier(self):
        if not self.suivi.tri["photos"]:
            messagebox.showinfo("Rien a trier",
                                "Aucune photo n'est presente a la racine du dossier source.",
                                parent=self.fenetre)
            return
        # `finally` est indispensable : si l'etape s'interrompait sur une
        # erreur, le menu resterait cache et le programme continuerait a tourner
        # sans aucune fenetre visible, empechant de manipuler le dossier des
        # photos sans qu'on comprenne pourquoi.
        self.fenetre.withdraw()
        try:
            lancer_tri(self.racine, self.suivi)
        finally:
            self.fenetre.deiconify()
        self._rafraichir()

    def _censurer(self):
        nom_dossier = self._demander_un_dossier(
            "Choisir le dossier a censurer",
            "Quel dossier voulez-vous passer en revue ?",
            self.suivi.noms_dossiers_censurables)
        if nom_dossier is None:
            return

        self.fenetre.withdraw()
        try:
            nombre = lancer_censure(self.racine, self.suivi, nom_dossier)
        finally:
            self.fenetre.deiconify()
        if nombre == 0:
            messagebox.showinfo("Dossier vide",
                                "Le dossier « %s » ne contient aucune photo." % nom_dossier,
                                parent=self.fenetre)
        self._rafraichir()

    def _demander_un_dossier(self, titre, question, noms):
        """Fait choisir un des dossiers de l'evenement (section 9.1).

        La meme boite sert a choisir le dossier a censurer et le dossier a
        dupliquer. Renvoie le nom choisi, ou None si l'utilisateur annule.
        """
        boite = tk.Toplevel(self.fenetre)
        boite.title(titre)
        boite.resizable(False, False)
        boite.transient(self.fenetre)
        boite.grab_set()

        choix = {"dossier": None}

        cadre = ttk.Frame(boite, padding=20)
        cadre.grid(row=0, column=0)
        ttk.Label(cadre, text=question,
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, pady=(0, 12))

        def choisir(nom):
            choix["dossier"] = nom
            boite.destroy()

        for numero, nom in enumerate(noms):
            nombre = self._nombre_de_photos(nom)
            ttk.Button(cadre, text="%s  (%d photo(s))" % (nom, nombre), width=34,
                       command=lambda n=nom: choisir(n)).grid(row=1 + numero, column=0,
                                                              pady=3)

        # Le bouton d'annulation se place apres le dernier dossier : leur nombre
        # varie, car les copies s'ajoutent aux quatre dossiers de tri.
        ttk.Button(cadre, text="Annuler", width=34,
                   command=boite.destroy).grid(row=1 + len(noms), column=0, pady=(14, 0))

        self.racine.wait_window(boite)
        return choix["dossier"]

    # ------------------------------------------------------------------
    # Duplication d'un dossier
    # ------------------------------------------------------------------

    def _dupliquer(self):
        """Copie un dossier de l'evenement sous un nouveau nom.

        Sert a garder les originaux intacts : on duplique un dossier, puis on
        ne censure qu'un seul des deux exemplaires — la censure reenregistre
        les photos par-dessus les originales (section 9.5).

        Une copie n'est pas un cinquieme dossier de tri : le tri en compte
        toujours quatre, chacun avec sa touche. Elle peut en revanche etre
        passee en revue a l'etape de censure, comme les autres.
        """
        nom_source = self._demander_un_dossier(
            "Dupliquer un dossier",
            "Quel dossier voulez-vous dupliquer ?",
            self.suivi.noms_dossiers_censurables)
        if nom_source is None:
            return

        nom_destination = self._demander_nom_de_copie(nom_source)
        if nom_destination is None:
            return

        try:
            nombre = dossiers.dupliquer_dossier(self.fenetre,
                                                self.suivi.dossier_evenement,
                                                nom_source, nom_destination)
        except OSError as erreur:
            messagebox.showerror("Duplication impossible", str(erreur),
                                 parent=self.fenetre)
            return

        self.suivi.ajouter_dossier_duplique(nom_destination)
        self.suivi.enregistrer()
        self._rafraichir()
        messagebox.showinfo(
            "Duplication terminee",
            "%d fichier(s) copie(s) dans le dossier « %s »."
            % (nombre, nom_destination),
            parent=self.fenetre)

    def _demander_nom_de_copie(self, nom_source):
        """Demande le nom de la copie et verifie qu'il est utilisable.

        On redemande tant que le nom ne convient pas, plutot que de tout
        annuler : l'utilisateur n'a ainsi pas a recommencer depuis le debut.
        """
        propose = dossiers.nom_de_copie_disponible(self.suivi.dossier_evenement,
                                                   nom_source)
        while True:
            saisi = simpledialog.askstring(
                "Nom de la copie",
                "Nom du nouveau dossier, cree a cote de « %s » :" % nom_source,
                initialvalue=propose, parent=self.fenetre)
            if saisi is None:
                return None

            saisi = saisi.strip()
            propose = saisi
            if not dossiers.nom_de_dossier_valide(saisi):
                messagebox.showerror(
                    "Nom impossible",
                    "Ce nom ne peut pas servir de nom de dossier.\n"
                    "Caracteres interdits : " + " ".join(sorted(
                        dossiers.CARACTERES_INTERDITS)),
                    parent=self.fenetre)
            elif os.path.exists(os.path.join(self.suivi.dossier_evenement, saisi)):
                messagebox.showerror(
                    "Nom deja pris",
                    "Le dossier « %s » existe deja dans le dossier de "
                    "l'evenement." % saisi,
                    parent=self.fenetre)
            else:
                return saisi

    def quitter(self):
        self.suivi.enregistrer()
        self.fenetre.destroy()


def signaler_les_erreurs(racine):
    """Montre les erreurs imprevues au lieu de les laisser passer inapercues.

    Sans cela, Tkinter se contente d'ecrire l'erreur dans la console : la
    fenetre concernee peut rester cachee et le programme continuer a tourner
    sans que rien ne soit visible a l'ecran. Avec un message, on sait ce qui
    s'est passe et on peut fermer le programme pour de bon.
    """
    def rapporter(type_erreur, valeur, trace):
        traceback.print_exception(type_erreur, valeur, trace)
        messagebox.showerror(
            "Erreur inattendue",
            "%s : %s\n\nLe detail complet a ete ecrit dans la console."
            % (type_erreur.__name__, valeur))

    racine.report_callback_exception = rapporter


def main():
    # Certaines consoles Windows n'acceptent pas les caracteres accentues ;
    # on evite ainsi qu'un simple message d'information fasse echouer le programme.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    # Le dossier courant du programme ne doit jamais etre un dossier de photos :
    # sous Windows, le dossier courant d'un programme en cours d'execution est
    # considere comme ouvert, et ne peut plus etre deplace, renomme ni supprime.
    # On se place donc une fois pour toutes dans le dossier du programme.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    racine = tk.Tk()
    racine.withdraw()
    signaler_les_erreurs(racine)

    try:
        demarrage = EcranDemarrage(racine)
        racine.wait_window(demarrage.fenetre)

        if demarrage.suivi is not None:
            menu = MenuPrincipal(racine, demarrage.suivi)
            racine.wait_window(menu.fenetre)
    finally:
        # Quoi qu'il arrive, toutes les fenetres sont fermees et le programme
        # se termine. Un programme qui reste en vie, meme sans fenetre visible,
        # empeche de deplacer ou de renommer le dossier des photos.
        racine.destroy()


if __name__ == "__main__":
    main()
