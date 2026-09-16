"""
Affichage d'une photo en grand : zoom, deplacement de la vue, rotation et cadre
de rognage (sections 8.1 et 8 bis).

Sert a l'etape de tri et au mode revue. Tout ce qui se passe ici est purement
visuel : le zoom, le deplacement de la vue et la rotation ne modifient jamais le
fichier. Le cadre de rognage n'est lui aussi qu'un dessin a l'ecran : c'est
rognage.py qui l'applique au fichier, et seulement quand l'utilisateur valide.

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

from polices import police

# Bornes du zoom. 1.0 correspond a la photo entiere ajustee a la fenetre.
ZOOM_MINIMUM = 1.0
ZOOM_MAXIMUM = 8.0
PAS_DE_ZOOM = 1.15

# Luminosite conservee autour du cadre de rognage (0 = noir, 1 = inchange).
# La partie qui sera coupee est assombrie, pour bien voir ce qui restera.
LUMINOSITE_HORS_CADRE = 0.35

# Un cadre plus petit que ceci, en pixels de la photo, est considere comme un
# simple clic et non comme un rognage voulu.
TAILLE_MINIMALE_CADRE = 10

COULEUR_FOND = "#1e1e1e"
COULEUR_TEXTE = "#f0f0f0"
COULEUR_ERREUR = "#ff8080"
COULEUR_CADRE = "#ffffff"


class Visionneuse:
    """Canvas qui affiche une photo et gere le zoom, la vue et le cadre de rognage.

    Deux reperes coexistent :
    - les pixels de l'ecran, ceux du canvas ;
    - les pixels de la photo entiere telle qu'elle est affichee, c'est-a-dire
      apres la rotation d'examen. Le zoom, la vue et le cadre de rognage sont
      exprimes dans ce second repere, ce qui les rend independants de la
      taille de la fenetre et de la version de la photo utilisee pour dessiner.
    """

    def __init__(self, parent):
        self.canvas = tk.Canvas(parent, bg=COULEUR_FOND, highlightthickness=0)

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

        # Ce qui est actuellement a l'ecran.
        self.rendu = None             # portion de photo affichee (image Pillow)
        self.photo_tk = None          # la meme, convertie pour Tkinter
        self.photo_sombre_tk = None   # la meme assombrie (rognage uniquement)
        self.photo_cadre_tk = None    # partie claire, a l'interieur du cadre
        self.element_photo = None     # identifiant de la photo dans le canvas

        # Dessin differe : voir demander_dessin.
        self.dessin_programme = None
        self.photo_a_redessiner = False

        # Rognage : actif ou non, point de depart du trace, cadre obtenu.
        self.en_rognage = False
        self.depart_cadre = None
        self.cadre = None             # (gauche, haut, droite, bas) ou None

        # La molette : Windows et macOS envoient <MouseWheel> avec un sens dans
        # `delta` ; X11, donc la plupart des Linux, envoie plutot un clic du
        # bouton 4 (vers le haut) ou 5 (vers le bas). On branche les trois.
        self.canvas.bind("<MouseWheel>", self._molette)
        self.canvas.bind("<Button-4>", lambda evenement: self._molette(evenement, 1))
        self.canvas.bind("<Button-5>", lambda evenement: self._molette(evenement, -1))
        self.canvas.bind("<Button-1>", self._souris_pressee)
        self.canvas.bind("<B1-Motion>", self._souris_glissee)
        self.canvas.bind("<ButtonRelease-1>", self._souris_relachee)
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

    def afficher_texte(self, texte):
        """Remplace la photo par un simple texte (chargement, ecran de fin...)."""
        self.image = None
        self.apercu = None
        self.apercu_pivote = None
        self.versions_zoom = {}
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
        """Montre la photo entiere ; cliquer-glisser trace alors un cadre."""
        self._remettre_a_zero()
        self.en_rognage = True
        self.demander_dessin()

    def arreter_rognage(self):
        self.en_rognage = False
        self.cadre = None
        self.depart_cadre = None
        self._demander_dessin_du_cadre()

    def cadre_de_rognage(self):
        """Cadre trace par l'utilisateur, en pixels entiers de la photo affichee.

        Renvoie None si aucun cadre n'a ete trace, ou s'il est trop petit pour
        correspondre a un rognage voulu.
        """
        if self.cadre is None:
            return None
        gauche, haut, droite, bas = (round(valeur) for valeur in self.cadre)
        if droite - gauche < TAILLE_MINIMALE_CADRE or bas - haut < TAILLE_MINIMALE_CADRE:
            return None
        return (gauche, haut, droite, bas)

    def arreter(self):
        """Annule un dessin programme. A appeler avant de fermer la fenetre."""
        if self.dessin_programme is not None:
            self.canvas.after_cancel(self.dessin_programme)
            self.dessin_programme = None

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
        self.depart_cadre = None

    def _appliquer_rotation(self):
        """Fait pivoter l'apercu, seulement quand la photo ou la rotation change.

        Seul l'apercu, petit, est pivote tout de suite (quelques millisecondes).
        La photo entiere ne l'est que si l'utilisateur zoome (voir
        _version_pour_le_zoom) : on evite ainsi de faire tourner 24 millions de
        pixels a chaque appui sur R.
        """
        self.versions_zoom = {}
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
        """Rapport entre un pixel de la photo et un pixel de l'ecran, zoom compris."""
        largeur_photo, hauteur_photo = self._dimensions()
        largeur = max(self.canvas.winfo_width(), 1)
        hauteur = max(self.canvas.winfo_height(), 1)
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

        if self.zoom == 1.0 and version.size == cible:
            # Cas le plus frequent : vue d'ensemble, et l'apercu a ete prepare
            # exactement a la taille de la zone d'affichage. Il est montre tel
            # quel, sans aucun calcul.
            self.rendu = version
        else:
            # Apercu : LANCZOS donne le rendu le plus net et reste rapide sur
            # une petite image. Zoom : BILINEAR, deux fois plus rapide, garde
            # le deplacement de la vue fluide.
            filtre = Image.LANCZOS if version is self.apercu_pivote else Image.BILINEAR
            self.rendu = version.resize(cible, filtre, box=zone)

        self.photo_tk = ImageTk.PhotoImage(self.rendu)
        self.photo_sombre_tk = None
        if self.en_rognage:
            # Preparee une fois pour toutes : le trace du cadre n'aura plus
            # qu'a la montrer (voir _dessiner_cadre).
            sombre = ImageEnhance.Brightness(self.rendu).enhance(LUMINOSITE_HORS_CADRE)
            self.photo_sombre_tk = ImageTk.PhotoImage(sombre)

        self.coin_ecran = ((largeur_canvas - cible[0]) // 2,
                           (hauteur_canvas - cible[1]) // 2)
        self.element_photo = self.canvas.create_image(*self.coin_ecran, anchor="nw",
                                                      image=self.photo_tk)
        self._dessiner_cadre()

    def _dessiner_cadre(self):
        """Dessine le cadre de rognage par-dessus la photo deja affichee.

        Pendant qu'on trace le cadre, la photo elle-meme n'est pas recalculee.
        Deux versions en ont ete preparees : l'une normale, l'autre assombrie.
        La version assombrie occupe le fond, et on pose par-dessus, a
        l'interieur du cadre, le morceau correspondant de la version normale :
        ce qui sera coupe apparait sombre, ce qui restera garde sa luminosite.
        """
        self.canvas.delete("cadre")
        if self.element_photo is None:
            return

        cadre_visible = (self.en_rognage and self.cadre is not None
                         and self.photo_sombre_tk is not None)
        fond = self.photo_sombre_tk if cadre_visible else self.photo_tk
        self.canvas.itemconfig(self.element_photo, image=fond)
        if not cadre_visible:
            return

        # Le cadre est exprime en pixels de la photo : on le ramene aux pixels
        # de l'image affichee, qui commence au coin de la vue.
        facteur = self._facteur()
        gauche = max(0, round((self.cadre[0] - self.vue_x) * facteur))
        haut = max(0, round((self.cadre[1] - self.vue_y) * facteur))
        droite = min(self.rendu.width, round((self.cadre[2] - self.vue_x) * facteur))
        bas = min(self.rendu.height, round((self.cadre[3] - self.vue_y) * facteur))

        if droite > gauche and bas > haut:
            self.photo_cadre_tk = ImageTk.PhotoImage(
                self.rendu.crop((gauche, haut, droite, bas)))
            self.canvas.create_image(self.coin_ecran[0] + gauche, self.coin_ecran[1] + haut,
                                     anchor="nw", image=self.photo_cadre_tk, tags="cadre")

        ecran_gauche, ecran_haut = self._vers_ecran(self.cadre[0], self.cadre[1])
        ecran_droite, ecran_bas = self._vers_ecran(self.cadre[2], self.cadre[3])
        self.canvas.create_rectangle(ecran_gauche, ecran_haut, ecran_droite, ecran_bas,
                                     outline=COULEUR_CADRE, width=2, tags="cadre")

    # ------------------------------------------------------------------
    # Souris : deplacement de la vue, ou trace du cadre de rognage
    # ------------------------------------------------------------------

    def _souris_pressee(self, evenement):
        if self.image is None:
            return
        if self.en_rognage:
            # Presser le bouton commence un nouveau cadre : pour corriger un
            # cadre mal trace, il suffit donc d'en tracer un autre.
            self.depart_cadre = self._point_dans_la_photo(evenement.x, evenement.y)
            self.cadre = None
            self._demander_dessin_du_cadre()
        else:
            self.glissement = (evenement.x, evenement.y)

    def _souris_glissee(self, evenement):
        if self.en_rognage:
            self._tracer_cadre(evenement)
        else:
            self._deplacer_vue(evenement)

    def _souris_relachee(self, evenement):
        self.glissement = None
        self.depart_cadre = None

    def _tracer_cadre(self, evenement):
        """Le cadre va du point ou le bouton a ete presse jusqu'a la souris.

        Les coordonnees sont rangees par ordre croissant : l'utilisateur peut
        ainsi tracer dans n'importe quel sens (vers le haut, vers la gauche...).
        """
        if self.depart_cadre is None:
            return
        depart_x, depart_y = self.depart_cadre
        x, y = self._point_dans_la_photo(evenement.x, evenement.y)
        self.cadre = (min(depart_x, x), min(depart_y, y),
                      max(depart_x, x), max(depart_y, y))
        self._demander_dessin_du_cadre()

    def _point_dans_la_photo(self, x_ecran, y_ecran):
        """Point de la photo sous la souris, ramene a l'interieur de la photo.

        Le cadre ne peut ainsi jamais deborder, meme si la souris sort de la photo.
        """
        x, y = self._vers_photo(x_ecran, y_ecran)
        largeur_photo, hauteur_photo = self._dimensions()
        return (max(0.0, min(x, largeur_photo)), max(0.0, min(y, hauteur_photo)))

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
