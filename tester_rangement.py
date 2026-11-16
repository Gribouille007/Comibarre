"""
Tests du rangement des photos sur le disque.

    python tester_rangement.py

Le tri deplace des fichiers : une erreur ici peut perdre une photo, ou la
laisser en double. Ces tests fabriquent un faux evenement dans un dossier
temporaire, puis verifient, fichier par fichier, ce que deviennent les photos :

1. la preparation et le dossier de l'evenement : renommage chronologique,
   RAW et videos mis de cote, autres fichiers intacts, rien d'ecrase, dossier
   des photos renomme, reprise des evenements de l'ancienne organisation ;
2. les dates de prise de vue : avant 1970, a zero, ecart au temps universel ;
3. le tri : touches de tri (clavier AZERTY compris), annulation, touche N,
   ecran de fin ;
4. le tri face aux fichiers bloques : suivi impossible a enregistrer,
   annulation qui echoue ou s'arrete a mi-chemin, enregistrement en cours ou
   rate, fermeture ;
5. le chargement anticipe : attente des enregistrements, lectures perimees ;
6. les bandeaux : rattachement d'un clic au bon visage, gestes de la souris ;
7. les photos revenues dans le dossier source, comme le fait OneDrive ;
8. la gestion des dossiers de tri depuis le menu ;
9. les regles des noms et des touches ;
10. les formats de nom des photos, et le renommage d'un evenement existant ;
11. l'annulation photo par photo, gardee d'une session a l'autre ;
12. les statistiques de la fenetre de tri ;
13. la fin de la session : tri definitif, dossiers vides supprimes.

Une vraie fenetre de tri est ouverte, mais rendue invisible, et les messages
sont interceptes au lieu d'etre affiches. Aucun fichier de l'utilisateur n'est
touche : tout se passe dans un dossier temporaire, efface a la fin, et les
preferences sont lues et ecrites dans un fichier temporaire, elles aussi.
"""

import os
import shutil
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import messagebox

from PIL import Image

import preferences

# Les preferences de l'utilisateur ne doivent pas etre modifiees par les tests.
DOSSIER_ESSAI = tempfile.mkdtemp(prefix="tester_rangement_")
preferences.CHEMIN_PREFERENCES = os.path.join(DOSSIER_ESSAI, "preferences.json")

import dossiers_tri                                   # noqa: E402
import fin_de_session                                 # noqa: E402
import gestion_dossiers                               # noqa: E402
import preparation                                    # noqa: E402
import rangement                                      # noqa: E402
import remise_en_place                                # noqa: E402
import renommage                                      # noqa: E402
import renommage_evenement                            # noqa: E402
import theme                                          # noqa: E402
from bandeaux import Bandeau                          # noqa: E402
from censure import OutilBandeaux                     # noqa: E402
from dossiers import photos_du_dossier, probleme_du_nom  # noqa: E402
from fichiers import deplacer_fichier, renommer_dossier  # noqa: E402
from images import ChargeurAnticipe                   # noqa: E402
from suivi import Suivi                               # noqa: E402
from revue import preparer_revue                      # noqa: E402
from tri import preparer_tri                          # noqa: E402
from visages import Visage, visage_le_plus_proche     # noqa: E402

resultats = []

# Messages interceptes : (fonction, titre). askyesno repond selon REPONSE_OUI.
messages = []
REPONSE_OUI = {"valeur": True}


def _intercepter(nom):
    def remplacer(titre="", texte="", **options):
        messages.append((nom, titre))
        return REPONSE_OUI["valeur"] if nom == "askyesno" else None
    return remplacer


for _nom in ("showinfo", "showwarning", "showerror", "askyesno"):
    setattr(messagebox, _nom, _intercepter(_nom))


def verifier(intitule, reussi, detail=""):
    resultats.append((bool(reussi), intitule))
    print("  [%s] %-58s %s" % ("OK" if reussi else "ECHEC", intitule, detail))


class Touche:
    """Une touche pressee, telle que Tkinter la decrit."""

    def __init__(self, keysym, char=""):
        self.keysym = keysym
        self.char = char


# ----------------------------------------------------------------------
# Fabrication d'un evenement d'essai
# ----------------------------------------------------------------------

def photo(chemin, couleur, date=None):
    """Ecrit une petite photo JPEG, avec une date de prise de vue si demandee."""
    image = Image.new("RGB", (320, 240), couleur)
    exif = Image.Exif()
    if date:
        exif.get_ifd(0x8769)[0x9003] = date      # DateTimeOriginal
    image.save(chemin, exif=exif.tobytes())


def nouvel_evenement(nom_dossier="Import", dossiers=None, nom_format="numero"):
    """Dossier de photos neuf, renomme « Mariage » et prepare comme le fait le logiciel."""
    parent = tempfile.mkdtemp(dir=DOSSIER_ESSAI)
    source = os.path.join(parent, nom_dossier)
    os.makedirs(source)
    # Noms dans le desordre de leurs dates : le renommage doit suivre les dates.
    for numero, date in ((3, "2026:05:01 10:00:02"), (1, "2026:05:01 10:00:00"),
                         (2, "2026:05:01 10:00:01"), (5, "2026:05:01 10:00:04"),
                         (4, "2026:05:01 10:00:03"), (6, "2026:05:01 10:00:05")):
        photo(os.path.join(source, "IMG_%d.jpg" % numero), (numero * 40, 80, 120), date)
    with open(os.path.join(source, "notes.txt"), "w") as fichier:
        fichier.write("a ne pas toucher")
    with open(os.path.join(source, "film.mp4"), "wb") as fichier:
        fichier.write(b"video")

    evenement = renommer_dossier(source, "Mariage")
    suivi = Suivi.creer(evenement, "Mariage", dossiers or [{"nom": "A garder", "touche": "1"},
                                                          {"nom": "Ratees", "touche": "2"}],
                        renommage=nom_format)
    suivi.enregistrer()
    rapport = preparation.preparer(suivi)
    return suivi, rapport


def contenu(dossier):
    return sorted(nom for nom in os.listdir(dossier)
                  if os.path.isfile(os.path.join(dossier, nom)))


def ouvrir_le_tri(racine, suivi):
    """Ouvre une vraie fenetre de tri, invisible, et attend sa premiere photo."""
    preparer_tri(suivi)
    fenetre = rangement.FenetreRangement(racine, suivi, suivi.tri, None, "essai")
    fenetre.fenetre.attributes("-alpha", 0.0)
    attendre(racine, 0.5)
    return fenetre


def attendre(racine, secondes):
    fin = time.time() + secondes
    while time.time() < fin:
        racine.update()
        time.sleep(0.01)


def presser(racine, fenetre, touche):
    """Presse une touche une fois la photo affichee, puis attend que son effet soit visible.

    Une touche de tri pressee pendant « Chargement... » est ignoree, a
    dessein : sur un ordinateur occupe, une attente fixe ne suffit pas toujours.
    """
    for _ in range(2):
        fin = time.time() + 5
        while time.time() < fin and (fenetre.attente is not None
                                     or fenetre.attente_enregistrement is not None
                                     or fenetre.ecritures.en_cours()):
            racine.update()
            time.sleep(0.01)
        if touche is not None:
            fenetre._touche(touche)
            touche = None
            attendre(racine, 0.15)


# ----------------------------------------------------------------------
# 1 et 2. Preparation et dossier de l'evenement
# ----------------------------------------------------------------------

def test_preparation():
    print("\n1. Preparation et dossier de l'evenement")
    suivi, rapport = nouvel_evenement()
    dossier = suivi.dossier_evenement
    verifier("le dossier des photos est renomme du nom de l'evenement",
             os.path.basename(dossier) == "Mariage", dossier)
    verifier("l'evenement est le dossier source lui-meme",
             suivi.dossier_source == dossier)
    verifier("les photos sont numerotees 1 a 6",
             contenu(dossier) == ["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg", "6.jpg",
                                  "notes.txt", "suivi.json"], contenu(dossier))
    verifier("la video est mise de cote, avec son numero",
             contenu(os.path.join(dossier, "Videos")) == ["7.mp4"])
    verifier("le compte rendu est exact",
             (rapport["photos"], rapport["videos"], rapport["ignores"]) == (6, 1, 1), rapport)
    with Image.open(os.path.join(dossier, "1.jpg")) as image:
        rouge = image.getpixel((5, 5))[0]
    verifier("1.jpg est bien la photo la plus ancienne", abs(rouge - 40) <= 4, rouge)
    verifier("la reprise relit le meme evenement",
             Suivi.charger(dossier).dossier_source == dossier)

    # Ancienne organisation : l'evenement dans un sous-dossier du dossier source.
    ancien = Suivi.creer(os.path.join(DOSSIER_ESSAI, "Ancien", "Fete"), "Fete", [])
    ancien.donnees["version"] = 1
    verifier("un evenement de la version 1 garde son dossier source parent",
             ancien.dossier_source == os.path.join(DOSSIER_ESSAI, "Ancien"))

    # Mise a l'ecart : un RAW du meme nom existe deja dans RAW/.
    parent = tempfile.mkdtemp(dir=DOSSIER_ESSAI)
    os.makedirs(os.path.join(parent, "RAW"))
    with open(os.path.join(parent, "RAW", "2.cr2"), "wb") as fichier:
        fichier.write(b"ancien RAW")
    photo(os.path.join(parent, "a.jpg"), (10, 10, 10), "2026:01:01 00:00:00")
    with open(os.path.join(parent, "b.cr2"), "wb") as fichier:
        fichier.write(b"nouveau RAW")
    os.utime(os.path.join(parent, "b.cr2"), (2e9, 2e9))      # plus recent que a.jpg
    suivi_raw = Suivi.creer(parent, "Raw", [{"nom": "A garder", "touche": "1"}],
                            renommage="numero")
    rapport = preparation.preparer(suivi_raw)
    with open(os.path.join(parent, "RAW", "2.cr2"), "rb") as fichier:
        intact = fichier.read() == b"ancien RAW"
    verifier("un RAW deja present dans RAW/ n'est jamais ecrase", intact)
    verifier("le nouveau RAW reste a la racine, et c'est signale",
             rapport["laisses"] == ["2.cr2"] and os.path.isfile(os.path.join(parent, "2.cr2")),
             rapport["laisses"])

    try:
        deplacer_fichier(os.path.join(parent, "2.cr2"), os.path.join(parent, "RAW", "2.cr2"))
        refuse = False
    except FileExistsError:
        refuse = True
    verifier("deplacer_fichier refuse une destination deja prise", refuse)

    # Un RAW occupe trop longtemps par un autre programme reste a la racine :
    # la preparation va jusqu'au bout au lieu de s'arreter apres le renommage.
    vrai_deplacer = preparation.deplacer_fichier

    def refuser(source, destination):
        raise PermissionError(13, "fichier utilise par un autre programme")
    preparation.deplacer_fichier = refuser
    try:
        restants, laisses = preparation.mettre_a_ecart(suivi_raw, ["1.jpg", "3.cr2"])
    finally:
        preparation.deplacer_fichier = vrai_deplacer
    verifier("un RAW occupe reste a la racine, sans arreter la preparation",
             restants == ["1.jpg"] and laisses == ["3.cr2"], (restants, laisses))

    verifier("les fichiers « ._ » de macOS ne sont pas pris pour des photos",
             not preparation.est_pris_en_charge("._IMG_0001.JPG")
             and preparation.est_pris_en_charge("IMG_0001.JPG"))
    with open(os.path.join(parent, "._3.jpg"), "wb") as fichier:
        fichier.write(b"Mac OS X")
    verifier("ni montres au tri, ni comptes au menu",
             "._3.jpg" not in photos_du_dossier(parent), photos_du_dossier(parent))

    # Un sous-dossier qui porte le nom que doit recevoir une photo : signale
    # avant d'avoir renomme quoi que ce soit.
    parent = tempfile.mkdtemp(dir=DOSSIER_ESSAI)
    photo(os.path.join(parent, "a.jpg"), (10, 10, 10), "2026:01:01 00:00:00")
    photo(os.path.join(parent, "b.jpg"), (20, 20, 20), "2026:01:01 00:00:01")
    os.makedirs(os.path.join(parent, "2.jpg"))
    try:
        preparation.preparer(Suivi.creer(parent, "Bloque", [{"nom": "A", "touche": "1"}],
                                         renommage="numero"))
        refuse = False
    except FileExistsError:
        refuse = True
    verifier("un sous-dossier « 2.jpg » est signale avant tout renommage",
             refuse and {"a.jpg", "b.jpg"} <= set(os.listdir(parent)), os.listdir(parent))
    return suivi


def photo_datee(chemin, originale=None, inscrite=None, decalage=None):
    """Petite photo JPEG portant les dates EXIF demandees."""
    exif = Image.Exif()
    if inscrite:
        exif[0x0132] = inscrite                       # DateTime
    details = exif.get_ifd(0x8769)
    if originale:
        details[0x9003] = originale                   # DateTimeOriginal
    if decalage:
        details[0x9011] = decalage                    # OffsetTimeOriginal
    Image.new("RGB", (32, 32)).save(chemin, exif=exif.tobytes())


def test_dates():
    print("\n2. Dates de prise de vue")
    dossier = tempfile.mkdtemp(dir=DOSSIER_ESSAI)

    chemin = os.path.join(dossier, "scan.jpg")
    photo_datee(chemin, "1969:07:20 20:17:00")
    try:
        preparation.ordre_chronologique(chemin)
        sans_erreur = True
    except Exception:
        sans_erreur = False
    verifier("une photo datee d'avant 1970 ne bloque pas la preparation", sans_erreur)

    chemin = os.path.join(dossier, "zeros.jpg")
    photo_datee(chemin, "0000:00:00 00:00:00", inscrite="2026:08:24 08:00:00")
    verifier("une DateTimeOriginal a zero laisse la place a DateTime",
             preparation.date_de_prise_de_vue_exif(chemin)
             == preparation._en_secondes("2026:08:24 08:00:00", None))

    # La nuit du changement d'heure : lues comme des heures locales, ces deux
    # photos seraient dans le mauvais ordre. Leur ecart au temps universel
    # remet l'instant exact.
    premiere = os.path.join(dossier, "premiere.jpg")
    seconde = os.path.join(dossier, "seconde.jpg")
    photo_datee(premiere, "2026:10:25 02:50:00", decalage="+02:00")     # 00:50 UTC
    photo_datee(seconde, "2026:10:25 02:40:00", decalage="+01:00")      # 01:40 UTC
    verifier("l'ecart au temps universel est pris en compte",
             preparation.date_de_prise_de_vue_exif(premiere)
             < preparation.date_de_prise_de_vue_exif(seconde))
    verifier("un ecart illisible est ignore",
             preparation._en_secondes("2026:10:25 02:50:00", "  :  ") is not None)


# ----------------------------------------------------------------------
# 3. Le tri
# ----------------------------------------------------------------------

def test_tri(racine):
    print("\n3. Le tri")
    suivi, _ = nouvel_evenement()
    dossier = suivi.dossier_evenement
    garder = os.path.join(dossier, "A garder")
    fenetre = ouvrir_le_tri(racine, suivi)
    try:
        fenetre._touche(Touche("1", "1"))
        attendre(racine, 0.2)
        verifier("la touche 1 range la photo 1", contenu(garder) == ["1.jpg"], contenu(garder))
        verifier("le rangement est retenu dans le suivi",
                 suivi.rangements.get("1.jpg") == "A garder")

        fenetre._touche(Touche("eacute", "\u00e9"))          # touche 2 d'un AZERTY
        attendre(racine, 0.2)
        verifier("AZERTY : la touche 2 sans Majuscule range dans « Ratees »",
                 "2.jpg" in contenu(os.path.join(dossier, "Ratees")))

        fenetre._touche(Touche("BackSpace"))
        attendre(racine, 0.2)
        verifier("Retour arriere ramene la photo dans le dossier source",
                 "2.jpg" in contenu(dossier)
                 and "2.jpg" not in contenu(os.path.join(dossier, "Ratees")))
        verifier("l'annulation efface le rangement retenu", "2.jpg" not in suivi.rangements)
        verifier("et revient sur la photo annulee", fenetre.position == 1, fenetre.position)

        # Touche N : la boite est remplacee par une reponse toute faite.
        reponse = {"nom": "Famille", "touche": "3"}
        ancienne_boite = rangement.demander_nouveau_dossier
        rangement.demander_nouveau_dossier = lambda parent, suivi_tri: dict(reponse)
        try:
            fenetre._touche(Touche("n", "n"))
        finally:
            rangement.demander_nouveau_dossier = ancienne_boite
        verifier("N cree le dossier sur le disque",
                 os.path.isdir(os.path.join(dossier, "Famille")))
        verifier("N ajoute le dossier a l'evenement",
                 suivi.dossier_tri_pour_touche("3") == "Famille")
        verifier("N retient le dossier pour les prochains evenements",
                 any(d["nom"] == "Famille" for d in preferences.dossiers_de_tri() or []))
        verifier("N laisse la photo affichee a sa place",
                 fenetre.position == 1 and "2.jpg" in contenu(dossier))
        verifier("le rappel des touches montre le nouveau dossier",
                 "[3] Famille" in fenetre.etiquette_rappel.cget("text"))
        fenetre._touche(Touche("3", "3"))
        attendre(racine, 0.2)
        verifier("la touche du nouveau dossier y range la photo",
                 contenu(os.path.join(dossier, "Famille")) == ["2.jpg"])

        # Passer les autres : l'ecran de fin dit combien il en reste.
        while fenetre.position < len(fenetre.photos):
            fenetre._touche(Touche("space", " "))
        attendre(racine, 0.1)
        verifier("l'ecran de fin dit combien de photos restent",
                 "Il en reste 4" in fenetre.visionneuse.message,
                 fenetre.visionneuse.message.splitlines()[1])
        fenetre._touche(Touche("Return"))
        verifier("Entree, a la fin, demande a repasser les photos restantes",
                 fenetre.recommencer)
    finally:
        if fenetre.fenetre.winfo_exists():
            fenetre.quitter()
    return suivi


def test_robustesse(racine):
    print("\n4. Le tri face aux fichiers bloques (OneDrive, antivirus)")
    suivi, _ = nouvel_evenement()
    dossier = suivi.dossier_evenement
    garder = os.path.join(dossier, "A garder")
    vrai_enregistrer = suivi.enregistrer

    def refuser_le_suivi():
        raise PermissionError(13, "fichier utilise par un autre programme")

    fenetre = ouvrir_le_tri(racine, suivi)
    try:
        # Suivi impossible a enregistrer : l'ecran doit rester sur la position.
        suivi.enregistrer = refuser_le_suivi
        del messages[:]
        fenetre._touche(Touche("space", " "))
        attendre(racine, 0.3)
        verifier("suivi bloque : l'ecran montre bien la photo suivante",
                 fenetre.position == 1
                 and "Photo 2 sur" in fenetre.etiquette_avancement.cget("text"))
        fenetre._touche(Touche("1", "1"))
        attendre(racine, 0.3)
        verifier("suivi bloque : la touche range la photo affichee",
                 contenu(garder) == ["2.jpg"], contenu(garder))
        avertissements = [m for m in messages if m[1] == "Avancement non enregistre"]
        verifier("suivi bloque : un seul avertissement", len(avertissements) == 1, messages)
        suivi.enregistrer = vrai_enregistrer

        # Annulation qui echoue (photo ouverte ailleurs) : l'action reste.
        vrai_deplacer = rangement.deplacer_fichier

        def refuser_le_deplacement(source, destination):
            raise PermissionError(13, "photo ouverte dans un autre programme")
        rangement.deplacer_fichier = refuser_le_deplacement
        del messages[:]
        try:
            fenetre._touche(Touche("BackSpace"))
            attendre(racine, 0.2)
        finally:
            rangement.deplacer_fichier = vrai_deplacer
        verifier("annulation impossible : l'utilisateur est prevenu",
                 ("showerror", "Annulation impossible") in messages, messages)
        verifier("annulation impossible : l'action reste a annuler",
                 len(suivi.historique) == 1 and contenu(garder) == ["2.jpg"])
        fenetre._touche(Touche("BackSpace"))
        attendre(racine, 0.2)
        verifier("rappuyer sur Retour arriere annule bien le rangement",
                 "2.jpg" in contenu(dossier) and not contenu(garder)
                 and not suivi.historique)

        # Une touche pendant qu'un enregistrement se termine : la fenetre ne
        # se fige pas, et l'action est faite des qu'il est fini.
        termine = {"fait": False}
        verrou = threading.Event()

        def enregistrement_lent():
            verrou.wait(5)
            termine["fait"] = True
        chemin = os.path.join(dossier, "2.jpg")
        fenetre.ecritures.ajouter(chemin, enregistrement_lent)
        fenetre._touche(Touche("1", "1"))
        verifier("pendant un enregistrement, la touche de tri attend sans figer",
                 contenu(garder) == [] and fenetre.attente_enregistrement is not None)
        verrou.set()
        attendre(racine, 0.4)
        verifier("puis range la photo une fois l'enregistrement fini",
                 termine["fait"] and contenu(garder) == ["2.jpg"], contenu(garder))
    finally:
        suivi.enregistrer = vrai_enregistrer
        if fenetre.fenetre.winfo_exists():
            fenetre.quitter()

    # Echap alors que le suivi est bloque : la fenetre se ferme quand meme.
    fenetre = ouvrir_le_tri(racine, suivi)
    suivi.enregistrer = refuser_le_suivi
    try:
        fenetre.quitter()
        attendre(racine, 0.2)
        verifier("Echap ferme la fenetre meme si le suivi est bloque",
                 not fenetre.fenetre.winfo_exists())
    finally:
        suivi.enregistrer = vrai_enregistrer
        if fenetre.fenetre.winfo_exists():
            fenetre.fenetre.destroy()


def pixel_sur_le_disque(chemin):
    with Image.open(chemin) as image:
        return image.convert("RGB").getpixel((160, 120))


def test_echecs(racine):
    print("\n4 bis. Enregistrements et annulations qui echouent")
    suivi, _ = nouvel_evenement()
    dossier = suivi.dossier_evenement
    garder = os.path.join(dossier, "A garder")

    def refuser(*arguments):
        raise PermissionError(13, "fichier utilise par un autre programme")

    fenetre = ouvrir_le_tri(racine, suivi)
    try:
        # Rognage dont l'enregistrement echoue : l'ecran doit reprendre le
        # fichier, sans quoi un bandeau tomberait a cote des yeux.
        vrai_rogner = rangement.rogner_fichier
        rangement.rogner_fichier = refuser
        del messages[:]
        try:
            fenetre.commencer_rognage()
            fenetre.visionneuse.cadre = (0.0, 0.0, 160.0, 120.0)
            fenetre.rogner()
            attendre(racine, 0.7)
        finally:
            rangement.rogner_fichier = vrai_rogner
        verifier("rognage rate : l'utilisateur est prevenu",
                 ("showerror", "Enregistrement impossible") in messages, messages)
        image = fenetre.visionneuse.image
        verifier("rognage rate : l'ecran reprend la photo du fichier",
                 image is not None and image.width == 320, image and image.size)

        # Une photo encore sur « Chargement... » n'est pas rangee.
        fenetre.attente = fenetre.fenetre.after(60000, lambda: None)
        fenetre._touche(Touche("1", "1"))
        verifier("une photo encore en chargement n'est pas rangee", contenu(garder) == [],
                 contenu(garder))
        fenetre._annuler_attente()

        # Annulation d'une retouche, faite a moitie : la copie intacte est
        # revenue, mais la version sans barre n'a pas pu etre effacee.
        fenetre.outil.bandeaux_manuels.append(Bandeau(160, 120, 120, 40, 0))
        fenetre._touche(Touche("Return"))
        attendre(racine, 0.4)
        fenetre._touche(Touche("Left"))
        attendre(racine, 0.4)
        nombre_d_actions = len(suivi.historique)
        vrai_supprimer = rangement.supprimer_fichier
        rangement.supprimer_fichier = refuser
        try:
            fenetre._touche(Touche("BackSpace"))
            attendre(racine, 0.4)
        finally:
            rangement.supprimer_fichier = vrai_supprimer
        image = fenetre.visionneuse.image
        verifier("annulation a moitie faite : l'ecran montre le fichier, sans bandeau",
                 image is not None and sum(image.getpixel((160, 120))) > 60,
                 image and image.getpixel((160, 120)))
        verifier("annulation a moitie faite : l'action reste a terminer",
                 len(suivi.historique) == nombre_d_actions)
        fenetre._touche(Touche("BackSpace"))
        attendre(racine, 0.3)
        verifier("et rappuyer la termine",
                 len(suivi.historique) == nombre_d_actions - 1)
    finally:
        if fenetre.fenetre.winfo_exists():
            fenetre.quitter()

    # Rangement avec bandeau, annule a moitie, puis fermeture : la copie
    # intacte ne doit pas partir avec le dossier des sauvegardes.
    fenetre = ouvrir_le_tri(racine, suivi)
    try:
        nom = fenetre.photos[fenetre.position]
        fenetre.outil.bandeaux_manuels.append(Bandeau(160, 120, 120, 40, 0))
        fenetre._touche(Touche("1", "1"))
        attendre(racine, 0.4)
        vrai_remplacer = rangement.remplacer_fichier
        rangement.remplacer_fichier = refuser
        try:
            fenetre._touche(Touche("BackSpace"))
            attendre(racine, 0.3)
        finally:
            rangement.remplacer_fichier = vrai_remplacer
        verifier("rangement annule a moitie : la photo est revenue, encore barree",
                 sum(pixel_sur_le_disque(os.path.join(dossier, nom))) < 60)
        fenetre.quitter()
        attendre(racine, 0.3)
        verifier("fermer termine l'annulation : la photo redevient intacte",
                 sum(pixel_sur_le_disque(os.path.join(dossier, nom))) > 60)
    finally:
        if fenetre.fenetre.winfo_exists():
            fenetre.quitter()


def test_chargeur():
    print("\n5. Chargement anticipe des photos")
    dossier = tempfile.mkdtemp(dir=DOSSIER_ESSAI)
    rouge = os.path.join(dossier, "rouge.jpg")
    bleue = os.path.join(dossier, "bleue.jpg")
    photo(rouge, (250, 0, 0))
    photo(bleue, (0, 0, 250))

    # L'attente d'enregistrement retient le fil juste avant qu'il lise la
    # photo rouge ; pendant ce temps, la photo « change de dossier ».
    vus = []
    libre = threading.Event()

    def attendre_ecriture(chemin):
        vus.append(chemin)
        libre.wait(5)
    chargeur = ChargeurAnticipe([rouge], (100, 100), attendre_ecriture=attendre_ecriture)
    try:
        time.sleep(0.3)
        chargeur.changer_chemin(0, bleue)
        libre.set()
        image, _ = chargeur.photo(0)
    finally:
        chargeur.arreter()
    verifier("le chargeur attend l'enregistrement en cours avant de lire",
             vus[:1] == [rouge], vus)
    verifier("une lecture devenue perimee est jetee, la photo relue au bon endroit",
             image is not None and image.getpixel((5, 5))[2] > 200,
             image.getpixel((5, 5)) if image else None)


# ----------------------------------------------------------------------
# Bandeaux : rattachement des clics et gestes de la souris
# ----------------------------------------------------------------------

class FausseVisionneuse:
    """Le strict necessaire de la visionneuse pour l'outil bandeaux : zoom 1, sans rotation."""

    def __init__(self, largeur, hauteur):
        self.image = Image.new("RGB", (largeur, hauteur))
        self.rotation = 0

    def facteur_affichage(self):
        return 1.0

    def dimensions_affichees(self):
        return self.image.size

    def demander_dessin(self):
        pass

    def definir_curseur(self, nom):
        pass


def test_bandeaux():
    print("\n6. Bandeaux : clics et gestes")
    # Un grand visage au premier plan, un petit derriere lui.
    grand = Visage(100, 100, 300, 300, (200, 200), (300, 200), 0.9)
    petit = Visage(255, 170, 60, 60, (270, 190), (300, 190), 0.9)
    verifier("un clic pres des yeux du grand visage lui revient, meme dans la "
             "boite du petit", visage_le_plus_proche([grand, petit], 262, 205) == 0)
    verifier("un clic sur une personne non detectee, a cote d'une autre, "
             "ne lui est pas rattache", visage_le_plus_proche([grand], 480, 200) is None)

    outil = OutilBandeaux(FausseVisionneuse(800, 600), lambda: None)
    outil.relachee(-40, 300, a_glisse=False)
    verifier("un clic hors de la photo ne pose aucun bandeau", not outil.bandeaux())

    # Clic avant l'arrivee des visages : un bandeau est pose aussitot, puis
    # remplace par celui du visage, qui suit l'inclinaison de la tete.
    penche = Visage(100, 100, 300, 300, (200, 180), (300, 220), 0.9)
    outil.relachee(250, 200, a_glisse=False)
    verifier("un clic avant la detection pose aussitot un bandeau",
             len(outil.bandeaux()) == 1)
    outil.recevoir_visages([penche])
    verifier("puis le bandeau suit la tete des que les visages arrivent",
             len(outil.bandeaux()) == 1 and 0 in outil.bandeaux_visages
             and abs(outil.bandeaux_visages[0].angle - 21.8) < 0.5,
             [round(b.angle, 1) for b in outil.bandeaux()])
    outil.vider()

    # Le meme bandeau, deplace a la main avant l'arrivee des visages : il
    # couvre une autre personne, et doit rester ou l'utilisateur l'a mis.
    outil.relachee(250, 200, a_glisse=False)
    deplace = outil.bandeau_selectionne
    outil.pressee(250, 200)
    outil.glissee(600, 120)
    outil.relachee(600, 120, a_glisse=True)
    outil.recevoir_visages([penche])
    verifier("un bandeau deplace avant la detection reste ou on l'a mis",
             outil.bandeaux() == [deplace] and (deplace.centre_x, deplace.centre_y) == (600, 120),
             (deplace.centre_x, deplace.centre_y))
    outil.vider()

    # Bandeau fin (moins de deux fois la zone des poignees) : le prendre par
    # son milieu le deplace, sans l'amincir.
    outil.recevoir_visages([grand])
    outil.relachee(250, 200, a_glisse=False)
    bandeau = outil.bandeau_selectionne
    bandeau.epaisseur = 10
    epaisseur = bandeau.epaisseur
    centre_x = bandeau.centre_x
    outil.pressee(bandeau.centre_x, bandeau.centre_y)
    outil.glissee(bandeau.centre_x + 40, bandeau.centre_y)
    outil.relachee(bandeau.centre_x, bandeau.centre_y, a_glisse=True)
    verifier("un bandeau fin pris par son milieu se deplace sans s'amincir",
             abs(bandeau.centre_x - centre_x - 40) < 0.01 and bandeau.epaisseur == epaisseur,
             (bandeau.centre_x - centre_x, bandeau.epaisseur))
    x_poignee, y_poignee = bandeau.poignees(outil._marge_rotation())["epaisseur_bas"]
    verifier("sa poignee d'epaisseur, elle, tire toujours l'epaisseur",
             outil._ce_qui_est_sous_le_point(x_poignee, y_poignee) == "epaisseur_bas")

    x_poignee, y_poignee = bandeau.poignees(outil._marge_rotation())["rotation"]
    verifier("un double-clic sur une poignee ne retire pas le bandeau",
             not outil.double_clic(x_poignee, y_poignee) and bandeau in outil.bandeaux())
    verifier("un double-clic sur le bandeau le retire",
             outil.double_clic(bandeau.centre_x, bandeau.centre_y) and not outil.bandeaux())

    # Rognage qui fait sortir le visage du cadre : il n'attire plus les clics.
    outil.decaler(420, 0, 380, 600)
    verifier("un visage sorti du cadre par un rognage est oublie", outil.visages == [])


# ----------------------------------------------------------------------
# 4. Photos revenues dans le dossier source
# ----------------------------------------------------------------------

def test_photos_revenues(suivi):
    print("\n7. Photos revenues dans le dossier source (OneDrive)")
    dossier = suivi.dossier_evenement
    garder = os.path.join(dossier, "A garder")
    # La synchronisation remet 1.jpg dans le dossier source.
    os.rename(os.path.join(garder, "1.jpg"), os.path.join(dossier, "1.jpg"))
    verifier("la photo revenue est reperee",
             remise_en_place.photos_revenues(suivi) == [("1.jpg", "A garder")])
    REPONSE_OUI["valeur"] = True
    remise_en_place.proposer_de_remettre_en_place(None, suivi)
    verifier("« Oui » la remet dans son dossier",
             contenu(garder) == ["1.jpg"] and "1.jpg" not in contenu(dossier))

    # Doublon identique (synchronisation qui a recopie la photo).
    shutil.copy2(os.path.join(garder, "1.jpg"), os.path.join(dossier, "1.jpg"))
    remise_en_place.proposer_de_remettre_en_place(None, suivi)
    verifier("un doublon identique est supprime du dossier source, sans perte",
             contenu(garder) == ["1.jpg"] and "1.jpg" not in contenu(dossier))

    # Fichier different du meme nom : rien n'est ecrase.
    photo(os.path.join(dossier, "1.jpg"), (250, 0, 0))
    avant = open(os.path.join(garder, "1.jpg"), "rb").read()
    remise_en_place.proposer_de_remettre_en_place(None, suivi)
    apres = open(os.path.join(garder, "1.jpg"), "rb").read()
    verifier("un fichier different du meme nom n'est jamais ecrase",
             avant == apres and os.path.isfile(os.path.join(dossier, "1.jpg")))
    verifier("et la photo est alors laissee a trier", "1.jpg" not in suivi.rangements)
    os.remove(os.path.join(dossier, "1.jpg"))

    # « Non » : la photo reste a trier, son rangement est oublie.
    os.rename(os.path.join(garder, "1.jpg"), os.path.join(dossier, "1.jpg"))
    suivi.noter_rangement("1.jpg", "A garder")
    REPONSE_OUI["valeur"] = False
    remise_en_place.proposer_de_remettre_en_place(None, suivi)
    REPONSE_OUI["valeur"] = True
    verifier("« Non » laisse la photo a trier et oublie son rangement",
             "1.jpg" in contenu(dossier) and "1.jpg" not in suivi.rangements)


# ----------------------------------------------------------------------
# 5. Gestion des dossiers de tri
# ----------------------------------------------------------------------

def test_gestion(suivi):
    print("\n8. Gestion des dossiers de tri")
    dossier = suivi.dossier_evenement
    # « Ratees » est vide, « Famille » contient 2.jpg.
    suivi.noter_rangement("2.jpg", "Famille")
    nouveaux = [{"nom": "A garder", "touche": "1", "origine": "A garder"},
                {"nom": "Gens", "touche": "3", "origine": "Famille"},
                {"nom": "Amis", "touche": "a", "origine": None}]
    erreurs = (dossiers_tri.erreurs_des_dossiers(nouveaux)
               + dossiers_tri.erreurs_sur_le_disque(nouveaux, dossier)
               + gestion_dossiers._erreurs_d_echange(nouveaux))
    verifier("la nouvelle liste est acceptee", not erreurs, erreurs)
    gestion_dossiers.appliquer(suivi, nouveaux)
    verifier("le dossier renomme garde ses photos",
             contenu(os.path.join(dossier, "Gens")) == ["2.jpg"]
             and not os.path.exists(os.path.join(dossier, "Famille")))
    verifier("le suivi suit le nouveau nom", suivi.rangements.get("2.jpg") == "Gens")
    verifier("le dossier vide retire est supprime du disque",
             not os.path.exists(os.path.join(dossier, "Ratees")))
    verifier("le dossier ajoute est cree", os.path.isdir(os.path.join(dossier, "Amis")))
    verifier("la liste du suivi est celle demandee, dans l'ordre",
             suivi.noms_dossiers_tri == ["A garder", "Gens", "Amis"], suivi.noms_dossiers_tri)

    try:
        gestion_dossiers.appliquer(suivi, [{"nom": "A garder", "touche": "1",
                                            "origine": "A garder"}])
        refuse = False
    except OSError:
        refuse = True
    verifier("un dossier non vide ne peut pas etre retire",
             refuse and os.path.isfile(os.path.join(dossier, "Gens", "2.jpg")))

    echange = [{"nom": "Gens", "touche": "1", "origine": "A garder"},
               {"nom": "A garder", "touche": "3", "origine": "Gens"}]
    verifier("echanger deux noms d'un coup est refuse",
             bool(gestion_dossiers._erreurs_d_echange(echange)))


# ----------------------------------------------------------------------
# 6. Regles des noms et des touches
# ----------------------------------------------------------------------

def test_regles():
    print("\n9. Regles des noms et des touches")
    for nom in ("CON", "nul.txt", "Photos.", " Photos", "a/b", "COM3"):
        verifier("nom refuse : %r" % nom, probleme_du_nom(nom) is not None)
    verifier("nom accepte : « A garder »", probleme_du_nom("A garder") is None)

    def erreurs(*paires):
        return dossiers_tri.erreurs_des_dossiers([{"nom": n, "touche": t} for n, t in paires])

    verifier("douze dossiers au plus", erreurs(*[("D%d" % i, "%d" % (i % 10)) for i in
                                                  range(13)]))
    verifier("touches R, C et N reservees",
             all(erreurs(("A", touche)) for touche in ("r", "C", "n")))
    verifier("noms du logiciel reserves",
             all(erreurs((nom, "1")) for nom in ("RAW", "videos", "Sans-barre")))
    verifier("deux fois la meme touche refusee", erreurs(("A", "1"), ("B", "1")))
    verifier("deux fois le meme nom refuse, majuscules comprises",
             erreurs(("Amis", "1"), ("amis", "2")))
    verifier("une liste correcte passe", not erreurs(("Amis", "1"), ("Famille", "&")))
    verifier("une touche libre est proposee",
             dossiers_tri.touche_libre([{"nom": "A", "touche": "1"}]) == "2")
    verifier("un dossier de tri ne peut pas prendre le nom d'une copie",
             dossiers_tri.erreurs_avec_les_copies([{"nom": "copie", "touche": "1",
                                                    "origine": "A garder"}], ["Copie"]))

    # Fichier de suivi abime : refuse proprement, ou complete s'il est seulement ancien.
    dossier = tempfile.mkdtemp(dir=DOSSIER_ESSAI)
    suivi = Suivi.creer(dossier, "Essai", [{"nom": "A", "touche": "1"}])
    suivi.donnees["rangements"] = []
    suivi.enregistrer()
    try:
        Suivi.charger(dossier)
        refuse = False
    except ValueError:
        refuse = True
    verifier("un suivi abime est refuse avec un message clair", refuse)
    suivi.donnees["rangements"] = {}
    suivi.donnees["tri"] = {}
    suivi.enregistrer()
    verifier("un suivi ancien, incomplet, est complete",
             Suivi.charger(dossier).historique == [])


# ----------------------------------------------------------------------
# 10. Formats de nom des photos
# ----------------------------------------------------------------------

def dossier_de_photos(photos):
    """Dossier neuf contenant les photos donnees : {nom: (couleur, date de prise de vue)}."""
    dossier = tempfile.mkdtemp(dir=DOSSIER_ESSAI)
    for nom, (couleur, date) in photos.items():
        photo(os.path.join(dossier, nom), couleur, date)
    return dossier


def preparer_au_format(dossier, nom_format, nom_evenement="Fete"):
    suivi = Suivi.creer(dossier, nom_evenement, [{"nom": "A garder", "touche": "1"}],
                        renommage=nom_format)
    suivi.enregistrer()
    preparation.preparer(suivi)
    return suivi


def test_formats_de_nom():
    print("\n10. Formats de nom des photos")
    photos = {"IMG_3.jpg": ((30, 0, 0), "2026:08:24 14:03:31"),
              "IMG_1.jpg": ((10, 0, 0), "2026:08:24 14:03:27"),
              "IMG_2.jpg": ((20, 0, 0), "2026:08:24 14:03:27"),     # meme seconde que IMG_1
              "IMG_4.jpg": ((40, 0, 0), "2026:08:25 09:00:00")}

    # Date, heure et code : le format par defaut.
    verifier("le format par defaut est « date, heure et code »",
             Suivi.creer(DOSSIER_ESSAI, "x", []).renommage == renommage.FORMAT_DATE_CODE)
    dossier = dossier_de_photos(photos)
    with open(os.path.join(dossier, "IMG_3.CR2"), "wb") as fichier:
        fichier.write(b"RAW de la photo 3")
    suivi = preparer_au_format(dossier, renommage.FORMAT_DATE_CODE)
    noms = suivi.tri["photos"]
    verifier("date et code : quatre photos, dans l'ordre des prises de vue",
             [nom[:19] for nom in noms] == ["2026-08-24_14-03-27", "2026-08-24_14-03-27",
                                            "2026-08-24_14-03-31", "2026-08-25_09-00-00"],
             noms)
    verifier("date et code : classer par nom donne l'ordre chronologique",
             sorted(noms) == noms and sorted(noms, key=str.lower) == noms)
    verifier("date et code : chaque nom finit par un code de quatre caracteres",
             all(len(os.path.splitext(nom)[0].rsplit("_", 1)[1]) == 4 for nom in noms), noms)
    verifier("deux photos de la meme seconde sont numerotees dans leur ordre",
             noms[0][19:22] == "-1_" and noms[1][19:22] == "-2_", noms[:2])
    couleurs = [Image.open(os.path.join(dossier, nom)).convert("RGB").getpixel((5, 5))[0]
                for nom in noms]
    verifier("chaque photo a recu le nom de sa propre date",
             [round(couleur, -1) for couleur in couleurs] == [10, 20, 30, 40], couleurs)
    raw = contenu(os.path.join(dossier, "RAW"))
    verifier("le RAW porte le meme nom que sa photo",
             len(raw) == 1 and os.path.splitext(raw[0])[0] == os.path.splitext(noms[2])[0],
             raw)

    # Les memes photos preparees sur un autre ordinateur recoivent les memes noms ;
    # une autre photo prise dans la meme seconde en recoit un different.
    ailleurs = preparer_au_format(dossier_de_photos(photos), renommage.FORMAT_DATE_CODE)
    verifier("une meme photo recoit le meme nom sur deux ordinateurs",
             ailleurs.tri["photos"] == noms, ailleurs.tri["photos"])
    autre = preparer_au_format(dossier_de_photos(
        {"DSC_9.jpg": ((200, 200, 0), "2026:08:25 09:00:00")}), renommage.FORMAT_DATE_CODE)
    verifier("deux appareils, meme seconde : deux noms differents",
             autre.tri["photos"][0] != noms[3]
             and autre.tri["photos"][0][:19] == noms[3][:19], autre.tri["photos"])

    # Date et heure seules.
    suivi = preparer_au_format(dossier_de_photos(photos), renommage.FORMAT_DATE)
    verifier("date seule : noms sans code, rafale numerotee",
             suivi.tri["photos"] == ["2026-08-24_14-03-27-1.jpg", "2026-08-24_14-03-27-2.jpg",
                                     "2026-08-24_14-03-31.jpg", "2026-08-25_09-00-00.jpg"],
             suivi.tri["photos"])

    # Nom de l'evenement et numero.
    suivi = preparer_au_format(dossier_de_photos(photos), renommage.FORMAT_EVENEMENT)
    verifier("nom de l'evenement : numeros completes par des zeros",
             suivi.tri["photos"] == ["Fete_0001.jpg", "Fete_0002.jpg", "Fete_0003.jpg",
                                     "Fete_0004.jpg"], suivi.tri["photos"])

    # Aucun renommage : les noms d'origine restent, classes comme dans un gestionnaire.
    photos_longues = dict(photos)
    photos_longues["IMG_10.jpg"] = ((50, 0, 0), "2026:08:26 09:00:00")
    dossier = dossier_de_photos(photos_longues)
    with open(os.path.join(dossier, "film.mp4"), "wb") as fichier:
        fichier.write(b"video")
    suivi = preparer_au_format(dossier, renommage.FORMAT_AUCUN)
    verifier("ne pas renommer : les photos gardent leur nom",
             suivi.tri["photos"] == ["IMG_1.jpg", "IMG_2.jpg", "IMG_3.jpg", "IMG_4.jpg",
                                     "IMG_10.jpg"], suivi.tri["photos"])
    verifier("ne pas renommer : la video est quand meme mise de cote",
             contenu(os.path.join(dossier, "Videos")) == ["film.mp4"])

    # Un renommage qui echoue en route rend leur nom a tous les fichiers.
    dossier = dossier_de_photos(photos)
    avant = contenu(dossier)
    vrai_deplacer = renommage.deplacer_fichier
    appels = {"nombre": 0}

    def echouer_au_sixieme(source, destination):
        appels["nombre"] += 1
        if appels["nombre"] == 6:
            raise PermissionError(13, "fichier utilise par un autre programme")
        vrai_deplacer(source, destination)
    renommage.deplacer_fichier = echouer_au_sixieme
    try:
        preparation.renommer_photos(dossier, avant, None, renommage.FORMAT_DATE, "Fete")
        echec = False
    except OSError:
        echec = True
    finally:
        renommage.deplacer_fichier = vrai_deplacer
    verifier("renommage interrompu : tous les fichiers reprennent leur nom",
             echec and contenu(dossier) == avant, contenu(dossier))

    verifier("classement : 2 avant 10, et les dates dans l'ordre",
             sorted(["10.jpg", "2.jpg", "IMG_10.jpg", "IMG_9.jpg"],
                    key=renommage.cle_de_classement)
             == ["2.jpg", "10.jpg", "IMG_9.jpg", "IMG_10.jpg"])


def test_renommage_d_un_evenement(racine):
    print("\n10 bis. Renommer les photos d'un evenement existant")
    suivi, _ = nouvel_evenement()
    dossier = suivi.dossier_evenement
    garder = os.path.join(dossier, "A garder")
    fenetre = ouvrir_le_tri(racine, suivi)
    try:
        # Photo 1 barree puis rangee, photo 2 rangee telle quelle.
        fenetre.outil.bandeaux_manuels.append(Bandeau(160, 120, 120, 40, 0))
        presser(racine, fenetre, Touche("1", "1"))
        presser(racine, fenetre, Touche("1", "1"))
    finally:
        fenetre.quitter()
        attendre(racine, 0.3)
    verifier("avant : photos numerotees, version sans barre gardee",
             contenu(garder) == ["1.jpg", "2.jpg"]
             and contenu(os.path.join(garder, "Sans-barre")) == ["1.jpg"])

    nombre = renommage_evenement.renommer_evenement(suivi, renommage.FORMAT_DATE_CODE)
    rangees = contenu(garder)
    verifier("toutes les photos de l'evenement sont renommees",
             nombre == 8 and all(nom.startswith("2026-05-01_10-00-0") for nom in rangees)
             and all(nom.startswith("2026-05-01_10-00-0") for nom in photos_du_dossier(dossier)),
             (nombre, rangees, contenu(dossier)))
    verifier("la version sans barre porte le meme nouveau nom que sa photo",
             contenu(os.path.join(garder, "Sans-barre")) == rangees[:1],
             contenu(os.path.join(garder, "Sans-barre")))
    verifier("la video mise de cote est renommee aussi",
             not contenu(os.path.join(dossier, "Videos"))[0].startswith("7"),
             contenu(os.path.join(dossier, "Videos")))
    verifier("le suivi suit les nouveaux noms",
             sorted(suivi.rangements) == rangees
             and sorted(action["fichier"] for action in suivi.historique) == rangees
             and Suivi.charger(dossier).renommage == renommage.FORMAT_DATE_CODE)

    # L'annulation fonctionne toujours apres le renommage, en revue.
    preparer_revue(suivi, "A garder")
    fenetre = rangement.FenetreRangement(racine, suivi, suivi.revue, "A garder", "essai")
    fenetre.fenetre.attributes("-alpha", 0.0)
    attendre(racine, 0.5)
    try:
        presser(racine, fenetre, Touche("BackSpace"))
        verifier("apres renommage, Retour arriere ramene la photo, sans ses bandeaux",
                 rangees[0] in contenu(dossier)
                 and sum(pixel_sur_le_disque(os.path.join(dossier, rangees[0]))) > 60
                 and not os.path.isdir(os.path.join(garder, "Sans-barre")),
                 contenu(dossier))
    finally:
        fenetre.quitter()
        attendre(racine, 0.3)

    # Revenir aux numeros reste possible.
    renommage_evenement.renommer_evenement(suivi, renommage.FORMAT_NUMERO)
    verifier("retour au format numerote",
             photos_du_dossier(dossier) == ["1.jpg", "3.jpg", "4.jpg", "5.jpg", "6.jpg"]
             and contenu(garder) == ["2.jpg"], (photos_du_dossier(dossier), contenu(garder)))


# ----------------------------------------------------------------------
# 11. Annulation photo par photo, gardee d'une session a l'autre
# ----------------------------------------------------------------------

def test_annulation_par_photo(racine):
    print("\n11. Annulation photo par photo")
    suivi, _ = nouvel_evenement()
    dossier = suivi.dossier_evenement
    garder = os.path.join(dossier, "A garder")
    fenetre = ouvrir_le_tri(racine, suivi)
    try:
        for _ in range(3):
            presser(racine, fenetre, Touche("1", "1"))
        verifier("trois photos rangees", contenu(garder) == ["1.jpg", "2.jpg", "3.jpg"],
                 (contenu(garder), messages[-3:]))
        verifier("le rappel annonce ce que Retour arriere annulera",
                 "annuler le rangement de 3.jpg dans « A garder »"
                 in fenetre.etiquette_rappel.cget("text"),
                 fenetre.etiquette_rappel.cget("text").splitlines()[-1][:90])

        # Revenir sur la photo 1 avec la fleche, et annuler CE rangement-la.
        for _ in range(3):
            presser(racine, fenetre, Touche("Left"))
        verifier("revenu sur la photo 1, le rappel la designe",
                 "annuler le rangement de 1.jpg" in fenetre.etiquette_rappel.cget("text"))
        presser(racine, fenetre, Touche("BackSpace"))
        verifier("Retour arriere annule le rangement de la photo affichee, pas le dernier",
                 contenu(garder) == ["2.jpg", "3.jpg"] and "1.jpg" in contenu(dossier),
                 contenu(garder))
        verifier("les autres actions restent annulables",
                 [action["fichier"] for action in suivi.historique] == ["2.jpg", "3.jpg"])

        # Sans navigation, Retour arriere remonte les actions de la session.
        presser(racine, fenetre, Touche("1", "1"))            # range de nouveau la photo 1
        presser(racine, fenetre, Touche("BackSpace"))
        presser(racine, fenetre, Touche("BackSpace"))
        verifier("sans fleche, Retour arriere annule les dernieres actions, dans l'ordre",
                 contenu(garder) == ["2.jpg"], contenu(garder))

        # Photo 4 rognee, puis photo 3 rangee : la photo 4 s'affiche, et Retour
        # arriere doit ramener la photo 3, pas defaire le rognage de la 4.
        presser(racine, fenetre, Touche("Right"))             # de la photo 3 a la photo 4
        fenetre.commencer_rognage()
        fenetre.visionneuse.cadre = (0.0, 0.0, 160.0, 120.0)
        fenetre.rogner()
        attendre(racine, 0.6)
        presser(racine, fenetre, Touche("Left"))
        presser(racine, fenetre, Touche("1", "1"))
        presser(racine, fenetre, Touche("BackSpace"))
        with Image.open(os.path.join(dossier, "4.jpg")) as image:
            largeur = image.width
        verifier("apres un rangement, Retour arriere l'annule, sans toucher a la photo suivante",
                 "3.jpg" in contenu(dossier) and largeur == 160, (contenu(garder), largeur))
    finally:
        fenetre.quitter()
        attendre(racine, 0.3)

    # Nouvelle session : la photo 4, rognee, se retrouve intacte par Retour arriere.
    sauvegardes = suivi.chemin_dossier_temporaire()
    verifier("fermer la fenetre garde les copies intactes et l'historique",
             len(contenu(sauvegardes)) == 1
             and [a["action"] for a in Suivi.charger(dossier).historique]
             == ["deplacement", "rognage"], Suivi.charger(dossier).historique)
    suivi = Suivi.charger(dossier)
    fenetre = ouvrir_le_tri(racine, suivi)
    try:
        fenetre.position = fenetre.photos.index("4.jpg")
        fenetre.afficher_photo_courante()
        attendre(racine, 0.4)
        presser(racine, fenetre, Touche("BackSpace"))
        with Image.open(os.path.join(dossier, "4.jpg")) as image:
            largeur = image.width
        verifier("a la session suivante, le rognage d'une ancienne photo s'annule encore",
                 largeur == 320 and not os.path.isdir(sauvegardes) or
                 (largeur == 320 and not contenu(sauvegardes)), largeur)
    finally:
        fenetre.quitter()
        attendre(racine, 0.3)

    # Un suivi d'avant l'historique unique est repris sans rien perdre.
    donnees = Suivi.charger(dossier).donnees
    del donnees["historique"]
    donnees["tri"]["historique"] = [{"action": "deplacement", "fichier": "2.jpg",
                                     "depuis": None, "dossier": "A garder", "index": 1,
                                     "sauvegarde": None, "sans_barre": None}]
    ancien = Suivi(dossier, donnees)
    ancien.enregistrer()
    repris = Suivi.charger(dossier)
    verifier("l'historique d'un ancien suivi est repris",
             [action["fichier"] for action in repris.historique] == ["2.jpg"]
             and "historique" not in repris.tri)


# ----------------------------------------------------------------------
# 12 et 13. Statistiques, fin de la session
# ----------------------------------------------------------------------

def test_statistiques_et_fin(racine):
    print("\n12. Statistiques de la fenetre de tri")
    suivi, _ = nouvel_evenement()
    dossier = suivi.dossier_evenement
    garder = os.path.join(dossier, "A garder")
    fenetre = ouvrir_le_tri(racine, suivi)
    try:
        verifier("au depart : tout est a trier",
                 fenetre.etiquette_stats.cget("text").startswith("A trier : 6")
                 and "Rangees : 0 sur 6 (0 %)" in fenetre.etiquette_stats.cget("text"),
                 fenetre.etiquette_stats.cget("text"))
        presser(racine, fenetre, Touche("1", "1"))
        presser(racine, fenetre, Touche("2", "2"))
        fenetre.outil.bandeaux_manuels.append(Bandeau(160, 120, 120, 40, 0))
        presser(racine, fenetre, Touche("1", "1"))
        stats = fenetre.etiquette_stats.cget("text")
        verifier("apres trois rangements : le reste et le pourcentage suivent",
                 "A trier : 3" in stats and "Rangees : 3 sur 6 (50 %)" in stats
                 and "Cette session : 3" in stats and "3 action(s) annulable(s)" in stats,
                 stats)
        rappel = fenetre.etiquette_rappel.cget("text")
        verifier("chaque dossier affiche son nombre de photos",
                 "[1] A garder (2)" in rappel and "[2] Ratees (1)" in rappel,
                 rappel.splitlines()[0])
        presser(racine, fenetre, Touche("BackSpace"))
        verifier("une annulation remet les compteurs a jour",
                 "A trier : 4" in fenetre.etiquette_stats.cget("text")
                 and "[1] A garder (1)" in fenetre.etiquette_rappel.cget("text"),
                 fenetre.etiquette_stats.cget("text"))
        for _ in range(4):
            presser(racine, fenetre, Touche("1", "1"))
        verifier("le rythme est annonce apres quelques photos",
                 "Rythme :" in fenetre.etiquette_stats.cget("text"),
                 fenetre.etiquette_stats.cget("text"))
        # Photo 3 barree : sa copie intacte doit exister jusqu'a la fin de session.
        presser(racine, fenetre, Touche("Left"))
        fenetre.outil.bandeaux_manuels.append(Bandeau(160, 120, 120, 40, 0))
        presser(racine, fenetre, Touche("Return"))
    finally:
        fenetre.quitter()
        attendre(racine, 0.3)

    print("\n13. Fin de la session")
    # « Ratees » est videe, et ne contient plus qu'un fichier depose par macOS.
    deplacer_fichier(os.path.join(dossier, "Ratees", "2.jpg"), os.path.join(garder, "2.jpg"))
    with open(os.path.join(dossier, "Ratees", ".DS_Store"), "wb") as fichier:
        fichier.write(b"finder")
    bilan = fin_de_session.bilan(suivi)
    verifier("le bilan annonce ce qui sera definitif",
             bilan["annulables"] == len(suivi.historique) > 0 and bilan["octets"] > 0
             and bilan["dossiers_vides"] == ["Ratees"], bilan)
    supprimes, refuses = fin_de_session.terminer(suivi)
    verifier("terminer supprime le dossier vide, malgre le fichier du systeme",
             supprimes == ["Ratees"] and not refuses
             and not os.path.exists(os.path.join(dossier, "Ratees")))
    verifier("terminer garde les dossiers qui contiennent des photos",
             len(contenu(garder)) == 6 and os.path.isdir(os.path.join(dossier, "Videos")))
    verifier("terminer efface les copies intactes et vide l'historique",
             not os.path.exists(suivi.chemin_dossier_temporaire())
             and Suivi.charger(dossier).historique == [])
    verifier("les versions sans barre sont gardees",
             len(contenu(os.path.join(garder, "Sans-barre"))) == 1)
    verifier("le dossier supprime reste dans la liste de l'evenement",
             suivi.dossier_tri_pour_touche("2") == "Ratees")

    # Apres la fin de session : plus rien a annuler, et le dossier supprime
    # est recree des qu'on y range une photo.
    preparer_revue(suivi, "A garder")
    fenetre = rangement.FenetreRangement(racine, suivi, suivi.revue, "A garder", "essai")
    fenetre.fenetre.attributes("-alpha", 0.0)
    attendre(racine, 0.5)
    try:
        verifier("apres la fin de session, il n'y a plus rien a annuler",
                 "rien a annuler" in fenetre.etiquette_rappel.cget("text"))
        presser(racine, fenetre, Touche("BackSpace"))
        verifier("et Retour arriere ne touche a rien", len(contenu(garder)) == 6)
        presser(racine, fenetre, Touche("2", "2"))
        verifier("ranger dans un dossier supprime le recree",
                 len(contenu(os.path.join(dossier, "Ratees"))) == 1)
    finally:
        fenetre.quitter()
        attendre(racine, 0.3)


# ----------------------------------------------------------------------

def main():
    print("\nTests du rangement des photos")
    print("=" * 76)
    racine = tk.Tk()
    racine.withdraw()
    theme.appliquer(racine)
    try:
        test_preparation()
        test_dates()
        suivi = test_tri(racine)
        test_robustesse(racine)
        test_echecs(racine)
        test_chargeur()
        test_bandeaux()
        test_photos_revenues(suivi)
        test_gestion(suivi)
        test_regles()
        test_formats_de_nom()
        test_renommage_d_un_evenement(racine)
        test_annulation_par_photo(racine)
        test_statistiques_et_fin(racine)
    finally:
        racine.destroy()
        shutil.rmtree(DOSSIER_ESSAI, ignore_errors=True)

    echecs = [intitule for reussi, intitule in resultats if not reussi]
    print("\n" + "=" * 76)
    if echecs:
        print("%d test(s) sur %d echouent :" % (len(echecs), len(resultats)))
        for intitule in echecs:
            print("  - " + intitule)
        return 1
    print("Les %d tests passent." % len(resultats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
