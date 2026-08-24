"""
Detection des visages et de la position des yeux (section 9.2).

La detection s'appuie sur YuNet, un modele fourni avec OpenCV
(`cv2.FaceDetectorYN`). Il a ete retenu a la place de mediapipe apres mesures :
sur des photos de groupe, mediapipe ne detectait aucun visage la ou YuNet en
trouve plusieurs dizaines, y compris des visages de 10 a 25 pixels de large et
sur des photos fortement sous-exposees. Voir CLAUDE.md, section 2.

Tout ce qui concerne la detection est enferme ici : le reste du programme ne
manipule que des objets `Visage`, sans savoir quelle bibliotheque les produit.
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

    @property
    def centre(self):
        return (self.x + self.largeur / 2, self.y + self.hauteur / 2)

    def contient(self, x, y):
        """Le point est-il a l'interieur de la boite du visage ?"""
        return (self.x <= x <= self.x + self.largeur
                and self.y <= y <= self.y + self.hauteur)

    def distance_au_centre(self, x, y):
        centre_x, centre_y = self.centre
        return math.hypot(x - centre_x, y - centre_y)


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
        hauteur, largeur = tableau.shape[:2]

        with self.verrou:
            # YuNet exige que la taille annoncee corresponde a l'image fournie.
            self.detecteur.setInputSize((largeur, hauteur))
            _, resultats = self.detecteur.detect(tableau)

        if resultats is None:
            return []

        # Chaque ligne contient : x, y, largeur, hauteur, puis cinq points
        # (oeil droit, oeil gauche, nez, coin droit et coin gauche de la bouche),
        # puis le score de confiance.
        echelle = 1.0 / facteur
        visages = []
        for ligne in resultats:
            visages.append(Visage(
                x=float(ligne[0]) * echelle,
                y=float(ligne[1]) * echelle,
                largeur=float(ligne[2]) * echelle,
                hauteur=float(ligne[3]) * echelle,
                oeil_droit=(float(ligne[4]) * echelle, float(ligne[5]) * echelle),
                oeil_gauche=(float(ligne[6]) * echelle, float(ligne[7]) * echelle),
                score=float(ligne[14]),
            ))
        return visages


def visage_le_plus_proche(visages, x, y):
    """Rattache un clic au visage auquel il correspond (section 9.3).

    Un clic tombant dans la boite d'un visage lui est attribue directement.
    Sinon, on accepte le visage le plus proche a condition que le clic ne soit
    pas trop loin de sa tete : au-dela, c'est que l'utilisateur visait un endroit
    ou aucun visage n'a ete detecte, et il faudra creer un bandeau manuel.

    Renvoie l'index du visage dans la liste, ou None.
    """
    if not visages:
        return None

    # Priorite aux visages dont la boite contient le clic. S'il y en a
    # plusieurs (visages qui se chevauchent), on garde le plus petit, car c'est
    # celui que l'utilisateur visait le plus precisement.
    contenants = [i for i, v in enumerate(visages) if v.contient(x, y)]
    if contenants:
        return min(contenants, key=lambda i: visages[i].largeur * visages[i].hauteur)

    index_proche = min(range(len(visages)),
                       key=lambda i: visages[i].distance_au_centre(x, y))
    visage = visages[index_proche]
    tolerance = max(visage.largeur, visage.hauteur)
    if visage.distance_au_centre(x, y) <= tolerance:
        return index_proche
    return None


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

        self.signal = threading.Condition()
        self.fil = threading.Thread(target=self._travailler, daemon=True)
        self.fil.start()

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
        """Force le recalcul d'une photo (utile apres une annulation)."""
        with self.signal:
            self.cache.pop(index, None)

    def arreter(self):
        with self.signal:
            self.actif = False
            self.signal.notify_all()

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

            image = self.chargeur.image(index)
            resultat = self.detecteur.detecter(image)

            with self.signal:
                self.cache[index] = resultat
                # On ne garde en memoire que les photos proches de la position.
                if len(self.cache) > 12:
                    trop_loin = sorted(self.cache,
                                       key=lambda i: abs(i - self.position))[12:]
                    for i in trop_loin:
                        del self.cache[i]
                self.signal.notify_all()
