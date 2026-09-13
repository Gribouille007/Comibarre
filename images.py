"""
Lecture des images, remise dans le bon sens, et chargement anticipe.

Ce module est partage par l'etape de tri et par l'etape de censure : c'est le
seul endroit ou l'on ouvre, oriente et enregistre une image. Le regrouper ici
evite que les deux etapes traitent l'orientation differemment, ce qui est la
premiere source d'erreur sur ce genre de logiciel.
"""

import os
import shutil
import threading
import time

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


def fabriquer_apercu(image, taille_maximale):
    """Reduit la photo pour qu'elle tienne dans taille_maximale (la zone d'affichage).

    L'apercu sert a l'affichage : inutile de redimensionner 24 millions de
    pixels a chaque dessin quand l'ecran n'en montre que 2 millions. Une photo
    deja plus petite que la zone d'affichage est renvoyee telle quelle.
    """
    largeur_maximale, hauteur_maximale = taille_maximale
    rapport = min(largeur_maximale / image.width, hauteur_maximale / image.height)
    if rapport >= 1:
        return image
    taille = (max(1, round(image.width * rapport)), max(1, round(image.height * rapport)))
    # reducing_gap : Pillow commence par une reduction grossiere par un facteur
    # entier (moyenne de blocs de pixels, tres rapide), puis ne fait le calcul
    # fin (LANCZOS) que sur la derniere etape. Trois fois plus rapide.
    return image.resize(taille, Image.LANCZOS, reducing_gap=1.0)


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
    _remplacer_fichier(chemin_temporaire, chemin)


def _remplacer_fichier(source, destination):
    """Comme os.replace, mais en reessayant un court instant si Windows refuse.

    Windows refuse de remplacer un fichier pendant qu'il est lu. Or les photos
    sont enregistrees en arriere-plan (voir ecritures.py), et le chargement
    anticipe peut justement etre en train de lire celle que l'on remplace. Une
    lecture ne durant qu'une fraction de seconde, on reessaie pendant deux
    secondes avant d'abandonner.
    """
    for _ in range(40):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(source, destination)     # dernier essai : cette fois, l'erreur remonte


def copie_de_sauvegarde(chemin, dossier_sauvegarde):
    """Garde une copie intacte de la photo avant de la modifier (section 9.6).

    Une meme photo peut etre modifiee plusieurs fois dans une session : rognee
    deux fois, ou censuree puis reprise apres un retour en arriere. Chaque copie
    recoit donc un nom unique, precede d'un numero (1_12.jpg, 2_12.jpg...), pour
    qu'une nouvelle sauvegarde n'ecrase jamais la precedente : chaque annulation
    retrouve ainsi exactement la version d'avant.

    Renvoie le chemin de la copie.
    """
    os.makedirs(dossier_sauvegarde, exist_ok=True)
    nom_fichier = os.path.basename(chemin)
    numero = 1
    while os.path.exists(os.path.join(dossier_sauvegarde, "%d_%s" % (numero, nom_fichier))):
        numero += 1
    sauvegarde = os.path.join(dossier_sauvegarde, "%d_%s" % (numero, nom_fichier))
    shutil.copy2(chemin, sauvegarde)
    return sauvegarde


class ChargeurAnticipe:
    """Prepare a l'avance, en arriere-plan, les prochaines photos (section 11.1).

    Pendant que l'utilisateur regarde la photo courante, un fil d'execution
    separe ouvre deja les suivantes et les garde en memoire. Le passage d'une
    photo a l'autre devient ainsi instantane, meme sur plusieurs milliers de
    fichiers.

    Pour chaque photo, deux versions sont preparees :
    - l'image entiere, qui sert au zoom, au rognage et a la detection ;
    - un apercu exactement a la taille de la zone d'affichage, qui s'affiche
      tel quel, sans aucun redimensionnement. Le fabriquer prend pres d'un
      dixieme de seconde : fait ici, ce travail disparait du passage d'une
      photo a l'autre.

    Le fil d'execution ne touche jamais a l'interface graphique : il se contente
    de produire des images Pillow. C'est indispensable, car Tkinter ne supporte
    pas d'etre manipule depuis un autre fil que le fil principal.
    """

    def __init__(self, chemins, taille_apercu, nb_avance=3, taille_cache=10):
        self.chemins = list(chemins)
        self.taille_apercu = taille_apercu
        self.nb_avance = nb_avance
        self.taille_cache = taille_cache

        # index -> (image, apercu). (None, None) si la photo est illisible ;
        # (image, None) si l'apercu est a refaire (voir changer_taille_apercu).
        self.cache = {}
        self.position = 0               # photo actuellement regardee
        self.en_lecture = None          # index que le fil d'arriere-plan prepare
        self.actif = True

        self.signal = threading.Condition()
        self.fil = threading.Thread(target=self._travailler, daemon=True)
        self.fil.start()

    # -- utilisation depuis le fil principal ---------------------------------

    def est_prete(self, index):
        """La photo et son apercu sont-ils prets ? Repond tout de suite, sans rien lire."""
        with self.signal:
            return self._est_prete(index)

    def photo(self, index):
        """Renvoie (image, apercu), en preparant la photo tout de suite si besoin."""
        with self.signal:
            self._attendre_fin_de_lecture(index)
            if self._est_prete(index):
                return self.cache[index]
            image_deja_lue = self._image_en_memoire(index)

        # Pas encore prete : on la prepare ici meme plutot que d'attendre que le
        # fil d'arriere-plan y arrive. C'est plus simple et cela ne peut jamais
        # se bloquer.
        photo = self._preparer(index, image_deja_lue)
        with self.signal:
            self.cache[index] = photo
            self.signal.notify_all()
        return photo

    def image(self, index):
        """Renvoie l'image entiere de la photo demandee (l'apercu n'est pas necessaire)."""
        with self.signal:
            self._attendre_fin_de_lecture(index)
            if index in self.cache:
                return self.cache[index][0]
        return self.photo(index)[0]

    def avancer(self, position):
        """Signale la nouvelle photo courante, pour orienter le prechargement."""
        with self.signal:
            self.position = position
            self._nettoyer_cache()
            self.signal.notify_all()

    def changer_taille_apercu(self, taille):
        """La zone d'affichage a change de taille : les apercus sont refaits a la nouvelle.

        Les images entieres restent valables : seuls les apercus sont refaits,
        en arriere-plan, sans relire les fichiers. D'ici la, un apercu de
        l'ancienne taille reste utilisable, il est simplement redimensionne a
        l'affichage.
        """
        with self.signal:
            if taille == self.taille_apercu:
                return
            self.taille_apercu = taille
            for index, (image, _) in list(self.cache.items()):
                if image is not None:
                    self.cache[index] = (image, None)
            self.signal.notify_all()

    def remplacer(self, index, image, apercu):
        """Garde en memoire la nouvelle version d'une photo que l'on vient de modifier.

        Le fichier, lui, est enregistre en arriere-plan (voir ecritures.py) et
        n'est donc pas encore a jour : le relire maintenant redonnerait
        l'ancienne version. On garde donc directement la version modifiee.
        """
        with self.signal:
            self._attendre_fin_de_lecture(index)
            self.cache[index] = (image, apercu)
            self.signal.notify_all()

    def oublier(self, index):
        """Retire une photo du cache pour forcer sa relecture depuis le disque.

        Necessaire chaque fois que le fichier a change sans que la nouvelle
        version soit deja en memoire : apres l'annulation d'une censure ou d'un
        rognage, c'est bien l'original restaure qu'il faut reafficher.
        """
        with self.signal:
            self._attendre_fin_de_lecture(index)
            self.cache.pop(index, None)
            self.signal.notify_all()

    def oublier_fichier(self, chemin):
        """Comme `oublier`, pour la photo qui se trouve a cet emplacement."""
        with self.signal:
            index_concernes = [index for index, chemin_photo in enumerate(self.chemins)
                               if chemin_photo == chemin]
        for index in index_concernes:
            self.oublier(index)

    def changer_chemin(self, index, chemin):
        """Indique qu'une photo a change de dossier (rangee, ou ramenee par une annulation).

        L'image deja en memoire reste valable : seul l'emplacement du fichier a
        change, pas son contenu. En revanche, une lecture ratee a l'ancien
        emplacement est oubliee, pour que la photo soit relue au bon endroit.
        """
        with self.signal:
            if self.chemins[index] == chemin:
                return
            self.chemins[index] = chemin
            if index in self.cache and self.cache[index][0] is None:
                del self.cache[index]
            self.signal.notify_all()

    def arreter(self):
        """Arrete le fil d'arriere-plan et attend qu'il ait fini de lire.

        L'attente n'est pas un detail : tant que le fil lit un fichier, Windows
        considere le dossier comme ouvert et refuse de le deplacer, de le
        renommer ou de le supprimer. En attendant ici, on garantit qu'au retour
        au menu plus aucun fichier de l'utilisateur n'est ouvert par le
        programme.

        Le delai d'attente evite de bloquer l'interface pour toujours si la
        lecture d'un fichier ne se termine pas ; le fil etant demarre en mode
        « daemon », il ne pourrait de toute facon pas empecher la fermeture.
        """
        with self.signal:
            self.actif = False
            self.signal.notify_all()
        self.fil.join(timeout=10)

    # -- fonctionnement interne ----------------------------------------------
    # Les methodes suivantes sont appelees avec le verrou deja pris, sauf
    # _preparer, qui fait le travail lent et doit donc s'en passer.

    def _est_prete(self, index):
        """Photo en memoire avec son apercu (ou illisible : rien de plus a faire)."""
        if index not in self.cache:
            return False
        image, apercu = self.cache[index]
        return image is None or apercu is not None

    def _image_en_memoire(self, index):
        """Image entiere deja lue, ou None s'il faut la lire sur le disque."""
        if index in self.cache:
            return self.cache[index][0]
        return None

    def _attendre_fin_de_lecture(self, index):
        """Attend que le fil d'arriere-plan ait fini de preparer cette photo, s'il la prepare.

        On evite ainsi de preparer deux fois la meme photo en meme temps, et
        surtout que le fil range en memoire une version perimee juste apres
        qu'on l'a remplacee ou oubliee. `wait` relache le verrou le temps de
        l'attente.
        """
        while self.en_lecture == index and self.actif:
            self.signal.wait()

    def _preparer(self, index, image_deja_lue):
        """Lit la photo si besoin, puis fabrique son apercu. Renvoie (image, apercu)."""
        image = image_deja_lue
        if image is None:
            try:
                image = charger_image(self.chemins[index])
            except Exception:
                # Fichier illisible ou corrompu : on ne fait pas echouer tout le
                # programme pour une photo. L'appelant affichera un message.
                return (None, None)
        return (image, fabriquer_apercu(image, self.taille_apercu))

    def _prochain_a_charger(self):
        """Index de la prochaine photo a preparer, ou None s'il n'y a rien a faire."""
        derniere = min(self.position + self.nb_avance, len(self.chemins) - 1)
        for index in range(self.position, derniere + 1):
            if not self._est_prete(index):
                return index
        # Puis la photo precedente, pour que la fleche gauche soit elle aussi
        # instantanee.
        precedente = min(self.position, len(self.chemins)) - 1
        if precedente >= 0 and not self._est_prete(precedente):
            return precedente
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
                image_deja_lue = self._image_en_memoire(index)
                self.en_lecture = index

            # La preparation, qui est lente, se fait en dehors du verrou pour ne
            # pas bloquer le fil principal quand il vient consulter le cache.
            photo = self._preparer(index, image_deja_lue)

            with self.signal:
                self.en_lecture = None
                self.signal.notify_all()
                if not self.actif:
                    return
                self.cache[index] = photo
                self._nettoyer_cache()
