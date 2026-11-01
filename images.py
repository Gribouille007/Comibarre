"""
Lecture des images, remise dans le bon sens, et chargement anticipe.

Ce module est partage par l'etape de tri et par l'etape de censure : c'est le
seul endroit ou l'on ouvre, oriente et enregistre une image. Le regrouper ici
evite que les deux etapes traitent l'orientation differemment, ce qui est la
premiere source d'erreur sur ce genre de logiciel.
"""

import io
import os
import shutil
import threading

from PIL import ExifTags, Image, ImageOps
import pillow_heif

# Le remplacement d'un fichier reessaie un court instant si Windows refuse :
# les photos sont enregistrees en arriere-plan (voir ecritures.py), et le
# chargement anticipe peut justement etre en train de lire celle que l'on
# remplace.
from fichiers import remplacer_fichier

# Enregistre le format HEIC aupres de Pillow (photos d'iPhone).
# A faire une seule fois, au chargement du module.
pillow_heif.register_heif_opener()

# Formats d'image traites par le tri et la censure.
EXTENSIONS_IMAGE = {
    ".jpg", ".jpeg", ".jpe", ".png", ".heic", ".heif",
    ".bmp", ".gif", ".tif", ".tiff", ".webp",
}


# Formats dans lesquels Pillow sait reecrire les donnees EXIF et le profil de
# couleurs de la photo.
FORMATS_AVEC_EXIF = {"JPEG", "PNG", "HEIF", "HEIC", "WEBP"}

# Extensions que le logiciel sait reenregistrer sans degrader la photo
# (CLAUDE.md, section 8). Les autres extensions de EXTENSIONS_IMAGE sont
# triees et renommees, mais ni rognees ni censurees : voir est_modifiable.
EXTENSIONS_MODIFIABLES = {".jpg", ".jpeg", ".jpe", ".png", ".heic", ".heif", ".webp"}

# Les memes, d'apres le contenu du fichier. « MPO » est le JPEG de certains
# appareils, qui y joignent une seconde vue : seule la premiere est gardee.
FORMATS_MODIFIABLES = {"JPEG", "MPO", "PNG", "WEBP", "HEIF", "HEIC"}


def extension_modifiable(nom_fichier):
    """Premier tri, sur la seule extension, sans ouvrir le fichier (voir est_modifiable).

    Sert a l'affichage de chaque photo : ouvrir le fichier a ce moment-la,
    sur le fil principal, forcerait le telechargement d'une photo OneDrive
    « disponible a la demande » avant meme que le chargeur ne s'en charge, et
    figerait la fenetre le temps de ce telechargement.
    """
    return os.path.splitext(nom_fichier)[1].lower() in EXTENSIONS_MODIFIABLES


def est_modifiable(chemin):
    """La photo peut-elle etre rognee ou censuree sans perte ?

    Le tri accepte plus de formats que la retouche. Un BMP, un GIF ou un TIFF
    se trie et se renomme sans risque, puisque le fichier n'est pas touche,
    mais le reenregistrer le degraderait : un GIF ne retient que 256 couleurs,
    et ni l'un ni l'autre ne conserve ses donnees EXIF a la reecriture. Plutot
    que d'abimer la photo en silence, le logiciel refuse de la modifier et le
    dit (voir rangement.py).

    L'extension ne suffit pas : un GIF anime ou un TIFF nommes « .jpg » (cela
    arrive avec des images telechargees) perdaient, une fois rognes, l'un ses
    images suivantes, l'autre sa date de prise de vue. On regarde donc aussi
    le contenu du fichier, dont seul l'en-tete est lu. Un PNG ou un WEBP
    animes sont refuses pour la meme raison. Si le fichier ne peut pas etre
    ouvert a cet instant, l'extension decide : l'enregistrement, lui, dira
    s'il echoue.

    N'est appele qu'au moment de modifier la photo, deja affichee : son
    fichier a alors ete lu, et l'ouvrir de nouveau ne coute rien.
    """
    if not extension_modifiable(chemin):
        return False
    try:
        with Image.open(chemin) as image:
            if image.format not in FORMATS_MODIFIABLES:
                return False
            if image.format in ("PNG", "WEBP"):
                return getattr(image, "n_frames", 1) == 1
            return True
    except Exception:
        return True


def est_une_image(nom_fichier):
    """Le fichier est-il une photo, d'apres son nom ?

    « ._IMG_0001.JPG » n'en est pas une : macOS l'ajoute a cote de chaque
    fichier copie sur une cle ou une carte memoire, avec l'extension de la
    photo, mais il ne contient que des informations du Mac. Ni la preparation,
    ni le tri, ni le menu ne doivent le compter.
    """
    if os.path.basename(nom_fichier).startswith("._"):
        return False
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

    Le fichier est d'abord lu en memoire d'un seul bloc, puis decode depuis la
    memoire. Sous Windows, un fichier ouvert ne peut etre ni remplace ni
    deplace : decodee directement depuis le disque, une photo de 24 Mpx
    restait ouverte 110 ms, pendant lesquelles un rangement ou un rognage de
    cette photo pouvait echouer. Lue d'un bloc, elle ne l'est plus que 2 ms.
    """
    with open(chemin, "rb") as fichier:
        donnees = fichier.read()
    with Image.open(io.BytesIO(donnees)) as fichier_ouvert:
        image = ImageOps.exif_transpose(fichier_ouvert)
    return ramener_en_rgb(image)


# Modes Pillow des images a 16 bits par point (PNG en niveaux de gris 16 bits).
MODES_16_BITS = {"I", "I;16", "I;16B", "I;16L", "I;16N"}


def ramener_en_rgb(image):
    """Ramene la photo en RGB, ou en RGBA si elle a de la transparence.

    Tout le logiciel travaille en RGB. Trois pieges, constates par les essais :
    - une image a 16 bits par point (valeurs de 0 a 65535) etait ecretee :
      tout ce qui depassait 255 devenait 255, et la photo devenait blanche.
      On divise donc d'abord par 256 ;
    - une transparence par « couleur-cle » (PNG a palette, ou RGB dont une
      couleur est declaree transparente) survivait a la conversion : a
      l'enregistrement, tous les points de cette couleur redevenaient
      transparents, bandeaux noirs compris si la couleur-cle etait le noir.
      Un vrai canal de transparence (RGBA) l'evite, et garde aussi celle
      d'un PNG gris avec transparence, que la conversion en RGB perdait ;
    - le profil de couleurs d'une photo CMJN ou en niveaux de gris ne decrit
      pas une image RGB : recolle tel quel, il fausserait les couleurs. Il
      est retire.
    """
    if image.mode in MODES_16_BITS:
        image = image.point(lambda valeur: valeur * (1 / 256)).convert("L")
    if image.mode == "RGBA" or (image.mode == "RGB" and "transparency" not in image.info):
        return image
    profil = image.info.get("icc_profile")
    if "A" in image.getbands() or "transparency" in image.info:
        image = image.convert("RGBA")
    else:
        image = image.convert("RGB")
    # Les octets 16 a 19 d'un profil de couleurs disent quel espace il decrit.
    if profil and profil[16:20] != b"RGB ":
        image.info.pop("icc_profile", None)
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
    if format_image == "MPO":
        # Un « MPO » est une suite de JPEG (plusieurs vues) : on enregistre la
        # premiere, en JPEG, quelle que soit l'extension (.jpg, .jpeg, .jpe).
        format_image = "JPEG"
    elif format_image is None:
        # Format inconnu : on se rabat sur ce que dit l'extension du fichier.
        format_image = "JPEG" if chemin.lower().endswith((".jpg", ".jpeg", ".jpe")) else "PNG"

    options = {}
    if format_image == "JPEG":
        image = image.convert("RGB")           # le JPEG n'accepte pas la transparence
        options = {"quality": 95, "subsampling": 0}
    elif format_image in ("HEIF", "HEIC"):
        options = {"quality": 95}
    elif format_image == "WEBP":
        # Sans reglage, Pillow reencode tout WEBP avec perte, en qualite 80 :
        # un WEBP sans perte doit le rester, et les autres suivent le JPEG.
        options = {"lossless": webp_sans_perte(chemin), "quality": 95}

    # Pillow n'ecrit les informations de la photo que si on les lui redonne.
    # Sans cela, une photo rognee ou censuree perdrait sa date de prise de vue
    # et son profil de couleurs (ses couleurs changeraient a l'ecran). Les
    # donnees EXIF ont deja perdu leur etiquette d'orientation (voir
    # charger_image) : la photo, enregistree droite, ne sera pas tournee une
    # seconde fois par les visionneuses.
    if format_image in FORMATS_AVEC_EXIF:
        exif = image.getexif()
        if exif:
            _mettre_a_jour_les_dimensions_exif(exif, image.size)
            options["exif"] = exif.tobytes()
        if image.info.get("icc_profile"):
            options["icc_profile"] = image.info["icc_profile"]

    chemin_temporaire = chemin + ".tmp"
    try:
        if format_image in ("HEIF", "HEIC"):
            _enregistrer_en_heic_lisible(image, chemin_temporaire, options)
        else:
            image.save(chemin_temporaire, format=format_image, **options)
        remplacer_fichier(chemin_temporaire, chemin)
    except Exception:
        # La photo d'origine est intacte ; le fichier temporaire, lui, ne doit
        # pas rester dans le dossier de l'utilisateur.
        try:
            os.remove(chemin_temporaire)
        except OSError:
            pass
        raise


# Le decodeur HEIC livre avec pillow-heif ne relit pas une image dont les
# donnees compressees depassent 16 Mio (voir _enregistrer_en_heic_lisible).
# En dessous de ce seuil, avec une marge, inutile de verifier.
TAILLE_HEIC_SANS_VERIFICATION = 15 * 1024 * 1024
QUALITES_HEIC = (95, 85, 75, 60, 40)


def _enregistrer_en_heic_lisible(image, chemin_temporaire, options):
    """Enregistre en HEIC, en baissant la qualite si le fichier ne se relirait pas.

    Mesure (pillow-heif 1.5, libheif 1.23, libde265 1.1) : une photo HEIC dont
    les donnees compressees depassent 16 Mio, quelle que soit sa taille en
    pixels, s'enregistre sans erreur mais ne se relit plus. Une photo de
    24 Mpx tres detaillee, reenregistree en qualite 95, y arrivait : apres
    une censure, elle devenait « illisible » dans le logiciel (Windows, lui,
    la lisait). Un gros fichier est donc relu avant de remplacer l'original,
    et reenregistre un peu plus compresse tant qu'il ne se relit pas. Si rien
    n'y fait, l'enregistrement echoue et la photo d'origine reste intacte.
    """
    for qualite in QUALITES_HEIC:
        image.save(chemin_temporaire, format="HEIF", **dict(options, quality=qualite))
        if os.path.getsize(chemin_temporaire) <= TAILLE_HEIC_SANS_VERIFICATION:
            return
        try:
            with Image.open(chemin_temporaire) as relue:
                relue.load()
            return
        except Exception:
            continue
    raise OSError("photo trop detaillee pour etre reenregistree en HEIC lisible")


def webp_sans_perte(chemin):
    """Le fichier WEBP est-il compresse sans perte ?

    Un WEBP est une suite de morceaux : « RIFF », sa taille, « WEBP », puis des
    morceaux faits d'un nom de 4 lettres, de leur taille et de leur contenu.
    L'image elle-meme est dans un morceau « VP8 » (avec perte) ou « VP8L »
    (sans perte), parfois precede de « VP8X », « ICCP » ou « ALPH ».
    """
    with open(chemin, "rb") as fichier:
        donnees = fichier.read()
    position = 12
    while position + 8 <= len(donnees):
        nom = donnees[position:position + 4]
        if nom in (b"VP8L", b"VP8 "):
            return nom == b"VP8L"
        taille = int.from_bytes(donnees[position + 4:position + 8], "little")
        position += 8 + taille + taille % 2        # morceaux alignes sur 2 octets
    return False


# Etiquettes EXIF donnant les dimensions de la photo, dans le bloc Exif :
# ExifImageWidth et ExifImageHeight.
ETIQUETTE_LARGEUR_EXIF = 0xA002
ETIQUETTE_HAUTEUR_EXIF = 0xA003


def _mettre_a_jour_les_dimensions_exif(exif, taille):
    """Fait suivre aux dimensions inscrites dans l'EXIF celles de la photo.

    Les photos portent dans leurs donnees EXIF leur propre largeur et hauteur.
    Un rognage ou un quart de tour les change, mais l'EXIF, lui, est recopie
    tel quel : le fichier annoncait alors une taille qui n'etait plus la
    sienne. Mesure sur une photo de 1200x800 rognee a 600x400 : l'EXIF
    continuait d'annoncer 1200x800.

    Ce n'est pas qu'une question de proprete. Certaines visionneuses et
    certains sites se fient a ces deux etiquettes plutot qu'a l'image
    elle-meme, et affichent alors la photo deformee.

    Les etiquettes absentes ne sont pas ajoutees : on ne corrige que ce que la
    photo declarait deja.
    """
    details = exif.get_ifd(ExifTags.IFD.Exif)
    for etiquette, valeur in ((ETIQUETTE_LARGEUR_EXIF, taille[0]),
                              (ETIQUETTE_HAUTEUR_EXIF, taille[1])):
        if etiquette in details:
            details[etiquette] = valeur


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

    Une photo modifiee est enregistree en arriere-plan (ecritures.py) : tant
    que son enregistrement n'est pas fini, le fichier contient encore
    l'ancienne version. `attendre_ecriture(chemin)`, donne par la fenetre, est
    donc appele avant toute lecture : sans lui, une photo pivotee puis quittee
    revenait sans sa rotation, et l'utilisateur la pivotait une seconde fois.
    """

    def __init__(self, chemins, taille_apercu, nb_avance=3, attendre_ecriture=None):
        self.chemins = list(chemins)
        self.taille_apercu = taille_apercu
        self.nb_avance = nb_avance
        self.attendre_ecriture = attendre_ecriture

        # index -> (image, apercu). (None, None) si la photo est illisible ;
        # (image, None) si l'apercu est a refaire (voir changer_taille_apercu).
        self.cache = {}
        # index -> numero de version, augmente chaque fois que la photo change
        # (remplacee, oubliee, deplacee). Une lecture commencee avant le
        # changement est perimee : son resultat est jete, au lieu d'ecraser en
        # memoire la version qui vient d'etre mise.
        self.versions = {}
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
        while True:
            with self.signal:
                self._attendre_fin_de_lecture(index)
                if self._est_prete(index):
                    return self.cache[index]
                image_deja_lue = self._image_en_memoire(index)
                version = self.versions.get(index, 0)

            # Pas encore prete : on la prepare ici meme plutot que d'attendre
            # que le fil d'arriere-plan y arrive. C'est plus simple et cela ne
            # peut jamais se bloquer.
            photo = self._preparer(index, image_deja_lue)
            with self.signal:
                if self.versions.get(index, 0) == version:
                    self.cache[index] = photo
                    self.signal.notify_all()
                    return photo
            # La photo a change pendant qu'on la preparait : on recommence.

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
            self._nouvelle_version(index)
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
            self._nouvelle_version(index)
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
        emplacement est oubliee, pour que la photo soit relue au bon endroit ;
        une lecture en cours a l'ancien emplacement est jetee pour la meme
        raison (sans cela, une photo rangee pendant « Chargement... » restait
        « illisible » pour toute la session).
        """
        with self.signal:
            if self.chemins[index] == chemin:
                return
            self.chemins[index] = chemin
            self._nouvelle_version(index)
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

    def _nouvelle_version(self, index):
        """Note que la photo a change : toute lecture deja commencee est perimee."""
        self.versions[index] = self.versions.get(index, 0) + 1

    def _preparer(self, index, image_deja_lue):
        """Lit la photo si besoin, puis fabrique son apercu. Renvoie (image, apercu).

        Tout le travail est protege, apercu compris : une erreur imprevue (un
        manque de memoire sur une tres grande photo) tuait sinon le fil
        d'arriere-plan, et toutes les photos suivantes restaient sur
        « Chargement... ».
        """
        try:
            image = image_deja_lue
            if image is None:
                chemin = self.chemins[index]
                if self.attendre_ecriture is not None:
                    self.attendre_ecriture(chemin)
                image = charger_image(chemin)
            return (image, fabriquer_apercu(image, self.taille_apercu))
        except Exception:
            # Fichier illisible ou corrompu : on ne fait pas echouer tout le
            # programme pour une photo. L'appelant affichera un message.
            return (None, None)

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
        """Ne garde en memoire que les photos que prepare _prochain_a_charger.

        C'est-a-dire la precedente, la courante et les nb_avance suivantes.
        Une photo de 24 Mpx occupe pres de 100 Mo en memoire : en garder dix,
        comme auparavant, montait a 3 Go avec des photos de 48 Mpx, de quoi
        saturer un portable. Garder exactement ce que le fil prepare evite
        aussi de jeter la photo qu'il vient de lire, qu'il relirait aussitot.
        """
        premiere = self.position - 1
        derniere = self.position + self.nb_avance
        for index in list(self.cache):
            if not premiere <= index <= derniere:
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
                version = self.versions.get(index, 0)
                self.en_lecture = index

            # La preparation, qui est lente, se fait en dehors du verrou pour ne
            # pas bloquer le fil principal quand il vient consulter le cache.
            photo = self._preparer(index, image_deja_lue)

            with self.signal:
                self.en_lecture = None
                self.signal.notify_all()
                if not self.actif:
                    return
                # Une photo remplacee, oubliee ou deplacee pendant sa lecture :
                # ce qui vient d'etre lu est perime, elle sera reprise au tour
                # suivant.
                if self.versions.get(index, 0) == version:
                    self.cache[index] = photo
                    self._nettoyer_cache()
