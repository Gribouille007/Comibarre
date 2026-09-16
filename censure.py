"""
Etape 2 - La censure des yeux (section 9).

Les photos d'un seul dossier de tri sont passees en revue. Sur chacune, le
logiciel detecte les visages et la position des yeux ; l'utilisateur clique sur
une tete pour poser un bandeau noir, reclique pour le retirer. La touche Entree
incruste les bandeaux et reenregistre la photo par-dessus l'originale. Les
fleches gauche et droite circulent d'une photo a l'autre sans rien enregistrer.

Point important : tant que la photo n'est pas validee, rien n'est ecrit sur le
disque (section 9.3). Les bandeaux ne sont que des dessins provisoires a l'ecran.
"""

import os
import shutil
import tkinter as tk

from PIL import Image, ImageTk

import selection
from bandeaux import Bandeau, poignee_sous_la_souris, remplir_polygone_lisse
from dossiers import photos_du_dossier
from ecritures import EcrituresEnArrierePlan, signaler_les_echecs
from images import (ChargeurAnticipe, charger_image, copie_de_sauvegarde,
                    enregistrer_au_format_origine, format_origine)
from polices import police
from visages import DetecteurVisages, DetectionAnticipee, visage_le_plus_proche

COULEUR_FOND = "#1e1e1e"
COULEUR_TEXTE = "#f0f0f0"
COULEUR_ERREUR = "#ff8080"

# Deplacement, en pixels ecran, en dessous duquel on considere que l'utilisateur
# a clique et non fait glisser. Sert a distinguer « selectionner un bandeau »
# de « deplacer un bandeau » (section 9.4).
SEUIL_DE_GLISSEMENT = 4

# Distances en pixels ecran, independantes du zoom.
TOLERANCE_POIGNEE = 11      # rayon de la zone sensible autour d'une poignee
MARGE_PRISE = 3             # debord accepte autour d'un bandeau, pour le saisir
MARGE_ROTATION = 30         # distance entre le bord du bandeau et sa poignee de rotation

# Forme du pointeur selon ce qui se trouve dessous. Tk traduit ces noms sur
# chaque systeme ; si l'un d'eux manque, on retombe sur la fleche ordinaire.
POINTEURS = {
    None: "",
    "corps": "fleur",
    "longueur_droite": "sb_h_double_arrow",
    "longueur_gauche": "sb_h_double_arrow",
    "epaisseur_haut": "sb_v_double_arrow",
    "epaisseur_bas": "sb_v_double_arrow",
    "rotation": "exchange",
}

# Delai, en millisecondes, avant de regarder de nouveau si une photo qui
# n'etait pas encore prete l'est enfin.
DELAI_ATTENTE_CHARGEMENT = 15


def incruster_bandeaux(chemin, liste_bandeaux):
    """Incruste les bandeaux dans le fichier et le reenregistre dans son format.

    La photo est relue et remise dans le bon sens AVANT l'incrustation,
    exactement comme elle etait affichee : les bandeaux se retrouvent donc a
    l'emplacement ou l'utilisateur les a poses (section 9.5).

    Cette fonction est executee en arriere-plan (voir ecritures.py). La copie
    de sauvegarde a deja ete faite par l'appelant.
    """
    format_image = format_origine(chemin)
    image = charger_image(chemin)
    for bandeau in liste_bandeaux:
        bandeau.dessiner(image)
    enregistrer_au_format_origine(image, chemin, format_image)


class FenetreCensure:
    """Fenetre de l'etape de censure."""

    def __init__(self, racine, suivi, nom_dossier):
        self.suivi = suivi
        self.nom_dossier = nom_dossier
        self.dossier = suivi.chemin_dossier(nom_dossier)
        self.photos = suivi.censure["photos"]

        # Etat de la photo courante (jamais enregistre sur le disque).
        self.image = None
        self.apercu = None           # photo reduite a la taille de l'affichage
        self.image_ecran = None      # apercu ajuste a la taille exacte de l'affichage
        self.message = ""            # texte montre quand il n'y a pas de photo
        self.couleur_message = COULEUR_TEXTE
        self.visages = []
        self.bandeaux_visages = {}   # index du visage -> Bandeau
        self.bandeaux_manuels = []
        self.bandeau_selectionne = None
        self.photo_tk = None

        # Etat de la manipulation a la souris.
        self.action = None           # None, "poignee" ou "corps"
        self.poignee_active = None
        self.point_presse = None
        self.a_glisse = False
        self.double_clic_en_cours = False
        self.survol = None           # nom de poignee, "corps", ou None

        # Dessin differe et attente du chargement (voir _demander_dessin et
        # _montrer_des_que_prete).
        self.dessin_programme = None
        self.attente = None

        chemins = [os.path.join(self.dossier, nom) for nom in self.photos]
        taille_ecran = (racine.winfo_screenwidth(), racine.winfo_screenheight())
        self.chargeur = ChargeurAnticipe(chemins, taille_ecran)
        try:
            self.detecteur = DetecteurVisages()
            self.detection = DetectionAnticipee(self.detecteur, self.chargeur,
                                                len(self.photos))
        except Exception:
            # Le chargement anticipe est deja lance : si la detection echoue
            # (modele absent par exemple), il faut l'arreter avant de laisser
            # remonter l'erreur. Sans cela, un fil continuerait a lire des
            # photos alors que la fenetre ne s'ouvrira jamais, et le dossier
            # resterait « ouvert » pour Windows.
            self.chargeur.arreter()
            raise
        self.ecritures = EcrituresEnArrierePlan()

        self.fenetre = tk.Toplevel(racine)
        self.fenetre.title("Censure - %s / %s" % (suivi.nom_evenement, nom_dossier))
        self.fenetre.geometry("1200x800")
        self.fenetre.configure(bg=COULEUR_FOND)
        self.fenetre.protocol("WM_DELETE_WINDOW", self.quitter)

        self._construire()
        self._brancher_commandes()
        self.fenetre.after(60, self.afficher_photo_courante)
        self.surveillance = self.fenetre.after(300, self._surveiller_ecritures)

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    def _construire(self):
        self.canvas = tk.Canvas(self.fenetre, bg=COULEUR_FOND, highlightthickness=0)
        self.canvas.pack(side="top", fill="both", expand=True)

        barre = tk.Frame(self.fenetre, bg="#2b2b2b")
        barre.pack(side="bottom", fill="x")

        self.etiquette_avancement = tk.Label(barre, text="", bg="#2b2b2b",
                                             fg=COULEUR_TEXTE,
                                             font=police(11, gras=True),
                                             anchor="w", padx=10, pady=6)
        self.etiquette_avancement.pack(side="left")

        rappel = ("Clic = poser ou choisir un bandeau  |  "
                  "Double-clic = le retirer  |  Entree = enregistrer  |  "
                  "Espace ou → = passer  |  ← = precedente  |  "
                  "Retour arriere = annuler  |  Echap = quitter")
        tk.Label(barre, text=rappel, bg="#2b2b2b", fg="#b8b8b8",
                 font=police(9), anchor="e", padx=10).pack(side="right")

    def _brancher_commandes(self):
        self.fenetre.bind("<Key>", self._touche)
        self.canvas.bind("<Button-1>", self._souris_pressee)
        self.canvas.bind("<Double-Button-1>", self._double_clic)
        self.canvas.bind("<B1-Motion>", self._souris_glissee)
        self.canvas.bind("<ButtonRelease-1>", self._souris_relachee)
        self.canvas.bind("<Motion>", self._souris_bougee)
        self.canvas.bind("<Leave>", lambda evenement: self._changer_survol(None))
        self.canvas.bind("<Configure>", self._zone_d_affichage_changee)
        self.fenetre.focus_force()

    def _zone_d_affichage_changee(self, evenement):
        """Les apercus sont prepares exactement a la taille de la zone d'affichage :
        la photo s'y affiche alors sans etre redimensionnee."""
        if evenement.width >= 10 and evenement.height >= 10:
            self.chargeur.changer_taille_apercu((evenement.width, evenement.height))
        self._demander_dessin()

    # ------------------------------------------------------------------
    # Correspondance entre coordonnees ecran et coordonnees photo
    # ------------------------------------------------------------------

    def _facteur(self):
        """Rapport entre un pixel de la photo et un pixel de l'ecran."""
        if self.image is None:
            return 1.0
        largeur = max(self.canvas.winfo_width(), 1)
        hauteur = max(self.canvas.winfo_height(), 1)
        return min(largeur / self.image.width, hauteur / self.image.height)

    def _decalage(self, facteur):
        """Position du coin haut-gauche de la photo dans le canvas (photo centree)."""
        largeur_affichee = self.image.width * facteur
        hauteur_affichee = self.image.height * facteur
        return ((self.canvas.winfo_width() - largeur_affichee) / 2,
                (self.canvas.winfo_height() - hauteur_affichee) / 2)

    def _vers_photo(self, x_ecran, y_ecran):
        """Convertit un point du canvas en coordonnees de la photo."""
        facteur = self._facteur()
        decalage_x, decalage_y = self._decalage(facteur)
        return ((x_ecran - decalage_x) / facteur, (y_ecran - decalage_y) / facteur)

    # ------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------

    @property
    def position(self):
        return self.suivi.censure["position"]

    @position.setter
    def position(self, valeur):
        self.suivi.censure["position"] = valeur

    def afficher_photo_courante(self):
        self._annuler_attente()
        if self.position >= len(self.photos):
            self._afficher_fin()
            return

        self.bandeaux_visages = {}
        self.bandeaux_manuels = []
        self.bandeau_selectionne = None
        self._changer_survol(None)

        self.chargeur.avancer(self.position)
        self.detection.avancer(self.position)
        self._montrer_des_que_prete()

    def _montrer_des_que_prete(self, deja_en_attente=False):
        """Montre la photo courante des que sa lecture et sa detection sont faites.

        Les deux se font en arriere-plan (images.py et visages.py). Si
        l'utilisateur va plus vite qu'elles, on ne les fait pas ici, ce qui
        figerait la fenetre : on affiche « Chargement... » et on revient voir
        quelques millisecondes plus tard. La fenetre reste ainsi toujours
        reactive.
        """
        self.attente = None
        nom_fichier = self.photos[self.position]
        prete = (self.chargeur.est_prete(self.position)
                 and self.detection.est_prete(self.position))
        if not prete:
            if not deja_en_attente:
                self.image = None
                self.message = "Chargement..."
                self.couleur_message = COULEUR_TEXTE
                self.etiquette_avancement.config(
                    text="Photo %d sur %d   -   %s   -   chargement..."
                         % (self.position + 1, len(self.photos), nom_fichier))
                self._demander_dessin()
            self.attente = self.fenetre.after(DELAI_ATTENTE_CHARGEMENT,
                                              self._montrer_des_que_prete, True)
            return

        self.image, self.apercu = self.chargeur.photo(self.position)
        self.image_ecran = None
        self.visages = self.detection.visages(self.position) if self.image else []
        self.message = "Photo illisible"
        self.couleur_message = COULEUR_ERREUR

        self.etiquette_avancement.config(
            text="Photo %d sur %d   -   %s   -   %d visage(s) detecte(s)"
                 % (self.position + 1, len(self.photos), nom_fichier, len(self.visages)))
        self._demander_dessin()

    def _annuler_attente(self):
        if self.attente is not None:
            self.fenetre.after_cancel(self.attente)
            self.attente = None

    def _bandeaux_actifs(self):
        """Tous les bandeaux poses sur la photo, detectes et manuels confondus."""
        return list(self.bandeaux_visages.values()) + self.bandeaux_manuels

    def _demander_dessin(self):
        """Programme un nouveau dessin de la photo et de ses bandeaux.

        Le dessin n'est pas fait tout de suite, mais des que Tkinter a fini de
        traiter les evenements en attente (after_idle). Quand un bandeau est
        tire a la souris, plusieurs mouvements rapproches ne donnent donc lieu
        qu'a un seul dessin, avec la position la plus recente : le bandeau suit
        la souris sans retard.
        """
        if self.dessin_programme is None:
            self.dessin_programme = self.fenetre.after_idle(self._dessiner)

    def _dessiner(self):
        self.dessin_programme = None
        self.canvas.delete("all")

        largeur_canvas = self.canvas.winfo_width()
        hauteur_canvas = self.canvas.winfo_height()
        if largeur_canvas < 10 or hauteur_canvas < 10:
            return

        if self.image is None:
            self.canvas.create_text(largeur_canvas // 2, hauteur_canvas // 2,
                                    text=self.message, fill=self.couleur_message,
                                    font=police(16), justify="center")
            return

        facteur = self._facteur()
        taille = (max(1, round(self.image.width * facteur)),
                  max(1, round(self.image.height * facteur)))
        # La photo a la taille de la fenetre est gardee en memoire : pendant
        # qu'on manipule un bandeau a la souris, seul le bandeau change. Elle
        # est obtenue a partir de l'apercu, deja prepare a la taille de
        # l'affichage : le plus souvent, il n'y a donc rien a redimensionner.
        if self.image_ecran is None or self.image_ecran.size != taille:
            self.image_ecran = self.apercu.resize(taille, Image.LANCZOS)

        # Les bandeaux sont peints dans l'image affichee avec la meme geometrie
        # et le meme lissage des bords que ceux qui serviront a les incruster
        # dans le fichier : ce que l'utilisateur voit est donc bien ce qui sera
        # enregistre.
        affichee = self.image_ecran.copy()
        for bandeau in self._bandeaux_actifs():
            remplir_polygone_lisse(affichee, [(x * facteur, y * facteur)
                                              for x, y in bandeau.coins()])

        # L'habillage du bandeau choisi (contour et poignees) est peint dans
        # cette meme image, et non trace sur le canvas : Tkinter ne sait pas
        # lisser ses traits, alors que Pillow le fait (voir selection.py).
        if self.bandeau_selectionne is not None:
            bandeau = self.bandeau_selectionne
            selection.dessiner_habillage(
                affichee,
                [(x * facteur, y * facteur) for x, y in bandeau.coins()],
                {nom: (x * facteur, y * facteur)
                 for nom, (x, y) in bandeau.poignees(self._marge_rotation()).items()},
                self.survol if self.survol != "corps" else None)

        self.photo_tk = ImageTk.PhotoImage(affichee)
        decalage_x, decalage_y = self._decalage(facteur)
        self.canvas.create_image(decalage_x, decalage_y, anchor="nw", image=self.photo_tk)

    def _afficher_fin(self):
        self.image = None
        self.message = ("Toutes les photos du dossier « %s » ont ete parcourues.\n"
                        "Appuyez sur Echap pour revenir au menu." % self.nom_dossier)
        self.couleur_message = COULEUR_TEXTE
        self.etiquette_avancement.config(text="Censure terminee")
        self._demander_dessin()
        self.suivi.enregistrer()

    # ------------------------------------------------------------------
    # Souris
    # ------------------------------------------------------------------

    def _marge_rotation(self):
        """Distance bord-poignee de rotation, convertie en pixels de la photo."""
        return MARGE_ROTATION / max(self._facteur(), 0.0001)

    def _bandeau_sous_le_point(self, x, y):
        """Le bandeau situe sous un point de la photo, ou None.

        Les bandeaux manuels sont examines en premier, et les plus recents
        avant les plus anciens : ce sont ceux qui apparaissent au-dessus des
        autres a l'ecran, et c'est donc celui-la que l'utilisateur vise quand
        deux bandeaux se superposent.
        """
        marge = MARGE_PRISE / max(self._facteur(), 0.0001)
        for bandeau in reversed(self.bandeaux_manuels):
            if bandeau.contient(x, y, marge):
                return bandeau
        for bandeau in reversed(list(self.bandeaux_visages.values())):
            if bandeau.contient(x, y, marge):
                return bandeau
        return None

    def _bandeau_du_visage_vise(self, x, y):
        """Le bandeau deja pose sur le visage que designe ce point, ou None.

        Sert quand le clic tombe a cote du bandeau mais bien sur la tete :
        c'est ce bandeau-la que l'utilisateur veut atteindre.
        """
        index_visage = visage_le_plus_proche(self.visages, x, y)
        if index_visage is None:
            return None
        return self.bandeaux_visages.get(index_visage)

    def _ce_qui_est_sous_le_point(self, x, y):
        """Ce que designe un point de la photo : nom de poignee, "corps", ou None."""
        if self.bandeau_selectionne is not None:
            tolerance = TOLERANCE_POIGNEE / max(self._facteur(), 0.0001)
            poignee = poignee_sous_la_souris(self.bandeau_selectionne, x, y,
                                             tolerance, self._marge_rotation())
            if poignee:
                return poignee
        if self._bandeau_sous_le_point(x, y) is not None:
            return "corps"
        return None

    def _souris_pressee(self, evenement):
        if self.image is None:
            return
        self.point_presse = (evenement.x, evenement.y)
        self.a_glisse = False
        self.action = None
        self.poignee_active = None

        x, y = self._vers_photo(evenement.x, evenement.y)

        # Une poignee du bandeau choisi a la priorite sur tout le reste.
        vise = self._ce_qui_est_sous_le_point(x, y)
        if vise is not None and vise != "corps":
            self.action = "poignee"
            self.poignee_active = vise
            return

        # Sinon, un clic sur un bandeau existant, detecte ou manuel, le choisit
        # et permet de le deplacer. Il n'est jamais retire ici : c'est le
        # double-clic qui retire (voir _double_clic).
        bandeau = self._bandeau_sous_le_point(x, y)
        if bandeau is not None:
            self.bandeau_selectionne = bandeau
            self.action = "corps"
            self._demander_dessin()

    def _souris_glissee(self, evenement):
        if self.action is None or self.point_presse is None:
            return

        depart_x, depart_y = self.point_presse
        if (abs(evenement.x - depart_x) > SEUIL_DE_GLISSEMENT
                or abs(evenement.y - depart_y) > SEUIL_DE_GLISSEMENT):
            self.a_glisse = True

        x, y = self._vers_photo(evenement.x, evenement.y)

        if self.action == "poignee":
            self.bandeau_selectionne.tirer_poignee(self.poignee_active, x, y)
        elif self.action == "corps":
            ancien_x, ancien_y = self._vers_photo(depart_x, depart_y)
            self.bandeau_selectionne.deplacer(x - ancien_x, y - ancien_y)
            # Un glissement trop vif ne doit pas emporter le bandeau hors de la
            # photo, ou il ne serait plus visible nulle part.
            self.bandeau_selectionne.limiter_au_cadre(self.image.width,
                                                      self.image.height)
            self.point_presse = (evenement.x, evenement.y)

        self._demander_dessin()

    def _souris_relachee(self, evenement):
        """Termine la manipulation en cours, ou pose un bandeau la ou l'on a clique.

        Un simple clic sur un bandeau ou sur une de ses poignees ne fait rien de
        plus ici : le bandeau a deja ete choisi a l'enfoncement du bouton. C'est
        important, car les poignees « longueur » et « epaisseur » sont posees
        sur le bord meme du bandeau : les traiter comme un clic sur le bandeau
        ferait disparaitre celui-ci des qu'on effleure une poignee.
        """
        if self.double_clic_en_cours:
            # Le retrait vient d'etre fait par le double-clic : ce relachement
            # est celui de son second clic, il ne doit rien poser de nouveau.
            self.double_clic_en_cours = False
        elif not self.a_glisse and self.action is None and self.image is not None:
            self._clic_dans_le_vide(*self._vers_photo(evenement.x, evenement.y))

        self.action = None
        self.poignee_active = None
        self.point_presse = None
        self.a_glisse = False

    def _clic_dans_le_vide(self, x, y):
        """Pose un bandeau la ou l'utilisateur a clique (sections 9.3 et 9.4)."""
        # 1. Le clic tombe sur une tete detectee, mais a cote du bandeau deja
        #    pose dessus : on choisit ce bandeau plutot que d'en creer un autre.
        deja_pose = self._bandeau_du_visage_vise(x, y)
        if deja_pose is not None:
            self.bandeau_selectionne = deja_pose
            self._demander_dessin()
            return

        # 2. Le clic est rattache au visage detecte correspondant : le bandeau
        #    epouse alors l'inclinaison de la tete (section 9.3).
        index_visage = visage_le_plus_proche(self.visages, x, y)
        if index_visage is not None:
            visage = self.visages[index_visage]
            nouveau = Bandeau.depuis_yeux(visage.oeil_droit, visage.oeil_gauche)
            self.bandeaux_visages[index_visage] = nouveau
            self.bandeau_selectionne = nouveau
            self._demander_dessin()
            return

        # 3. Aucun visage a cet endroit : bandeau manuel de taille standard.
        nouveau = Bandeau.manuel_par_defaut(x, y, self.image.width)
        self.bandeaux_manuels.append(nouveau)
        self.bandeau_selectionne = nouveau
        self._demander_dessin()

    def _double_clic(self, evenement):
        """Retire le bandeau double-clique, qu'il ait ete pose a la main ou non.

        Le premier des deux clics a pu poser ou choisir un bandeau : le
        double-clic retire celui qui se trouve sous le pointeur, quel qu'il
        soit. Double-cliquer dans le vide revient donc a poser un bandeau puis
        a le retirer aussitot, c'est-a-dire a ne rien faire.
        """
        self.double_clic_en_cours = True
        if self.image is None:
            return

        x, y = self._vers_photo(evenement.x, evenement.y)
        bandeau = self._bandeau_sous_le_point(x, y)
        if bandeau is None:
            bandeau = self._bandeau_du_visage_vise(x, y)
        if bandeau is not None:
            self._retirer(bandeau)

    def _retirer(self, bandeau):
        """Retire un bandeau de la photo courante (rien n'est ecrit sur le disque)."""
        if bandeau in self.bandeaux_manuels:
            self.bandeaux_manuels.remove(bandeau)
        else:
            for index, pose in list(self.bandeaux_visages.items()):
                if pose is bandeau:
                    del self.bandeaux_visages[index]
                    break

        if self.bandeau_selectionne is bandeau:
            self.bandeau_selectionne = None
        self.action = None
        self.poignee_active = None
        self._changer_survol(None)
        self._demander_dessin()

    # ------------------------------------------------------------------
    # Survol : ce que la souris designe, sans avoir encore clique
    # ------------------------------------------------------------------

    def _souris_bougee(self, evenement):
        """Met en avant la poignee ou le bandeau que la souris survole.

        L'utilisateur voit ainsi ce qu'il va saisir avant d'appuyer, et la
        forme du pointeur lui dit ce qui va se passer.
        """
        if self.action is not None or self.image is None:
            return
        self._changer_survol(
            self._ce_qui_est_sous_le_point(*self._vers_photo(evenement.x, evenement.y)))

    def _changer_survol(self, nouveau):
        if nouveau == self.survol:
            return
        self.survol = nouveau
        try:
            self.canvas.config(cursor=POINTEURS.get(nouveau, ""))
        except tk.TclError:
            # Ce systeme ne connait pas ce pointeur : la fleche ordinaire fera.
            self.canvas.config(cursor="")
        self._demander_dessin()

    # ------------------------------------------------------------------
    # Clavier
    # ------------------------------------------------------------------

    def _touche(self, evenement):
        touche = evenement.keysym
        if touche == "Escape":
            self.quitter()
        elif touche in ("Return", "KP_Enter"):
            self.valider()
        elif touche in ("space", "Right"):
            self.passer()
        elif touche == "Left":
            self.precedente()
        elif touche == "BackSpace":
            self.annuler()

    # ------------------------------------------------------------------
    # Validation, passage, annulation
    # ------------------------------------------------------------------

    def valider(self):
        """Incruste les bandeaux, enregistre la photo sur place, puis passe a la suivante.

        L'enregistrement lui-meme se fait en arriere-plan (voir ecritures.py) :
        la photo suivante apparait sans attendre la fin de l'encodage.
        """
        if self.position >= len(self.photos):
            return

        nom_fichier = self.photos[self.position]
        chemin = os.path.join(self.dossier, nom_fichier)
        liste_bandeaux = self._bandeaux_actifs()

        sauvegarde = None
        if liste_bandeaux and os.path.isfile(chemin):
            # Copie intacte AVANT toute modification, pour permettre l'annulation
            # (section 9.6). Aucune photo d'origine n'est perdue tant que la
            # session est en cours. Si cette photo est encore en cours
            # d'enregistrement (validee, puis reprise apres un retour en
            # arriere), la copie attend la version a jour.
            self.ecritures.attendre(chemin)
            sauvegarde = copie_de_sauvegarde(chemin, self.suivi.chemin_dossier_temporaire())
            self.ecritures.ajouter(chemin, incruster_bandeaux, chemin, liste_bandeaux)

            # Le fichier ne sera a jour que dans un instant : la version
            # censuree est donc mise en memoire des maintenant, pour qu'un
            # retour avec la fleche gauche la montre bien avec ses bandeaux.
            # La detection, elle, devra etre refaite sur cette nouvelle version.
            self._garder_la_version_censuree(liste_bandeaux)
            self.detection.oublier(self.position)

        # Sans aucun bandeau, le fichier n'est pas reecrit : cela eviterait une
        # recompression inutile, qui degraderait la photo sans rien y ajouter.
        self.suivi.censure["historique"].append({
            "fichier": nom_fichier,
            "sauvegarde": sauvegarde,
            "index": self.position,
        })
        self.position += 1
        self.suivi.enregistrer()
        self.afficher_photo_courante()

    def _garder_la_version_censuree(self, liste_bandeaux):
        """Place dans le cache la photo et son apercu, bandeaux incrustes."""
        image = self.image.copy()
        for bandeau in liste_bandeaux:
            bandeau.dessiner(image)

        # L'apercu recoit les memes bandeaux, ramenes a son echelle.
        apercu = self.apercu.copy()
        echelle = apercu.width / image.width
        for bandeau in liste_bandeaux:
            remplir_polygone_lisse(apercu, [(x * echelle, y * echelle)
                                            for x, y in bandeau.coins()])
        self.chargeur.remplacer(self.position, image, apercu)

    def passer(self):
        """Passe a la photo suivante sans la modifier (section 9.5)."""
        if self.position < len(self.photos):
            self.position += 1
            self.suivi.enregistrer()
            self.afficher_photo_courante()

    def precedente(self):
        """Revient a la photo precedente sans rien enregistrer.

        Comme pour le passage, les bandeaux provisoires de la photo quittee sont
        abandonnes : seule la validation ecrit sur le disque.
        """
        if self.position > 0:
            self.position -= 1
            self.suivi.enregistrer()
            self.afficher_photo_courante()

    def annuler(self):
        """Annule la derniere validation en restaurant la copie d'origine (section 9.6)."""
        historique = self.suivi.censure["historique"]
        if not historique:
            return

        # L'enregistrement de la photo peut etre encore en cours : il doit etre
        # termine avant que l'on remette l'original en place.
        self.ecritures.attendre()

        derniere = historique.pop()
        sauvegarde = derniere.get("sauvegarde")
        if sauvegarde and os.path.isfile(sauvegarde):
            chemin = os.path.join(self.dossier, derniere["fichier"])
            shutil.move(sauvegarde, chemin)

        self.position = derniere["index"]
        # L'image restauree n'a plus de bandeaux : le cache doit etre vide pour
        # que ce soit bien l'original qui reapparaisse a l'ecran.
        self.chargeur.oublier(self.position)
        self.detection.oublier(self.position)
        self.suivi.enregistrer()
        self.afficher_photo_courante()

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
        """Enregistre l'avancement, vide le dossier temporaire, ferme la fenetre."""
        self._annuler_attente()
        self.fenetre.after_cancel(self.surveillance)
        if self.dessin_programme is not None:
            self.fenetre.after_cancel(self.dessin_programme)
            self.dessin_programme = None

        # Les dernieres photos validees doivent etre enregistrees avant de
        # fermer, et avant de vider le dossier des sauvegardes.
        self.etiquette_avancement.config(text="Enregistrement des dernieres photos...")
        self.fenetre.update_idletasks()
        self.ecritures.arreter()
        signaler_les_echecs(self.ecritures, self.chargeur, self.fenetre)

        # La detection se sert du chargeur : on l'arrete donc en premier, sans
        # quoi elle pourrait redemander une photo a un chargeur deja arrete.
        self.detection.arreter()
        self.chargeur.arreter()

        # Les copies de sauvegarde ne servent qu'a l'annulation en cours de
        # session (section 9.6) : elles sont effacees a la fermeture, et
        # l'historique correspondant devient donc inutilisable.
        shutil.rmtree(self.suivi.chemin_dossier_temporaire(), ignore_errors=True)
        self.suivi.censure["historique"] = []
        self.suivi.enregistrer()
        self.fenetre.destroy()


def lancer_censure(racine, suivi, nom_dossier):
    """Prepare le suivi puis ouvre l'etape de censure sur un dossier de tri."""
    chemin = suivi.chemin_dossier(nom_dossier)

    # On ne recalcule la liste des photos que lorsqu'on change de dossier :
    # reprendre le meme dossier doit retomber exactement sur la meme photo
    # qu'a la fermeture precedente (section 9.7).
    if (suivi.censure.get("dossier") != nom_dossier
            or not suivi.censure.get("photos")):
        suivi.censure["dossier"] = nom_dossier
        suivi.censure["photos"] = photos_du_dossier(chemin)
        suivi.censure["position"] = 0
        suivi.censure["historique"] = []
        suivi.enregistrer()
    elif suivi.censure["position"] >= len(suivi.censure["photos"]):
        # Le dossier avait deja ete parcouru en entier : le rouvrir signifie que
        # l'utilisateur veut le reprendre depuis le debut, et non retomber
        # aussitot sur l'ecran de fin.
        suivi.censure["photos"] = photos_du_dossier(chemin)
        suivi.censure["position"] = 0
        suivi.censure["historique"] = []
        suivi.enregistrer()

    if not suivi.censure["photos"]:
        return 0

    fenetre = FenetreCensure(racine, suivi, nom_dossier)
    racine.wait_window(fenetre.fenetre)
    return len(suivi.censure["photos"])
