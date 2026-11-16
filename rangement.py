"""
Fenetre unique du logiciel : tri, revue et censure des yeux (sections 8, 8 bis
et 9).

Les photos defilent une par une en grand, et une touche du clavier deplace la
photo affichee vers l'un des dossiers de tri. La touche N cree un nouveau
dossier de tri sans quitter la fenetre. Seul change le dossier d'ou viennent
les photos :

- a l'etape de tri, le dossier source, ou attendent les photos brutes ;
- en revue, l'un des dossiers de tri, que l'on repasse pour corriger un
  rangement, ou l'une des copies faites depuis le menu. Une copie n'a pas de
  touche de tri : on n'y fait que retoucher et censurer.

La censure n'est plus une etape a part : la touche Tab active le mode
« barrer », ou un clic sur une tete pose un bandeau sur ses yeux (censure.py).
Ce mode reste actif d'une photo a l'autre, et d'une session a l'autre, tant
qu'on ne rappuie pas sur Tab.

Retouches. La rotation (R) et les bandeaux restent provisoires a l'ecran. Ils
sont enregistres dans le fichier par Entree, qui passe ensuite a la photo
suivante, ou par une touche de tri, qui enregistre puis range. Espace et les
fleches les abandonnent. Le rognage (C), lui, s'enregistre des sa validation.

Les fleches gauche et droite font circuler d'une photo a l'autre sans rien
deplacer. On peut ainsi revenir sur une photo deja rangee : elle est montree
depuis le dossier ou elle se trouve maintenant, et une touche de tri la deplace
de ce dossier vers le nouveau.

Annulation (decision de l'utilisateur, 16 novembre 2026). Retour arriere annule
la derniere action ; mais si l'on est revenu sur une photo avec les fleches,
il annule ce qui a ete fait a CETTE photo, meme si ce n'est pas la derniere
modifiee (voir _action_a_annuler). Le rappel des touches dit toujours ce que
Retour arriere annulera. Tout reste annulable d'une session a l'autre, tant
que la session n'a pas ete declaree terminee depuis le menu.

Statistiques. Le bas de la fenetre dit en permanence combien de photos restent
a trier, combien sont rangees dans chaque dossier, et a quel rythme on avance
(statistiques.py).
"""

import filecmp
import gc
import os
import shutil
import tkinter as tk
from tkinter import messagebox

import preferences
import theme
import touches
from censure import OutilBandeaux
from dossiers import photos_du_dossier
from ecritures import EcrituresEnArrierePlan, signaler_les_echecs
from editeur_dossiers import demander_nouveau_dossier
from fichiers import deplacer_fichier, remplacer_fichier, supprimer_fichier
from images import (ChargeurAnticipe, copie_de_sauvegarde, est_modifiable,
                    extension_modifiable, fabriquer_apercu)
from polices import police
from remise_en_place import proposer_de_remettre_en_place
from retouches import (appliquer_retouches, chemin_sans_barre, deplacer_sans_barre,
                       effacer_si_vide, enregistrer_retouches, tourner_sans_barre)
from rognage import cadre_dans_le_sens_d_origine, rogner_fichier, rogner_image
from statistiques import Statistiques
from visages import DetecteurVisages, DetectionAnticipee
from visionneuse import Visionneuse

COULEUR_FOND = theme.FOND
COULEUR_BARRE = theme.SURFACE
COULEUR_TEXTE = theme.TEXTE
COULEUR_RAPPEL = theme.TEXTE_DOUX
COULEUR_SEPARATEUR = theme.SEPARATEUR
COULEUR_ATTENTION = theme.ATTENTION    # retouches pas encore enregistrees
COULEUR_MODE_ACTIF = theme.ALERTE      # pastille du mode barrer

RAPPEL_ROGNAGE = ("ROGNAGE  -  Tirez un bord ou un coin pour reduire la photo  |  "
                  "Glissez dans le cadre pour le deplacer  |  Entree = rogner  |  "
                  "Echap ou C = abandonner sans rien modifier")
RAPPEL_BARRER = ("BARRER  -  Clic sur une tete = bandeau  |  Clic sur un bandeau = le choisir  |  "
                 "Double-clic = le retirer  |  Glisser dans le vide = deplacer la vue")

# Delai, en millisecondes, avant de refabriquer les apercus apres un
# redimensionnement de la fenetre. Voir _zone_d_affichage_changee.
DELAI_APRES_REDIMENSIONNEMENT = 250

# Delai, en millisecondes, avant de regarder de nouveau si une photo (ou ses
# visages) qui n'etait pas encore prete l'est enfin.
DELAI_ATTENTE_CHARGEMENT = 15

# Ce que le rappel des touches dit de chaque genre d'action annulable.
NOMS_DES_ACTIONS = {"deplacement": "le rangement", "retouche": "les retouches",
                    "rognage": "le rognage"}


class FenetreRangement:
    """Fenetre ou l'on range, retouche et censure les photos."""

    def __init__(self, racine, suivi, etat, dossier_origine, titre):
        """
        etat            : la partie du fichier de suivi propre a cette etape
                          (suivi.tri ou suivi.revue) : liste des photos,
                          position et historique.
        dossier_origine : nom du dossier d'ou viennent les photos, ou None
                          pour le dossier source (etape de tri).
        """
        # Fait le menage des fenetres fermees avant de lancer les fils
        # d'arriere-plan. Une fenetre fermee (tri, revue, boite de saisie) ne
        # disparait pas tout de suite : ses objets se referencent les uns les
        # autres, et c'est le ramasse-miettes de Python qui les detruit, plus
        # tard, depuis le fil qui se trouve alors en train de travailler. Or
        # detruire une image ou une variable Tkinter passe par Tkinter, qui
        # n'obeit qu'au fil principal : le fil de chargement restait alors
        # bloque, la photo ouverte, tant que le fil principal etait occupe. Si
        # celui-ci etait justement en train de ranger cette photo, Windows
        # refusait de la deplacer, et elle restait dans le dossier source
        # (en double, avec l'ancien `shutil.move`). Collecte ici, sur le fil
        # principal, ce menage ne peut plus tomber sur un autre fil.
        gc.collect()

        self.suivi = suivi
        self.etat = etat
        self.photos = etat["photos"]
        # Position de chaque photo dans la liste, pour retrouver d'un coup
        # celle que designe une action de l'historique.
        self.index_des_photos = {nom: index for index, nom in enumerate(self.photos)}
        self.dossier_origine = dossier_origine
        # Les touches de tri ne servent qu'au dossier source et aux dossiers
        # de tri. Dans une copie, elles creeraient des doublons.
        self.touches_de_tri = (dossier_origine is None
                               or dossier_origine in suivi.noms_dossiers_tri)
        # Passe a True quand, au bout des photos, l'utilisateur demande a
        # repasser celles qui restent dans le dossier source (voir tri.lancer_tri).
        self.recommencer = False

        # Annulation : voir _action_a_annuler. Les actions faites dans cette
        # fenetre sont retenues a part, de la plus ancienne a la plus recente.
        self.actions_de_la_session = []
        # Vrai quand l'utilisateur est arrive sur la photo affichee de
        # lui-meme (ouverture de la fenetre, fleches), et non a la suite d'un
        # rangement ou d'une annulation.
        self.a_navigue = True

        # Statistiques affichees en bas de la fenetre (voir statistiques.py).
        self.stats = Statistiques(suivi, avec_rythme=dossier_origine is None)

        # Les apercus sont d'abord prepares a la taille de l'ecran, que la
        # fenetre ne peut pas depasser, puis a celle de la zone d'affichage des
        # qu'elle est connue (voir _zone_d_affichage_changee).
        dossier = self._chemin_du_dossier(dossier_origine)
        taille_ecran = (racine.winfo_screenwidth(), racine.winfo_screenheight())
        # Les photos ne sont pas forcement dans le dossier d'origine : elles ont
        # pu etre rangees ailleurs lors d'une session precedente. On les
        # localise donc des maintenant. Sans cela, le chargement anticipe lisait
        # des chemins perimes, echouait, et chaque photo deplacee devait ensuite
        # etre relue au moment de l'afficher, avec l'attente que cela suppose.
        # Le dossier d'origine est lu une seule fois : interroger le disque
        # photo par photo prenait 0,2 s pour 3 000 photos.
        dans_l_origine = set(photos_du_dossier(dossier))
        chemins = [os.path.join(dossier, nom) if nom in dans_l_origine
                   else self._localiser(nom)[1] or os.path.join(dossier, nom)
                   for nom in self.photos]
        self.ecritures = EcrituresEnArrierePlan()
        # Le chargeur attend la fin de l'enregistrement d'une photo avant de la
        # relire : sinon il en relirait l'ancienne version (voir images.py).
        self.chargeur = ChargeurAnticipe(chemins, taille_ecran,
                                         attendre_ecriture=self.ecritures.attendre)
        self.attente = None          # nouvel essai programme si la photo n'est pas chargee
        self.attente_visages = None  # idem pour la detection des visages
        self.visages_recus = False   # les visages de la photo affichee sont-ils connus ?
        # Action remise a plus tard, le temps qu'un enregistrement en cours se
        # termine (voir _attendre_les_enregistrements).
        self.attente_enregistrement = None
        self.surveillance = None     # verification reguliere des enregistrements
        # Vrai apres un enregistrement du suivi rate : on ne previent qu'une
        # fois (voir _noter_avancement).
        self.avancement_en_echec = False

        # Redimensionnement de la fenetre : voir _zone_d_affichage_changee.
        self.attente_apercus = None
        self.derniere_taille_affichage = None
        # Passe a True des le debut de la fermeture. La fermeture laisse
        # Tkinter traiter ses evenements en attente (update_idletasks), ce qui
        # peut encore signaler un changement de taille : sans ce temoin, on
        # programmerait alors un appel sur une fenetre sur le point d'etre
        # detruite.
        self.en_fermeture = False

        # Detection des visages : lancee seulement en mode barrer, ou elle
        # sert. Le modele est charge une fois, la premiere fois qu'on l'active.
        self.detecteur = None
        self.detection = None

        self.fenetre = tk.Toplevel(racine)
        try:
            self.fenetre.title(titre)
            # La fenetre reprend la taille qu'on lui avait laissee ; la premiere
            # fois, elle s'ouvre agrandie : une photo se juge mieux en grand.
            fenetre_retenue = preferences.fenetre_de_tri()
            self.fenetre.geometry(fenetre_retenue["geometrie"])
            if fenetre_retenue["agrandie"]:
                theme.agrandir(self.fenetre)
            self.fenetre.configure(bg=COULEUR_FOND)
            self.fenetre.protocol("WM_DELETE_WINDOW", self.quitter)

            self._construire()
            self.outil = OutilBandeaux(self.visionneuse, self._mettre_a_jour_barre)
            if suivi.mode_barrer and not self._activer_barrage():
                suivi.mode_barrer = False

            self.fenetre.bind("<Key>", self._touche)
            self.fenetre.focus_force()
            self.fenetre.after(60, self.afficher_photo_courante)
            self.surveillance = self.fenetre.after(300, self._surveiller_ecritures)
        except Exception:
            # Une fenetre a moitie construite ne doit ni rester a l'ecran (sa
            # croix de fermeture echouait), ni laisser ses fils tourner.
            if self.detection is not None:
                self.detection.arreter()
            self.chargeur.arreter()
            self.ecritures.arreter()
            self.fenetre.destroy()
            raise

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    def _construire(self):
        # La barre du bas est placee en premier : si la fenetre est reduite,
        # c'est la photo qui retrecit, et le rappel des touches reste visible.
        barre = tk.Frame(self.fenetre, bg=COULEUR_BARRE)
        barre.pack(side="bottom", fill="x")

        # Un filet d'un pixel detache la barre de la photo. Sans lui, une photo
        # sombre se confond avec la barre et les textes semblent flotter sur
        # l'image.
        tk.Frame(barre, bg=COULEUR_SEPARATEUR, height=1).pack(side="top", fill="x")

        self.visionneuse = Visionneuse(self.fenetre,
                                       au_changement_du_cadre=self._mettre_a_jour_barre)
        self.visionneuse.canvas.pack(side="top", fill="both", expand=True)
        # Les apercus sont prepares exactement a la taille de la zone
        # d'affichage : une photo s'y affiche alors sans etre redimensionnee.
        self.visionneuse.canvas.bind("<Configure>", self._zone_d_affichage_changee, add="+")

        ligne = tk.Frame(barre, bg=COULEUR_BARRE)
        ligne.pack(side="top", fill="x", padx=14, pady=(10, 0))
        self.etiquette_mode = tk.Label(ligne, text="", bg=COULEUR_BARRE,
                                       font=police(10, gras=True))
        self.etiquette_mode.pack(side="right")
        self.etiquette_avancement = tk.Label(ligne, text="", bg=COULEUR_BARRE,
                                             fg=COULEUR_TEXTE, font=police(11, gras=True),
                                             anchor="w")
        self.etiquette_avancement.pack(side="left")
        self.etiquette_retouches = tk.Label(ligne, text="", bg=COULEUR_BARRE,
                                            fg=COULEUR_ATTENTION, font=police(10),
                                            anchor="w")
        self.etiquette_retouches.pack(side="left")

        # Statistiques en temps reel : ce qui reste, ce qui est range, le rythme.
        self.etiquette_stats = tk.Label(barre, text="", bg=COULEUR_BARRE,
                                        fg=COULEUR_TEXTE, font=police(10),
                                        anchor="w", justify="left")
        self.etiquette_stats.pack(side="top", fill="x", padx=14, pady=(6, 0))

        self.etiquette_rappel = tk.Label(barre, text="", bg=COULEUR_BARRE,
                                         fg=COULEUR_RAPPEL, font=police(9),
                                         anchor="w", justify="left")
        self.etiquette_rappel.pack(side="top", fill="x", padx=14, pady=(6, 10))
        # Avec beaucoup de dossiers, la ligne des touches de tri peut depasser
        # la largeur de la fenetre : elle passe alors a la ligne au lieu d'etre
        # coupee.
        barre.bind("<Configure>", self._largeur_de_la_barre_changee)

    def _largeur_de_la_barre_changee(self, evenement):
        largeur = max(evenement.width - 28, 100)
        self.etiquette_rappel.config(wraplength=largeur)
        self.etiquette_stats.config(wraplength=largeur)

    def _texte_des_touches(self):
        """Rappel des touches, refait a chaque fois : la touche N ajoute des dossiers."""
        touches_de_tri = ""
        if self.touches_de_tri:
            # Les touches de rangement sont mises sur leur propre ligne : ce
            # sont celles que l'on cherche des yeux a chaque photo, et elles se
            # perdaient au milieu d'une seule longue ligne de rappels.
            # Chaque dossier est suivi du nombre de photos qu'il contient.
            touches_de_tri = "   ".join(
                "[%s] %s (%d)" % (dossier["touche"], dossier["nom"],
                                  self.stats.nombre(dossier["nom"]))
                for dossier in self.suivi.dossiers_tri)
            if not self.suivi.dossier_tri_pour_touche("n"):
                touches_de_tri += "      [N] nouveau dossier"
            touches_de_tri += "\n"
        return (touches_de_tri
                + "[Entree] enregistrer et suivante   [Espace] [→] suivante   "
                  "[←] precedente   [Retour arriere] %s   [R] pivoter   "
                  "[C] rogner   [Tab] mode barrer   [Echap] quitter"
                % self._texte_de_l_annulation())

    def _texte_de_l_annulation(self):
        """Dit ce que Retour arriere annulera : « annuler le rognage de 12.jpg »."""
        action = self._action_a_annuler()
        if action is None:
            return "rien a annuler"
        texte = "annuler %s de %s" % (NOMS_DES_ACTIONS.get(action.get("action"), "l'action"),
                                      action["fichier"])
        if action.get("action") == "deplacement":
            texte += " dans « %s »" % action["dossier"]
        return texte

    def _zone_d_affichage_changee(self, evenement):
        """La zone d'affichage a change de taille : les apercus seront refaits.

        Pas tout de suite, toutefois. Tkinter envoie un evenement par pixel
        parcouru pendant qu'on redimensionne la fenetre a la souris, et chacun
        aurait condamne les apercus de toutes les photos en memoire : le fil
        d'arriere-plan passait son temps a refaire des apercus aussitot
        perimes. On attend donc que la fenetre ait cesse de bouger.
        """
        if evenement.width < 10 or evenement.height < 10 or self.en_fermeture:
            return
        self.derniere_taille_affichage = (evenement.width, evenement.height)
        if self.attente_apercus is not None:
            self.fenetre.after_cancel(self.attente_apercus)
        self.attente_apercus = self.fenetre.after(DELAI_APRES_REDIMENSIONNEMENT,
                                                  self._refaire_les_apercus)

    def _refaire_les_apercus(self):
        """Demande les apercus a la nouvelle taille, puis reprend celui de la photo affichee."""
        self.attente_apercus = None
        if self.derniere_taille_affichage is None:
            return
        self.chargeur.changer_taille_apercu(self.derniere_taille_affichage)
        self._reprendre_l_apercu_courant()

    def _reprendre_l_apercu_courant(self):
        """Donne a la visionneuse l'apercu refait, des qu'il est pret.

        Sans cela, la photo affichee garderait son apercu a l'ancienne taille,
        que la visionneuse doit alors redimensionner a chaque dessin : elle
        apparaissait moins nette que les photos suivantes, et pour toujours.

        On ne passe pas par `montrer`, qui repart de zero : cela abandonnerait
        la rotation en attente, le zoom et le cadre de rognage en cours, juste
        parce que l'utilisateur a redimensionne sa fenetre.
        """
        self.attente_apercus = None
        if self.visionneuse.image is None or self.position >= len(self.photos):
            return
        if not self.chargeur.est_prete(self.position):
            self.attente_apercus = self.fenetre.after(DELAI_ATTENTE_CHARGEMENT,
                                                      self._reprendre_l_apercu_courant)
            return
        _, apercu = self.chargeur.photo(self.position)
        if apercu is not None:
            self.visionneuse.remplacer_apercu(apercu)

    def _mettre_a_jour_rappel(self):
        if self.visionneuse.en_rognage:
            texte = RAPPEL_ROGNAGE
        elif self.suivi.mode_barrer:
            texte = RAPPEL_BARRER + "\n" + self._texte_des_touches()
        else:
            texte = self._texte_des_touches()
        self.etiquette_rappel.config(text=texte)
        self.etiquette_stats.config(text=self.stats.texte())

    def _mettre_a_jour_barre(self):
        """Pastille du mode barrer, et retouches en attente d'enregistrement."""
        if self.visionneuse.en_rognage:
            self.etiquette_mode.config(text="●  ROGNAGE  (C)", fg=COULEUR_MODE_ACTIF)
        elif self.suivi.mode_barrer:
            texte = "●  MODE BARRER  (Tab)"
            if self.visionneuse.image is not None:
                if self.visages_recus:
                    texte += "   -   %d visage(s)" % len(self.outil.visages)
                else:
                    texte += "   -   detection..."
            self.etiquette_mode.config(text=texte, fg=COULEUR_MODE_ACTIF)
        else:
            self.etiquette_mode.config(text="Mode barrer : non  (Tab)", fg=COULEUR_RAPPEL)

        # Pendant le rognage, la taille du cadre remplace la liste des
        # retouches : c'est la seule chose utile a savoir a ce moment-la, et on
        # la voit changer pendant qu'on tire les bords.
        if self.visionneuse.en_rognage:
            taille = self.visionneuse.taille_du_cadre()
            if taille is None:
                texte = "   -   photo entiere : tirez un bord pour la reduire"
            else:
                texte = "   -   cadre : %d x %d pixels (Entree)" % taille
            self.etiquette_retouches.config(text=texte)
            return

        morceaux = []
        if self.visionneuse.image is not None and self.visionneuse.rotation:
            morceaux.append("rotation %d°" % self.visionneuse.rotation)
        nombre_bandeaux = len(self.outil.bandeaux())
        if nombre_bandeaux:
            morceaux.append("%d bandeau(x)" % nombre_bandeaux)
        texte = ""
        if morceaux:
            texte = "   -   A enregistrer : %s (Entree)" % ", ".join(morceaux)
        self.etiquette_retouches.config(text=texte)

    # ------------------------------------------------------------------
    # Ou se trouve chaque photo
    # ------------------------------------------------------------------

    @property
    def position(self):
        return self.etat["position"]

    @position.setter
    def position(self, valeur):
        self.etat["position"] = valeur

    def _chemin_du_dossier(self, nom_dossier):
        """Chemin d'un dossier de l'evenement ; None designe le dossier source."""
        if nom_dossier is None:
            return self.suivi.dossier_source
        return self.suivi.chemin_dossier(nom_dossier)

    def _localiser(self, nom_fichier):
        """Trouve le dossier ou se trouve la photo en ce moment.

        Une photo n'est pas forcement la ou elle etait au lancement : elle a pu
        etre rangee, ici ou lors d'une session precedente. On la cherche d'abord
        dans le dossier d'origine, puis dans les dossiers de tri. Les photos
        etant numerotees une fois pour toutes (1, 2, 3...), un meme nom ne
        designe qu'une seule photo dans tout l'evenement.

        Exception : une copie contient les memes noms que les dossiers de tri,
        et ses photos n'en sortent jamais. On ne cherche donc que dans la copie.

        Renvoie (nom du dossier, chemin complet). Le nom vaut None pour le
        dossier source ; le chemin vaut None si la photo est introuvable.
        """
        candidats = [self.dossier_origine]
        if self.touches_de_tri:
            candidats += [nom for nom in self.suivi.noms_dossiers_tri
                          if nom != self.dossier_origine]
            # En revue, une photo peut aussi etre revenue dans le dossier
            # source (synchronisation qui defait un rangement) : elle y est
            # trouvee, au lieu d'etre annoncee « introuvable ».
            if self.dossier_origine is not None:
                candidats.append(None)
        for nom_dossier in candidats:
            chemin = os.path.join(self._chemin_du_dossier(nom_dossier), nom_fichier)
            if os.path.isfile(chemin):
                return nom_dossier, chemin
        return None, None

    # ------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------

    def afficher_photo_courante(self):
        """Affiche la photo a la position courante, la ou elle se trouve.

        Les retouches provisoires de la photo precedente sont abandonnees :
        seuls Entree et les touches de tri les enregistrent.
        """
        self._annuler_attente()
        self.visages_recus = False
        self.outil.vider()
        if self.position >= len(self.photos):
            self._afficher_fin()
            return

        nom_fichier = self.photos[self.position]
        dossier_actuel, chemin = self._localiser(nom_fichier)

        texte = "Photo %d sur %d   -   %s" % (self.position + 1, len(self.photos), nom_fichier)
        if chemin is not None and dossier_actuel != self.dossier_origine:
            texte += "   -   actuellement dans « %s »" % (dossier_actuel or "dossier source")
        if not extension_modifiable(nom_fichier):
            # Dit des maintenant que cette photo ne se retouche pas, plutot que
            # de le decouvrir apres avoir pose des bandeaux pour rien. (Seule
            # l'extension compte ici : voir images.extension_modifiable.)
            texte += "   -   format non modifiable : tri seulement"
        self.etiquette_avancement.config(text=texte)
        self._mettre_a_jour_rappel()

        if self.detection is not None:
            self.detection.avancer(self.position)
        if chemin is None:
            self.chargeur.avancer(self.position)
            self.visionneuse.montrer(None, None, "Photo introuvable : %s" % nom_fichier)
            self._mettre_a_jour_barre()
            return

        self.chargeur.changer_chemin(self.position, chemin)
        self.chargeur.avancer(self.position)
        self._montrer_des_que_prete()

    def _montrer_des_que_prete(self, deja_en_attente=False):
        """Montre la photo courante si elle est chargee, sinon reessaie un peu plus tard.

        Les photos sont lues en arriere-plan (voir images.py). Si l'utilisateur
        va plus vite que cette lecture, la photo n'est pas lue ici, ce qui
        figerait la fenetre : on affiche « Chargement... » et on revient voir
        quelques millisecondes plus tard. La fenetre reste ainsi toujours
        reactive.
        """
        self.attente = None
        if not self.chargeur.est_prete(self.position):
            if not deja_en_attente:
                self.visionneuse.afficher_texte("Chargement...")
            self.attente = self.fenetre.after(DELAI_ATTENTE_CHARGEMENT,
                                              self._montrer_des_que_prete, True)
            return

        image, apercu = self.chargeur.photo(self.position)
        self.visionneuse.montrer(image, apercu,
                                 "Photo illisible : %s" % self.photos[self.position])
        self._mettre_a_jour_barre()
        if self.detection is not None and image is not None:
            self._donner_les_visages_des_que_prets(self.position)

    def _donner_les_visages_des_que_prets(self, index):
        """Transmet a l'outil les visages detectes sur la photo, des qu'ils sont prets.

        Meme principe que pour la photo : la detection se fait en arriere-plan,
        et la fenetre ne l'attend jamais. La photo s'affiche sans attendre ses
        visages ; ceux-ci arrivent en general dans la foulee, car ils ont ete
        calcules a l'avance.
        """
        self.attente_visages = None
        if self.detection is None or index != self.position:
            return
        if not self.detection.est_prete(index):
            self.attente_visages = self.fenetre.after(
                DELAI_ATTENTE_CHARGEMENT, self._donner_les_visages_des_que_prets, index)
            return
        self.outil.recevoir_visages(self.detection.visages(index))
        self.visages_recus = True
        self._mettre_a_jour_barre()

    def _annuler_attente(self):
        if self.attente is not None:
            self.fenetre.after_cancel(self.attente)
            self.attente = None
        if self.attente_visages is not None:
            self.fenetre.after_cancel(self.attente_visages)
            self.attente_visages = None

    def _annuler_attente_apercus(self):
        """A appeler avant de fermer : sans cela, Tkinter rappellerait une
        methode de cette fenetre alors qu'elle n'existe plus."""
        if self.attente_apercus is not None:
            self.fenetre.after_cancel(self.attente_apercus)
            self.attente_apercus = None

    def _afficher_fin(self):
        """Ecran de fin : au tri, dit combien de photos restent dans le dossier source.

        Il en reste quand certaines ont ete passees (Espace, fleche, Entree),
        ramenees par une annulation, ou remises la par un service de
        synchronisation. Entree permet de les repasser aussitot, sans revenir
        au menu : sans ce decompte, on pouvait croire tout trie alors que des
        photos attendaient encore.
        """
        self.etiquette_avancement.config(text="Toutes les photos ont ete parcourues")
        # Les compteurs sont relus sur le disque : c'est le moment du bilan.
        self.stats.compter()
        self._mettre_a_jour_rappel()
        restantes = self._photos_restantes()
        if restantes:
            texte = ("Toutes les photos ont ete parcourues.\n"
                     "Il en reste %d dans le dossier source, pas encore rangee(s).\n\n"
                     "Entree : les repasser maintenant\n"
                     "Fleche gauche : revenir en arriere      Echap : revenir au menu"
                     % restantes)
        elif self.dossier_origine is None:
            texte = ("Toutes les photos sont rangees : le dossier source est vide.\n\n"
                     "Fleche gauche : revenir en arriere      Echap : revenir au menu\n\n"
                     "Tout reste annulable. Quand vous aurez fini, « Terminer la session » "
                     "dans le menu\nrend le tri definitif et supprime les dossiers vides.")
        else:
            texte = ("Toutes les photos du dossier ont ete revues.\n\n"
                     "Fleche gauche : revenir en arriere      Echap : revenir au menu")
        self.visionneuse.afficher_texte(texte)
        self._mettre_a_jour_barre()
        self.etat["terminee"] = True
        self._noter_avancement()

    def _photos_restantes(self):
        """Nombre de photos encore a la racine du dossier source (tri seulement, sinon 0)."""
        if self.dossier_origine is not None:
            return 0
        return len(photos_du_dossier(self.suivi.dossier_source))

    def _repasser_les_restantes(self):
        """Ferme la fenetre pour en rouvrir une sur les seules photos restantes.

        Les photos revenues dans le dossier source apres avoir ete rangees
        sont d'abord signalees, avec la proposition de les remettre en place
        (voir remise_en_place.py). La nouvelle fenetre est ouverte par
        tri.lancer_tri, qui refait la liste a partir du dossier source.
        """
        if self.ecritures.en_cours():
            self._attendre_les_enregistrements(self._repasser_les_restantes)
            return
        proposer_de_remettre_en_place(self.fenetre, self.suivi)
        self.recommencer = True
        self.quitter()

    # ------------------------------------------------------------------
    # Mode barrer
    # ------------------------------------------------------------------

    def basculer_barrage(self):
        """Active ou desactive le mode barrer. Le choix est retenu dans le suivi."""
        if self.visionneuse.en_rognage:
            return
        if self.suivi.mode_barrer:
            self._desactiver_barrage()
            self.suivi.mode_barrer = False
        elif self._activer_barrage():
            self.suivi.mode_barrer = True
            if self.visionneuse.image is not None and self.position < len(self.photos):
                self.detection.avancer(self.position)
                self._donner_les_visages_des_que_prets(self.position)
        self._mettre_a_jour_rappel()
        self._mettre_a_jour_barre()
        self._noter_avancement()

    def _activer_barrage(self):
        """Lance la detection des visages et confie les clics a l'outil bandeaux.

        Renvoie False si la detection ne peut pas demarrer (modele absent).
        """
        try:
            if self.detecteur is None:
                self.detecteur = DetecteurVisages()
            self.detection = DetectionAnticipee(self.detecteur, self.chargeur,
                                                len(self.photos))
            # Les visages de la photo affichee restent a detecter : sans cette
            # remise a zero, desactiver puis reactiver le mode barrer faisait
            # annoncer « 0 visage(s) » au lieu de « detection... », les visages
            # ayant ete oublies mais le temoin etant reste vrai.
            self.visages_recus = False
        except Exception as erreur:
            messagebox.showerror("Mode barrer indisponible",
                                 "La detection des visages n'a pas pu demarrer :\n%s"
                                 % erreur, parent=self.fenetre)
            return False
        self.detection.avancer(min(self.position, len(self.photos) - 1))
        self.visionneuse.outil = self.outil
        return True

    def _desactiver_barrage(self):
        """Arrete la detection ; les bandeaux non enregistres sont abandonnes."""
        if self.attente_visages is not None:
            self.fenetre.after_cancel(self.attente_visages)
            self.attente_visages = None
        self.outil.vider()
        self.visionneuse.outil = None
        self.visionneuse.demander_dessin()
        if self.detection is not None:
            self.detection.arreter()
            self.detection = None

    def _oublier_les_visages(self, index):
        """La photo a change : ses visages devront etre detectes de nouveau."""
        if self.detection is not None:
            self.detection.oublier(index)

    # ------------------------------------------------------------------
    # Clavier
    # ------------------------------------------------------------------

    def _touche(self, evenement):
        touche = evenement.keysym

        # Fenetre en train de se fermer, ou action en attente de la fin d'un
        # enregistrement : les touches sont ignorees, sans quoi elles
        # s'appliqueraient a une photo qui n'est pas encore celle qu'on attend.
        if self.en_fermeture or self.attente_enregistrement is not None:
            return "break"

        # Pendant le rognage, seules trois touches comptent : rien d'autre ne
        # doit deplacer ou changer la photo tant que le cadre est a l'ecran.
        if self.visionneuse.en_rognage:
            if touche in ("Return", "KP_Enter"):
                self.rogner()
            elif touche == "Escape" or touche.lower() == "c":
                self.abandonner_rognage()
            return "break"

        if touche == "Escape":
            self.quitter()
        elif touche == "Tab":
            self.basculer_barrage()
        elif touche in ("Return", "KP_Enter"):
            if self.position >= len(self.photos) and self._photos_restantes():
                self._repasser_les_restantes()
            else:
                self.valider()
        # Les touches du pave numerique portent un autre nom quand le verrouillage
        # numerique est desactive : « KP_Right » au lieu de « Right ».
        elif touche in ("space", "Right", "KP_Right"):
            self.a_navigue = True
            self.suivante()
        elif touche in ("Left", "KP_Left"):
            self.a_navigue = True
            self.precedente()
        elif touche == "BackSpace":
            self.annuler()
        elif touche.lower() == "r":
            self.visionneuse.pivoter()
            self._mettre_a_jour_barre()
        elif touche.lower() == "c":
            self.commencer_rognage()
        elif (touche.lower() == "n" and self.touches_de_tri
              and not self.suivi.dossier_tri_pour_touche("n")):
            # Un evenement cree avant l'arrivee de cette touche peut avoir un
            # dossier range par N : la touche continue alors de ranger.
            self.creer_dossier()
        elif self.touches_de_tri:
            # Le caractere exact d'abord, puis le chiffre de la meme touche sur
            # un clavier AZERTY (voir touches.py).
            for caractere in touches.caracteres_de_la_touche(evenement):
                nom_dossier = self.suivi.dossier_tri_pour_touche(caractere)
                if nom_dossier:
                    self.ranger(nom_dossier)
                    break
        # « break » empeche Tk de traiter la touche a sa facon : sans cela, Tab
        # deplacerait le focus du clavier hors de la fenetre.
        return "break"

    def creer_dossier(self):
        """Cree un nouveau dossier de tri sans quitter le tri (touche N).

        La boite demande son nom et sa touche. Le dossier est cree aussitot,
        ajoute a l'evenement et retenu pour les prochains evenements
        (decision de l'utilisateur, 26 octobre 2026). La photo affichee ne
        bouge pas : il suffit d'appuyer ensuite sur la touche du nouveau
        dossier pour l'y ranger.
        """
        nouveau = demander_nouveau_dossier(self.fenetre, self.suivi)
        # La boite fermee laisse derriere elle des objets Tkinter qui se
        # referencent les uns les autres : ils sont detruits ici, sur le fil
        # principal, et non plus tard par le ramasse-miettes depuis un fil
        # d'arriere-plan (voir __init__).
        gc.collect()
        self.fenetre.focus_force()
        if nouveau is None:
            return
        try:
            os.makedirs(self.suivi.chemin_dossier(nouveau["nom"]), exist_ok=True)
        except OSError as erreur:
            messagebox.showerror("Dossier impossible a creer",
                                 "Le dossier « %s » n'a pas pu etre cree :\n%s"
                                 % (nouveau["nom"], erreur), parent=self.fenetre)
            self.fenetre.focus_force()
            return
        self.suivi.ajouter_dossier_tri(nouveau["nom"], nouveau["touche"])
        preferences.retenir_dossiers_de_tri(self.suivi.dossiers_tri)
        self.stats.compter()
        self._mettre_a_jour_rappel()
        self._noter_avancement()

    # ------------------------------------------------------------------
    # Retouches : rotation et bandeaux
    # ------------------------------------------------------------------

    def _retouches_en_attente(self):
        return self.visionneuse.image is not None and (
            self.visionneuse.rotation != 0 or bool(self.outil.bandeaux()))

    def _preparer_retouches(self, chemin):
        """Garde une copie intacte de la photo, et met sa version retouchee en memoire.

        Le fichier ne sera reenregistre qu'en arriere-plan (voir ecritures.py) :
        la version retouchee est donc mise en memoire des maintenant, pour
        qu'un retour avec la fleche gauche la montre bien telle qu'elle sera
        enregistree. Les visages, eux, devront etre detectes de nouveau.

        Renvoie (chemin de la sauvegarde, bandeaux, rotation), ou None si la
        copie de sauvegarde n'a pas pu etre faite : la photo n'est alors pas
        modifiee, et l'utilisateur en est prevenu.
        """
        bandeaux = self.outil.bandeaux()
        rotation = self.visionneuse.rotation

        # Copie intacte AVANT toute modification, pour permettre l'annulation
        # (section 9.6). Si un rognage de cette photo est encore en cours
        # d'enregistrement, la copie attend la version a jour.
        self.ecritures.attendre(chemin)
        sauvegarde = self._copie_de_sauvegarde(chemin)
        if sauvegarde is None:
            return None

        image = self.visionneuse.image
        apercu = self.visionneuse.apercu
        image_retouchee = appliquer_retouches(image, bandeaux, rotation)
        apercu_retouche = appliquer_retouches(apercu, bandeaux, rotation,
                                              echelle=apercu.width / image.width)
        self.chargeur.remplacer(self.position, image_retouchee, apercu_retouche)
        self._oublier_les_visages(self.position)
        return sauvegarde, bandeaux, rotation

    def _copie_de_sauvegarde(self, chemin):
        """Copie intacte de la photo avant modification, ou None (l'utilisateur est prevenu).

        Sans copie, pas d'annulation possible : la photo ne doit donc pas etre
        modifiee. Un echec (disque plein, dossier en lecture seule) arretait
        sinon l'action a mi-chemin, sur un message d'erreur imprevue.
        """
        try:
            return copie_de_sauvegarde(chemin, self.suivi.chemin_dossier_temporaire())
        except OSError as erreur:
            messagebox.showerror(
                "Modification impossible",
                "La copie de sauvegarde de « %s » n'a pas pu etre faite :\n%s\n\n"
                "La photo n'a pas ete modifiee." % (os.path.basename(chemin), erreur),
                parent=self.fenetre)
            self.fenetre.focus_force()
            return None

    def valider(self):
        """Enregistre les retouches de la photo sur place, puis passe a la suivante.

        Sans retouche, rien n'est reecrit : cela eviterait une recompression
        inutile, qui degraderait la photo sans rien y ajouter.
        """
        if self.position >= len(self.photos):
            return
        # Sans retouche, Entree ne fait que passer a la suivante, comme Espace.
        self.a_navigue = True
        nom_fichier = self.photos[self.position]
        dossier_actuel, chemin = self._localiser(nom_fichier)
        if chemin is not None and self._retouches_en_attente():
            if self.ecritures.en_cours(chemin):
                # Un rognage de cette photo s'enregistre encore : on attend sa
                # fin sans figer la fenetre.
                self._attendre_les_enregistrements(self.valider)
                return
            if not self._verifier_que_la_photo_est_modifiable():
                # Format que l'on ne sait pas reecrire sans perte : les
                # retouches sont abandonnees, la photo n'est pas touchee.
                self.suivante()
                return
            preparees = self._preparer_retouches(chemin)
            if preparees is None:
                return      # on reste sur la photo, retouches toujours a l'ecran
            sauvegarde, bandeaux, rotation = preparees
            self.ecritures.ajouter(chemin, enregistrer_retouches, chemin, bandeaux, rotation)
            self._inscrire({
                "action": "retouche",
                "fichier": nom_fichier,
                "emplacement": dossier_actuel,
                "sauvegarde": os.path.basename(sauvegarde),
                "sans_barre": self._garder_sans_barre(sauvegarde, chemin, bandeaux, rotation),
            })
        self.suivante()

    def _inscrire(self, action):
        """Ajoute une action a l'historique : elle pourra etre annulee par Retour arriere."""
        self.suivi.historique.append(action)
        self.actions_de_la_session.append(action)
        # Retour arriere annulera d'abord cette action (voir _action_a_annuler).
        self.a_navigue = False

    def _garder_sans_barre(self, sauvegarde, chemin, bandeaux, rotation):
        """Range une copie de la photo sans ses bandeaux dans « Sans-barre ».

        Le dossier « Sans-barre » est cree a cote de la photo barree. La copie
        part de la sauvegarde intacte, et recoit la meme rotation que la photo
        barree. Si une version sans barre existe deja (photo barree une seconde
        fois), elle est gardee : c'est elle qui n'a aucun bandeau.

        Renvoie True si la copie a ete creee : l'annulation devra l'effacer.
        Un echec ne doit pas interrompre la validation, deja en cours
        d'enregistrement : on previent, et la photo barree est gardee seule.
        """
        copie = chemin_sans_barre(chemin)
        if not bandeaux or os.path.exists(copie):
            return False
        try:
            os.makedirs(os.path.dirname(copie), exist_ok=True)
            shutil.copy2(sauvegarde, copie)
        except OSError as erreur:
            messagebox.showwarning(
                "Version sans barre non creee",
                "La version sans bandeaux de « %s » n'a pas pu etre creee :\n%s\n\n"
                "La photo barree est bien enregistree ; Retour arriere la rend "
                "intacte." % (os.path.basename(chemin), erreur), parent=self.fenetre)
            self.fenetre.focus_force()
            return False
        if rotation:
            self.ecritures.ajouter(copie, tourner_sans_barre, copie, rotation)
        return True

    def _deplacer_sans_barre(self, ancien_chemin, nouveau_chemin):
        """Deplace la version sans bandeaux d'une photo, si elle en a une, avec elle.

        Un echec ici ne doit pas faire croire que la photo n'a pas ete rangee :
        elle l'a ete. On previent, et la version sans barre reste ou elle est.
        """
        self.ecritures.attendre(chemin_sans_barre(ancien_chemin))
        try:
            deplacer_sans_barre(ancien_chemin, nouveau_chemin)
        except OSError as erreur:
            messagebox.showwarning(
                "Version sans barre non deplacee",
                "La photo « %s » a bien ete deplacee, mais pas sa version sans "
                "bandeaux, restee dans « %s » :\n%s"
                % (os.path.basename(ancien_chemin),
                   os.path.dirname(chemin_sans_barre(ancien_chemin)), erreur),
                parent=self.fenetre)
            self.fenetre.focus_force()

    def _retirer_sans_barre(self, action, chemin_photo):
        """Efface la version sans bandeaux creee par une action que l'on annule.

        Elle se trouve a cote de la photo, la ou celle-ci est maintenant
        (`chemin_photo`) : elle l'a suivie a chaque deplacement.
        """
        if not action.get("sans_barre"):
            return
        copie = chemin_sans_barre(chemin_photo)
        if os.path.isfile(copie):
            self.ecritures.attendre(copie)
            supprimer_fichier(copie)
            effacer_si_vide(os.path.dirname(copie))

    # ------------------------------------------------------------------
    # Rangement et navigation
    # ------------------------------------------------------------------

    def ranger(self, nom_dossier):
        """Deplace la photo affichee vers un dossier de tri, puis passe a la suivante.

        Les retouches en attente (rotation, bandeaux) sont enregistrees au
        passage : la touche de tri vaut validation.
        """
        if self.position >= len(self.photos):
            return

        # Photo encore sur « Chargement... » : on ne range pas ce qu'on n'a pas
        # vu. Une touche maintenue enfoncee, ou un disque lent, rangeaient
        # sinon des photos jamais affichees.
        if self.attente is not None:
            return

        nom_fichier = self.photos[self.position]
        dossier_actuel, chemin = self._localiser(nom_fichier)
        if chemin is None or dossier_actuel == nom_dossier:
            # Photo introuvable, ou deja dans ce dossier : il n'y a rien a
            # deplacer. On enregistre les retouches et on passe a la suivante.
            self.valider()
            return

        # Si la photo vient d'etre rognee ou retouchee, son enregistrement (ou
        # celui de sa version sans barre) peut etre encore en cours : on attend
        # qu'il soit fini avant de la comparer ou de la deplacer, sans figer
        # la fenetre.
        if self.ecritures.en_cours(chemin) or self.ecritures.en_cours(chemin_sans_barre(chemin)):
            self._attendre_les_enregistrements(lambda: self.ranger(nom_dossier))
            return

        destination = os.path.join(self.suivi.chemin_dossier(nom_dossier), nom_fichier)
        doublon = os.path.exists(destination)
        if doublon and not filecmp.cmp(chemin, destination, shallow=False):
            # Ne jamais ecraser une photo : on previent et on laisse tout en place.
            messagebox.showwarning(
                "Deplacement impossible",
                "Le dossier « %s » contient deja un fichier nomme « %s ».\n"
                "La photo n'a pas ete deplacee." % (nom_dossier, nom_fichier),
                parent=self.fenetre)
            self.fenetre.focus_force()
            return

        # Le rangement d'une photo au format non modifiable se fait quand meme :
        # la deplacer ne l'altere pas. Seules ses retouches sont abandonnees,
        # apres avoir prevenu.
        garder_retouches = (self._retouches_en_attente()
                            and self._verifier_que_la_photo_est_modifiable())

        if not self._deplacer_la_photo(chemin, destination, doublon):
            return

        # L'historique permet d'annuler plusieurs actions de suite. Le dossier
        # de depart y est note, car en revue (ou apres un retour en arriere)
        # ce n'est pas forcement le dossier source. La sauvegarde, s'il y en
        # a une, permet d'annuler les retouches en meme temps que le rangement.
        # Le rangement y est inscrit des que la photo a bouge : quoi qu'il
        # arrive ensuite, il doit pouvoir etre annule.
        action = {
            "action": "deplacement",
            "fichier": nom_fichier,
            "depuis": dossier_actuel,
            "dossier": nom_dossier,
            "sauvegarde": None,
            "sans_barre": False,
        }
        self._inscrire(action)
        self.stats.deplacement(dossier_actuel, nom_dossier)
        self.stats.rangement_fait()
        self.chargeur.changer_chemin(self.position, destination)
        # Le choix est retenu dans le suivi, independamment du disque : c'est
        # ce qui permet de reperer ensuite une photo que la synchronisation
        # aurait remise dans le dossier source (voir remise_en_place.py).
        self.suivi.noter_rangement(nom_fichier, nom_dossier)
        # Une version sans bandeaux gardee auparavant suit la photo.
        self._deplacer_sans_barre(chemin, destination)

        # Les retouches ne sont preparees qu'une fois la photo a sa nouvelle
        # place : si le deplacement avait echoue, rien ne devait changer. Elles
        # sont enregistrees en arriere-plan : la fenetre n'attend pas la fin de
        # l'encodage pour passer a la suite.
        if garder_retouches:
            preparees = self._preparer_retouches(destination)
            if preparees is not None:
                sauvegarde, bandeaux, rotation = preparees
                self.ecritures.ajouter(destination, enregistrer_retouches, destination,
                                       bandeaux, rotation)
                action["sauvegarde"] = os.path.basename(sauvegarde)
                action["sans_barre"] = self._garder_sans_barre(sauvegarde, destination,
                                                               bandeaux, rotation)
        self.position += 1
        self.afficher_photo_courante()
        self._noter_avancement()

    def _deplacer_la_photo(self, chemin, destination, doublon):
        """Deplace la photo vers son dossier de tri. Renvoie False en cas d'echec.

        `doublon` signale qu'une copie identique, octet pour octet, se trouve
        deja a destination. C'est la trace d'un rangement interrompu par une
        version precedente du logiciel, ou d'une synchronisation qui a recopie
        la photo dans le dossier source. Il suffit alors d'effacer
        l'exemplaire du dossier source : rien n'est perdu, l'autre etant
        identique.

        En cas d'echec, la photo reste exactement ou elle etait, et l'on
        reste sur elle : l'utilisateur peut simplement rappuyer sur la touche.
        """
        try:
            if doublon:
                supprimer_fichier(chemin)
            else:
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                deplacer_fichier(chemin, destination)
        except OSError as erreur:
            messagebox.showerror(
                "Deplacement impossible",
                "La photo « %s » n'a pas pu etre deplacee :\n%s\n\n"
                "Elle est restee a sa place. Un autre programme l'utilise "
                "peut-etre ; rappuyez sur la touche pour reessayer."
                % (os.path.basename(chemin), erreur),
                parent=self.fenetre)
            self.fenetre.focus_force()
            return False
        return True

    def suivante(self):
        """Passe a la photo suivante sans rien deplacer (section 8.2)."""
        if self.position < len(self.photos):
            self.position += 1
            self.afficher_photo_courante()
            self._noter_avancement()

    def precedente(self):
        """Revient a la photo precedente sans rien deplacer."""
        if self.position > 0:
            self.position -= 1
            self.afficher_photo_courante()
            self._noter_avancement()

    def _noter_avancement(self):
        """Enregistre le suivi ; un echec previent, sans interrompre l'action.

        L'ecriture du suivi reessaie deja deux secondes si un autre programme
        le tient ouvert (OneDrive, l'antivirus : voir fichiers.ecrire_json).
        Si elle echoue encore, l'action, elle, a bien eu lieu : on previent une
        seule fois, et le suivi sera enregistre a l'action suivante, avec tout
        ce qui s'est passe entre-temps.

        Avant, l'erreur interrompait l'action entre le changement de position
        et l'affichage : l'ecran montrait encore une photo alors que la
        position designait la suivante, et la touche de tri d'apres rangeait
        une photo jamais vue, laissant l'autre dans le dossier source.
        """
        try:
            self.suivi.enregistrer()
        except OSError as erreur:
            if not self.avancement_en_echec:
                self.avancement_en_echec = True
                messagebox.showwarning(
                    "Avancement non enregistre",
                    "Le fichier de suivi n'a pas pu etre enregistre :\n%s\n\n"
                    "Vous pouvez continuer : il le sera a la prochaine action. "
                    "Un autre programme l'utilise peut-etre (synchronisation, "
                    "antivirus)." % erreur, parent=self.fenetre)
                self.fenetre.focus_force()
            return
        self.avancement_en_echec = False

    def _attendre_les_enregistrements(self, action, chemin=None):
        """Lance `action` des que les enregistrements en cours sont termines.

        Une photo HEIC met trois a quatre secondes a s'enregistrer. Annuler,
        ranger ou fermer juste apres l'avoir validee obligeait a attendre la
        fin de son enregistrement, fenetre figee, et Windows la declarait
        « ne repond pas ». On revient donc voir toutes les 50 ms ; d'ici la,
        les touches sont ignorees (voir _touche) et un message dit pourquoi.
        """
        self._attendre_puis(action, chemin, None)

    def _attendre_puis(self, action, chemin, texte_avant):
        """Un tour d'attente de _attendre_les_enregistrements ; remet le texte d'avant a la fin."""
        self.attente_enregistrement = None
        if self.ecritures.en_cours(chemin):
            if texte_avant is None:
                texte_avant = self.etiquette_avancement.cget("text")
                self.etiquette_avancement.config(text="Enregistrement en cours, un instant...")
            self.attente_enregistrement = self.fenetre.after(
                50, self._attendre_puis, action, chemin, texte_avant)
            return
        if texte_avant is not None:
            self.etiquette_avancement.config(text=texte_avant)
        # L'enregistrement attendu a pu echouer : l'action visait alors une
        # image qui n'est pas celle du fichier, et n'a plus lieu d'etre.
        if self._traiter_les_echecs():
            return
        action()

    # ------------------------------------------------------------------
    # Rognage
    # ------------------------------------------------------------------

    def commencer_rognage(self):
        """Entre en mode rognage : le cadre part des quatre bords de la photo."""
        if self.visionneuse.image is None or self.position >= len(self.photos):
            return
        if not self._verifier_que_la_photo_est_modifiable():
            return
        self.visionneuse.commencer_rognage()
        self._mettre_a_jour_rappel()
        self._mettre_a_jour_barre()

    def abandonner_rognage(self):
        self.visionneuse.arreter_rognage()
        self._mettre_a_jour_rappel()
        self._mettre_a_jour_barre()

    def _verifier_que_la_photo_est_modifiable(self):
        """Refuse de retoucher un format que l'on ne sait pas reecrire sans perte.

        Un BMP, un GIF ou un TIFF se trie sans risque, mais le reenregistrer le
        degraderait (CLAUDE.md, section 8). Mieux vaut le dire que d'abimer la
        photo en silence.
        """
        nom_fichier = self.photos[self.position]
        _, chemin = self._localiser(nom_fichier)
        if est_modifiable(chemin or nom_fichier):
            return True
        messagebox.showwarning(
            "Format non modifiable",
            "La photo « %s » peut etre triee, mais pas modifiee : son format ne "
            "peut pas etre reenregistre sans perte de qualite.\n\n"
            "Seuls les formats JPEG, PNG, HEIC et WEBP sont rognables et "
            "censurables, et pas les images animees." % nom_fichier,
            parent=self.fenetre)
        self.fenetre.focus_force()
        return False

    def rogner(self):
        """Rogne la photo affichee selon le cadre, et l'enregistre sur place.

        La photo rognee est montree aussitot ; le fichier, lui, est reenregistre
        en arriere-plan (voir ecritures.py), ce qui evite de figer la fenetre
        pendant l'encodage. La rotation et les bandeaux en attente restent en
        attente : ils suivent simplement le nouveau cadrage.
        """
        if self.position >= len(self.photos):
            self.abandonner_rognage()
            return

        cadre = self.visionneuse.cadre_de_rognage()
        if cadre is None:
            # Le cadre couvre encore toute la photo : il n'y a rien a rogner. On
            # sort simplement du mode, sans rien reecrire, plutot que de rester
            # bloque dans un mode dont rien n'expliquerait qu'on ne sort pas.
            self.abandonner_rognage()
            return

        nom_fichier = self.photos[self.position]
        dossier_actuel, chemin = self._localiser(nom_fichier)
        if chemin is None:
            self.abandonner_rognage()
            return

        # La copie de sauvegarde doit etre prise sur le fichier a jour : si un
        # rognage precedent de cette photo est encore en cours d'enregistrement,
        # on attend sa fin, sans figer la fenetre.
        if self.ecritures.en_cours(chemin):
            self._attendre_les_enregistrements(self.rogner)
            return
        rotation = self.visionneuse.rotation
        sauvegarde = self._copie_de_sauvegarde(chemin)
        if sauvegarde is None:
            return      # on reste en rognage : Entree reessaie, Echap abandonne
        self.ecritures.ajouter(chemin, rogner_fichier, chemin, cadre, rotation)

        self._inscrire({
            "action": "rognage",
            "fichier": nom_fichier,
            "emplacement": dossier_actuel,
            "sauvegarde": os.path.basename(sauvegarde),
        })

        # A l'ecran, le meme rognage est applique a la photo deja en memoire,
        # qui remplace l'ancienne version dans le cache.
        image = self.visionneuse.image
        gauche, haut, _, _ = cadre_dans_le_sens_d_origine(cadre, rotation,
                                                         image.width, image.height)
        image_rognee = rogner_image(image, cadre, rotation)
        apercu = fabriquer_apercu(image_rognee, self.chargeur.taille_apercu)
        self.chargeur.remplacer(self.position, image_rognee, apercu)
        self._oublier_les_visages(self.position)
        self.outil.decaler(gauche, haut, image_rognee.width, image_rognee.height)
        self.visionneuse.montrer(image_rognee, apercu,
                                 "Photo illisible : %s" % nom_fichier,
                                 garder_rotation=True)
        self._mettre_a_jour_rappel()
        self._mettre_a_jour_barre()
        self._noter_avancement()

    # ------------------------------------------------------------------
    # Annulation
    # ------------------------------------------------------------------

    def _actions_de_la_photo(self, nom_fichier):
        """Actions encore annulables de cette photo, la plus recente en dernier.

        Une copie faite depuis le menu contient les memes noms que les
        dossiers de tri : ses retouches ne sont pas celles de la photo
        d'origine. Dans une copie, on ne voit donc que les actions faites
        dans cette copie ; ailleurs, on ne voit pas celles des copies.
        """
        actions = self.suivi.actions_de_la_photo(nom_fichier)
        if not self.touches_de_tri:
            return [action for action in actions
                    if action.get("emplacement") == self.dossier_origine]
        copies = self.suivi.dossiers_dupliques
        return [action for action in actions if action.get("emplacement") not in copies]

    def _action_a_annuler(self):
        """Choisit l'action que Retour arriere annulera, ou None.

        Deux habitudes doivent cohabiter :

        - on vient de ranger une photo par erreur : la suivante est deja a
          l'ecran, et Retour arriere doit ramener la photo rangee. Plusieurs
          appuis remontent les actions de la session, de la plus recente a la
          plus ancienne ;
        - on revient sur une ancienne photo avec les fleches, pour defaire ce
          qu'on lui a fait : Retour arriere doit alors annuler la derniere
          action de CETTE photo, meme si d'autres photos ont ete modifiees
          depuis, et meme si c'etait lors d'une session precedente.

        C'est la facon d'arriver sur la photo qui les departage (`a_navigue`).
        Sans cela, apres un rangement fait par erreur, Retour arriere aurait
        retire les bandeaux poses la veille sur la photo suivante, au lieu de
        ramener la photo qu'on venait de ranger.
        """
        if self.a_navigue and self.position < len(self.photos):
            actions = self._actions_de_la_photo(self.photos[self.position])
            if actions:
                return actions[-1]
        # Derniere action de la session qui soit encore dans l'historique
        # (elle a pu en sortir : dossier retire, session terminee).
        for action in reversed(self.actions_de_la_session):
            if any(action is autre for autre in self.suivi.historique):
                return action
        return None

    def _oublier_l_action(self, action):
        """Retire de l'historique une action qui vient d'etre annulee."""
        self.suivi.donnees["historique"] = [autre for autre in self.suivi.historique
                                            if autre is not action]
        self.actions_de_la_session = [autre for autre in self.actions_de_la_session
                                      if autre is not action]

    def annuler(self):
        """Annule une action (rangement, retouche ou rognage) et reaffiche sa photo.

        L'action est choisie par _action_a_annuler : la derniere de la
        session, ou la derniere de la photo sur laquelle on est revenu.

        Elle ne quitte l'historique qu'une fois annulee. Si un fichier
        refuse de bouger (photo ouverte dans un autre programme, OneDrive...),
        l'utilisateur est prevenu et l'action reste en place : rappuyer sur
        Retour arriere reprend la ou l'on s'etait arrete. Auparavant, elle
        etait retiree d'abord : apres un echec, elle etait perdue, et le
        second appui annulait l'action d'avant, sur une autre photo ; une
        photo pivotee le restait alors pour de bon.
        """
        action = self._action_a_annuler()
        if action is None:
            return

        # Les enregistrements en cours doivent etre termines avant de deplacer
        # ou de remettre en place un fichier ; on attend sans figer la fenetre.
        if self.ecritures.en_cours():
            self._attendre_les_enregistrements(self.annuler)
            return

        index = self.index_des_photos.get(action["fichier"])
        try:
            if action.get("action") in ("rognage", "retouche"):
                chemin = self._remettre_la_sauvegarde(action)
                self._retirer_sans_barre(action, chemin)
            else:
                self._annuler_deplacement(action)
        except OSError as erreur:
            messagebox.showerror(
                "Annulation impossible",
                "L'annulation de la derniere action sur « %s » n'a pas pu aller "
                "jusqu'au bout :\n%s\n\n"
                "Rien n'est perdu. Un autre programme utilise peut-etre le fichier ; "
                "rappuyez sur Retour arriere pour reessayer."
                % (action["fichier"], erreur), parent=self.fenetre)
            self.fenetre.focus_force()
            # Une partie de l'annulation a pu avoir lieu : l'ecran et le suivi
            # doivent dire ce qui est reellement sur le disque. Sinon, l'ecran
            # pouvait montrer un bandeau qui n'etait plus dans le fichier.
            if index == self.position:
                self.afficher_photo_courante()
            self._noter_avancement()
            return

        self._oublier_l_action(action)
        if index is not None:
            self.position = index
        self.etat["terminee"] = False
        self.afficher_photo_courante()
        self._noter_avancement()

    def _annuler_deplacement(self, deplacement):
        """Ramene la photo dans le dossier d'ou elle venait, sans ses retouches.

        Peut lever OSError (fichier occupe) : l'action reste alors dans
        l'historique, et le prochain appui reprend ou l'on s'etait arrete.
        `ramenee` note que la photo elle-meme est deja revenue.
        """
        nom_fichier = deplacement["fichier"]
        index = self.index_des_photos.get(nom_fichier)
        # Les historiques ecrits par une version precedente ne notaient pas le
        # dossier de depart : c'etait alors toujours le dossier source (None).
        depuis = deplacement.get("depuis")
        chemin_actuel = os.path.join(self.suivi.chemin_dossier(deplacement["dossier"]),
                                     nom_fichier)
        chemin_retour = os.path.join(self._chemin_du_dossier(depuis), nom_fichier)

        if not deplacement.get("ramenee"):
            # L'annulation ne doit jamais echouer en silence : l'utilisateur
            # croirait la photo revenue alors qu'elle n'a pas bouge. Comme rien
            # n'y changera en rappuyant, l'action quitte tout de meme
            # l'historique : les actions precedentes restent ainsi annulables.
            if not os.path.isfile(chemin_actuel) or os.path.exists(chemin_retour):
                raison = ("elle n'est plus dans « %s »" % deplacement["dossier"]
                          if not os.path.isfile(chemin_actuel)
                          else "un fichier du meme nom occupe deja sa place d'origine")
                messagebox.showwarning("Annulation impossible",
                                       "La photo « %s » n'a pas pu etre ramenee : %s."
                                       % (nom_fichier, raison), parent=self.fenetre)
                self.fenetre.focus_force()
                return
            deplacer_fichier(chemin_actuel, chemin_retour)
            deplacement["ramenee"] = True
            self.stats.deplacement(deplacement["dossier"], depuis)
            self.stats.rangement_annule()
            if index is not None:
                self.chargeur.changer_chemin(index, chemin_retour)
            self.suivi.noter_rangement(
                nom_fichier, depuis if depuis in self.suivi.noms_dossiers_tri else None)

        # La copie intacte est remise avant tout le reste : c'est elle qui
        # compte. La version sans barre n'en est qu'une copie, qui n'est
        # effacee qu'une fois l'originale revenue.
        sauvegarde = self.suivi.chemin_sauvegarde(deplacement)
        if sauvegarde and os.path.isfile(sauvegarde):
            remplacer_fichier(sauvegarde, chemin_retour)
            if index is not None:
                self.chargeur.oublier(index)
                self._oublier_les_visages(index)
        # La version sans bandeaux creee par ce rangement disparait avec ses
        # bandeaux ; une version plus ancienne revient avec la photo.
        self._retirer_sans_barre(deplacement, chemin_actuel)
        self._deplacer_sans_barre(chemin_actuel, chemin_retour)

    def _remettre_la_sauvegarde(self, action):
        """Remet en place la copie intacte gardee avant un rognage ou une retouche.

        La copie est remise la ou se trouve la photo maintenant. Une
        synchronisation a pu la deplacer depuis (la ramener dans le dossier
        source) : remise a son ancien emplacement, la copie aurait fait un
        doublon, et la photo serait restee modifiee.

        Renvoie le chemin de la photo.
        """
        sauvegarde = self.suivi.chemin_sauvegarde(action)
        chemin = os.path.join(self._chemin_du_dossier(action.get("emplacement")),
                              action["fichier"])
        if not os.path.isfile(chemin):
            chemin = self._localiser(action["fichier"])[1] or chemin
        if sauvegarde and os.path.isfile(sauvegarde):
            remplacer_fichier(sauvegarde, chemin)
        # L'image en memoire est la version modifiee : il faut relire l'originale.
        index = self.index_des_photos.get(action["fichier"])
        if index is not None:
            self.chargeur.oublier(index)
            self._oublier_les_visages(index)
        return chemin

    # ------------------------------------------------------------------
    # Enregistrements en arriere-plan
    # ------------------------------------------------------------------

    def _surveiller_ecritures(self):
        """Verifie regulierement qu'aucun enregistrement en arriere-plan n'a echoue."""
        self._traiter_les_echecs()
        self.surveillance = self.fenetre.after(300, self._surveiller_ecritures)

    def _traiter_les_echecs(self):
        """Previent des enregistrements rates, et reprend la photo affichee si elle en est.

        L'image montree ne correspond alors plus au fichier : apres un rognage
        rate, l'ecran gardait la photo rognee, et un bandeau pose sur des yeux
        y etait ecrit au meme endroit du fichier non rogne, a cote des yeux.
        La photo est donc reaffichee telle qu'elle est sur le disque.

        Renvoie True si la photo affichee a ete reprise.
        """
        echecs = signaler_les_echecs(self.ecritures, self.chargeur, self.fenetre)
        if not echecs or self.position >= len(self.photos):
            return False
        _, chemin = self._localiser(self.photos[self.position])
        if chemin not in echecs:
            return False
        if self.visionneuse.en_rognage:
            self.abandonner_rognage()
        self.afficher_photo_courante()
        return True

    # ------------------------------------------------------------------
    # Fermeture
    # ------------------------------------------------------------------

    def quitter(self):
        """Enregistre l'avancement et ferme la fenetre proprement.

        Les retouches provisoires de la photo affichee sont abandonnees, comme
        lorsqu'on passe a une autre photo.
        """
        if self.en_fermeture:
            return          # deja en cours (Echap presse deux fois, croix...)
        self.en_fermeture = True
        self._annuler_attente()
        self._annuler_attente_apercus()
        if self.surveillance is not None:
            self.fenetre.after_cancel(self.surveillance)
        if self.attente_enregistrement is not None:
            self.fenetre.after_cancel(self.attente_enregistrement)
            self.attente_enregistrement = None

        # Taille de la fenetre, retenue pour la prochaine ouverture. Agrandie,
        # sa geometrie est celle de l'ecran : seule compte alors l'information
        # « agrandie », l'ancienne taille normale etant gardee telle quelle.
        agrandie = theme.est_agrandie(self.fenetre)
        geometrie = (preferences.fenetre_de_tri()["geometrie"] if agrandie
                     else self.fenetre.geometry())
        preferences.retenir_fenetre_de_tri(geometrie, agrandie)

        self.visionneuse.arreter()
        self._finir_de_quitter()

    def _finir_de_quitter(self):
        """Attend les derniers enregistrements, sans figer la fenetre, puis la ferme.

        Plusieurs photos HEIC validees a la suite demandent chacune trois a
        quatre secondes d'enregistrement : la fenetre restait figee tout ce
        temps, Windows la declarait « ne repond pas », et la fermer de force
        aurait perdu des retouches validees. Elle dit donc ou elle en est, et
        revient voir toutes les dixiemes de seconde.
        """
        restants = self.ecritures.nombre_en_cours()
        if restants:
            self.etiquette_avancement.config(
                text="Enregistrement des dernieres modifications : %d photo(s)..." % restants)
            self.fenetre.after(100, self._finir_de_quitter)
            return
        self.ecritures.arreter()
        signaler_les_echecs(self.ecritures, self.chargeur, self.fenetre)

        # La detection se sert du chargeur : on l'arrete donc en premier, sans
        # quoi elle pourrait redemander une photo a un chargeur deja arrete.
        if self.detection is not None:
            self.detection.arreter()
        self.chargeur.arreter()

        # Une annulation restee a mi-chemin est terminee tant que la copie
        # intacte existe encore. Seule la derniere action d'une photo est
        # concernee : une plus ancienne designerait un emplacement que la
        # photo a pu quitter.
        for action in [action for action in self.suivi.historique if action.get("ramenee")]:
            if self._actions_de_la_photo(action["fichier"])[-1:] != [action]:
                continue
            try:
                self._annuler_deplacement(action)
                self._oublier_l_action(action)
            except OSError:
                pass

        # Les copies de sauvegarde et l'historique sont gardes : tout reste
        # annulable a la prochaine session, jusqu'a ce que l'utilisateur
        # declare la session terminee (fin_de_session.py). Seul un dossier de
        # sauvegardes reste vide est retire.
        effacer_si_vide(self.suivi.chemin_dossier_temporaire())
        # La fenetre se ferme meme si le suivi ne peut pas etre enregistre
        # (tenu ouvert par un autre programme) : elle restait sinon a l'ecran,
        # ses fils deja arretes, photos bloquees sur « Chargement... ».
        try:
            self.suivi.enregistrer()
        except OSError as erreur:
            messagebox.showwarning(
                "Avancement non enregistre",
                "Le fichier de suivi n'a pas pu etre enregistre :\n%s\n\n"
                "Les photos rangees le restent ; seule la position dans la "
                "liste pourrait etre perdue." % erreur, parent=self.fenetre)
        self.fenetre.destroy()

