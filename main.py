"""
Programme principal : lancement, gestion des sessions et menu (sections 4 et 5).

Se lance simplement par :

    python main.py

Le deroule est toujours le meme : on demarre un nouvel evenement ou l'on reprend
un evenement existant, puis le menu principal propose le tri, la revue d'un
dossier, la gestion des dossiers de tri, la duplication d'un dossier, ou de
quitter. La censure des yeux n'est plus une etape a part : c'est le mode
« barrer » de la fenetre de tri et de revue, active par la touche Tab (voir
rangement.py).

Un nouvel evenement s'installe dans le dossier des photos lui-meme, renomme du
nom de l'evenement (decision de l'utilisateur, 26 octobre 2026).
"""

import gc
import os
import sys
import threading
import time
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

import dossiers
import preferences
import preparation
import theme
from configuration import dans_un_autre_evenement, demander_configuration
from dossiers_tri import NOMS_RESERVES
from fichiers import renommer_dossier
from gestion_dossiers import gerer_les_dossiers
from polices import police
from remise_en_place import photos_revenues, proposer_de_remettre_en_place
from revue import lancer_revue
from suivi import NOM_FICHIER_SUIVI, Suivi
from synchronisation import service_de_synchronisation
from tri import lancer_tri, photos_a_trier


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
        configuration = demander_configuration(self.racine, self.fenetre)
        if configuration is None:
            return
        preferences.retenir_dossiers_de_tri(configuration["dossiers_tri"])
        preferences.retenir_dossier_des_photos(
            os.path.dirname(configuration["dossier_source"]))

        dossier_evenement = self._renommer_si_possible(configuration["dossier_source"],
                                                       configuration["nom_evenement"])
        suivi = Suivi.creer(dossier_evenement, configuration["nom_evenement"],
                            configuration["dossiers_tri"])
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
        """Lance la preparation automatique en montrant ou elle en est.

        La preparation lit la date de chaque photo, puis les renomme toutes :
        sur plusieurs milliers de photos, et plus encore dans un dossier
        OneDrive dont les photos doivent d'abord etre telechargees, cela peut
        durer plusieurs minutes. Faite sur le fil principal, elle figeait la
        fenetre, que Windows declarait alors « ne repond pas ». Elle tourne
        donc sur un fil separe, qui ne touche jamais a l'interface ; la
        fenetre d'attente est rafraichie ici, sur le fil principal, avec le
        dernier etat annonce par la preparation.
        """
        attente = tk.Toplevel(self.fenetre)
        attente.title("Preparation")
        attente.resizable(False, False)
        attente.transient(self.fenetre)
        # On n'interrompt pas un renommage en cours.
        attente.protocol("WM_DELETE_WINDOW", lambda: None)
        theme.habiller(attente)
        cadre = ttk.Frame(attente, padding=theme.MARGE)
        cadre.grid(row=0, column=0)
        ttk.Label(cadre, text="Preparation en cours...", font=police(11, gras=True)).grid(
            row=0, column=0)
        etiquette = ttk.Label(cadre, text="Creation des dossiers", style="Doux.TLabel",
                              width=46, anchor="center")
        etiquette.grid(row=1, column=0, pady=(10, 0))
        theme.centrer(attente, self.fenetre)
        attente.grab_set()

        etat = {"texte": "Creation des dossiers", "rapport": None, "erreur": None,
                "fini": False}

        def preparer():
            try:
                etat["rapport"] = preparation.preparer(
                    suivi, avancement=lambda texte: etat.update(texte=texte))
            except Exception as erreur:
                etat["erreur"] = erreur
            etat["fini"] = True

        fil = threading.Thread(target=preparer, daemon=True)
        fil.start()
        while not etat["fini"]:
            etiquette.config(text=etat["texte"])
            attente.update()
            time.sleep(0.05)
        fil.join()
        attente.grab_release()
        attente.destroy()

        erreur = etat["erreur"]
        if isinstance(erreur, OSError):
            messagebox.showerror(
                "Erreur pendant la preparation",
                "%s\n\nLa preparation n'est pas allee au bout. Reprenez l'evenement "
                "depuis l'ecran d'accueil pour la terminer, une fois la cause ecartee "
                "(fichier ouvert dans un autre programme, synchronisation...)." % erreur,
                parent=self.fenetre)
            return None
        if erreur is not None:
            raise erreur        # erreur imprevue : voir signaler_les_erreurs
        return etat["rapport"]

    def _reprendre(self, dossier=None):
        if dossier is None:
            dossier = dossiers.choisir_dossier(
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
                    "seront numerotees, et les RAW et videos mis de cote.",
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


class MenuPrincipal:
    """Menu propose apres la preparation ou la reprise (section 4)."""

    def __init__(self, racine, suivi):
        self.racine = racine
        self.suivi = suivi

        self.fenetre = tk.Toplevel(racine)
        self.fenetre.title("Menu - %s" % suivi.nom_evenement)
        self.fenetre.resizable(False, False)
        self.fenetre.protocol("WM_DELETE_WINDOW", self.quitter)
        theme.habiller(self.fenetre)

        cadre = ttk.Frame(self.fenetre, padding=theme.MARGE)
        cadre.grid(row=0, column=0)

        ttk.Label(cadre, text=suivi.nom_evenement,
                  style="Titre.TLabel").grid(row=0, column=0, sticky="w")
        self.etiquette_etat = ttk.Label(cadre, text="", style="Doux.TLabel",
                                        justify="left")
        self.etiquette_etat.grid(row=1, column=0, sticky="w", pady=(6, 4))

        ttk.Separator(cadre, orient="horizontal").grid(row=2, column=0, sticky="we",
                                                       pady=(12, 16))

        # Avertissements : photos revenues dans le dossier source, dossier
        # synchronise. Vides la plupart du temps, ils ne prennent alors aucune place.
        self.etiquette_alerte = ttk.Label(cadre, text="", style="Alerte.TLabel",
                                          justify="left", wraplength=460)
        self.etiquette_alerte.grid(row=2, column=0, sticky="w")

        ttk.Separator(cadre, orient="horizontal").grid(row=3, column=0, sticky="we",
                                                       pady=(12, 16))

        ttk.Button(cadre, text="Trier les photos du dossier source", width=42,
                   style="Accent.TButton",
                   command=self._trier).grid(row=4, column=0, pady=4)
        ttk.Button(cadre, text="Revoir un dossier  (reclasser, barrer les yeux)", width=42,
                   command=self._revoir).grid(row=5, column=0, pady=4)
        ttk.Label(cadre, text="Touche Tab dans la fenetre : mode barrer les yeux",
                  style="Doux.TLabel").grid(row=6, column=0, pady=(4, 0))
        ttk.Button(cadre, text="Gerer les dossiers de tri", width=42,
                   command=self._gerer_les_dossiers).grid(row=7, column=0, pady=(14, 4))
        ttk.Button(cadre, text="Dupliquer un dossier", width=42,
                   command=self._dupliquer).grid(row=8, column=0, pady=4)
        ttk.Button(cadre, text="Quitter", width=42,
                   command=self.quitter).grid(row=9, column=0, pady=(18, 0))

        self._rafraichir()
        theme.centrer(self.fenetre, racine)

    def _rafraichir(self):
        """Met a jour le resume de l'avancement affiche dans le menu."""
        # On compte ce qui se trouve reellement dans le dossier source : c'est
        # exactement ce que « Trier » proposera (voir tri.preparer_tri).
        a_trier = len(photos_a_trier(self.suivi))

        lignes = ["Dossier : %s" % self.suivi.dossier_evenement]
        if a_trier:
            lignes.append("Tri : %d photo(s) encore a trier dans le dossier source." % a_trier)
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

        alertes = []
        revenues = photos_revenues(self.suivi)
        if revenues:
            alertes.append("%d photo(s) rangee(s) sont revenue(s) dans le dossier source : "
                           "« Trier » proposera de les remettre en place." % len(revenues))
        service = service_de_synchronisation(self.suivi.dossier_source)
        if service:
            alertes.append("Dossier synchronise par %s : suspendez la synchronisation "
                           "pendant le tri, pour qu'elle ne remette pas de photos rangees "
                           "dans le dossier source." % service)
        self.etiquette_alerte.config(text="\n".join(alertes))
        self.etiquette_alerte.grid_configure(pady=(8, 0) if alertes else 0)

    def _nombre_de_photos(self, nom_dossier):
        return len(dossiers.photos_du_dossier(self.suivi.chemin_dossier(nom_dossier)))

    def _trier(self):
        # Les photos revenues dans le dossier source sont signalees avant que
        # le menu disparaisse : la question s'affiche ainsi par-dessus lui.
        proposer_de_remettre_en_place(self.fenetre, self.suivi)
        self._rafraichir()
        if not photos_a_trier(self.suivi):
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

    def _gerer_les_dossiers(self):
        """Ajouter, renommer ou retirer des dossiers de tri (voir gestion_dossiers.py)."""
        if gerer_les_dossiers(self.fenetre, self.suivi):
            self._rafraichir()

    def _revoir(self):
        """Repasse un dossier pour corriger des rangements ou barrer des yeux (section 8 bis).

        Les dossiers de tri sont proposes, ainsi que les copies faites depuis
        le menu. Dans une copie, les touches de tri sont sans effet : on n'y
        fait que retoucher et censurer.
        """
        nom_dossier = self._demander_un_dossier(
            "Choisir le dossier a revoir",
            "Quel dossier voulez-vous revoir ?",
            self.suivi.noms_dossiers_censurables)
        if nom_dossier is None:
            return

        self.fenetre.withdraw()
        try:
            nombre = lancer_revue(self.racine, self.suivi, nom_dossier)
        finally:
            self.fenetre.deiconify()
        if nombre == 0:
            messagebox.showinfo("Dossier vide",
                                "Le dossier « %s » ne contient aucune photo." % nom_dossier,
                                parent=self.fenetre)
        self._rafraichir()

    def _demander_un_dossier(self, titre, question, noms):
        """Fait choisir un des dossiers de l'evenement (section 9.1).

        La meme boite sert a choisir le dossier a revoir et le dossier a
        dupliquer. Renvoie le nom choisi, ou None si l'utilisateur annule.
        """
        boite = tk.Toplevel(self.fenetre)
        boite.title(titre)
        boite.resizable(False, False)
        boite.transient(self.fenetre)
        theme.habiller(boite)

        choix = {"dossier": None}

        cadre = ttk.Frame(boite, padding=theme.MARGE)
        cadre.grid(row=0, column=0)
        ttk.Label(cadre, text=question,
                  font=police(11, gras=True)).grid(row=0, column=0, pady=(0, 14))

        def choisir(nom):
            choix["dossier"] = nom
            boite.destroy()

        for numero, nom in enumerate(noms):
            nombre = self._nombre_de_photos(nom)
            ttk.Button(cadre, text="%s  (%d photo(s))" % (nom, nombre), width=34,
                       command=lambda n=nom: choisir(n)).grid(row=1 + numero, column=0,
                                                              pady=3)

        # Le bouton d'annulation se place apres le dernier dossier : leur nombre
        # varie, avec les dossiers de tri et les copies.
        ttk.Button(cadre, text="Annuler", width=34,
                   command=boite.destroy).grid(row=1 + len(noms), column=0, pady=(16, 0))

        boite.bind("<Escape>", lambda evenement: boite.destroy())
        # Le placement doit preceder la capture du clavier, sinon on voit la
        # boite sauter sous les yeux de l'utilisateur.
        theme.centrer(boite, self.fenetre)
        boite.grab_set()
        self.racine.wait_window(boite)
        return choix["dossier"]

    # ------------------------------------------------------------------
    # Duplication d'un dossier
    # ------------------------------------------------------------------

    def _dupliquer(self):
        """Copie un dossier de l'evenement sous un nouveau nom.

        Sert a garder les originaux intacts : on duplique un dossier, puis on
        ne censure qu'un seul des deux exemplaires : la censure reenregistre
        les photos par-dessus les originales (section 9.5).

        Une copie n'est pas un dossier de tri : elle n'a pas de touche, et le
        tri n'y range rien. Elle peut en revanche etre revue, et censuree,
        comme les autres.
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
        try:
            self.suivi.enregistrer()
        except OSError:
            # La copie est faite et notee en memoire : le suivi sera reecrit a
            # la prochaine action, ou en quittant le menu (voir quitter).
            pass
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
            saisi = theme.demander_texte(
                self.fenetre, "Nom de la copie",
                "Nom du nouveau dossier, cree a cote de « %s » :" % nom_source,
                propose)
            if saisi is None:
                return None

            saisi = saisi.strip()
            propose = saisi
            probleme = self._probleme_du_nom_de_copie(saisi)
            if probleme is None:
                return saisi
            messagebox.showerror("Nom impossible", "Ce nom ne convient pas : %s." % probleme,
                                 parent=self.fenetre)

    def _probleme_du_nom_de_copie(self, nom):
        """Explique pourquoi `nom` ne peut pas nommer une copie, ou renvoie None.

        Les noms du logiciel lui-meme sont refuses, en majuscules comme en
        minuscules : une copie nommee « _sauvegardes_temporaires » etait
        effacee, photos comprises, a la fermeture de la fenetre de tri, qui vide
        ce dossier. Un nom deja connu de l'evenement l'est aussi, meme si le
        dossier a disparu du disque : il apparaissait sinon deux fois au menu.
        """
        probleme = dossiers.probleme_du_nom(nom)
        if probleme:
            return probleme
        if nom.lower() in {reserve.lower() for reserve in NOMS_RESERVES}:
            return "« %s » est un nom reserve au logiciel" % nom
        noms_connus = self.suivi.noms_dossiers_tri + self.suivi.dossiers_dupliques
        if nom.lower() in {connu.lower() for connu in noms_connus}:
            return "l'evenement a deja un dossier « %s »" % nom
        if os.path.exists(os.path.join(self.suivi.dossier_evenement, nom)):
            return "le dossier « %s » existe deja dans le dossier de l'evenement" % nom
        return None

    def quitter(self):
        """Enregistre le suivi et ferme le menu, meme si l'enregistrement echoue.

        Un fichier de suivi tenu ouvert par un autre programme (OneDrive,
        l'antivirus) empechait sinon de quitter, tant que durait le blocage.
        Tout ce qui compte est deja enregistre a chaque action : on previent,
        et on ferme quand meme.
        """
        try:
            self.suivi.enregistrer()
        except OSError as erreur:
            messagebox.showwarning(
                "Suivi non enregistre",
                "Le fichier de suivi n'a pas pu etre enregistre :\n%s\n\n"
                "Les photos deja rangees le restent ; seul le dernier etat du "
                "menu pourrait etre perdu." % erreur, parent=self.fenetre)
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
