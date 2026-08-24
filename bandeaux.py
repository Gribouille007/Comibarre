"""
Le bandeau de censure : sa geometrie, ses poignees, son dessin.

Un bandeau est un rectangle noir plein, pose sur les yeux d'une personne et
incline comme sa tete. Ce module ne connait ni Tkinter ni la detection de
visages : il ne manipule que des coordonnees exprimees en pixels de la photo.
C'est ce qui permet d'utiliser exactement les memes calculs pour l'affichage a
l'ecran et pour l'incrustation definitive dans le fichier enregistre.
"""

import math

# Proportions du bandeau par rapport a l'ecartement des deux yeux.
# Un bandeau doit deborder franchement de part et d'autre des yeux pour que la
# personne ne soit plus identifiable, sans pour autant couvrir tout le visage.
FACTEUR_LONGUEUR = 2.2
FACTEUR_EPAISSEUR = 0.8
EPAISSEUR_MINIMALE = 6

# Taille d'un bandeau cree a la main, quand la detection a echoue (section 9.4).
# Exprimee en pixels de la photo : elle est ajustee a la taille de l'image pour
# rester visible aussi bien sur une petite photo que sur une tres grande.
LONGUEUR_MANUELLE_PAR_DEFAUT = 0.08   # 8 % de la largeur de la photo
RAPPORT_EPAISSEUR_MANUELLE = 0.35     # epaisseur = 35 % de la longueur

# Distance, en pixels ecran, en dessous de laquelle on considere que la souris
# est posee sur une poignee.
RAYON_POIGNEE = 7


class Bandeau:
    """Un rectangle noir eventuellement incline.

    Il est decrit par le centre, la longueur, l'epaisseur et l'angle, plutot que
    par ses quatre coins : c'est cette description qui rend le deplacement, le
    redimensionnement et la rotation simples a ecrire.
    """

    def __init__(self, centre_x, centre_y, longueur, epaisseur, angle,
                 manuel=False):
        self.centre_x = centre_x
        self.centre_y = centre_y
        self.longueur = longueur
        self.epaisseur = epaisseur
        self.angle = angle          # en degres, 0 = horizontal
        self.manuel = manuel        # True si pose a la main par l'utilisateur

    # ------------------------------------------------------------------
    # Constructions
    # ------------------------------------------------------------------

    @classmethod
    def depuis_yeux(cls, oeil_droit, oeil_gauche):
        """Construit le bandeau d'un visage detecte, a partir de ses deux yeux.

        Le bandeau est centre sur le milieu des deux yeux, et son angle est
        celui de la droite qui les relie. C'est ce qui lui fait epouser
        l'inclinaison de la tete (section 9.3) : si la personne penche la tete,
        le bandeau penche d'autant, au lieu de rester horizontal.
        """
        x_droit, y_droit = oeil_droit
        x_gauche, y_gauche = oeil_gauche

        centre_x = (x_droit + x_gauche) / 2
        centre_y = (y_droit + y_gauche) / 2

        ecart = math.hypot(x_gauche - x_droit, y_gauche - y_droit)
        # atan2 donne l'angle de la droite reliant les deux yeux, en radians.
        angle = math.degrees(math.atan2(y_gauche - y_droit, x_gauche - x_droit))

        longueur = max(ecart * FACTEUR_LONGUEUR, EPAISSEUR_MINIMALE * 2)
        epaisseur = max(ecart * FACTEUR_EPAISSEUR, EPAISSEUR_MINIMALE)
        return cls(centre_x, centre_y, longueur, epaisseur, angle, manuel=False)

    @classmethod
    def manuel_par_defaut(cls, x, y, largeur_photo):
        """Construit un bandeau de taille standard la ou l'utilisateur a clique."""
        longueur = max(largeur_photo * LONGUEUR_MANUELLE_PAR_DEFAUT, 24)
        epaisseur = max(longueur * RAPPORT_EPAISSEUR_MANUELLE, EPAISSEUR_MINIMALE)
        return cls(x, y, longueur, epaisseur, 0.0, manuel=True)

    # ------------------------------------------------------------------
    # Geometrie
    # ------------------------------------------------------------------

    def _cos_sin(self):
        radians = math.radians(self.angle)
        return math.cos(radians), math.sin(radians)

    def _vers_repere_local(self, x, y):
        """Exprime un point dans le repere du bandeau (non incline, centre en 0).

        On ramene le point au centre du bandeau, puis on annule la rotation.
        Dans ce repere, tester si le point est dans le rectangle revient a
        comparer ses coordonnees a la demi-longueur et a la demi-epaisseur.
        """
        cosinus, sinus = self._cos_sin()
        dx = x - self.centre_x
        dy = y - self.centre_y
        return (dx * cosinus + dy * sinus, -dx * sinus + dy * cosinus)

    def _vers_repere_photo(self, local_x, local_y):
        """Operation inverse de _vers_repere_local."""
        cosinus, sinus = self._cos_sin()
        return (self.centre_x + local_x * cosinus - local_y * sinus,
                self.centre_y + local_x * sinus + local_y * cosinus)

    def coins(self):
        """Les quatre coins du rectangle, dans l'ordre, en coordonnees photo."""
        demi_longueur = self.longueur / 2
        demi_epaisseur = self.epaisseur / 2
        return [
            self._vers_repere_photo(-demi_longueur, -demi_epaisseur),
            self._vers_repere_photo(demi_longueur, -demi_epaisseur),
            self._vers_repere_photo(demi_longueur, demi_epaisseur),
            self._vers_repere_photo(-demi_longueur, demi_epaisseur),
        ]

    def contient(self, x, y, marge=0):
        """Le point est-il sur le bandeau ?"""
        local_x, local_y = self._vers_repere_local(x, y)
        return (abs(local_x) <= self.longueur / 2 + marge
                and abs(local_y) <= self.epaisseur / 2 + marge)

    def poignees(self):
        """Les poignees de manipulation, en coordonnees photo (section 9.4).

        - "longueur"  : au milieu du bord droit, pour allonger ou raccourcir ;
        - "epaisseur" : au milieu du bord bas, pour epaissir ou affiner ;
        - "rotation"  : au-dessus du bandeau, pour l'incliner.
        """
        demi_longueur = self.longueur / 2
        demi_epaisseur = self.epaisseur / 2
        distance_rotation = demi_epaisseur + max(self.epaisseur, 18)
        return {
            "longueur": self._vers_repere_photo(demi_longueur, 0),
            "epaisseur": self._vers_repere_photo(0, demi_epaisseur),
            "rotation": self._vers_repere_photo(0, -distance_rotation),
        }

    # ------------------------------------------------------------------
    # Manipulation a la souris
    # ------------------------------------------------------------------

    def deplacer(self, dx, dy):
        self.centre_x += dx
        self.centre_y += dy

    def tirer_poignee(self, nom_poignee, x, y):
        """Applique le deplacement d'une poignee jusqu'au point (x, y)."""
        local_x, local_y = self._vers_repere_local(x, y)

        if nom_poignee == "longueur":
            # La poignee est au bord droit : la demi-longueur suit la souris.
            self.longueur = max(abs(local_x) * 2, EPAISSEUR_MINIMALE * 2)
        elif nom_poignee == "epaisseur":
            self.epaisseur = max(abs(local_y) * 2, EPAISSEUR_MINIMALE)
        elif nom_poignee == "rotation":
            # L'angle vise est celui du vecteur allant du centre vers la souris.
            # La poignee etant placee au-dessus du bandeau, on ajoute 90 degres
            # pour que le bandeau reste perpendiculaire a ce vecteur.
            angle_souris = math.degrees(math.atan2(y - self.centre_y,
                                                   x - self.centre_x))
            self.angle = angle_souris + 90

    # ------------------------------------------------------------------
    # Dessin definitif
    # ------------------------------------------------------------------

    def dessiner(self, dessin):
        """Incruste le bandeau dans l'image, via un objet ImageDraw de Pillow."""
        dessin.polygon(self.coins(), fill=(0, 0, 0))

    # ------------------------------------------------------------------
    # Enregistrement dans le fichier de suivi
    # ------------------------------------------------------------------

    def en_dictionnaire(self):
        return {
            "centre_x": self.centre_x,
            "centre_y": self.centre_y,
            "longueur": self.longueur,
            "epaisseur": self.epaisseur,
            "angle": self.angle,
            "manuel": self.manuel,
        }

    @classmethod
    def depuis_dictionnaire(cls, donnees):
        return cls(donnees["centre_x"], donnees["centre_y"], donnees["longueur"],
                   donnees["epaisseur"], donnees["angle"], donnees["manuel"])


def poignee_sous_la_souris(bandeau, x, y, tolerance):
    """Renvoie le nom de la poignee situee sous le point, ou None.

    `tolerance` est exprimee en pixels de la photo : l'appelant la calcule a
    partir du facteur d'affichage, pour que la zone sensible garde toujours la
    meme taille a l'ecran quel que soit le zoom.
    """
    for nom, (poignee_x, poignee_y) in bandeau.poignees().items():
        if math.hypot(x - poignee_x, y - poignee_y) <= tolerance:
            return nom
    return None
