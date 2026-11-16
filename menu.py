"""
Menu principal d'un evenement (section 4).

Propose apres la preparation ou la reprise : trier, revoir un dossier, gerer
les dossiers de tri, dupliquer un dossier, renommer les photos, terminer la
session, quitter. La censure des yeux n'est pas une etape a part : c'est le
mode « barrer » de la fenetre de tri et de revue, active par la touche Tab
(voir rangement.py).

Ce module charge tout le logiciel (fenetre de tri, detection des visages) :
main.py ne l'importe qu'une fois l'ecran d'accueil affiche, pour que celui-ci
apparaisse sans attendre.
"""

import os
import tkinter as tk
from tkinter import messagebox, ttk

import dossiers
import fin_de_session
import preferences
import renommage
import theme
from attente import executer_avec_attente
from choix_renommage import ChoixDuRenommage
from dossiers_tri import NOMS_RESERVES
from gestion_dossiers import gerer_les_dossiers
from polices import police
from remise_en_place import photos_revenues, proposer_de_remettre_en_place
from renommage_evenement import renommer_evenement
from revue import lancer_revue
from synchronisation import service_de_synchronisation
from tri import lancer_tri, photos_a_trier


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
        ttk.Button(cadre, text="Renommer les photos", width=42,
                   command=self._renommer).grid(row=9, column=0, pady=4)
        ttk.Button(cadre, text="Terminer la session  (rend le tri definitif)", width=42,
                   command=self._terminer).grid(row=10, column=0, pady=(14, 4))
        self.etiquette_session = ttk.Label(cadre, text="", style="Doux.TLabel",
                                           justify="center", wraplength=460)
        self.etiquette_session.grid(row=11, column=0)
        ttk.Button(cadre, text="Quitter", width=42,
                   command=self.quitter).grid(row=12, column=0, pady=(18, 0))

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

        lignes.append("Nom des photos : %s" % renommage.libelle(self.suivi.renommage))
        self.etiquette_etat.config(text="\n".join(lignes))

        # Ce qui peut encore etre annule, et la place que cela prend.
        bilan = fin_de_session.bilan(self.suivi)
        if bilan["annulables"]:
            session = ("%d action(s) encore annulable(s) (Retour arriere sur la photo) ; "
                       "originaux gardes : %s."
                       % (bilan["annulables"], fin_de_session.taille_en_clair(bilan["octets"])))
        else:
            session = "Vous pouvez quitter et revenir : rien n'est definitif d'ici la."
        self.etiquette_session.config(text=session)

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

    # ------------------------------------------------------------------
    # Renommage des photos
    # ------------------------------------------------------------------

    def _renommer(self):
        """Donne un autre format de nom a toutes les photos de l'evenement.

        Utile surtout aux evenements numerotes 1, 2, 3, dont deux tris faits
        separement ne peuvent pas etre reunis (voir renommage_evenement.py).
        """
        nom_format = self._demander_le_format()
        if nom_format is None:
            return
        nombre, erreur = executer_avec_attente(
            self.fenetre, "Renommage",
            lambda avancement: renommer_evenement(self.suivi, nom_format, avancement))
        self._rafraichir()
        if isinstance(erreur, OSError):
            messagebox.showerror(
                "Renommage impossible",
                "%s\n\nLes photos ont garde leur ancien nom. Un autre programme utilise "
                "peut-etre un fichier (synchronisation, antivirus) : reessayez dans un "
                "instant." % (erreur.strerror or erreur), parent=self.fenetre)
            return
        if erreur is not None:
            raise erreur        # erreur imprevue : voir main.signaler_les_erreurs
        preferences.retenir_format_de_renommage(nom_format)
        messagebox.showinfo("Renommage termine",
                            "%d fichier(s) portent maintenant un nom au format :\n%s."
                            % (nombre, renommage.libelle(nom_format)), parent=self.fenetre)

    def _demander_le_format(self):
        """Boite de choix du format des noms. Renvoie le format, ou None si l'on annule."""
        boite = tk.Toplevel(self.fenetre)
        boite.title("Renommer les photos")
        boite.resizable(False, False)
        boite.transient(self.fenetre)
        theme.habiller(boite)
        choix = {"format": None}

        cadre = ttk.Frame(boite, padding=theme.MARGE)
        cadre.grid(row=0, column=0)
        ttk.Label(cadre, text="Renommer les photos", style="Titre.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(cadre, text="Toutes les photos de l'evenement sont renommees d'apres "
                              "leur date de prise de vue, la ou elles se trouvent : a "
                              "trier, rangees, mises de cote (RAW, Videos) ou sans barre.",
                  style="Doux.TLabel", wraplength=560, justify="left").grid(
            row=1, column=0, sticky="w", pady=(0, 14))
        # « Ne pas renommer » n'est pas propose : on ne peut pas rendre leur
        # nom d'origine a des photos deja renommees.
        formats = [nom_format for nom_format, _ in renommage.FORMATS
                   if nom_format != renommage.FORMAT_AUCUN]
        liste = ChoixDuRenommage(cadre, self.suivi.renommage, self.suivi.nom_evenement,
                                 formats)
        liste.cadre.grid(row=2, column=0, sticky="w")

        def valider():
            choix["format"] = liste.nom_format()
            boite.destroy()

        boutons = ttk.Frame(cadre)
        boutons.grid(row=3, column=0, sticky="e", pady=(18, 0))
        ttk.Button(boutons, text="Annuler", width=14,
                   command=boite.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(boutons, text="Renommer", width=14, style="Accent.TButton",
                   command=valider).grid(row=0, column=1)
        boite.bind("<Escape>", lambda evenement: boite.destroy())
        theme.centrer(boite, self.fenetre)
        boite.grab_set()
        self.racine.wait_window(boite)
        return choix["format"]

    # ------------------------------------------------------------------
    # Fin de la session
    # ------------------------------------------------------------------

    def _terminer(self):
        """Rend le tri definitif, apres confirmation (voir fin_de_session.py)."""
        bilan = fin_de_session.bilan(self.suivi)
        a_trier = len(photos_a_trier(self.suivi))
        lignes = ["Terminer la session rend le tri definitif :", ""]
        if bilan["annulables"]:
            lignes.append("- %d action(s) ne pourront plus etre annulees, et les originaux "
                          "gardes (%s) seront effaces ;"
                          % (bilan["annulables"],
                             fin_de_session.taille_en_clair(bilan["octets"])))
        else:
            lignes.append("- aucune action n'est a annuler ;")
        if bilan["dossiers_vides"]:
            lignes.append("- les dossiers vides seront supprimes : %s."
                          % ", ".join(bilan["dossiers_vides"]))
        else:
            lignes.append("- aucun dossier n'est vide.")
        if a_trier:
            lignes += ["", "Attention : %d photo(s) restent a trier dans le dossier "
                           "source." % a_trier]
        lignes += ["", "Les photos rangees et les versions sans barre ne sont pas "
                       "touchees. Continuer ?"]
        if not messagebox.askyesno("Terminer la session", "\n".join(lignes),
                                   parent=self.fenetre):
            return

        try:
            supprimes, refuses = fin_de_session.terminer(self.suivi)
        except OSError as erreur:
            messagebox.showerror(
                "Session non terminee",
                "Le fichier de suivi n'a pas pu etre enregistre :\n%s\n\n"
                "Rien n'a ete efface. Reessayez dans un instant." % erreur,
                parent=self.fenetre)
            return
        self._rafraichir()
        lignes = ["Le tri est definitif."]
        if supprimes:
            lignes.append("Dossiers vides supprimes : %s." % ", ".join(supprimes))
        if refuses:
            lignes.append("Dossiers vides impossibles a supprimer (ouverts dans un autre "
                          "programme ?) : %s." % ", ".join(refuses))
        lignes.append("\nVous pouvez encore rouvrir l'evenement : ce que vous y ferez "
                      "ensuite sera de nouveau annulable, jusqu'a la prochaine fin de session.")
        messagebox.showinfo("Session terminee", "\n".join(lignes), parent=self.fenetre)

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
