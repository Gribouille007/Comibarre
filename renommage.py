"""
Noms donnes aux photos (decision de l'utilisateur, 16 novembre 2026).

Le format des noms se choisit a la configuration d'un evenement, et peut etre
change apres coup depuis le menu (« Renommer les photos »). Cinq formats :

- « date_code » (par defaut) : 2026-08-24_14-03-27_K7F2.jpg
  La date et l'heure de prise de vue, puis un code de quatre caracteres tire
  du contenu de la photo. Deux tris faits sur deux ordinateurs se reunissent
  sans que deux photos differentes portent le meme nom, meme prises dans la
  meme seconde ; et une meme photo recoit partout le meme nom.
- « date » : 2026-08-24_14-03-27.jpg, sans le code.
- « numero » : 1.jpg, 2.jpg, 3.jpg... (le seul format avant cette date).
- « evenement » : Mariage_0001.jpg, Mariage_0002.jpg...
- « aucun » : les fichiers gardent le nom que leur a donne l'appareil.

Dans tous les formats, classer les fichiers par nom les donne de la plus
ancienne a la plus recente : les dates s'ecrivent annee, mois, jour, heure, et
les numeros du format « evenement » sont completes par des zeros. (Le format
« numero » n'en a pas : c'est la regle d'origine ; les gestionnaires de
fichiers classent 2 avant 10, mais pas tous les autres programmes.)

Ce module ne fait que calculer des noms et renommer des fichiers : il ne
touche jamais a l'interface, et peut tourner sur un fil d'arriere-plan.
"""

import base64
import hashlib
import os
import time
from datetime import datetime

from fichiers import deplacer_fichier

FORMAT_DATE_CODE = "date_code"
FORMAT_DATE = "date"
FORMAT_NUMERO = "numero"
FORMAT_EVENEMENT = "evenement"
FORMAT_AUCUN = "aucun"

FORMAT_PAR_DEFAUT = FORMAT_DATE_CODE

# Dans l'ordre ou ils sont proposes a l'ecran : (format, libelle).
FORMATS = [
    (FORMAT_DATE_CODE, "Date, heure et code (aucun doublon entre deux tris)"),
    (FORMAT_DATE, "Date et heure"),
    (FORMAT_NUMERO, "Numeros : 1, 2, 3..."),
    (FORMAT_EVENEMENT, "Nom de l'evenement et numero"),
    (FORMAT_AUCUN, "Ne pas renommer"),
]

# Formats dont le nom vient de la date : une photo et son fichier RAW, ou une
# photo et sa video (« Live Photo »), y recoivent le meme nom.
FORMATS_PAR_DATE = (FORMAT_DATE_CODE, FORMAT_DATE)

# Prefixe des noms temporaires utilises pendant le renommage.
PREFIXE_TEMPORAIRE = "_renommage_temporaire_"

# Nombre d'octets du debut du fichier qui servent a calculer son code.
OCTETS_DU_CODE = 65536


def est_un_format(valeur):
    return valeur in [nom_format for nom_format, _ in FORMATS]


def libelle(nom_format):
    for connu, texte in FORMATS:
        if connu == nom_format:
            return texte
    return nom_format


def exemple(nom_format, nom_evenement):
    """Quelques noms tels que ce format les donnera, pour l'ecran de configuration."""
    if nom_format == FORMAT_DATE_CODE:
        return ("2026-08-24_14-03-27_K7F2.jpg,  2026-08-24_14-03-31_Q9XB.jpg\n"
                "Le code evite que deux photos portent le meme nom quand on reunit "
                "des tris faits sur deux ordinateurs.")
    if nom_format == FORMAT_DATE:
        return ("2026-08-24_14-03-27.jpg,  2026-08-24_14-03-31.jpg\n"
                "Attention : deux appareils qui declenchent dans la meme seconde "
                "donnent le meme nom.")
    if nom_format == FORMAT_NUMERO:
        return ("1.jpg,  2.jpg,  3.jpg\n"
                "Attention : deux tris faits separement ont les memes noms.")
    if nom_format == FORMAT_EVENEMENT:
        return ("%s_0001.jpg,  %s_0002.jpg\n"
                "Deux tris se reunissent sans conflit si leurs evenements ne portent "
                "pas le meme nom." % (nom_evenement or "Evenement", nom_evenement or "Evenement"))
    return ("IMG_4012.jpg,  DSC_0034.jpg\n"
            "Les fichiers gardent le nom donne par l'appareil.")


def code_du_fichier(chemin):
    """Code de quatre caracteres (lettres et chiffres) propre au contenu du fichier.

    Il est calcule a partir de la taille du fichier et de son debut, qui
    contient les reglages de la prise de vue et le commencement de l'image :
    deux photos differentes n'ont pas le meme, meme prises dans la meme
    seconde, alors que deux copies d'une meme photo ont toujours le meme, sur
    n'importe quel ordinateur. Lire tout le fichier n'apporterait rien, et
    prendrait des minutes sur 3 000 photos.
    """
    empreinte = hashlib.sha1()
    empreinte.update(str(os.path.getsize(chemin)).encode("ascii"))
    with open(chemin, "rb") as fichier:
        empreinte.update(fichier.read(OCTETS_DU_CODE))
    # base32 : lettres majuscules et chiffres de 2 a 7, lisibles partout et
    # sans risque de confondre deux noms qui ne different que par la casse.
    return base64.b32encode(empreinte.digest()).decode("ascii")[:4]


def identite(nom_fichier, nom_format):
    """Ce qui designe une prise de vue parmi les fichiers a renommer.

    Les fichiers de meme identite recoivent le meme nouveau nom, chacun avec
    son extension. Dans les formats par date, c'est le nom sans l'extension :
    « IMG_12.JPG » et « IMG_12.CR2 » sont la meme prise de vue. Dans les
    formats numerotes, c'est le nom entier : chaque fichier a son numero, et
    « 2.cr2 » se place ainsi entre « 1.jpg » et « 3.jpg » (regle d'origine).
    Une photo et sa version sans barre, ou sa copie, portent le meme nom
    entier : elles restent donc toujours ensemble.
    """
    if nom_format in FORMATS_PAR_DATE:
        return os.path.splitext(nom_fichier)[0]
    return nom_fichier


def calculer_les_noms(prises, nom_format, nom_evenement):
    """Calcule le nouveau nom, sans extension, de chaque prise de vue.

    `prises` : liste de dictionnaires {"identite", "date" (en secondes),
    "nom" (nom d'origine, qui departage deux dates egales), "chemin" (fichier
    dont le contenu donne le code)}.

    Renvoie {identite: nom sans extension}. L'ordre est toujours celui des
    dates, de la plus ancienne a la plus recente, puis celui des noms d'origine.
    """
    ordonnees = sorted(prises, key=lambda prise: (prise["date"], prise["nom"].lower()))
    noms = {}

    if nom_format == FORMAT_NUMERO:
        for numero, prise in enumerate(ordonnees, start=1):
            noms[prise["identite"]] = "%d" % numero
        return noms

    if nom_format == FORMAT_EVENEMENT:
        # Assez de zeros pour que le classement par nom suive les numeros.
        largeur = max(4, len(str(len(ordonnees))))
        for numero, prise in enumerate(ordonnees, start=1):
            noms[prise["identite"]] = "%s_%0*d" % (nom_evenement, largeur, numero)
        return noms

    # Formats par date. Les prises de la meme seconde (rafale) sont
    # numerotees -1, -2... dans leur ordre : sans cela, leur classement par
    # nom dependrait du code, et non de l'ordre des prises de vue.
    par_seconde = {}
    for prise in ordonnees:
        texte = datetime.fromtimestamp(int(prise["date"])).strftime("%Y-%m-%d_%H-%M-%S")
        par_seconde.setdefault(texte, []).append(prise)
    for texte, groupe in par_seconde.items():
        largeur = len(str(len(groupe)))
        for rang, prise in enumerate(groupe, start=1):
            nom = texte
            if len(groupe) > 1:
                nom += "-%0*d" % (largeur, rang)
            if nom_format == FORMAT_DATE_CODE:
                nom += "_" + code_du_fichier(prise["chemin"])
            noms[prise["identite"]] = nom
    return noms


def renommer_en_deux_passes(renommages, avancement=None):
    """Renomme des fichiers sans jamais en ecraser un. `renommages` : [(ancien, nouveau)].

    Renommer directement « a.jpg » en « 3.jpg » ecraserait un autre fichier
    qui porterait deja ce nom, et qui attend lui-meme d'etre renomme. La
    premiere passe donne donc a chacun un nom temporaire, forcement libre ; la
    seconde attribue les noms definitifs. Les noms temporaires portent la
    date et l'heure : ceux d'un renommage interrompu auparavant ne peuvent
    pas les rencontrer.

    Chaque renommage reessaie un instant si le fichier est occupe, et aucun
    n'ecrase un fichier existant (voir fichiers.deplacer_fichier). Si l'un
    echoue, tout ce qui a deja ete renomme reprend son ancien nom, autant que
    possible, puis l'erreur remonte a l'appelant.
    """
    prefixe = "%s%s_" % (PREFIXE_TEMPORAIRE, time.strftime("%Y%m%d%H%M%S"))
    total = 2 * len(renommages)
    faits = []          # (nom actuel, ancien nom) de chaque fichier deja renomme
    try:
        temporaires = []
        for numero, (ancien, nouveau) in enumerate(renommages, start=1):
            temporaire = os.path.join(os.path.dirname(ancien), "%s%d%s" % (
                prefixe, numero, os.path.splitext(ancien)[1]))
            deplacer_fichier(ancien, temporaire)
            faits.append((temporaire, ancien))
            temporaires.append(temporaire)
            if avancement is not None:
                avancement("Renommage : %d sur %d" % (numero, total))

        for numero, (ancien, nouveau) in enumerate(renommages):
            deplacer_fichier(temporaires[numero], nouveau)
            faits[numero] = (nouveau, ancien)
            if avancement is not None:
                avancement("Renommage : %d sur %d" % (len(renommages) + numero + 1, total))
    except OSError:
        for actuel, ancien in faits:
            try:
                deplacer_fichier(actuel, ancien)
            except OSError:
                pass        # ce fichier garde son nom du moment : rien n'est perdu
        raise


def cle_de_classement(nom_fichier):
    """Cle pour classer des noms de fichiers comme le fait un gestionnaire de fichiers.

    Les nombres y sont compares comme des nombres : « 2.jpg » passe avant
    « 10.jpg », et « IMG_9 » avant « IMG_10 ». Les noms par date, de longueur
    fixe, se classent d'eux-memes du plus ancien au plus recent.
    """
    morceaux = []
    courant = ""
    for caractere in nom_fichier.lower():
        if courant and caractere.isdigit() != courant[-1].isdigit():
            morceaux.append(courant)
            courant = ""
        courant += caractere
    if courant:
        morceaux.append(courant)
    # (0, nombre) ou (1, texte) : un nombre et un texte ne se comparent pas
    # entre eux en Python, le premier element les departage.
    return [(0, int(morceau)) if morceau.isdigit() else (1, morceau)
            for morceau in morceaux] + [(1, nom_fichier)]
