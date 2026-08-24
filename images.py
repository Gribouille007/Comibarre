"""
Lecture des images, remise dans le bon sens, et chargement anticipe.

Ce module est partage par l'etape de tri et par l'etape de censure : c'est le
seul endroit ou l'on ouvre, oriente et enregistre une image. Le regrouper ici
evite que les deux etapes traitent l'orientation differemment, ce qui est la
premiere source d'erreur sur ce genre de logiciel.
"""

import os
import threading

from PIL import Image, ImageOps
import pillow_heif

# Enregistre le format HEIC aupres de Pillow (photos d'iPhone).
# A faire une seule fois, au chargement du module.
pillow_heif.register_heif_opener()

# Formats d'image traites par le tri et la censure.
EXTENSIONS_IMAGE = {
    ".jpg", ".jpeg", ".jpe", ".png", ".heic", ".heif",
    ".bmp", ".gif", ".tif", ".tiff", ".webp",
}


def est_une_image(nom_fichier):
    return os.path.splitext(nom_fichier)[1].lower() in EXTENSIONS_IMAGE


def format_origine(chemin):
    """Renvoie le format Pillow du fichier ("JPEG", "PNG", "HEIF"...).

    Sert a reenregistrer la photo dans son format d'origine (section 9.5).
    """
    with Image.open(chemin) as image:
        return image.format


def charger_image(chemin):
    """Ouvre une photo et la remet dans le bon sens.

    Les appareils photo et les telephones enregistrent souvent la photo telle
    que le capteur l'a vue, en ajoutant une etiquette d'orientation (EXIF) qui
    indique de quel quart de tour il faut la faire pivoter pour l'afficher
    correctement. `exif_transpose` applique cette rotation et retire l'etiquette,
    de sorte que la suite du programme n'a plus jamais a s'en soucier : les
    coordonnees a l'ecran et celles de l'image enregistree coincident.
    """
    image = Image.open(chemin)
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    return image


def enregistrer_au_format_origine(image, chemin, format_image):
    """Reenregistre la photo par-dessus le fichier existant, dans son format.

    L'ecriture passe par un fichier temporaire, renomme ensuite par-dessus
    l'original : si l'enregistrement echoue en cours de route, la photo
    d'origine reste intacte au lieu d'etre remplacee par un fichier a moitie
    ecrit.
    """
    if format_image in (None, "MPO"):
        # Format inconnu : on se rabat sur ce que dit l'extension du fichier.
        format_image = "JPEG" if chemin.lower().endswith((".jpg", ".jpeg")) else "PNG"

    options = {}
    if format_image == "JPEG":
        image = image.convert("RGB")           # le JPEG n'accepte pas la transparence
        options = {"quality": 95, "subsampling": 0}
    elif format_image in ("HEIF", "HEIC"):
        options = {"quality": 95}

    chemin_temporaire = chemin + ".tmp"
    image.save(chemin_temporaire, format=format_image, **options)
    os.replace(chemin_temporaire, chemin)


class ChargeurAnticipe:
    """Prepare a l'avance, en arriere-plan, les prochaines photos (section 11.1).

    Pendant que l'utilisateur regarde la photo courante, un fil d'execution
    separe ouvre deja les suivantes et les garde en memoire. Le passage d'une
    photo a l'autre devient ainsi instantane, meme sur plusieurs milliers de
    fichiers.

    Le fil d'execution ne touche jamais a l'interface graphique : il se contente
    de produire des images Pillow. C'est indispensable, car Tkinter ne supporte
    pas d'etre manipule depuis un autre fil que le fil principal.
    """

    def __init__(self, chemins, nb_avance=3, taille_cache=10):
        self.chemins = list(chemins)
        self.nb_avance = nb_avance
        self.taille_cache = taille_cache

        self.cache = {}                 # index -> image Pillow
        self.position = 0               # photo actuellement regardee
        self.actif = True

        self.signal = threading.Condition()
        self.fil = threading.Thread(target=self._travailler, daemon=True)
        self.fil.start()

    # -- utilisation depuis le fil principal ---------------------------------

    def image(self, index):
        """Renvoie la photo demandee, en la chargeant tout de suite si besoin."""
        with self.signal:
            if index in self.cache:
                return self.cache[index]

        # Pas encore prete : on la charge ici meme plutot que d'attendre le fil
        # d'arriere-plan. C'est plus simple et cela ne peut jamais se bloquer.
        image = self._ouvrir(index)
        with self.signal:
            self.cache[index] = image
            self.signal.notify_all()
        return image

    def avancer(self, position):
        """Signale la nouvelle photo courante, pour orienter le prechargement."""
        with self.signal:
            self.position = position
            self._nettoyer_cache()
            self.signal.notify_all()

    def oublier(self, index):
        """Retire une photo du cache pour forcer sa relecture depuis le disque.

        Necessaire apres une annulation de censure : le fichier a ete remplace
        par sa copie d'origine, et c'est bien celle-ci qu'il faut reafficher.
        """
        with self.signal:
            self.cache.pop(index, None)
            self.signal.notify_all()

    def arreter(self):
        with self.signal:
            self.actif = False
            self.signal.notify_all()

    # -- fonctionnement interne ----------------------------------------------

    def _ouvrir(self, index):
        try:
            return charger_image(self.chemins[index])
        except Exception:
            # Fichier illisible ou corrompu : on ne fait pas echouer tout le
            # programme pour une photo. L'appelant affichera un message.
            return None

    def _prochain_a_charger(self):
        """Index de la prochaine photo a preparer, ou None s'il n'y a rien a faire."""
        derniere = min(self.position + self.nb_avance, len(self.chemins) - 1)
        for index in range(self.position, derniere + 1):
            if index not in self.cache:
                return index
        return None

    def _nettoyer_cache(self):
        """Oublie les photos trop eloignees pour ne pas saturer la memoire."""
        if len(self.cache) <= self.taille_cache:
            return
        for index in sorted(self.cache, key=lambda i: abs(i - self.position))[self.taille_cache:]:
            del self.cache[index]

    def _travailler(self):
        while True:
            with self.signal:
                while self.actif and self._prochain_a_charger() is None:
                    self.signal.wait()
                if not self.actif:
                    return
                index = self._prochain_a_charger()

            # Le chargement, qui est lent, se fait en dehors du verrou pour ne
            # pas bloquer le fil principal quand il vient consulter le cache.
            image = self._ouvrir(index)

            with self.signal:
                self.cache[index] = image
                self._nettoyer_cache()
                self.signal.notify_all()
