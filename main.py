"""
Programme principal : lancement et ecran d'accueil (sections 4 et 5).

Se lance simplement par :

    python main.py

Le deroule est toujours le meme : on demarre un nouvel evenement ou l'on reprend
un evenement existant, puis le menu principal (menu.py) propose le tri, la
revue d'un dossier et les autres actions.

Un nouvel evenement s'installe dans le dossier des photos lui-meme, renomme du
nom de l'evenement (decision de l'utilisateur, 26 octobre 2026).

Demarrage rapide (demande de l'utilisateur, 16 novembre 2026). Ce fichier
n'importe en tete que des modules legers : l'ecran d'accueil n'a besoin ni de
Pillow, ni d'OpenCV, dont le chargement prend plusieurs secondes sur un
ordinateur lent ou surveille par un antivirus. Le reste du logiciel est charge
en arriere-plan pendant que l'ecran d'accueil est deja affiche (voir
charger_la_suite_en_arriere_plan), et les fonctions qui en ont besoin
l'importent au moment de s'en servir : d'ou les « import » places dans les
fonctions, que l'on ne trouve nulle part ailleurs dans le projet.
"""

import gc
import os
import sys
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

import preferences
import theme
from suivi import NOM_FICHIER_SUIVI, Suivi


class EcranDemarrage:
    """Premiere fenetre : nouvel evenement ou reprise (section 5)."""

    def __init__(self, racine):
        self.racine = racine
        self.suivi = None

        self.fenetre = tk.Toplevel(racine)
        self.fenetre.title("Tri et censure de photos")
        self.fenetre.resizable(False, False)
        self.fenetre.protocol("WM_DELETE_WINDOW", self.fenetre.destroy)
        theme.habiller(self.fenetre)

        cadre = ttk.Frame(self.fenetre, padding=theme.MARGE)
        cadre.grid(row=0, column=0)

        ttk.Label(cadre, text="Tri et censure de photos",
                  style="Titre.TLabel").grid(row=0, column=0, pady=(0, 4))
        ttk.Label(cadre, text="Que voulez-vous faire ?",
                  style="Doux.TLabel").grid(row=1, column=0, pady=(0, 18))

        ttk.Button(cadre, text="Demarrer un nouvel evenement", width=40,
                   style="Accent.TButton",
                   command=self._nouveau).grid(row=2, column=0, pady=4)

        # Le dernier evenement ouvert se reprend en un clic, s'il existe encore.
        dernier = preferences.dernier_evenement()
        rang = 3
        if dernier and Suivi.existe(dernier):
            ttk.Button(cadre, text="Reprendre « %s »" % _raccourcir(os.path.basename(dernier)),
                       width=40, command=lambda: self._reprendre(dernier)).grid(
                row=rang, column=0, pady=4)
            rang += 1
        ttk.Button(cadre, text="Reprendre un evenement existant...", width=40,
                   command=self._reprendre).grid(row=rang, column=0, pady=4)
        ttk.Button(cadre, text="Quitter", width=40,
                   command=self.fenetre.destroy).grid(row=rang + 1, column=0, pady=(18, 0))
        theme.centrer(self.fenetre, racine)

    def _nouveau(self):
        from configuration import demander_configuration

        configuration = demander_configuration(self.racine, self.fenetre)
        if configuration is None:
            return
        preferences.retenir_dossiers_de_tri(configuration["dossiers_tri"])
        preferences.retenir_format_de_renommage(configuration["renommage"])
        preferences.retenir_dossier_des_photos(
            os.path.dirname(configuration["dossier_source"]))

        dossier_evenement = self._renommer_si_possible(configuration["dossier_source"],
                                                       configuration["nom_evenement"])
        suivi = Suivi.creer(dossier_evenement, configuration["nom_evenement"],
                            configuration["dossiers_tri"], configuration["renommage"])
        # Le suivi est ecrit avant la preparation : si celle-ci s'interrompt
        # (coupure, fichier bloque), l'evenement existe deja, et la reprise
        # proposera de la terminer.
        try:
            suivi.enregistrer()
        except OSError as erreur:
            messagebox.showerror("Evenement impossible a creer", str(erreur),
                                 parent=self.fenetre)
            return
        preferences.retenir_dernier_evenement(dossier_evenement)

        rapport = self._preparer_avec_attente(suivi)
        if rapport is None:
            return
        self._annoncer_la_preparation(suivi, rapport)
        self.suivi = suivi
        self.fenetre.destroy()

    def _renommer_si_possible(self, dossier_source, nom_evenement):
        """Renomme le dossier des photos du nom de l'evenement, si possible.

        Le dossier des photos devient le dossier de l'evenement (decision de
        l'utilisateur, 26 octobre 2026). S'il ne peut pas etre renomme
        (fichier ouvert par un autre programme, synchronisation en cours,
        racine d'une carte memoire), le tri se fait dans le dossier tel quel,
        sous son nom actuel : c'est le choix de l'utilisateur, qui en est
        simplement prevenu. Renvoie le chemin du dossier de l'evenement.
        """
        from configuration import dans_un_autre_evenement
        from fichiers import renommer_dossier

        if (os.path.basename(dossier_source) == nom_evenement
                or dans_un_autre_evenement(dossier_source)):
            return dossier_source
        try:
            return renommer_dossier(dossier_source, nom_evenement)
        except OSError as erreur:
            messagebox.showinfo(
                "Dossier non renomme",
                "Le dossier « %s » n'a pas pu etre renomme « %s » :\n%s\n\n"
                "Le tri se fera dans ce dossier, sous son nom actuel. Vous pourrez le "
                "renommer vous-meme plus tard, logiciel ferme."
                % (os.path.basename(dossier_source) or dossier_source, nom_evenement,
                   erreur.strerror or erreur),
                parent=self.fenetre)
            return dossier_source

    def _annoncer_la_preparation(self, suivi, rapport):
        """Resume de la preparation : ce qui est a trier, ce qui a ete mis de cote."""
        from synchronisation import service_de_synchronisation

        lignes = ["Photos a trier : %d" % rapport["photos"],
                  "Fichiers RAW mis de cote : %d" % rapport["raw"],
                  "Videos mises de cote : %d" % rapport["videos"]]
        if rapport["laisses"]:
            lignes.append("\n%d fichier(s) RAW ou video laisse(s) dans le dossier (un "
                          "fichier du meme nom existait deja a l'arrivee, ou le fichier "
                          "etait occupe par un autre programme) : %s"
                          % (len(rapport["laisses"]), ", ".join(rapport["laisses"][:8])))
        service = service_de_synchronisation(suivi.dossier_source)
        if service:
            lignes.append("\nCe dossier est synchronise par %s. Pour eviter que des photos "
                          "rangees reviennent dans le dossier source, suspendez la "
                          "synchronisation le temps du tri." % service)
        messagebox.showinfo("Preparation terminee", "\n".join(lignes), parent=self.fenetre)

    def _preparer_avec_attente(self, suivi):
        """Lance la preparation automatique en montrant ou elle en est (voir attente.py).

        Renvoie le compte rendu de la preparation, ou None si elle n'est pas
        allee au bout : l'utilisateur en a alors ete prevenu.
        """
        import preparation
        from attente import executer_avec_attente

        rapport, erreur = executer_avec_attente(
            self.fenetre, "Preparation",
            lambda avancement: preparation.preparer(suivi, avancement))
        if isinstance(erreur, OSError):
            messagebox.showerror(
                "Erreur pendant la preparation",
                "%s\n\nLa preparation n'est pas allee au bout. Reprenez l'evenement "
                "depuis l'ecran d'accueil pour la terminer, une fois la cause ecartee "
                "(fichier ouvert dans un autre programme, synchronisation...)."
                % (erreur.strerror or erreur),
                parent=self.fenetre)
            return None
        if erreur is not None:
            raise erreur        # erreur imprevue : voir signaler_les_erreurs
        return rapport

    def _reprendre(self, dossier=None):
        if dossier is None:
            from dossiers import choisir_dossier

            dossier = choisir_dossier(
                "Choisir le dossier de l'evenement a reprendre", self.fenetre,
                preferences.dossier_des_photos())
        if not dossier:
            return

        dossier_evenement = trouver_evenement(dossier)
        if dossier_evenement is None:
            messagebox.showerror(
                "Evenement introuvable",
                "Ce dossier ne contient pas de fichier de suivi (%s).\n\n"
                "Choisissez le dossier de l'evenement : celui qui porte son nom, et "
                "qui contient les dossiers de tri." % NOM_FICHIER_SUIVI,
                parent=self.fenetre)
            return

        try:
            suivi = Suivi.charger(dossier_evenement)
        except (OSError, ValueError) as erreur:
            messagebox.showerror("Fichier de suivi illisible", str(erreur),
                                 parent=self.fenetre)
            return

        # Une preparation interrompue (fichier bloque, coupure) n'a jamais eu
        # lieu en entier : la terminer n'est pas la rejouer (section 10).
        if not suivi.donnees.get("preparation_faite", True):
            if not messagebox.askyesno(
                    "Preparation a terminer",
                    "La preparation de cet evenement n'est pas allee au bout.\n\n"
                    "La terminer maintenant ? Les photos encore a la racine du dossier "
                    "seront renommees, et les RAW et videos mis de cote.",
                    parent=self.fenetre):
                return
            rapport = self._preparer_avec_attente(suivi)
            if rapport is None:
                return
            self._annoncer_la_preparation(suivi, rapport)

        preferences.retenir_dernier_evenement(dossier_evenement)
        self.suivi = suivi
        self.fenetre.destroy()


def trouver_evenement(dossier):
    """Dossier de l'evenement correspondant au dossier choisi, ou None.

    C'est en principe le dossier choisi lui-meme. Mais les evenements crees
    avant le 26 octobre 2026 vivaient dans un sous-dossier du dossier des
    photos, et l'on choisit facilement le dossier des photos par habitude :
    s'il contient un seul sous-dossier d'evenement, c'est celui-la.
    """
    if Suivi.existe(dossier):
        return dossier
    try:
        sous_dossiers = [os.path.join(dossier, nom) for nom in os.listdir(dossier)]
    except OSError:
        return None
    evenements = [chemin for chemin in sous_dossiers
                  if os.path.isdir(chemin) and Suivi.existe(chemin)]
    return evenements[0] if len(evenements) == 1 else None


def _raccourcir(texte, longueur=30):
    """Coupe un nom trop long pour tenir sur un bouton."""
    return texte if len(texte) <= longueur else texte[:longueur - 3] + "..."


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


# Delai entre deux passages du ramasse-miettes, en millisecondes.
DELAI_RAMASSE_MIETTES = 2000


def ramasser_les_miettes(racine):
    """Fait le menage de la memoire, toujours sur le fil principal.

    Laisse a lui-meme, le ramasse-miettes de Python se declenche sur le fil
    qui travaille a ce moment-la, souvent un fil d'arriere-plan (chargement,
    enregistrement, preparation). S'il y detruit une variable ou une image
    Tkinter restee prise dans un cycle d'objets, ce fil reste bloque plus
    d'une seconde, Tkinter n'obeissant qu'au fil principal ; et s'il lisait
    une photo, Windows refuse pendant ce temps de la deplacer. Mesure : sur
    sept collectes automatiques, deux tombaient sur un fil d'arriere-plan, et
    une boite de saisie fermee suffisait a faire echouer un rangement.

    Le ramasse-miettes automatique est donc coupe au demarrage (voir main), et
    ce menage est fait ici, entre deux evenements de la fenetre : 5 ms
    toutes les deux secondes.
    """
    gc.collect()
    racine.after(DELAI_RAMASSE_MIETTES, ramasser_les_miettes, racine)


def charger_la_suite_en_arriere_plan():
    """Charge le reste du logiciel pendant que l'ecran d'accueil est deja affiche.

    Le menu, la fenetre de tri et la detection des visages demandent Pillow et
    OpenCV, longs a charger. Importes ici, sur un fil d'arriere-plan, ils sont
    prets quand l'utilisateur a choisi son evenement ; s'il est plus rapide,
    l'import fait par le fil principal attend simplement la fin de celui-ci
    (Python ne charge jamais deux fois le meme module).

    Ce fil ne fait qu'importer : il ne cree et ne detruit aucun objet Tkinter.
    Une erreur d'import n'est pas traitee ici : elle se reproduira sur le fil
    principal, au moment ou le module servira, et sera alors montree.
    """
    def charger():
        try:
            import menu        # noqa: F401  (entraine tout le reste)
        except Exception:
            pass

    threading.Thread(target=charger, daemon=True).start()


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
    # L'apparence est reglee avant d'ouvrir la moindre fenetre, sans quoi la
    # premiere s'afficherait en gris clair le temps d'un battement de cil.
    theme.appliquer(racine)
    signaler_les_erreurs(racine)
    gc.disable()
    ramasser_les_miettes(racine)

    try:
        demarrage = EcranDemarrage(racine)
        # L'ecran d'accueil est dessine avant que le chargement du reste ne
        # commence : c'est lui que l'utilisateur attend.
        racine.update()
        charger_la_suite_en_arriere_plan()
        racine.wait_window(demarrage.fenetre)

        if demarrage.suivi is not None:
            from menu import MenuPrincipal

            menu = MenuPrincipal(racine, demarrage.suivi)
            racine.wait_window(menu.fenetre)
    finally:
        # Quoi qu'il arrive, toutes les fenetres sont fermees et le programme
        # se termine. Un programme qui reste en vie, meme sans fenetre visible,
        # empeche de deplacer ou de renommer le dossier des photos.
        racine.destroy()


if __name__ == "__main__":
    main()
