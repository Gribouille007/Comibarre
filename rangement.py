"""
Fenetre unique du logiciel : tri, revue et censure des yeux (sections 8, 8 bis
et 9).

Les photos defilent une par une en grand, et une touche du clavier deplace la
photo affichee vers l'un des quatre dossiers de tri. Seul change le dossier
d'ou viennent les photos :

- a l'etape de tri, le dossier source, ou attendent les photos brutes ;
- en revue, l'un des quatre dossiers de tri, que l'on repasse pour corriger un
  rangement, ou l'une des copies faites depuis le menu. Une copie n'a pas de
  touche de tri : on n'y fait que retoucher et censurer.

La censure n'est plus une etape a part : la touche Tab active le mode
« barrer », ou un clic sur une tete pose un bandeau sur ses yeux (censure.py).
Ce mode reste actif d'une photo a l'autre, et d'une session a l'autre, tant
qu'on ne rappuie pas sur Tab.

Retouches. La rotation (R) et les bandeaux restent provisoires a l'ecran. Ils
sont enregistres dans le fichier par Entree, qui passe ensuite a la photo
suivante, ou par une touche de tri, qui enregistre puis range. Espace et les
fleches les abandonnent. Le rognage (C), lui, s'enregistre des sa validation.

Les fleches gauche et droite font circuler d'une photo a l'autre sans rien
deplacer. On peut ainsi revenir sur une photo deja rangee : elle est montree
depuis le dossier ou elle se trouve maintenant, et une touche de tri la deplace
de ce dossier vers le nouveau.
"""

import os
import shutil
import tkinter as tk
from tkinter import messagebox

from censure import OutilBandeaux
from ecritures import EcrituresEnArrierePlan, signaler_les_echecs
from images import ChargeurAnticipe, copie_de_sauvegarde, fabriquer_apercu
from polices import police
from retouches import appliquer_retouches, enregistrer_retouches
from rognage import cadre_dans_le_sens_d_origine, rogner_fichier, rogner_image
from visages import DetecteurVisages, DetectionAnticipee
from visionneuse import Visionneuse

COULEUR_FOND = "#1e1e1e"
COULEUR_BARRE = "#2b2b2b"
COULEUR_TEXTE = "#f0f0f0"
COULEUR_RAPPEL = "#b8b8b8"
COULEUR_ATTENTION = "#ffcc66"     # retouches pas encore enregistrees
COULEUR_MODE_ACTIF = "#ff6b6b"    # pastille du mode barrer

RAPPEL_ROGNAGE = ("ROGNAGE  -  Tracez un cadre a la souris  |  Entree = rogner la photo  |  "
                  "Echap ou C = abandonner sans rien modifier")
RAPPEL_BARRER = ("BARRER  -  Clic sur une tete = bandeau  |  Clic sur un bandeau = le choisir  |  "
                 "Double-clic = le retirer  |  Glisser dans le vide = deplacer la vue")

# Delai, en millisecondes, avant de regarder de nouveau si une photo (ou ses
# visages) qui n'etait pas encore prete l'est enfin.
DELAI_ATTENTE_CHARGEMENT = 15


class FenetreRangement:
    """Fenetre ou l'on range, retouche et censure les photos."""

    def __init__(self, racine, suivi, etat, dossier_origine, titre):
        """
        etat            : la partie du fichier de suivi propre a cette etape
                          (suivi.tri ou suivi.revue) : liste des photos,
                          position et historique.
        dossier_origine : nom du dossier d'ou viennent les photos, ou None
                          pour le dossier source (etape de tri).
        """
        self.suivi = suivi
        self.etat = etat
        self.photos = etat["photos"]
        self.dossier_origine = dossier_origine
        # Les touches de tri ne servent qu'au dossier source et aux quatre
        # dossiers de tri. Dans une copie, elles creeraient des doublons.
        self.touches_de_tri = (dossier_origine is None
                               or dossier_origine in suivi.noms_dossiers_tri)

        # Les apercus sont d'abord prepares a la taille de l'ecran, que la
        # fenetre ne peut pas depasser, puis a celle de la zone d'affichage des
        # qu'elle est connue (voir _zone_d_affichage_changee).
        dossier = self._chemin_du_dossier(dossier_origine)
        taille_ecran = (racine.winfo_screenwidth(), racine.winfo_screenheight())
        self.chargeur = ChargeurAnticipe([os.path.join(dossier, nom) for nom in self.photos],
                                         taille_ecran)
        self.ecritures = EcrituresEnArrierePlan()
        self.attente = None          # nouvel essai programme si la photo n'est pas chargee
        self.attente_visages = None  # idem pour la detection des visages
        self.visages_recus = False   # les visages de la photo affichee sont-ils connus ?

        # Detection des visages : lancee seulement en mode barrer, ou elle
        # sert. Le modele est charge une fois, la premiere fois qu'on l'active.
        self.detecteur = None
        self.detection = None

        self.fenetre = tk.Toplevel(racine)
        self.fenetre.title(titre)
        self.fenetre.geometry("1200x800")
        self.fenetre.configure(bg=COULEUR_FOND)
        self.fenetre.protocol("WM_DELETE_WINDOW", self.quitter)

        self._construire()
        self.outil = OutilBandeaux(self.visionneuse, self._mettre_a_jour_barre)
        if suivi.mode_barrer and not self._activer_barrage():
            suivi.mode_barrer = False

        self.fenetre.bind("<Key>", self._touche)
        self.fenetre.focus_force()
        self.fenetre.after(60, self.afficher_photo_courante)
        self.surveillance = self.fenetre.after(300, self._surveiller_ecritures)

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    def _construire(self):
        # La barre du bas est placee en premier : si la fenetre est reduite,
        # c'est la photo qui retrecit, et le rappel des touches reste visible.
        barre = tk.Frame(self.fenetre, bg=COULEUR_BARRE)
        barre.pack(side="bottom", fill="x")

        self.visionneuse = Visionneuse(self.fenetre)
        self.visionneuse.canvas.pack(side="top", fill="both", expand=True)
        # Les apercus sont prepares exactement a la taille de la zone
        # d'affichage : une photo s'y affiche alors sans etre redimensionnee.
        self.visionneuse.canvas.bind("<Configure>", self._zone_d_affichage_changee, add="+")

        ligne = tk.Frame(barre, bg=COULEUR_BARRE)
        ligne.pack(side="top", fill="x", pady=(6, 0))
        self.etiquette_mode = tk.Label(ligne, text="", bg=COULEUR_BARRE,
                                       font=police(11, gras=True), padx=10)
        self.etiquette_mode.pack(side="right")
        self.etiquette_avancement = tk.Label(ligne, text="", bg=COULEUR_BARRE,
                                             fg=COULEUR_TEXTE, font=police(11, gras=True),
                                             anchor="w", padx=10)
        self.etiquette_avancement.pack(side="left")
        self.etiquette_retouches = tk.Label(ligne, text="", bg=COULEUR_BARRE,
                                            fg=COULEUR_ATTENTION, font=police(11),
                                            anchor="w")
        self.etiquette_retouches.pack(side="left")

        touches = ""
        if self.touches_de_tri:
            touches = "  |  ".join("%s = %s" % (dossier["touche"], dossier["nom"])
                                   for dossier in self.suivi.dossiers_tri) + "  |  "
        self.rappel = (touches + "Entree = enregistrer et suivante  |  Espace ou → = suivante  |  "
                       "← = precedente  |  Retour arriere = annuler  |  R = pivoter  |  "
                       "C = rogner  |  Tab = mode barrer  |  Echap = quitter")
        self.etiquette_rappel = tk.Label(barre, text="", bg=COULEUR_BARRE,
                                         fg=COULEUR_RAPPEL, font=police(9),
                                         anchor="w", justify="left", padx=10)
        self.etiquette_rappel.pack(side="top", fill="x", pady=(0, 6))

    def _zone_d_affichage_changee(self, evenement):
        if evenement.width >= 10 and evenement.height >= 10:
            self.chargeur.changer_taille_apercu((evenement.width, evenement.height))

    def _mettre_a_jour_rappel(self):
        if self.visionneuse.en_rognage:
            texte = RAPPEL_ROGNAGE
        elif self.suivi.mode_barrer:
            texte = RAPPEL_BARRER + "\n" + self.rappel
        else:
            texte = self.rappel
        self.etiquette_rappel.config(text=texte)

    def _mettre_a_jour_barre(self):
        """Pastille du mode barrer, et retouches en attente d'enregistrement."""
        if self.suivi.mode_barrer:
            texte = "●  MODE BARRER  (Tab)"
            if self.visionneuse.image is not None:
                if self.visages_recus:
                    texte += "   -   %d visage(s)" % len(self.outil.visages)
                else:
                    texte += "   -   detection..."
            self.etiquette_mode.config(text=texte, fg=COULEUR_MODE_ACTIF)
        else:
            self.etiquette_mode.config(text="Mode barrer : non  (Tab)", fg=COULEUR_RAPPEL)

        morceaux = []
        if self.visionneuse.image is not None and self.visionneuse.rotation:
            morceaux.append("rotation %d°" % self.visionneuse.rotation)
        nombre_bandeaux = len(self.outil.bandeaux())
        if nombre_bandeaux:
            morceaux.append("%d bandeau(x)" % nombre_bandeaux)
        texte = ""
        if morceaux:
            texte = "   -   A enregistrer : %s (Entree)" % ", ".join(morceaux)
        self.etiquette_retouches.config(text=texte)

    # ------------------------------------------------------------------
    # Ou se trouve chaque photo
    # ------------------------------------------------------------------

    @property
    def position(self):
        return self.etat["position"]

    @position.setter
    def position(self, valeur):
        self.etat["position"] = valeur

    def _chemin_du_dossier(self, nom_dossier):
        """Chemin d'un dossier de l'evenement ; None designe le dossier source."""
        if nom_dossier is None:
            return self.suivi.dossier_source
        return self.suivi.chemin_dossier(nom_dossier)

    def _localiser(self, nom_fichier):
        """Trouve le dossier ou se trouve la photo en ce moment.

        Une photo n'est pas forcement la ou elle etait au lancement : elle a pu
        etre rangee, ici ou lors d'une session precedente. On la cherche d'abord
        dans le dossier d'origine, puis dans les quatre dossiers de tri. Les
        photos etant numerotees une fois pour toutes (1, 2, 3...), un meme nom
        ne designe qu'une seule photo dans tout l'evenement.

        Exception : une copie contient les memes noms que les dossiers de tri,
        et ses photos n'en sortent jamais. On ne cherche donc que dans la copie.

        Renvoie (nom du dossier, chemin complet). Le nom vaut None pour le
        dossier source ; le chemin vaut None si la photo est introuvable.
        """
        candidats = [self.dossier_origine]
        if self.touches_de_tri:
            candidats += [nom for nom in self.suivi.noms_dossiers_tri
                          if nom != self.dossier_origine]
        for nom_dossier in candidats:
            chemin = os.path.join(self._chemin_du_dossier(nom_dossier), nom_fichier)
            if os.path.isfile(chemin):
                return nom_dossier, chemin
        return None, None

    # ------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------

    def afficher_photo_courante(self):
        """Affiche la photo a la position courante, la ou elle se trouve.

        Les retouches provisoires de la photo precedente sont abandonnees :
        seuls Entree et les touches de tri les enregistrent.
        """
        self._annuler_attente()
        self.visages_recus = False
        self.outil.vider()
        if self.position >= len(self.photos):
            self._afficher_fin()
            return

        nom_fichier = self.photos[self.position]
        dossier_actuel, chemin = self._localiser(nom_fichier)

        texte = "Photo %d sur %d   -   %s" % (self.position + 1, len(self.photos), nom_fichier)
        if chemin is not None and dossier_actuel != self.dossier_origine:
            texte += "   -   actuellement dans « %s »" % (dossier_actuel or "dossier source")
        self.etiquette_avancement.config(text=texte)
        self._mettre_a_jour_rappel()

        if self.detection is not None:
            self.detection.avancer(self.position)
        if chemin is None:
            self.chargeur.avancer(self.position)
            self.visionneuse.montrer(None, None, "Photo introuvable : %s" % nom_fichier)
            self._mettre_a_jour_barre()
            return

        self.chargeur.changer_chemin(self.position, chemin)
        self.chargeur.avancer(self.position)
        self._montrer_des_que_prete()

    def _montrer_des_que_prete(self, deja_en_attente=False):
        """Montre la photo courante si elle est chargee, sinon reessaie un peu plus tard.

        Les photos sont lues en arriere-plan (voir images.py). Si l'utilisateur
        va plus vite que cette lecture, la photo n'est pas lue ici, ce qui
        figerait la fenetre : on affiche « Chargement... » et on revient voir
        quelques millisecondes plus tard. La fenetre reste ainsi toujours
        reactive.
        """
        self.attente = None
        if not self.chargeur.est_prete(self.position):
            if not deja_en_attente:
                self.visionneuse.afficher_texte("Chargement...")
            self.attente = self.fenetre.after(DELAI_ATTENTE_CHARGEMENT,
                                              self._montrer_des_que_prete, True)
            return

        image, apercu = self.chargeur.photo(self.position)
        self.visionneuse.montrer(image, apercu,
                                 "Photo illisible : %s" % self.photos[self.position])
        self._mettre_a_jour_barre()
        if self.detection is not None and image is not None:
            self._donner_les_visages_des_que_prets(self.position)

    def _donner_les_visages_des_que_prets(self, index):
        """Transmet a l'outil les visages detectes sur la photo, des qu'ils sont prets.

        Meme principe que pour la photo : la detection se fait en arriere-plan,
        et la fenetre ne l'attend jamais. La photo s'affiche sans attendre ses
        visages ; ceux-ci arrivent en general dans la foulee, car ils ont ete
        calcules a l'avance.
        """
        self.attente_visages = None
        if self.detection is None or index != self.position:
            return
        if not self.detection.est_prete(index):
            self.attente_visages = self.fenetre.after(
                DELAI_ATTENTE_CHARGEMENT, self._donner_les_visages_des_que_prets, index)
            return
        self.outil.visages = self.detection.visages(index)
        self.visages_recus = True
        self._mettre_a_jour_barre()

    def _annuler_attente(self):
        if self.attente is not None:
            self.fenetre.after_cancel(self.attente)
            self.attente = None
        if self.attente_visages is not None:
            self.fenetre.after_cancel(self.attente_visages)
            self.attente_visages = None

    def _afficher_fin(self):
        self.etiquette_avancement.config(text="Toutes les photos ont ete parcourues")
        self.visionneuse.afficher_texte(
            "Toutes les photos ont ete parcourues.\n"
            "Fleche gauche pour revenir en arriere, Echap pour revenir au menu.")
        self._mettre_a_jour_barre()
        self.etat["terminee"] = True
        self.suivi.enregistrer()

    # ------------------------------------------------------------------
    # Mode barrer
    # ------------------------------------------------------------------

    def basculer_barrage(self):
        """Active ou desactive le mode barrer. Le choix est retenu dans le suivi."""
        if self.visionneuse.en_rognage:
            return
        if self.suivi.mode_barrer:
            self._desactiver_barrage()
            self.suivi.mode_barrer = False
        elif self._activer_barrage():
            self.suivi.mode_barrer = True
            if self.visionneuse.image is not None and self.position < len(self.photos):
                self.detection.avancer(self.position)
                self._donner_les_visages_des_que_prets(self.position)
        self.suivi.enregistrer()
        self._mettre_a_jour_rappel()
        self._mettre_a_jour_barre()

    def _activer_barrage(self):
        """Lance la detection des visages et confie les clics a l'outil bandeaux.

        Renvoie False si la detection ne peut pas demarrer (modele absent).
        """
        try:
            if self.detecteur is None:
                self.detecteur = DetecteurVisages()
            self.detection = DetectionAnticipee(self.detecteur, self.chargeur,
                                                len(self.photos))
        except Exception as erreur:
            messagebox.showerror("Mode barrer indisponible",
                                 "La detection des visages n'a pas pu demarrer :\n%s"
                                 % erreur, parent=self.fenetre)
            return False
        self.detection.avancer(min(self.position, len(self.photos) - 1))
        self.visionneuse.outil = self.outil
        return True

    def _desactiver_barrage(self):
        """Arrete la detection ; les bandeaux non enregistres sont abandonnes."""
        if self.attente_visages is not None:
            self.fenetre.after_cancel(self.attente_visages)
            self.attente_visages = None
        self.outil.vider()
        self.visionneuse.outil = None
        self.visionneuse.demander_dessin()
        if self.detection is not None:
            self.detection.arreter()
            self.detection = None

    def _oublier_les_visages(self, index):
        """La photo a change : ses visages devront etre detectes de nouveau."""
        if self.detection is not None:
            self.detection.oublier(index)

    # ------------------------------------------------------------------
    # Clavier
    # ------------------------------------------------------------------

    def _touche(self, evenement):
        touche = evenement.keysym

        # Pendant le rognage, seules trois touches comptent : rien d'autre ne
        # doit deplacer ou changer la photo tant que le cadre est a l'ecran.
        if self.visionneuse.en_rognage:
            if touche in ("Return", "KP_Enter"):
                self.rogner()
            elif touche == "Escape" or touche.lower() == "c":
                self.abandonner_rognage()
            return "break"

        if touche == "Escape":
            self.quitter()
        elif touche == "Tab":
            self.basculer_barrage()
        elif touche in ("Return", "KP_Enter"):
            self.valider()
        elif touche in ("space", "Right"):
            self.suivante()
        elif touche == "Left":
            self.precedente()
        elif touche == "BackSpace":
            self.annuler()
        elif touche.lower() == "r":
            self.visionneuse.pivoter()
            self._mettre_a_jour_barre()
        elif touche.lower() == "c":
            self.commencer_rognage()
        elif evenement.char and self.touches_de_tri:
            nom_dossier = self.suivi.dossier_tri_pour_touche(evenement.char)
            if nom_dossier:
                self.ranger(nom_dossier)
        # « break » empeche Tk de traiter la touche a sa facon : sans cela, Tab
        # deplacerait le focus du clavier hors de la fenetre.
        return "break"

    # ------------------------------------------------------------------
    # Retouches : rotation et bandeaux
    # ------------------------------------------------------------------

    def _retouches_en_attente(self):
        return self.visionneuse.image is not None and (
            self.visionneuse.rotation != 0 or bool(self.outil.bandeaux()))

    def _preparer_retouches(self, chemin):
        """Garde une copie intacte de la photo, et met sa version retouchee en memoire.

        Le fichier ne sera reenregistre qu'en arriere-plan (voir ecritures.py) :
        la version retouchee est donc mise en memoire des maintenant, pour
        qu'un retour avec la fleche gauche la montre bien telle qu'elle sera
        enregistree. Les visages, eux, devront etre detectes de nouveau.

        Renvoie (chemin de la sauvegarde, bandeaux, rotation).
        """
        bandeaux = self.outil.bandeaux()
        rotation = self.visionneuse.rotation

        # Copie intacte AVANT toute modification, pour permettre l'annulation
        # (section 9.6). Si un rognage de cette photo est encore en cours
        # d'enregistrement, la copie attend la version a jour.
        self.ecritures.attendre(chemin)
        sauvegarde = copie_de_sauvegarde(chemin, self.suivi.chemin_dossier_temporaire())

        image = self.visionneuse.image
        apercu = self.visionneuse.apercu
        image_retouchee = appliquer_retouches(image, bandeaux, rotation)
        apercu_retouche = appliquer_retouches(apercu, bandeaux, rotation,
                                              echelle=apercu.width / image.width)
        self.chargeur.remplacer(self.position, image_retouchee, apercu_retouche)
        self._oublier_les_visages(self.position)
        return sauvegarde, bandeaux, rotation

    def valider(self):
        """Enregistre les retouches de la photo sur place, puis passe a la suivante.

        Sans retouche, rien n'est reecrit : cela eviterait une recompression
        inutile, qui degraderait la photo sans rien y ajouter.
        """
        if self.position >= len(self.photos):
            return
        nom_fichier = self.photos[self.position]
        dossier_actuel, chemin = self._localiser(nom_fichier)
        if chemin is not None and self._retouches_en_attente():
            sauvegarde, bandeaux, rotation = self._preparer_retouches(chemin)
            self.ecritures.ajouter(chemin, enregistrer_retouches, chemin, bandeaux, rotation)
            self.etat["historique"].append({
                "action": "retouche",
                "fichier": nom_fichier,
                "emplacement": dossier_actuel,
                "sauvegarde": sauvegarde,
                "index": self.position,
            })
        self.suivante()

    # ------------------------------------------------------------------
    # Rangement et navigation
    # ------------------------------------------------------------------

    def ranger(self, nom_dossier):
        """Deplace la photo affichee vers un dossier de tri, puis passe a la suivante.

        Les retouches en attente (rotation, bandeaux) sont enregistrees au
        passage : la touche de tri vaut validation.
        """
        if self.position >= len(self.photos):
            return

        nom_fichier = self.photos[self.position]
        dossier_actuel, chemin = self._localiser(nom_fichier)
        if chemin is None or dossier_actuel == nom_dossier:
            # Photo introuvable, ou deja dans ce dossier : il n'y a rien a
            # deplacer. On enregistre les retouches et on passe a la suivante.
            self.valider()
            return

        destination = os.path.join(self.suivi.chemin_dossier(nom_dossier), nom_fichier)
        if os.path.exists(destination):
            # Ne jamais ecraser une photo : on previent et on laisse tout en place.
            messagebox.showwarning(
                "Deplacement impossible",
                "Le dossier « %s » contient deja un fichier nomme « %s ».\n"
                "La photo n'a pas ete deplacee." % (nom_dossier, nom_fichier),
                parent=self.fenetre)
            self.fenetre.focus_force()
            return

        sauvegarde = None
        retouches = None
        if self._retouches_en_attente():
            sauvegarde, bandeaux, rotation = self._preparer_retouches(chemin)
            retouches = (bandeaux, rotation)

        # Si la photo vient d'etre rognee, son enregistrement peut etre encore
        # en cours : on attend qu'il soit fini avant de la deplacer.
        self.ecritures.attendre(chemin)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.move(chemin, destination)
        self.chargeur.changer_chemin(self.position, destination)
        # Les retouches sont enregistrees a la nouvelle place, en arriere-plan :
        # la fenetre n'attend pas la fin de l'encodage pour passer a la suite.
        if retouches is not None:
            self.ecritures.ajouter(destination, enregistrer_retouches, destination, *retouches)

        # L'historique permet d'annuler plusieurs actions de suite. Le dossier
        # de depart y est note, car en revue (ou apres un retour en arriere)
        # ce n'est pas forcement le dossier source. La sauvegarde, s'il y en
        # a une, permet d'annuler les retouches en meme temps que le rangement.
        self.etat["historique"].append({
            "action": "deplacement",
            "fichier": nom_fichier,
            "depuis": dossier_actuel,
            "dossier": nom_dossier,
            "sauvegarde": sauvegarde,
            "index": self.position,
        })
        self.position += 1
        self.suivi.enregistrer()
        self.afficher_photo_courante()

    def suivante(self):
        """Passe a la photo suivante sans rien deplacer (section 8.2)."""
        if self.position < len(self.photos):
            self.position += 1
            self.suivi.enregistrer()
            self.afficher_photo_courante()

    def precedente(self):
        """Revient a la photo precedente sans rien deplacer."""
        if self.position > 0:
            self.position -= 1
            self.suivi.enregistrer()
            self.afficher_photo_courante()

    # ------------------------------------------------------------------
    # Rognage
    # ------------------------------------------------------------------

    def commencer_rognage(self):
        if self.visionneuse.image is None:
            return
        self.visionneuse.commencer_rognage()
        self._mettre_a_jour_rappel()

    def abandonner_rognage(self):
        self.visionneuse.arreter_rognage()
        self._mettre_a_jour_rappel()

    def rogner(self):
        """Rogne la photo affichee selon le cadre trace, et l'enregistre sur place.

        La photo rognee est montree aussitot ; le fichier, lui, est reenregistre
        en arriere-plan (voir ecritures.py), ce qui evite de figer la fenetre
        pendant l'encodage. La rotation et les bandeaux en attente restent en
        attente : ils suivent simplement le nouveau cadrage.
        """
        cadre = self.visionneuse.cadre_de_rognage()
        if cadre is None:
            return      # aucun cadre trace : on reste en mode rognage

        nom_fichier = self.photos[self.position]
        dossier_actuel, chemin = self._localiser(nom_fichier)
        if chemin is None:
            self.abandonner_rognage()
            return

        rotation = self.visionneuse.rotation
        # La copie de sauvegarde doit etre prise sur le fichier a jour : si un
        # rognage precedent de cette photo est encore en cours d'enregistrement,
        # on l'attend.
        self.ecritures.attendre(chemin)
        sauvegarde = copie_de_sauvegarde(chemin, self.suivi.chemin_dossier_temporaire())
        self.ecritures.ajouter(chemin, rogner_fichier, chemin, cadre, rotation)

        self.etat["historique"].append({
            "action": "rognage",
            "fichier": nom_fichier,
            "emplacement": dossier_actuel,
            "sauvegarde": sauvegarde,
            "index": self.position,
        })
        self.suivi.enregistrer()

        # A l'ecran, le meme rognage est applique a la photo deja en memoire,
        # qui remplace l'ancienne version dans le cache.
        image = self.visionneuse.image
        gauche, haut, _, _ = cadre_dans_le_sens_d_origine(cadre, rotation,
                                                         image.width, image.height)
        image_rognee = rogner_image(image, cadre, rotation)
        apercu = fabriquer_apercu(image_rognee, self.chargeur.taille_apercu)
        self.chargeur.remplacer(self.position, image_rognee, apercu)
        self._oublier_les_visages(self.position)
        self.outil.decaler(gauche, haut, image_rognee.width, image_rognee.height)
        self.visionneuse.montrer(image_rognee, apercu,
                                 "Photo illisible : %s" % nom_fichier,
                                 garder_rotation=True)
        self._mettre_a_jour_rappel()
        self._mettre_a_jour_barre()

    # ------------------------------------------------------------------
    # Annulation
    # ------------------------------------------------------------------

    def annuler(self):
        """Annule la derniere action (rangement, retouche ou rognage) et reaffiche la photo."""
        historique = self.etat["historique"]
        if not historique:
            return

        # Les enregistrements en cours doivent etre termines avant de deplacer
        # ou de remettre en place un fichier.
        self.ecritures.attendre()

        derniere = historique.pop()
        if derniere.get("action") in ("rognage", "retouche"):
            self._remettre_la_sauvegarde(derniere)
        else:
            self._annuler_deplacement(derniere)

        self.position = derniere["index"]
        self.etat["terminee"] = False
        self.suivi.enregistrer()
        self.afficher_photo_courante()

    def _annuler_deplacement(self, deplacement):
        """Ramene la photo dans le dossier d'ou elle venait, sans ses retouches."""
        nom_fichier = deplacement["fichier"]
        # Les historiques ecrits par une version precedente ne notaient pas le
        # dossier de depart : c'etait alors toujours le dossier source (None).
        depuis = deplacement.get("depuis")
        chemin_actuel = os.path.join(self.suivi.chemin_dossier(deplacement["dossier"]),
                                     nom_fichier)
        chemin_retour = os.path.join(self._chemin_du_dossier(depuis), nom_fichier)

        if os.path.isfile(chemin_actuel) and not os.path.exists(chemin_retour):
            shutil.move(chemin_actuel, chemin_retour)
            self.chargeur.changer_chemin(deplacement["index"], chemin_retour)
            sauvegarde = deplacement.get("sauvegarde")
            if sauvegarde and os.path.isfile(sauvegarde):
                os.replace(sauvegarde, chemin_retour)
                self.chargeur.oublier(deplacement["index"])
                self._oublier_les_visages(deplacement["index"])

    def _remettre_la_sauvegarde(self, action):
        """Remet en place la copie intacte gardee avant un rognage ou une retouche."""
        sauvegarde = action.get("sauvegarde")
        chemin = os.path.join(self._chemin_du_dossier(action["emplacement"]),
                              action["fichier"])
        if sauvegarde and os.path.isfile(sauvegarde):
            os.replace(sauvegarde, chemin)
        # L'image en memoire est la version modifiee : il faut relire l'originale.
        self.chargeur.oublier(action["index"])
        self._oublier_les_visages(action["index"])

    # ------------------------------------------------------------------
    # Enregistrements en arriere-plan
    # ------------------------------------------------------------------

    def _surveiller_ecritures(self):
        """Verifie regulierement qu'aucun enregistrement en arriere-plan n'a echoue."""
        signaler_les_echecs(self.ecritures, self.chargeur, self.fenetre)
        self.surveillance = self.fenetre.after(300, self._surveiller_ecritures)

    # ------------------------------------------------------------------
    # Fermeture
    # ------------------------------------------------------------------

    def quitter(self):
        """Enregistre l'avancement et ferme la fenetre proprement.

        Les retouches provisoires de la photo affichee sont abandonnees, comme
        lorsqu'on passe a une autre photo.
        """
        self._annuler_attente()
        self.fenetre.after_cancel(self.surveillance)
        self.visionneuse.arreter()

        # Les dernieres retouches doivent etre enregistrees avant de fermer, et
        # avant de vider le dossier des sauvegardes.
        self.etiquette_avancement.config(text="Enregistrement des dernieres modifications...")
        self.fenetre.update_idletasks()
        self.ecritures.arreter()
        signaler_les_echecs(self.ecritures, self.chargeur, self.fenetre)

        # La detection se sert du chargeur : on l'arrete donc en premier, sans
        # quoi elle pourrait redemander une photo a un chargeur deja arrete.
        if self.detection is not None:
            self.detection.arreter()
        self.chargeur.arreter()

        # Les copies de sauvegarde ne servent qu'a l'annulation en cours de
        # session (section 9.6) : elles sont effacees a la fermeture, et les
        # rognages et retouches quittent donc l'historique. Les deplacements,
        # eux, restent annulables a la session suivante, sans leurs retouches.
        shutil.rmtree(self.suivi.chemin_dossier_temporaire(), ignore_errors=True)
        historique = []
        for action in self.etat["historique"]:
            if action.get("action") in ("rognage", "retouche"):
                continue
            action["sauvegarde"] = None
            historique.append(action)
        self.etat["historique"] = historique
        self.suivi.enregistrer()
        self.fenetre.destroy()
