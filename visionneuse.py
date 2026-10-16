"""
Affichage d'une photo en grand : zoom, deplacement de la vue, rotation et cadre
de rognage (sections 8.1 et 8 bis).

Sert a l'etape de tri et au mode revue. Rien de ce qui se passe ici n'ecrit sur
le disque : le zoom et le deplacement de la vue sont purement visuels, et la
rotation et le cadre de rognage ne sont que des propositions a l'ecran. C'est
la fenetre (rangement.py) qui les fait enregistrer, et seulement quand
l'utilisateur valide.

Le rognage se fait en reduisant les bords de la photo, comme sur un telephone
(decision de l'utilisateur, 16 octobre 2026) : a l'ouverture, le cadre epouse
la photo entiere, et l'on tire l'un de ses quatre bords, l'un de ses quatre
coins, ou le cadre entier. Auparavant il fallait tracer un rectangle a la
souris, ce qui obligeait a repartir de zero des qu'on l'avait mal place, et ne
permettait pas de ne retirer qu'une bande sur un seul cote.

En mode « barrer », les clics sur la photo sont confies a un outil (voir
censure.py), qui pose et retouche les bandeaux. La visionneuse lui transmet les
clics en coordonnees de la photo d'origine, et lui laisse peindre ses bandeaux
sur l'image affichee.

Fluidite (section 11.1). Redimensionner une photo de 24 millions de pixels
prend pres d'un cinquieme de seconde : bien trop pour le refaire a chaque
mouvement de souris. La visionneuse part donc toujours de la plus petite
version de la photo qui reste assez detaillee : l'apercu, prepare a l'avance
par le chargeur exactement a la taille de la zone d'affichage, pour la vue
d'ensemble, et des versions reduites de moitie en moitie quand on zoome. De plus, quand plusieurs
mouvements de souris arrivent coup sur coup, un seul dessin est fait.
"""

import tkinter as tk

from PIL import Image, ImageEnhance, ImageTk

import theme
from polices import police

# Bornes du zoom. 1.0 correspond a la photo entiere ajustee a la fenetre.
ZOOM_MINIMUM = 1.0
ZOOM_MAXIMUM = 8.0
PAS_DE_ZOOM = 1.15

# Luminosite conservee autour du cadre de rognage (0 = noir, 1 = inchange).
# La partie qui sera coupee est assombrie, pour bien voir ce qui restera.
LUMINOSITE_HORS_CADRE = 0.35

# Un cadre plus petit que ceci, en pixels de la photo, ne correspond pas a un
# rognage voulu : il est ignore.
TAILLE_MINIMALE_CADRE = 10

# Deplacement, en pixels ecran, en dessous duquel un appui suivi d'un
# relachement compte comme un simple clic, et non comme un glissement.
SEUIL_DE_GLISSEMENT = 4

# --- Rognage -------------------------------------------------------------
# Ces distances sont exprimees en pixels d'ecran, et non en pixels de la photo :
# les bords du cadre s'attrapent ainsi toujours aussi facilement, que la photo
# mesure 600 ou 6000 pixels de large.
TOLERANCE_BORD = 12          # distance a laquelle un bord ou un coin se saisit
COTE_MINIMAL_ECRAN = 44      # cote minimal du cadre : en dessous, on ne pourrait
                             # plus rattraper ses bords a la souris
LONGUEUR_EQUERRE = 26        # trait d'angle, aux quatre coins du cadre
LONGUEUR_TRAIT_MILIEU = 24   # trait au milieu de chaque bord
EPAISSEUR_TRAIT_PRISE = 3
# Espace laisse autour de la photo pendant le rognage. Sans lui, le cadre part
# colle aux bords de la fenetre : ses prises sont alors a moitie hors de
# l'ecran, et le bord exterieur est penible a attraper a la souris.
MARGE_ROGNAGE = 48

# Forme du pointeur au-dessus de chaque partie du cadre. Elle annonce a
# l'utilisateur ce qu'un appui va faire, avant qu'il n'appuie.
CURSEURS_ROGNAGE = {
    "gauche": "sb_h_double_arrow",
    "droite": "sb_h_double_arrow",
    "haut": "sb_v_double_arrow",
    "bas": "sb_v_double_arrow",
    "haut_gauche": "top_left_corner",
    "haut_droite": "top_right_corner",
    "bas_gauche": "bottom_left_corner",
    "bas_droite": "bottom_right_corner",
    "interieur": "fleur",
}

COULEUR_FOND = theme.NOIR_PHOTO
COULEUR_TEXTE = theme.TEXTE
COULEUR_ERREUR = theme.ALERTE
COULEUR_CADRE = "#ffffff"
COULEUR_GRILLE = "#8f8f8f"


class Visionneuse:
    """Canvas qui affiche une photo et gere le zoom, la vue et le cadre de rognage.

    Deux reperes coexistent :
    - les pixels de l'ecran, ceux du canvas ;
    - les pixels de la photo entiere telle qu'elle est affichee, c'est-a-dire
      apres la rotation d'examen. Le zoom, la vue et le cadre de rognage sont
      exprimes dans ce second repere, ce qui les rend independants de la
      taille de la fenetre et de la version de la photo utilisee pour dessiner.
    """

    def __init__(self, parent, au_changement_du_cadre=None):
        """`au_changement_du_cadre` est appele chaque fois que le cadre de
        rognage bouge, pour que la fenetre puisse en afficher les dimensions."""
        self.canvas = tk.Canvas(parent, bg=COULEUR_FOND, highlightthickness=0)
        self.au_changement_du_cadre = au_changement_du_cadre

        self.image = None             # photo entiere, dans son sens d'origine
        self.apercu = None            # la meme, reduite a la taille de l'affichage
        self.apercu_pivote = None     # l'apercu apres la rotation d'examen
        self.versions_zoom = {}       # reduction (1, 2, 4...) -> photo pivotee reduite d'autant
        self.message = ""             # texte montre quand il n'y a pas de photo
        self.couleur_message = COULEUR_TEXTE
        self.rotation = 0             # en degres, dans le sens des aiguilles d'une montre
        self.zoom = 1.0
        self.vue_x = 0.0              # coin haut-gauche de la portion visible
        self.vue_y = 0.0
        self.coin_ecran = (0, 0)      # position de la photo dans le canvas
        self.glissement = None

        # Outil auquel sont confies les clics (mode barrer), ou None. Voir
        # censure.OutilBandeaux pour les methodes qu'il doit offrir.
        self.outil = None
        self.clic_pour_l_outil = False    # l'appui en cours a-t-il ete pris par l'outil ?
        self.point_presse = None
        self.a_glisse = False

        # Ce qui est actuellement a l'ecran.
        self.rendu = None             # portion de photo affichee (image Pillow)
        self.rendu_nu = None          # la meme, sans les bandeaux de l'outil
        self.cle_rendu = None         # ce qui a servi a fabriquer rendu_nu
        self.photo_tk = None          # la meme, convertie pour Tkinter
        self.image_sombre = None      # la meme assombrie (rognage uniquement)
        self.bandes_tk = []           # bandes sombres autour du cadre de rognage
        self.cle_bandes = None        # decoupes qui ont servi a les fabriquer
        self.element_photo = None     # identifiant de la photo dans le canvas

        # Forme du pointeur actuellement demandee. Le pointeur est regle ici, et
        # nulle part ailleurs : voir definir_curseur.
        self.curseur = ""

        # Dessin differe : voir demander_dessin.
        self.dessin_programme = None
        self.photo_a_redessiner = False

        # Rognage. Le cadre est exprime en pixels de la photo affichee ; il
        # couvre la photo entiere tant qu'on ne l'a pas reduit.
        self.en_rognage = False
        self.cadre = None             # (gauche, haut, droite, bas) ou None
        self.prise_rognage = None     # bord, coin ou « interieur » en cours de
                                      # deplacement, ou None si rien n'est saisi
        self.cadre_au_depart = None   # cadre au moment ou la prise a ete saisie
        self.depart_ecran = None      # point du canvas ou elle a ete saisie

        # La molette : Windows et macOS envoient <MouseWheel> avec un sens dans
        # `delta` ; X11, donc la plupart des Linux, envoie plutot un clic du
        # bouton 4 (vers le haut) ou 5 (vers le bas). On branche les trois.
        self.canvas.bind("<MouseWheel>", self._molette)
        self.canvas.bind("<Button-4>", lambda evenement: self._molette(evenement, 1))
        self.canvas.bind("<Button-5>", lambda evenement: self._molette(evenement, -1))
        self.canvas.bind("<Button-1>", self._souris_pressee)
        self.canvas.bind("<B1-Motion>", self._souris_glissee)
        self.canvas.bind("<ButtonRelease-1>", self._souris_relachee)
        self.canvas.bind("<Double-Button-1>", self._double_clic)
        self.canvas.bind("<Motion>", self._souris_bougee)
        self.canvas.bind("<Leave>", self._souris_sortie)
        self.canvas.bind("<Configure>", lambda evenement: self.demander_dessin())

    # ------------------------------------------------------------------
    # Ce que la fenetre demande a la visionneuse
    # ------------------------------------------------------------------

    def montrer(self, image, apercu, message_si_absente="", garder_rotation=False):
        """Affiche une nouvelle photo, ajustee a la fenetre.

        `apercu` est la meme photo reduite a la taille de l'affichage,
        preparee a l'avance par le chargeur. Si l'image est absente (fichier illisible ou
        introuvable), le message est affiche a sa place. `garder_rotation` sert
        apres un rognage : la photo rognee reste presentee dans le sens ou
        l'utilisateur l'examinait.
        """
        self.image = image
        self.apercu = apercu
        self.message = message_si_absente
        self.couleur_message = COULEUR_ERREUR
        if not garder_rotation:
            self.rotation = 0
        self._appliquer_rotation()
        self._remettre_a_zero()
        self.demander_dessin()

    def remplacer_apercu(self, apercu):
        """Remplace l'apercu de la photo affichee par une version d'une autre taille.

        Sert apres un redimensionnement de la fenetre, ou les apercus sont
        refaits a la nouvelle taille d'affichage. Contrairement a `montrer`,
        cette methode ne touche ni au zoom, ni a la rotation, ni au cadre de
        rognage : seule change la version de la photo qui sert a dessiner.
        """
        if self.image is None or apercu is None:
            return
        self.apercu = apercu
        self._appliquer_rotation()
        self.demander_dessin()

    def afficher_texte(self, texte):
        """Remplace la photo par un simple texte (chargement, ecran de fin...)."""
        self.image = None
        self.apercu = None
        self.apercu_pivote = None
        self.versions_zoom = {}
        self.cle_rendu = None
        self.message = texte
        self.couleur_message = COULEUR_TEXTE
        self._remettre_a_zero()
        self.demander_dessin()

    def pivoter(self):
        """Fait pivoter l'affichage d'un quart de tour (le fichier n'est pas modifie)."""
        if self.image is None:
            return
        self.rotation = (self.rotation + 90) % 360
        self._appliquer_rotation()
        self._remettre_a_zero()
        self.demander_dessin()

    def commencer_rognage(self):
        """Montre la photo entiere, cadre de rognage pose sur ses quatre bords.

        Le cadre part de la photo entiere, et non d'un rectangle vide : on le
        reduit en tirant ses bords, comme sur un telephone. Tant qu'aucun bord
        n'a bouge, valider ne rogne donc rien.
        """
        self._remettre_a_zero()
        self.en_rognage = True
        largeur_photo, hauteur_photo = self._dimensions()
        self.cadre = (0.0, 0.0, float(largeur_photo), float(hauteur_photo))
        self.demander_dessin()

    def arreter_rognage(self):
        self.en_rognage = False
        self.cadre = None
        self._oublier_la_prise()
        self.definir_curseur("")
        # Dessin complet, et non du seul cadre : la photo reprend toute la
        # place, l'espace laisse autour d'elle pendant le rognage disparaissant
        # avec lui (voir _facteur).
        self.demander_dessin()

    def cadre_de_rognage(self):
        """Cadre a decouper, en pixels entiers de la photo affichee.

        Renvoie None quand il n'y a rien a rogner : soit le cadre couvre encore
        toute la photo, soit il est trop petit pour correspondre a un rognage
        voulu. L'appelant ne doit alors rien reenregistrer, ce qui eviterait une
        recompression qui degraderait la photo sans la modifier.
        """
        if self.cadre is None:
            return None
        largeur_photo, hauteur_photo = self._dimensions()
        gauche, haut, droite, bas = (round(valeur) for valeur in self.cadre)
        if (gauche <= 0 and haut <= 0
                and droite >= round(largeur_photo) and bas >= round(hauteur_photo)):
            return None
        if droite - gauche < TAILLE_MINIMALE_CADRE or bas - haut < TAILLE_MINIMALE_CADRE:
            return None
        return (gauche, haut, droite, bas)

    def taille_du_cadre(self):
        """Dimensions du cadre de rognage en pixels, ou None s'il n'y a rien a rogner.

        Sert a les afficher dans la barre du bas : l'utilisateur voit ainsi
        exactement ce qu'il garde pendant qu'il ajuste les bords.
        """
        cadre = self.cadre_de_rognage()
        if cadre is None:
            return None
        return (cadre[2] - cadre[0], cadre[3] - cadre[1])

    def definir_curseur(self, forme):
        """Change la forme du pointeur, en retombant sur la fleche si inconnue.

        Toutes les formes ne sont pas connues sur tous les systemes (CLAUDE.md,
        section 4 ter) : d'ou le `try`. Le pointeur est regle ici, et nulle part
        ailleurs, pour que le rognage et le mode barrer ne se le disputent pas :
        auparavant, entrer en rognage faisait reclamer la fleche ordinaire par
        l'outil bandeaux, qui effacait aussitot le pointeur du rognage.
        """
        if forme == self.curseur:
            return
        self.curseur = forme
        try:
            self.canvas.config(cursor=forme)
        except tk.TclError:
            self.canvas.config(cursor="")
            self.curseur = ""

    def arreter(self):
        """Annule un dessin programme. A appeler avant de fermer la fenetre."""
        if self.dessin_programme is not None:
            self.canvas.after_cancel(self.dessin_programme)
            self.dessin_programme = None

    def facteur_affichage(self):
        """Nombre de pixels d'ecran pour un pixel de la photo, zoom compris."""
        if self.image is None:
            return 1.0
        return self._facteur()

    def point_d_origine(self, x_ecran, y_ecran):
        """Point de la photo d'origine (non pivotee) situe sous un point du canvas."""
        return self._affiche_vers_origine(*self._vers_photo(x_ecran, y_ecran))

    # ------------------------------------------------------------------
    # Rotation d'examen : passer d'un repere a l'autre
    # ------------------------------------------------------------------

    def _origine_vers_affiche(self, x, y):
        """Point de la photo d'origine -> meme point sur la photo pivotee a l'ecran.

        Les bandeaux sont toujours memorises dans le repere de la photo
        d'origine : ils restent ainsi a leur place quand on pivote la photo, et
        s'incrustent directement dans le fichier, avant que celui-ci soit
        lui-meme pivote. Pour les afficher, il faut donc faire tourner leurs
        points comme la photo.

        Quart de tour (90 degres) : le haut de la photo d'origine passe a
        droite de l'ecran. Un point situe a la distance y du haut se retrouve a
        la meme distance du bord droit, soit en x = hauteur - y ; et sa distance
        au bord gauche devient sa distance au haut de l'ecran. Les deux autres
        cas se raisonnent de la meme facon (voir aussi rognage.py).
        """
        largeur, hauteur = self.image.size
        if self.rotation == 90:
            return (hauteur - y, x)
        if self.rotation == 180:
            return (largeur - x, hauteur - y)
        if self.rotation == 270:
            return (y, largeur - x)
        return (x, y)

    def _affiche_vers_origine(self, x, y):
        """Operation inverse de _origine_vers_affiche."""
        largeur, hauteur = self.image.size
        if self.rotation == 90:
            return (y, hauteur - x)
        if self.rotation == 180:
            return (largeur - x, hauteur - y)
        if self.rotation == 270:
            return (largeur - y, x)
        return (x, y)

    # ------------------------------------------------------------------
    # Dessin differe
    # ------------------------------------------------------------------

    def demander_dessin(self):
        """Programme un nouveau dessin complet de la photo.

        Le dessin n'est pas fait tout de suite, mais des que Tkinter a fini de
        traiter les evenements en attente (after_idle). Si la souris envoie
        plusieurs mouvements pendant qu'un dessin se fait, ils sont tous pris
        en compte d'un coup, puis un seul nouveau dessin suit, avec la position
        la plus recente. Sans cela, les dessins s'empileraient et l'image
        suivrait la souris avec un retard croissant.
        """
        self.photo_a_redessiner = True
        self._programmer_dessin()

    def _demander_dessin_du_cadre(self):
        """Programme le dessin du seul cadre de rognage : la photo ne change pas."""
        self._programmer_dessin()

    def _programmer_dessin(self):
        if self.dessin_programme is None:
            self.dessin_programme = self.canvas.after_idle(self._dessiner)

    def _dessiner(self):
        self.dessin_programme = None
        if self.photo_a_redessiner:
            self.photo_a_redessiner = False
            self._dessiner_photo()          # redessine aussi le cadre
        else:
            self._dessiner_cadre()

    # ------------------------------------------------------------------
    # Calculs d'affichage
    # ------------------------------------------------------------------

    def _remettre_a_zero(self):
        """Photo entiere, sans zoom, et aucun rognage en cours."""
        self.zoom = 1.0
        self.vue_x = 0.0
        self.vue_y = 0.0
        self.glissement = None
        self.en_rognage = False
        self.cadre = None
        self._oublier_la_prise()
        # Le pointeur revient a la fleche ordinaire : sans cela, il gardait la
        # forme de la derniere prise du cadre (une fleche d'angle, par exemple)
        # apres un rognage valide, et restait ainsi tant que l'outil bandeaux
        # n'avait pas repris la main, ce qui n'arrive pas hors du mode barrer.
        self.definir_curseur("")

    def _oublier_la_prise(self):
        """Oublie le bord ou le coin du cadre que la souris tenait."""
        self.prise_rognage = None
        self.cadre_au_depart = None
        self.depart_ecran = None

    def _appliquer_rotation(self):
        """Fait pivoter l'apercu, seulement quand la photo ou la rotation change.

        Seul l'apercu, petit, est pivote tout de suite (quelques millisecondes).
        La photo entiere ne l'est que si l'utilisateur zoome (voir
        _version_pour_le_zoom) : on evite ainsi de faire tourner 24 millions de
        pixels a chaque appui sur R.
        """
        self.versions_zoom = {}
        self.cle_rendu = None
        if self.apercu is None or not self.rotation:
            self.apercu_pivote = self.apercu
        else:
            # expand=True agrandit le cadre pour que la photo pivotee tienne
            # entierement dedans, au lieu d'etre coupee.
            self.apercu_pivote = self.apercu.rotate(-self.rotation, expand=True)

    def _dimensions(self):
        """Largeur et hauteur de la photo entiere, apres la rotation d'examen."""
        largeur, hauteur = self.image.size
        if self.rotation in (90, 270):
            return hauteur, largeur
        return largeur, hauteur

    def _facteur(self):
        """Rapport entre un pixel de la photo et un pixel de l'ecran, zoom compris.

        Pendant le rognage, la photo est un peu reduite pour qu'un espace
        subsiste tout autour : le cadre commence sur ses bords, et il faut
        pouvoir les saisir sans buter sur le bord de la fenetre.
        """
        largeur_photo, hauteur_photo = self._dimensions()
        marge = 2 * MARGE_ROGNAGE if self.en_rognage else 0
        largeur = max(self.canvas.winfo_width() - marge, 1)
        hauteur = max(self.canvas.winfo_height() - marge, 1)
        return min(largeur / largeur_photo, hauteur / hauteur_photo) * self.zoom

    def _zone_visible(self, facteur):
        """Taille, en pixels de la photo, de la portion montree a l'ecran."""
        largeur_photo, hauteur_photo = self._dimensions()
        largeur = min(largeur_photo, self.canvas.winfo_width() / facteur)
        hauteur = min(hauteur_photo, self.canvas.winfo_height() / facteur)
        return largeur, hauteur

    def _vers_photo(self, x_ecran, y_ecran):
        """Convertit un point du canvas en coordonnees de la photo affichee."""
        facteur = self._facteur()
        return (self.vue_x + (x_ecran - self.coin_ecran[0]) / facteur,
                self.vue_y + (y_ecran - self.coin_ecran[1]) / facteur)

    def _vers_ecran(self, x_photo, y_photo):
        """Operation inverse de _vers_photo."""
        facteur = self._facteur()
        return (self.coin_ecran[0] + (x_photo - self.vue_x) * facteur,
                self.coin_ecran[1] + (y_photo - self.vue_y) * facteur)

    def _version_pour_le_zoom(self, facteur):
        """Plus petite version de la photo qui reste assez detaillee pour ce zoom.

        « Assez detaillee » : au moins un pixel de photo par pixel d'ecran.
        L'apercu suffit tant qu'on ne zoome pas, ou peu. Au-dela, on prend la
        photo entiere reduite de moitie autant de fois que possible : on ne
        redimensionne ainsi jamais plus de deux fois trop de pixels. Chaque
        version est fabriquee une seule fois, puis gardee pour les zooms et
        deplacements suivants.
        """
        largeur_photo, _ = self._dimensions()
        if self.apercu_pivote.width >= facteur * largeur_photo:
            return self.apercu_pivote

        reduction = 1
        while 1 / (reduction * 2) >= facteur:
            reduction *= 2
        if reduction not in self.versions_zoom:
            # On reduit avant de pivoter : il y a ainsi moins de pixels a tourner.
            version = self.image.reduce(reduction) if reduction > 1 else self.image
            if self.rotation:
                version = version.rotate(-self.rotation, expand=True)
            self.versions_zoom[reduction] = version
        return self.versions_zoom[reduction]

    def _dessiner_photo(self):
        """Dessine la photo dans le canvas, en tenant compte du zoom et du cadrage.

        Seule la portion visible de la photo est redimensionnee, et non la photo
        entiere. Sans cette precaution, zoomer x4 sur une photo de 24 millions de
        pixels obligerait a fabriquer une image de 400 millions de pixels en
        memoire ; ici, le travail reste proportionnel a la taille de la fenetre.
        """
        self.canvas.delete("all")
        self.element_photo = None
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
        largeur_visible, hauteur_visible = self._zone_visible(facteur)

        # Le cadrage ne doit jamais sortir de la photo.
        largeur_photo, hauteur_photo = self._dimensions()
        self.vue_x = max(0.0, min(self.vue_x, largeur_photo - largeur_visible))
        self.vue_y = max(0.0, min(self.vue_y, hauteur_photo - hauteur_visible))

        # La zone visible est ramenee a l'echelle de la version choisie.
        version = self._version_pour_le_zoom(facteur)
        echelle_x = version.width / largeur_photo
        echelle_y = version.height / hauteur_photo
        zone = (self.vue_x * echelle_x,
                self.vue_y * echelle_y,
                min(version.width, (self.vue_x + largeur_visible) * echelle_x),
                min(version.height, (self.vue_y + hauteur_visible) * echelle_y))
        cible = (max(1, round(largeur_visible * facteur)),
                 max(1, round(hauteur_visible * facteur)))

        # Quand seuls les bandeaux changent (on en tire un a la souris), la
        # portion de photo a montrer est la meme que la fois precedente : on la
        # reprend telle quelle au lieu de la recalculer a chaque mouvement.
        cle = (id(version), zone, cible)
        if cle != self.cle_rendu:
            if self.zoom == 1.0 and version.size == cible:
                # Cas le plus frequent : vue d'ensemble, et l'apercu a ete
                # prepare exactement a la taille de la zone d'affichage. Il est
                # montre tel quel, sans aucun calcul.
                self.rendu_nu = version
            else:
                # Apercu : LANCZOS donne le rendu le plus net et reste rapide
                # sur une petite image. Zoom : BILINEAR, deux fois plus rapide,
                # garde le deplacement de la vue fluide.
                filtre = Image.LANCZOS if version is self.apercu_pivote else Image.BILINEAR
                self.rendu_nu = version.resize(cible, filtre, box=zone)
            self.cle_rendu = cle

        self.rendu = self.rendu_nu
        if self.outil is not None:
            # Les bandeaux sont peints dans une copie : la portion de photo
            # sans bandeaux reste disponible pour le dessin suivant.
            self.rendu = self.rendu_nu.copy()

            def vers_rendu(x, y):
                """Point de la photo d'origine -> pixel de la portion affichee."""
                x_affiche, y_affiche = self._origine_vers_affiche(x, y)
                return ((x_affiche - self.vue_x) * facteur, (y_affiche - self.vue_y) * facteur)

            self.outil.peindre(self.rendu, vers_rendu)

        self.photo_tk = ImageTk.PhotoImage(self.rendu)
        # La portion affichee vient d'etre refaite : les bandes sombres gardees
        # pour le cadre ne correspondent plus a rien et seront redecoupees.
        self.image_sombre = None
        self.bandes_tk = []
        self.cle_bandes = None
        if self.en_rognage:
            # Version assombrie de la portion visible, preparee une fois par
            # photo (environ 8 millisecondes) : le trace du cadre n'a plus qu'a
            # y decouper les bandes qui entourent le cadre.
            self.image_sombre = ImageEnhance.Brightness(
                self.rendu).enhance(LUMINOSITE_HORS_CADRE)

        self.coin_ecran = ((largeur_canvas - cible[0]) // 2,
                           (hauteur_canvas - cible[1]) // 2)
        self.element_photo = self.canvas.create_image(*self.coin_ecran, anchor="nw",
                                                      image=self.photo_tk)
        self._dessiner_cadre()

    def _dessiner_cadre(self):
        """Dessine le cadre de rognage par-dessus la photo deja affichee.

        Pendant qu'on ajuste le cadre, la photo elle-meme n'est pas recalculee :
        elle reste affichee telle quelle, en clair, et l'on pose par-dessus
        quatre bandes assombries, celles qui entourent le cadre. Ce qui sera
        coupe apparait donc sombre, ce qui restera garde sa luminosite.

        Pourquoi les bandes plutot que l'inverse. On obtient le meme resultat en
        assombrissant toute la photo et en reposant la partie claire a
        l'interieur du cadre, et c'est ce que faisait la version precedente. Le
        temps passe suit le nombre de pixels reposes a l'ecran : la partie
        claire est grande quand le cadre est grand, les bandes sont grandes
        quand il est petit. Or le rognage par les bords part toujours du cadre
        plein et ne fait que l'entamer. Mesures sur une photo de 24 millions de
        pixels affichee en 1620 x 1080, pour un ajustement complet :

            cadre a 95 % de la photo    3,3 ms   (contre 14,1 ms avant)
            cadre a 50 %               13,1 ms
            cadre a 10 %               16,0 ms

        La methode retenue est donc quatre fois plus rapide dans le cas de loin
        le plus courant. Son cas defavorable, un cadre reduit au dixieme de la
        photo, atteint le budget de 16,7 ms d'une image a 60 par seconde, mais
        sans consequence visible : les mouvements de souris sont regroupes par
        `after_idle` (voir demander_dessin), si bien que le cadre ne prend
        jamais de retard sur la souris, meme lorsqu'un dessin depasse.
        """
        self.canvas.delete("cadre")
        if self.element_photo is None:
            return
        if not (self.en_rognage and self.cadre is not None
                and self.image_sombre is not None):
            self.bandes_tk = []
            self.cle_bandes = None
            return

        # Le cadre est exprime en pixels de la photo : on le ramene aux pixels
        # de l'image affichee, qui commence au coin de la vue.
        facteur = self._facteur()
        largeur = self.rendu.width
        hauteur = self.rendu.height
        gauche = max(0, min(largeur, round((self.cadre[0] - self.vue_x) * facteur)))
        haut = max(0, min(hauteur, round((self.cadre[1] - self.vue_y) * facteur)))
        droite = max(0, min(largeur, round((self.cadre[2] - self.vue_x) * facteur)))
        bas = max(0, min(hauteur, round((self.cadre[3] - self.vue_y) * facteur)))

        # Les quatre bandes a assombrir : au-dessus et au-dessous du cadre sur
        # toute la largeur, puis a sa gauche et a sa droite entre les deux.
        decoupes = ((0, 0, largeur, haut),
                    (0, bas, largeur, hauteur),
                    (0, haut, gauche, bas),
                    (droite, haut, largeur, bas))

        # On ne redecoupe que si le cadre a reellement bouge : un simple survol,
        # qui ne change que la forme du pointeur, ne recalcule alors rien.
        if decoupes != self.cle_bandes:
            self.bandes_tk = [(decoupe, ImageTk.PhotoImage(self.image_sombre.crop(decoupe)))
                              for decoupe in decoupes
                              if decoupe[2] > decoupe[0] and decoupe[3] > decoupe[1]]
            self.cle_bandes = decoupes
        for decoupe, bande in self.bandes_tk:
            self.canvas.create_image(self.coin_ecran[0] + decoupe[0],
                                     self.coin_ecran[1] + decoupe[1],
                                     anchor="nw", image=bande, tags="cadre")

        ecran_gauche, ecran_haut = self._vers_ecran(self.cadre[0], self.cadre[1])
        ecran_droite, ecran_bas = self._vers_ecran(self.cadre[2], self.cadre[3])
        self._dessiner_prises(ecran_gauche, ecran_haut, ecran_droite, ecran_bas)

    def _dessiner_prises(self, gauche, haut, droite, bas):
        """Trace le contour du cadre, ses prises, et la grille des tiers.

        Les prises sont des traits epais : une equerre a chaque coin, et un
        trait au milieu de chaque bord. Elles disent ou poser la souris, et
        le trait du milieu montre que c'est le bord entier qui se tire, et pas
        seulement ses extremites.

        Tous ces traits sont strictement horizontaux ou verticaux : ils ne
        peuvent donc pas presenter de marches d'escalier, et Tkinter suffit a
        les dessiner. C'est la seule exception a la regle qui veut que les
        traces passent par Pillow (voir selection.py) : cette regle ne vise que
        les obliques, comme les bords inclines d'un bandeau.
        """
        largeur = droite - gauche
        hauteur = bas - haut

        # La grille des tiers n'apparait que pendant l'ajustement. Affichee en
        # permanence, elle encombrerait la photo sans rien apprendre de plus.
        if self.prise_rognage is not None:
            for proportion in (1 / 3, 2 / 3):
                x = gauche + largeur * proportion
                y = haut + hauteur * proportion
                self.canvas.create_line(x, haut, x, bas, fill=COULEUR_GRILLE,
                                        tags="cadre")
                self.canvas.create_line(gauche, y, droite, y, fill=COULEUR_GRILLE,
                                        tags="cadre")

        self.canvas.create_rectangle(gauche, haut, droite, bas,
                                     outline=COULEUR_CADRE, width=1, tags="cadre")

        # Sur un cadre devenu petit, les prises sont raccourcies pour ne pas se
        # rejoindre et noyer le cadre sous les traits.
        equerre = min(LONGUEUR_EQUERRE, largeur / 3, hauteur / 3)
        for x, y, vers_x, vers_y in ((gauche, haut, 1, 1), (droite, haut, -1, 1),
                                     (gauche, bas, 1, -1), (droite, bas, -1, -1)):
            self._trait_de_prise(x, y, x + equerre * vers_x, y)
            self._trait_de_prise(x, y, x, y + equerre * vers_y)

        demi_horizontal = min(LONGUEUR_TRAIT_MILIEU, largeur / 4) / 2
        demi_vertical = min(LONGUEUR_TRAIT_MILIEU, hauteur / 4) / 2
        milieu_x = gauche + largeur / 2
        milieu_y = haut + hauteur / 2
        self._trait_de_prise(milieu_x - demi_horizontal, haut,
                             milieu_x + demi_horizontal, haut)
        self._trait_de_prise(milieu_x - demi_horizontal, bas,
                             milieu_x + demi_horizontal, bas)
        self._trait_de_prise(gauche, milieu_y - demi_vertical,
                             gauche, milieu_y + demi_vertical)
        self._trait_de_prise(droite, milieu_y - demi_vertical,
                             droite, milieu_y + demi_vertical)

    def _trait_de_prise(self, x1, y1, x2, y2):
        """Trait epais d'une prise du cadre.

        « projecting » prolonge le trait d'une demi-epaisseur a chaque bout :
        sans cela, les deux traits d'une equerre laisseraient un creux a
        l'angle exact du cadre.
        """
        self.canvas.create_line(x1, y1, x2, y2, fill=COULEUR_CADRE,
                                width=EPAISSEUR_TRAIT_PRISE, capstyle="projecting",
                                tags="cadre")

    # ------------------------------------------------------------------
    # Souris : deplacement de la vue, ou trace du cadre de rognage
    # ------------------------------------------------------------------

    def _souris_pressee(self, evenement):
        if self.image is None:
            return
        self.point_presse = (evenement.x, evenement.y)
        self.a_glisse = False
        if self.en_rognage:
            # Presser le bouton saisit le bord, le coin ou le cadre qui se
            # trouve sous la souris. Un appui ailleurs ne saisit rien : le cadre
            # reste ou il est, au lieu d'etre efface comme avant.
            self.prise_rognage = self._prise_sous_la_souris(evenement.x, evenement.y)
            self.cadre_au_depart = self.cadre
            self.depart_ecran = (evenement.x, evenement.y)
            if self.prise_rognage is not None:
                self._demander_dessin_du_cadre()
            return

        # En mode barrer, l'outil prend l'appui s'il tombe sur un bandeau ou
        # sur une poignee. Sinon, cliquer-glisser deplace la vue, comme
        # d'habitude ; et un simple clic, sans glisser, posera un bandeau au
        # relachement (voir _souris_relachee).
        self.clic_pour_l_outil = (self.outil is not None and self.outil.pressee(
            *self.point_d_origine(evenement.x, evenement.y)))
        if not self.clic_pour_l_outil:
            self.glissement = (evenement.x, evenement.y)

    def _souris_glissee(self, evenement):
        # La photo peut avoir change entre l'appui et ce mouvement : rien
        # n'empeche d'appuyer sur une touche de tri en maintenant le bouton
        # enfonce. Sans cette garde, le calcul des coordonnees cherchait la
        # taille d'une photo devenue absente, et le logiciel s'arretait.
        if self.image is None:
            return

        if self.point_presse is not None:
            depart_x, depart_y = self.point_presse
            if (abs(evenement.x - depart_x) > SEUIL_DE_GLISSEMENT
                    or abs(evenement.y - depart_y) > SEUIL_DE_GLISSEMENT):
                self.a_glisse = True

        if self.en_rognage:
            self._ajuster_cadre(evenement)
        elif self.clic_pour_l_outil:
            self.outil.glissee(*self.point_d_origine(evenement.x, evenement.y))
        else:
            self._deplacer_vue(evenement)

    def _souris_relachee(self, evenement):
        if (self.outil is not None and not self.en_rognage and self.image is not None
                and self.point_presse is not None):
            self.outil.relachee(*self.point_d_origine(evenement.x, evenement.y),
                                a_glisse=self.a_glisse)
        self.glissement = None
        self.point_presse = None
        self.clic_pour_l_outil = False
        self.a_glisse = False

        prise_relachee = self.prise_rognage is not None
        self._oublier_la_prise()
        if prise_relachee:
            # La grille des tiers ne s'affiche que pendant l'ajustement : il
            # faut donc un dernier dessin pour la faire disparaitre.
            self._demander_dessin_du_cadre()

    def _double_clic(self, evenement):
        if self.outil is not None and not self.en_rognage and self.image is not None:
            self.outil.double_clic(*self.point_d_origine(evenement.x, evenement.y))

    def _souris_bougee(self, evenement):
        """Annonce ce que la souris survole, bouton relache.

        Pendant le rognage, c'est le cadre qui repond ; sinon, c'est l'outil
        bandeaux, quand il y en a un.
        """
        if self.point_presse is not None:
            return      # un glissement est en cours : voir _souris_glissee
        if self.en_rognage:
            self._survoler_le_cadre(evenement)
        elif self.outil is not None:
            if self.image is None:
                self.outil.survoler(None)
            else:
                self.outil.survoler(self.point_d_origine(evenement.x, evenement.y))

    def _souris_sortie(self, evenement):
        if self.en_rognage:
            self.definir_curseur("")
        elif self.outil is not None:
            self.outil.survoler(None)

    # ------------------------------------------------------------------
    # Rognage : saisir un bord, un coin, ou le cadre entier
    # ------------------------------------------------------------------

    def _prise_sous_la_souris(self, x_ecran, y_ecran):
        """Ce que la souris s'apprete a saisir sur le cadre de rognage.

        Renvoie le nom d'un bord (« gauche », « haut »...), d'un coin
        (« haut_gauche »...), « interieur » pour deplacer le cadre entier, ou
        None si la souris est ailleurs.

        Les coins sont examines avant les bords : au voisinage d'un angle, les
        deux zones se recouvrent, et c'est le coin que l'utilisateur vise, car
        lui seul permet de regler les deux cotes d'un seul geste.

        Les noms composes ne sont pas un detail d'affichage : « haut_gauche »
        contient « haut » et « gauche », ce qui permet a _cadre_apres_prise de
        savoir quels bords deplacer sans enumerer les huit cas.
        """
        if self.cadre is None:
            return None
        gauche, haut = self._vers_ecran(self.cadre[0], self.cadre[1])
        droite, bas = self._vers_ecran(self.cadre[2], self.cadre[3])

        pres_de_gauche = abs(x_ecran - gauche) <= TOLERANCE_BORD
        pres_de_droite = abs(x_ecran - droite) <= TOLERANCE_BORD
        pres_du_haut = abs(y_ecran - haut) <= TOLERANCE_BORD
        pres_du_bas = abs(y_ecran - bas) <= TOLERANCE_BORD
        # Un bord ne se saisit que sur sa longueur, pas dans son prolongement
        # au-dela du cadre.
        dans_la_hauteur = haut - TOLERANCE_BORD <= y_ecran <= bas + TOLERANCE_BORD
        dans_la_largeur = gauche - TOLERANCE_BORD <= x_ecran <= droite + TOLERANCE_BORD

        if dans_la_hauteur and dans_la_largeur:
            horizontal = "haut" if pres_du_haut else "bas" if pres_du_bas else ""
            vertical = "gauche" if pres_de_gauche else "droite" if pres_de_droite else ""
            if horizontal and vertical:
                return horizontal + "_" + vertical
            if horizontal or vertical:
                return horizontal or vertical

        if gauche < x_ecran < droite and haut < y_ecran < bas:
            return "interieur"
        return None

    def _cote_minimal(self):
        """Cote minimal du cadre, en pixels de la photo.

        Il est fixe en pixels d'ecran puis converti : sur une photo de 6000
        pixels de large comme sur une de 600, le cadre reste assez grand pour
        qu'on puisse rattraper ses bords a la souris. Sans cette limite, un
        geste un peu vif reduirait le cadre a un trait dont plus aucun bord ne
        serait saisissable.
        """
        largeur_photo, hauteur_photo = self._dimensions()
        en_pixels_photo = COTE_MINIMAL_ECRAN / max(self._facteur(), 0.0001)
        return min(max(TAILLE_MINIMALE_CADRE, en_pixels_photo),
                   largeur_photo, hauteur_photo)

    def _cadre_apres_prise(self, x_ecran, y_ecran):
        """Nouveau cadre apres avoir tire la prise jusqu'au point (x_ecran, y_ecran).

        Le calcul part toujours du cadre tel qu'il etait au moment de la saisie,
        et non du cadre courant : les arrondis ne s'accumulent donc pas, et le
        cadre suit la souris exactement, meme apres un long glissement.
        """
        facteur = self._facteur()
        decalage_x = (x_ecran - self.depart_ecran[0]) / facteur
        decalage_y = (y_ecran - self.depart_ecran[1]) / facteur
        gauche, haut, droite, bas = self.cadre_au_depart
        largeur_photo, hauteur_photo = self._dimensions()

        if self.prise_rognage == "interieur":
            # Le cadre entier se deplace : sa taille ne change pas, et il reste
            # entierement dans la photo.
            largeur_cadre = droite - gauche
            hauteur_cadre = bas - haut
            gauche = min(max(gauche + decalage_x, 0.0), largeur_photo - largeur_cadre)
            haut = min(max(haut + decalage_y, 0.0), hauteur_photo - hauteur_cadre)
            return (gauche, haut, gauche + largeur_cadre, haut + hauteur_cadre)

        cote = self._cote_minimal()
        if "gauche" in self.prise_rognage:
            gauche = min(max(gauche + decalage_x, 0.0), droite - cote)
        if "droite" in self.prise_rognage:
            droite = max(min(droite + decalage_x, largeur_photo), gauche + cote)
        if "haut" in self.prise_rognage:
            haut = min(max(haut + decalage_y, 0.0), bas - cote)
        if "bas" in self.prise_rognage:
            bas = max(min(bas + decalage_y, hauteur_photo), haut + cote)
        return (gauche, haut, droite, bas)

    def _ajuster_cadre(self, evenement):
        """Deplace le bord, le coin ou le cadre que la souris tient."""
        if self.prise_rognage is None or self.cadre_au_depart is None:
            return
        self.cadre = self._cadre_apres_prise(evenement.x, evenement.y)
        self._demander_dessin_du_cadre()
        if self.au_changement_du_cadre is not None:
            self.au_changement_du_cadre()

    def _survoler_le_cadre(self, evenement):
        """Met la forme du pointeur en accord avec ce que la souris survole."""
        prise = self._prise_sous_la_souris(evenement.x, evenement.y)
        self.definir_curseur(CURSEURS_ROGNAGE.get(prise, ""))

    def _deplacer_vue(self, evenement):
        if self.glissement is None or self.image is None:
            return
        ancien_x, ancien_y = self.glissement
        facteur = self._facteur()
        # Un deplacement de la souris vers la droite fait glisser la vue vers
        # la gauche dans la photo, d'ou le signe negatif.
        self.vue_x -= (evenement.x - ancien_x) / facteur
        self.vue_y -= (evenement.y - ancien_y) / facteur
        self.glissement = (evenement.x, evenement.y)
        self.demander_dessin()

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def _molette(self, evenement, sens=None):
        """Zoome ou dezoome. `sens` vaut 1 ou -1 quand l'evenement ne le dit pas."""
        # Pendant le rognage, la photo reste entiere a l'ecran : le cadre se
        # trace ainsi toujours sur la photo complete.
        if self.image is None or self.en_rognage:
            return
        if sens is None:
            sens = 1 if evenement.delta > 0 else -1
        self._zoomer(PAS_DE_ZOOM if sens > 0 else 1 / PAS_DE_ZOOM)

    def _zoomer(self, multiplicateur):
        """Change le zoom en gardant au centre le meme point de la photo."""
        largeur_avant, hauteur_avant = self._zone_visible(self._facteur())
        centre_x = self.vue_x + largeur_avant / 2
        centre_y = self.vue_y + hauteur_avant / 2

        self.zoom = max(ZOOM_MINIMUM, min(ZOOM_MAXIMUM, self.zoom * multiplicateur))

        largeur_apres, hauteur_apres = self._zone_visible(self._facteur())
        self.vue_x = centre_x - largeur_apres / 2
        self.vue_y = centre_y - hauteur_apres / 2
        self.demander_dessin()
