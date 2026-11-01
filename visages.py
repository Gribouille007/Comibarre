"""
Detection des visages et de la position des yeux (section 9.2).

La detection s'appuie sur YuNet, un modele fourni avec OpenCV
(`cv2.FaceDetectorYN`). Il a ete retenu a la place de mediapipe apres mesures :
sur des photos de groupe, mediapipe ne detectait aucun visage la ou YuNet en
trouve plusieurs dizaines, y compris des visages de 10 a 25 pixels de large et
sur des photos fortement sous-exposees. Voir CLAUDE.md, section 2.

Tout ce qui concerne la detection est enferme ici : le reste du programme ne
manipule que des objets `Visage`, sans savoir quelle bibliotheque les produit.

Tetes penchees
--------------
YuNet trouve bien un visage penche, mais il place mal ses yeux : il les met a
peu pres a l'horizontale, comme sur un visage droit, au lieu de suivre la tete.
Mesure sur de vraies photos : une tete penchee de 40 degres donnait un bandeau
penche de 18 degres seulement, et les petits visages (moins de 100 pixels)
donnaient un bandeau presque horizontal quelle que soit la tete. Le bandeau
tombait alors a cote des yeux.

Deux remedes, dans `detecter` :

1. les PASSES TOURNEES : au-dela de 40 degres environ, YuNet ne voit plus du
   tout le visage. On cherche donc aussi sur la photo entiere tournee de
   45 degres dans un sens puis dans l'autre.
2. le REDRESSEMENT : chaque visage trouve est decoupe, agrandi et tourne pour
   que sa tete soit droite, puis detecte de nouveau. Sur un grand visage
   droit, YuNet place les yeux avec precision ; on ramene ensuite ces yeux
   dans la photo. Cela corrige aussi les tres grands visages (portrait
   rapproche), que YuNet repere mal : mesure, un oeil place a 64 % de l'ecart
   des yeux a cote de la pupille, contre 3 % une fois le visage redresse.
"""

import math
import os
import threading

import cv2
import numpy as np

# Modele livre avec le code, charge depuis le disque.
CHEMIN_MODELE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "modeles", "face_detection_yunet_2023mar.onnx")

# Seuil de confiance volontairement bas.
# Dans ce logiciel, rien n'est dessine tant que l'utilisateur n'a pas clique
# (section 9.3) : une detection en trop est donc invisible et sans consequence,
# alors qu'un visage manque oblige a poser un bandeau a la main (section 9.4).
# Mieux vaut donc trop detecter que pas assez.
SEUIL_CONFIANCE = 0.5

# La detection se fait sur une version reduite de la photo quand celle-ci est
# tres grande : au-dela, on gagne peu en fiabilite et on perd beaucoup en temps.
# Les coordonnees obtenues sont ensuite ramenees a l'echelle de la photo entiere.
LARGEUR_MAXI_DETECTION = 2400

# --- Redressement de chaque visage ---------------------------------------
# Ecart des yeux, en pixels, que l'on donne au visage dans la decoupe. YuNet ne
# suit l'inclinaison d'une tete que si le visage est grand : mesure sur
# 64 visages, il la suit a 76 % quand le visage fait 160 pixels de haut, mais
# a 20 % seulement quand il en fait 64. On agrandit donc les petits visages
# (et on reduit les tres grands, pour aller plus vite).
ECART_YEUX_REDRESSE = 80
# Cote de la decoupe carree, en pixels : le visage y tient avec une marge.
COTE_DECOUPE = 400
# On arrete de redresser quand la correction devient plus petite que ceci.
CORRECTION_NEGLIGEABLE = 1.0       # degres
NB_REDRESSEMENTS_MAXI = 3
# Les visages plus petits ne sont pas redresses. Dans une foule, ils sont des
# centaines, et chaque redressement coute quelques millisecondes ; surtout, le
# bandeau fait au moins EPAISSEUR_MINIMALE (6) pixels d'epaisseur (bandeaux.py),
# soit la moitie de l'ecart des yeux a 12 pixels : il tolere alors une erreur
# d'angle d'une vingtaine de degres, et davantage en dessous.
ECART_YEUX_MINI_REDRESSEMENT = 12  # pixels

# --- Passes sur la photo tournee ---------------------------------------
ANGLES_PASSES_TOURNEES = (45, -45)  # degres
# Les passes tournees se font sur la photo reduite de moitie. Elles ne servent
# qu'a trouver les tetes tres penchees assez grandes pour etre redressees (les
# plus petites ne pourraient pas etre confirmees, voir detecter) ; a cette
# taille, elles coutent a elles deux a peu pres autant que la passe droite.
ECHELLE_PASSES_TOURNEES = 0.5


class Visage:
    """Un visage detecte, avec la position de ses deux yeux.

    Les coordonnees sont exprimees en pixels de la photo remise dans le bon sens,
    c'est-a-dire exactement celles utilisees pour enregistrer les bandeaux.
    """

    def __init__(self, x, y, largeur, hauteur, oeil_droit, oeil_gauche, score):
        self.x = x
        self.y = y
        self.largeur = largeur
        self.hauteur = hauteur
        self.oeil_droit = oeil_droit      # (x, y) - oeil droit de la personne
        self.oeil_gauche = oeil_gauche    # (x, y) - oeil gauche de la personne
        self.score = score

    def contient(self, x, y, marge=0.0):
        """Le point est-il a l'interieur de la boite du visage, elargie de `marge` ?"""
        return (self.x - marge <= x <= self.x + self.largeur + marge
                and self.y - marge <= y <= self.y + self.hauteur + marge)


class DetecteurVisages:
    """Charge le modele une seule fois et detecte les visages photo par photo."""

    def __init__(self, chemin_modele=CHEMIN_MODELE, seuil=SEUIL_CONFIANCE):
        if not os.path.isfile(chemin_modele):
            raise FileNotFoundError(
                "Modele de detection introuvable : %s. "
                "Il doit etre livre avec le programme, dans le dossier modeles/."
                % chemin_modele)

        self.seuil = seuil
        self.detecteur = cv2.FaceDetectorYN.create(chemin_modele, "", (320, 320),
                                                   seuil, 0.3, 5000)
        # Le detecteur n'est pas prevu pour etre utilise par deux fils a la fois.
        self.verrou = threading.Lock()

    def detecter(self, image_pillow):
        """Renvoie la liste des visages trouves sur une photo Pillow."""
        if image_pillow is None:
            return []

        largeur_origine, hauteur_origine = image_pillow.size

        # Reduction eventuelle avant detection, pour borner le temps de calcul.
        facteur = 1.0
        image_travail = image_pillow
        if largeur_origine > LARGEUR_MAXI_DETECTION:
            facteur = LARGEUR_MAXI_DETECTION / largeur_origine
            nouvelle_taille = (LARGEUR_MAXI_DETECTION,
                               max(1, round(hauteur_origine * facteur)))
            image_travail = image_pillow.resize(nouvelle_taille)

        # OpenCV travaille en BGR, Pillow en RGB : il faut inverser les canaux.
        tableau = np.array(image_travail.convert("RGB"))[:, :, ::-1]
        tableau = np.ascontiguousarray(tableau)

        # 1. Les candidats : la photo telle quelle, puis tournee. Chacun est
        #    note (visage, vient_de_la_photo_droite).
        candidats = [(visage, True) for visage in self._passe(tableau, 0)]
        for angle in ANGLES_PASSES_TOURNEES:
            candidats.extend((visage, False) for visage in self._passe(tableau, angle))

        # 2. Un meme visage est souvent trouve par plusieurs passes. On examine
        #    les candidats du plus sur au moins sur (score de YuNet) : chaque
        #    visage est ainsi pris dans la passe ou il paraissait le plus droit,
        #    et ses autres detections, ensuite, sont reconnues et ignorees.
        #    Chaque visage retenu est redresse (voir _redresser).
        #
        #    La photo tournee fait aussi apparaitre des visages imaginaires, ou
        #    un vrai visage vu de travers, les yeux places sur la joue. Un
        #    candidat venu d'une passe tournee n'est donc garde que si YuNet le
        #    retrouve une fois la tete redressee. Ceux de la photo droite sont
        #    toujours gardes, comme avant.
        #
        #    Deux visages de la photo droite ne s'eliminent jamais l'un
        #    l'autre : YuNet a deja decide qu'ils etaient distincts, et dans
        #    une foule serree les yeux d'une personne tombent parfois dans la
        #    boite de sa voisine.
        candidats.sort(key=lambda candidat: candidat[0].score, reverse=True)
        retenus_droits = []      # visages venus de la photo droite
        retenus_tournes = []     # visages trouves seulement sur la photo tournee
        for candidat, vient_de_la_photo_droite in candidats:
            if vient_de_la_photo_droite:
                if _deja_connu(retenus_tournes, candidat):
                    continue    # deja pris, mieux vu, sur la photo tournee
            elif _deja_connu(retenus_droits + retenus_tournes, candidat):
                continue

            redresse, confirme = self._redresser(tableau, candidat)
            deja_pris = _deja_connu(retenus_droits + retenus_tournes, redresse)
            if vient_de_la_photo_droite:
                # Si le redressement a echoue, ou s'il a glisse sur un visage
                # deja retenu, on garde le visage tel que YuNet l'a trouve,
                # comme avant.
                retenus_droits.append(redresse if confirme and not deja_pris else candidat)
            elif confirme and not deja_pris:
                retenus_tournes.append(redresse)

        # 3. Retour a l'echelle de la photo entiere.
        echelle = 1.0 / facteur
        return [_agrandir(visage, echelle) for visage in retenus_droits + retenus_tournes]

    # ------------------------------------------------------------------
    # Les etapes de la detection
    # ------------------------------------------------------------------

    def _lancer_yunet(self, tableau):
        """Lance YuNet sur un tableau BGR ; renvoie ses lignes de resultats.

        Chaque ligne contient : x, y, largeur, hauteur de la boite, puis cinq
        points (oeil droit, oeil gauche, nez, coin droit et coin gauche de la
        bouche), puis le score de confiance.
        """
        hauteur, largeur = tableau.shape[:2]
        with self.verrou:
            # YuNet exige que la taille annoncee corresponde a l'image fournie.
            self.detecteur.setInputSize((largeur, hauteur))
            _, resultats = self.detecteur.detect(tableau)
        if resultats is None:
            return []
        return list(resultats)

    def _passe(self, tableau, angle):
        """Detecte les visages sur la photo tournee de `angle` degres.

        La photo tournee occupe un cadre plus grand que la photo (un carre
        deux fois plus grand pour 45 degres) ; elle est donc reduite de
        ECHELLE_PASSES_TOURNEES. Les visages trouves sont ramenes dans le
        repere de la photo.
        """
        if angle == 0:
            matrice = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
            tourne = tableau
        else:
            hauteur, largeur = tableau.shape[:2]
            radians = math.radians(angle)
            # Taille du cadre qui contient toute la photo une fois tournee.
            largeur_tournee = largeur * abs(math.cos(radians)) + hauteur * abs(math.sin(radians))
            hauteur_tournee = largeur * abs(math.sin(radians)) + hauteur * abs(math.cos(radians))
            echelle = ECHELLE_PASSES_TOURNEES
            taille = (max(1, round(largeur_tournee * echelle)),
                      max(1, round(hauteur_tournee * echelle)))
            matrice = _matrice_rotation((largeur / 2, hauteur / 2), angle, echelle,
                                        (taille[0] / 2, taille[1] / 2))
            tourne = cv2.warpAffine(tableau, matrice, taille, flags=cv2.INTER_LINEAR)

        retour = cv2.invertAffineTransform(matrice)
        return [_visage_ramene(ligne, retour) for ligne in self._lancer_yunet(tourne)]

    def _redresser(self, tableau, visage):
        """Mesure l'inclinaison exacte d'une tete en la remettant droite.

        On decoupe un carre autour des yeux, tourne de l'angle des yeux tel
        que YuNet l'a mesure : si cette mesure etait juste, la tete est
        maintenant droite dans la decoupe. On y detecte le visage de nouveau ;
        l'angle des yeux trouve dans la decoupe est ce qu'il reste de
        l'inclinaison, que l'on ajoute a l'angle deja connu. On recommence
        tant que ce reste n'est pas negligeable.

        La decoupe est aussi agrandie (ou reduite) pour que l'ecart des yeux y
        vaille ECART_YEUX_REDRESSE pixels : c'est a cette taille que YuNet
        suit le mieux l'inclinaison de la tete.

        Renvoie (visage, confirme) : le visage redresse si possible, tel quel
        sinon, et confirme vaut True si YuNet l'a retrouve dans une decoupe.
        """
        confirme = False
        if _ecart_des_yeux(visage) < ECART_YEUX_MINI_REDRESSEMENT:
            return visage, confirme

        for _ in range(NB_REDRESSEMENTS_MAXI):
            angle = _angle_des_yeux(visage)
            centre = _milieu(visage.oeil_droit, visage.oeil_gauche)
            echelle = ECART_YEUX_REDRESSE / _ecart_des_yeux(visage)
            matrice = _matrice_rotation(centre, angle, echelle,
                                        (COTE_DECOUPE / 2, COTE_DECOUPE / 2))
            # Un visage au bord de la photo deborde de la decoupe : le bord de
            # la photo est alors prolonge, plutot que remplace par du noir.
            decoupe = cv2.warpAffine(tableau, matrice, (COTE_DECOUPE, COTE_DECOUPE),
                                     flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REPLICATE)

            ligne = self._visage_au_centre(decoupe)
            if ligne is None:
                break       # visage perdu : on garde la meilleure mesure obtenue
            confirme = True

            # Les yeux trouves dans la decoupe sont ramenes dans la photo par la
            # transformation inverse de celle qui a produit la decoupe.
            visage = _visage_ramene(ligne, cv2.invertAffineTransform(matrice))

            # Angle des yeux dans la decoupe = inclinaison qui restait.
            reste = math.degrees(math.atan2(ligne[7] - ligne[5], ligne[6] - ligne[4]))
            if abs(reste) < CORRECTION_NEGLIGEABLE:
                break
        return visage, confirme

    def _visage_au_centre(self, decoupe):
        """Le visage detecte au centre de la decoupe, ou None.

        La decoupe est centree sur les yeux du visage examine, tels que YuNet
        les avait places. Sur une tete tres penchee, il les place jusqu'a un
        ecart des yeux a cote des vrais : on accepte donc le visage dont les
        yeux sont a moins d'un ecart des yeux du centre. Un voisin (dans une
        foule) est plus loin.
        """
        centre = COTE_DECOUPE / 2
        meilleure_ligne = None
        meilleure_distance = ECART_YEUX_REDRESSE
        for ligne in self._lancer_yunet(decoupe):
            milieu = _milieu((ligne[4], ligne[5]), (ligne[6], ligne[7]))
            distance = math.hypot(milieu[0] - centre, milieu[1] - centre)
            if distance < meilleure_distance:
                meilleure_ligne = ligne
                meilleure_distance = distance
        return meilleure_ligne


# ----------------------------------------------------------------------
# Geometrie
# ----------------------------------------------------------------------

def _milieu(point_a, point_b):
    return ((point_a[0] + point_b[0]) / 2, (point_a[1] + point_b[1]) / 2)


def _ecart_des_yeux(visage):
    return math.hypot(visage.oeil_gauche[0] - visage.oeil_droit[0],
                      visage.oeil_gauche[1] - visage.oeil_droit[1])


def _angle_des_yeux(visage):
    """Inclinaison de la droite qui joint les yeux, en degres (meme calcul que
    Bandeau.depuis_yeux). L'axe y descend : l'angle est positif quand la tete
    penche dans le sens des aiguilles d'une montre."""
    return math.degrees(math.atan2(visage.oeil_gauche[1] - visage.oeil_droit[1],
                                   visage.oeil_gauche[0] - visage.oeil_droit[0]))


def _matrice_rotation(centre, angle, echelle, arrivee):
    """Matrice de passage de la photo a une image tournee (decoupe ou passe).

    Elle fait tourner la photo de `angle` degres autour du point `centre`,
    l'agrandit de `echelle`, et amene `centre` au point `arrivee` de la
    nouvelle image. Pour OpenCV, un angle positif tourne l'image dans le sens
    inverse des aiguilles d'une montre : tourner de l'angle des yeux annule
    donc l'inclinaison de la tete.

    C'est une matrice 2 x 3 : un point (x, y) de la photo arrive en
    (a*x + b*y + c, d*x + e*y + f) dans l'image tournee.
    """
    matrice = cv2.getRotationMatrix2D(centre, angle, echelle)
    # getRotationMatrix2D laisse `centre` a sa place : on le decale jusqu'a
    # `arrivee`.
    matrice[0, 2] += arrivee[0] - centre[0]
    matrice[1, 2] += arrivee[1] - centre[1]
    return matrice


def _appliquer(matrice, x, y):
    """Position du point (x, y) apres la transformation decrite par `matrice`."""
    return (matrice[0, 0] * x + matrice[0, 1] * y + matrice[0, 2],
            matrice[1, 0] * x + matrice[1, 1] * y + matrice[1, 2])


def _visage_ramene(ligne, retour):
    """Construit le Visage d'une ligne de YuNet trouvee dans une image tournee.

    `retour` est la transformation inverse de celle qui a produit l'image
    tournee (cv2.invertAffineTransform) : elle ramene chaque point a sa place
    dans la photo. Les yeux y sont ramenes tels quels.

    La boite, elle, deviendrait penchee une fois ramenee. On garde une boite
    droite, de la taille propre du visage (ramenee a l'echelle de la photo),
    centree au meme endroit. Le rectangle droit qui englobe la boite penchee,
    garde au depart, etait jusqu'a 1,4 fois plus grand pour une tete penchee
    de 45 degres : c'est sur cette boite que visage_le_plus_proche rattache un
    clic au visage, et elle captait alors les clics autour de la tete, si bien
    que poser le bandeau manuel d'un voisin non detecte devenait impossible.
    """
    x, y, largeur, hauteur = (float(valeur) for valeur in ligne[:4])
    # Facteur d'agrandissement de la transformation : longueur de l'image
    # du vecteur (1, 0), la rotation ne changeant pas les longueurs.
    echelle = math.hypot(retour[0, 0], retour[1, 0])
    centre_x, centre_y = _appliquer(retour, x + largeur / 2, y + hauteur / 2)
    return Visage(x=centre_x - largeur * echelle / 2,
                  y=centre_y - hauteur * echelle / 2,
                  largeur=largeur * echelle,
                  hauteur=hauteur * echelle,
                  oeil_droit=_appliquer(retour, float(ligne[4]), float(ligne[5])),
                  oeil_gauche=_appliquer(retour, float(ligne[6]), float(ligne[7])),
                  score=float(ligne[14]))


def _meme_visage(visage_a, visage_b):
    """Deux detections sont-elles le meme visage ?

    Oui si les yeux de l'une tombent dans la boite de l'autre. Deux personnes
    distinctes, meme serrees, ont chacune leurs yeux dans leur propre boite.
    """
    return (visage_a.contient(*_milieu(visage_b.oeil_droit, visage_b.oeil_gauche))
            or visage_b.contient(*_milieu(visage_a.oeil_droit, visage_a.oeil_gauche)))


def _deja_connu(visages, candidat):
    """Le candidat est-il un visage deja present dans la liste ?"""
    return any(_meme_visage(candidat, visage) for visage in visages)


def _agrandir(visage, echelle):
    """Le meme visage, ses coordonnees multipliees par `echelle`."""
    return Visage(x=visage.x * echelle,
                  y=visage.y * echelle,
                  largeur=visage.largeur * echelle,
                  hauteur=visage.hauteur * echelle,
                  oeil_droit=(visage.oeil_droit[0] * echelle, visage.oeil_droit[1] * echelle),
                  oeil_gauche=(visage.oeil_gauche[0] * echelle, visage.oeil_gauche[1] * echelle),
                  score=visage.score)


# Marge autour de la boite d'un visage dans laquelle un clic lui est encore
# rattache (cheveux, oreilles) : un quart de la taille du visage.
MARGE_RATTACHEMENT = 0.25


def visage_le_plus_proche(visages, x, y):
    """Rattache un clic au visage auquel il correspond (section 9.3).

    Sont candidats les visages dont la boite, elargie d'un quart de sa
    taille, contient le clic. Parmi eux, on retient celui dont les yeux sont
    les plus proches du clic, la distance etant mesuree en tailles de visage :
    le bandeau se pose sur les yeux, et un grand visage au premier plan n'est
    ainsi pas defavorise face a un petit visage derriere lui.

    Deux erreurs de l'ancienne regle, constatees par les essais :
    - le plus petit visage contenant le clic l'emportait : un clic a 15 px
      de l'oeil d'un grand visage, tombant aussi dans la boite d'un visage
      plus petit place derriere, posait le bandeau sur ce dernier ;
    - tout clic a moins d'une taille de visage du centre etait rattache :
      cliquer sur les yeux d'une personne non detectee, joue contre joue avec
      une personne detectee, posait le bandeau sur la voisine, a chaque fois,
      et le bandeau manuel devenait impossible.

    Hors de tout candidat, l'utilisateur visait un endroit ou aucun visage n'a
    ete detecte : il faudra creer un bandeau manuel.

    Renvoie l'index du visage dans la liste, ou None.
    """
    candidats = [index for index, visage in enumerate(visages)
                 if visage.contient(x, y, MARGE_RATTACHEMENT * max(visage.largeur,
                                                                   visage.hauteur))]
    if not candidats:
        return None

    def distance_aux_yeux(index):
        visage = visages[index]
        milieu_x, milieu_y = _milieu(visage.oeil_droit, visage.oeil_gauche)
        return math.hypot(x - milieu_x, y - milieu_y) / max(visage.largeur, visage.hauteur, 1)

    return min(candidats, key=distance_aux_yeux)


class DetectionAnticipee:
    """Calcule a l'avance, en arriere-plan, les visages des prochaines photos.

    Meme principe que le chargement anticipe des images (section 11.1) : quand
    l'utilisateur valide une photo, la detection de la suivante est deja faite.
    """

    def __init__(self, detecteur, chargeur, nb_photos, nb_avance=2):
        self.detecteur = detecteur
        self.chargeur = chargeur
        self.nb_photos = nb_photos
        self.nb_avance = nb_avance

        self.cache = {}
        self.position = 0
        self.actif = True
        # Nombre de fois ou chaque photo a ete oubliee (voir oublier).
        self.oublis = {}

        self.signal = threading.Condition()
        self.fil = threading.Thread(target=self._travailler, daemon=True)
        self.fil.start()

    def est_prete(self, index):
        """Les visages de cette photo sont-ils deja calcules ? (sans rien calculer)"""
        with self.signal:
            return index in self.cache

    def visages(self, index):
        """Renvoie les visages de la photo demandee, en calculant si besoin."""
        with self.signal:
            if index in self.cache:
                return self.cache[index]

        resultat = self.detecteur.detecter(self.chargeur.image(index))
        with self.signal:
            self.cache[index] = resultat
            self.signal.notify_all()
        return resultat

    def avancer(self, position):
        with self.signal:
            self.position = position
            self.signal.notify_all()

    def oublier(self, index):
        """Force le recalcul d'une photo, apres un rognage, une retouche ou une annulation.

        Le fil d'arriere-plan peut etre en train de calculer cette photo,
        sur l'ancienne version de l'image : le compteur d'oublis lui permet de
        s'en rendre compte, et de jeter ce resultat perime au lieu de le garder.
        """
        with self.signal:
            self.cache.pop(index, None)
            self.oublis[index] = self.oublis.get(index, 0) + 1
            self.signal.notify_all()

    def arreter(self):
        """Arrete le fil de detection et attend qu'il ait termine.

        Comme pour le chargement anticipe, ce fil ouvre des photos : on attend
        sa fin pour etre sur qu'aucun fichier de l'utilisateur n'est encore
        ouvert quand on revient au menu (voir `ChargeurAnticipe.arreter`).
        """
        with self.signal:
            self.actif = False
            self.signal.notify_all()
        self.fil.join(timeout=10)

    def _prochain_a_calculer(self):
        derniere = min(self.position + self.nb_avance, self.nb_photos - 1)
        for index in range(self.position, derniere + 1):
            if index not in self.cache:
                return index
        return None

    def _travailler(self):
        while True:
            with self.signal:
                while self.actif and self._prochain_a_calculer() is None:
                    self.signal.wait()
                if not self.actif:
                    return
                index = self._prochain_a_calculer()
                oublis_avant = self.oublis.get(index, 0)

            # Une erreur imprevue ne doit pas tuer ce fil : toutes les photos
            # suivantes resteraient sur « detection... ». Sans visages, on
            # peut toujours poser des bandeaux a la main.
            try:
                resultat = self.detecteur.detecter(self.chargeur.image(index))
            except Exception:
                resultat = []

            with self.signal:
                if not self.actif:
                    return
                if self.oublis.get(index, 0) != oublis_avant:
                    continue    # la photo a change pendant le calcul : on recommence
                self.cache[index] = resultat
                # On ne garde en memoire que les photos proches de la position.
                if len(self.cache) > 12:
                    trop_loin = sorted(self.cache,
                                       key=lambda i: abs(i - self.position))[12:]
                    for i in trop_loin:
                        del self.cache[i]
                self.signal.notify_all()
