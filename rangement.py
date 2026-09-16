"""
Fenetre commune a l'etape de tri et au mode revue (sections 8 et 8 bis).

Les deux fonctionnent de la meme facon : les photos defilent une par une en
grand, et une touche du clavier deplace la photo affichee vers l'un des quatre
dossiers de tri. Seul change le dossier d'ou viennent les photos :

- a l'etape de tri, le dossier source, ou attendent les photos brutes ;
- en mode revue, l'un des quatre dossiers de tri, que l'on repasse pour
  corriger un rangement.

Les fleches gauche et droite font circuler d'une photo a l'autre sans rien
deplacer. On peut ainsi revenir sur une photo deja rangee : elle est montree
depuis le dossier ou elle se trouve maintenant, et une touche de tri la deplace
de ce dossier vers le nouveau.
"""

import os
import shutil
import tkinter as tk
from tkinter import messagebox

from ecritures import EcrituresEnArrierePlan, signaler_les_echecs
from images import ChargeurAnticipe, copie_de_sauvegarde, fabriquer_apercu
from polices import police
from rognage import rogner_fichier, rogner_image
from visionneuse import Visionneuse

COULEUR_FOND = "#1e1e1e"
COULEUR_BARRE = "#2b2b2b"
COULEUR_TEXTE = "#f0f0f0"
COULEUR_RAPPEL = "#b8b8b8"

RAPPEL_ROGNAGE = ("ROGNAGE  -  Tracez un cadre a la souris  |  Entree = rogner la photo  |  "
                  "Echap ou C = abandonner sans rien modifier")

# Delai, en millisecondes, avant de regarder de nouveau si une photo qui
# n'etait pas encore chargee l'est enfin.
DELAI_ATTENTE_CHARGEMENT = 15


class FenetreRangement:
    """Fenetre ou l'on range les photos au clavier, pour le tri comme pour la revue."""

    def __init__(self, racine, suivi, etat, dossier_origine, titre):
        """
        etat            : la partie du fichier de suivi propre a cette etape
                          (suivi.tri ou suivi.revue) : liste des photos,
                          position et historique.
        dossier_origine : nom du dossier d'ou viennent les photos, ou None
                          pour le dossier source (etape de tri).
        """
        self.suivi = suivi
        self.etat = etat
        self.photos = etat["photos"]
        self.dossier_origine = dossier_origine

        # Les apercus sont d'abord prepares a la taille de l'ecran, que la
        # fenetre ne peut pas depasser, puis a celle de la zone d'affichage des
        # qu'elle est connue (voir _zone_d_affichage_changee).
        dossier = self._chemin_du_dossier(dossier_origine)
        taille_ecran = (racine.winfo_screenwidth(), racine.winfo_screenheight())
        self.chargeur = ChargeurAnticipe([os.path.join(dossier, nom) for nom in self.photos],
                                         taille_ecran)
        self.ecritures = EcrituresEnArrierePlan()
        self.attente = None         # nouvel essai programme si la photo n'est pas chargee

        self.fenetre = tk.Toplevel(racine)
        self.fenetre.title(titre)
        self.fenetre.geometry("1200x800")
        self.fenetre.configure(bg=COULEUR_FOND)
        self.fenetre.protocol("WM_DELETE_WINDOW", self.quitter)

        self._construire()
        self.fenetre.bind("<Key>", self._touche)
        self.fenetre.focus_force()
        self.fenetre.after(60, self.afficher_photo_courante)
        self.surveillance = self.fenetre.after(300, self._surveiller_ecritures)

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    def _construire(self):
        # La barre du bas est placee en premier : si la fenetre est reduite,
        # c'est la photo qui retrecit, et le rappel des touches reste visible.
        barre = tk.Frame(self.fenetre, bg=COULEUR_BARRE)
        barre.pack(side="bottom", fill="x")

        self.visionneuse = Visionneuse(self.fenetre)
        self.visionneuse.canvas.pack(side="top", fill="both", expand=True)
        # Les apercus sont prepares exactement a la taille de la zone
        # d'affichage : une photo s'y affiche alors sans etre redimensionnee.
        self.visionneuse.canvas.bind("<Configure>", self._zone_d_affichage_changee, add="+")

        self.etiquette_avancement = tk.Label(barre, text="", bg=COULEUR_BARRE,
                                             fg=COULEUR_TEXTE, font=police(11, gras=True),
                                             anchor="w", padx=10)
        self.etiquette_avancement.pack(side="top", fill="x", pady=(6, 0))

        touches = "  |  ".join("%s = %s" % (dossier["touche"], dossier["nom"])
                               for dossier in self.suivi.dossiers_tri)
        self.rappel = (touches + "  |  Espace ou → = suivante  |  ← = precedente  |  "
                       "Retour arriere = annuler  |  R = pivoter  |  C = rogner  |  "
                       "Echap = quitter")
        self.etiquette_rappel = tk.Label(barre, text=self.rappel, bg=COULEUR_BARRE,
                                         fg=COULEUR_RAPPEL, font=police(9),
                                         anchor="w", padx=10)
        self.etiquette_rappel.pack(side="top", fill="x", pady=(0, 6))

    def _zone_d_affichage_changee(self, evenement):
        if evenement.width >= 10 and evenement.height >= 10:
            self.chargeur.changer_taille_apercu((evenement.width, evenement.height))

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
        dans le dossier d'origine, puis dans les quatre dossiers de tri. Les
        photos etant numerotees une fois pour toutes (1, 2, 3...), un meme nom
        ne designe qu'une seule photo dans tout l'evenement.

        Renvoie (nom du dossier, chemin complet). Le nom vaut None pour le
        dossier source ; le chemin vaut None si la photo est introuvable.
        """
        candidats = [self.dossier_origine] + [nom for nom in self.suivi.noms_dossiers_tri
                                              if nom != self.dossier_origine]
        for nom_dossier in candidats:
            chemin = os.path.join(self._chemin_du_dossier(nom_dossier), nom_fichier)
            if os.path.isfile(chemin):
                return nom_dossier, chemin
        return None, None

    # ------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------

    def afficher_photo_courante(self):
        """Affiche la photo a la position courante, la ou elle se trouve."""
        self._annuler_attente()
        self.etiquette_rappel.config(text=self.rappel)
        if self.position >= len(self.photos):
            self._afficher_fin()
            return

        nom_fichier = self.photos[self.position]
        dossier_actuel, chemin = self._localiser(nom_fichier)

        texte = "Photo %d sur %d   -   %s" % (self.position + 1, len(self.photos), nom_fichier)
        if chemin is not None and dossier_actuel != self.dossier_origine:
            texte += "   -   actuellement dans « %s »" % (dossier_actuel or "dossier source")
        self.etiquette_avancement.config(text=texte)

        if chemin is None:
            self.chargeur.avancer(self.position)
            self.visionneuse.montrer(None, None, "Photo introuvable : %s" % nom_fichier)
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

    def _annuler_attente(self):
        if self.attente is not None:
            self.fenetre.after_cancel(self.attente)
            self.attente = None

    def _afficher_fin(self):
        self.etiquette_avancement.config(text="Toutes les photos ont ete parcourues")
        self.visionneuse.afficher_texte(
            "Toutes les photos ont ete parcourues.\n"
            "Fleche gauche pour revenir en arriere, Echap pour revenir au menu.")
        self.etat["terminee"] = True
        self.suivi.enregistrer()

    # ------------------------------------------------------------------
    # Clavier
    # ------------------------------------------------------------------

    def _touche(self, evenement):
        touche = evenement.keysym

        # Pendant le rognage, seules trois touches comptent : rien d'autre ne
        # doit deplacer ou changer la photo tant que le cadre est a l'ecran.
        if self.visionneuse.en_rognage:
            if touche in ("Return", "KP_Enter"):
                self.rogner()
            elif touche == "Escape" or touche.lower() == "c":
                self.abandonner_rognage()
            return

        if touche == "Escape":
            self.quitter()
        elif touche in ("space", "Right"):
            self.suivante()
        elif touche == "Left":
            self.precedente()
        elif touche == "BackSpace":
            self.annuler()
        elif touche.lower() == "r":
            self.visionneuse.pivoter()
        elif touche.lower() == "c":
            self.commencer_rognage()
        elif evenement.char:
            nom_dossier = self.suivi.dossier_tri_pour_touche(evenement.char)
            if nom_dossier:
                self.ranger(nom_dossier)

    # ------------------------------------------------------------------
    # Rangement et navigation
    # ------------------------------------------------------------------

    def ranger(self, nom_dossier):
        """Deplace la photo affichee vers un dossier de tri, puis passe a la suivante."""
        if self.position >= len(self.photos):
            return

        nom_fichier = self.photos[self.position]
        dossier_actuel, chemin = self._localiser(nom_fichier)
        if chemin is None or dossier_actuel == nom_dossier:
            # Photo introuvable, ou deja dans ce dossier : il n'y a rien a
            # deplacer, on passe simplement a la suivante.
            self.suivante()
            return

        destination = os.path.join(self.suivi.chemin_dossier(nom_dossier), nom_fichier)
        if os.path.exists(destination):
            # Ne jamais ecraser une photo : on previent et on laisse tout en place.
            messagebox.showwarning(
                "Deplacement impossible",
                "Le dossier « %s » contient deja un fichier nomme « %s ».\n"
                "La photo n'a pas ete deplacee." % (nom_dossier, nom_fichier),
                parent=self.fenetre)
            self.fenetre.focus_force()
            return

        # Si la photo vient d'etre rognee, son enregistrement peut etre encore
        # en cours : on attend qu'il soit fini avant de la deplacer.
        self.ecritures.attendre(chemin)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.move(chemin, destination)
        self.chargeur.changer_chemin(self.position, destination)

        # L'historique permet d'annuler plusieurs actions de suite. Le dossier
        # de depart y est note, car en revue (ou apres un retour en arriere)
        # ce n'est pas forcement le dossier source.
        self.etat["historique"].append({
            "action": "deplacement",
            "fichier": nom_fichier,
            "depuis": dossier_actuel,
            "dossier": nom_dossier,
            "index": self.position,
        })
        self.position += 1
        self.suivi.enregistrer()
        self.afficher_photo_courante()

    def suivante(self):
        """Passe a la photo suivante sans rien deplacer (section 8.2)."""
        if self.position < len(self.photos):
            self.position += 1
            self.suivi.enregistrer()
            self.afficher_photo_courante()

    def precedente(self):
        """Revient a la photo precedente sans rien deplacer."""
        if self.position > 0:
            self.position -= 1
            self.suivi.enregistrer()
            self.afficher_photo_courante()

    # ------------------------------------------------------------------
    # Rognage
    # ------------------------------------------------------------------

    def commencer_rognage(self):
        if self.visionneuse.image is None:
            return
        self.visionneuse.commencer_rognage()
        self.etiquette_rappel.config(text=RAPPEL_ROGNAGE)

    def abandonner_rognage(self):
        self.visionneuse.arreter_rognage()
        self.etiquette_rappel.config(text=self.rappel)

    def rogner(self):
        """Rogne la photo affichee selon le cadre trace, et l'enregistre sur place.

        La photo rognee est montree aussitot ; le fichier, lui, est reenregistre
        en arriere-plan (voir ecritures.py), ce qui evite de figer la fenetre
        pendant l'encodage.
        """
        cadre = self.visionneuse.cadre_de_rognage()
        if cadre is None:
            return      # aucun cadre trace : on reste en mode rognage

        nom_fichier = self.photos[self.position]
        dossier_actuel, chemin = self._localiser(nom_fichier)
        if chemin is None:
            self.abandonner_rognage()
            return

        rotation = self.visionneuse.rotation
        # La copie de sauvegarde doit etre prise sur le fichier a jour : si un
        # rognage precedent de cette photo est encore en cours d'enregistrement,
        # on l'attend.
        self.ecritures.attendre(chemin)
        sauvegarde = copie_de_sauvegarde(chemin, self.suivi.chemin_dossier_temporaire())
        self.ecritures.ajouter(chemin, rogner_fichier, chemin, cadre, rotation)

        self.etat["historique"].append({
            "action": "rognage",
            "fichier": nom_fichier,
            "emplacement": dossier_actuel,
            "sauvegarde": sauvegarde,
            "index": self.position,
        })
        self.suivi.enregistrer()

        # A l'ecran, le meme rognage est applique a la photo deja en memoire,
        # qui remplace l'ancienne version dans le cache.
        image_rognee = rogner_image(self.visionneuse.image, cadre, rotation)
        apercu = fabriquer_apercu(image_rognee, self.chargeur.taille_apercu)
        self.chargeur.remplacer(self.position, image_rognee, apercu)
        self.visionneuse.montrer(image_rognee, apercu,
                                 "Photo illisible : %s" % nom_fichier,
                                 garder_rotation=True)
        self.etiquette_rappel.config(text=self.rappel)

    # ------------------------------------------------------------------
    # Annulation
    # ------------------------------------------------------------------

    def annuler(self):
        """Annule la derniere action (deplacement ou rognage) et reaffiche la photo."""
        historique = self.etat["historique"]
        if not historique:
            return

        # Les enregistrements en cours doivent etre termines avant de deplacer
        # ou de remettre en place un fichier.
        self.ecritures.attendre()

        derniere = historique.pop()
        if derniere.get("action") == "rognage":
            self._annuler_rognage(derniere)
        else:
            self._annuler_deplacement(derniere)

        self.position = derniere["index"]
        self.etat["terminee"] = False
        self.suivi.enregistrer()
        self.afficher_photo_courante()

    def _annuler_deplacement(self, deplacement):
        """Ramene la photo dans le dossier d'ou elle venait."""
        nom_fichier = deplacement["fichier"]
        # Les historiques ecrits par une version precedente ne notaient pas le
        # dossier de depart : c'etait alors toujours le dossier source (None).
        depuis = deplacement.get("depuis")
        chemin_actuel = os.path.join(self.suivi.chemin_dossier(deplacement["dossier"]),
                                     nom_fichier)
        chemin_retour = os.path.join(self._chemin_du_dossier(depuis), nom_fichier)

        if os.path.isfile(chemin_actuel) and not os.path.exists(chemin_retour):
            shutil.move(chemin_actuel, chemin_retour)
            self.chargeur.changer_chemin(deplacement["index"], chemin_retour)

    def _annuler_rognage(self, rognage):
        """Remet en place la copie intacte gardee avant le rognage."""
        sauvegarde = rognage.get("sauvegarde")
        chemin = os.path.join(self._chemin_du_dossier(rognage["emplacement"]),
                              rognage["fichier"])
        if sauvegarde and os.path.isfile(sauvegarde):
            os.replace(sauvegarde, chemin)
        # L'image en memoire est la version rognee : il faut relire l'originale.
        self.chargeur.oublier(rognage["index"])

    # ------------------------------------------------------------------
    # Enregistrements en arriere-plan
    # ------------------------------------------------------------------

    def _surveiller_ecritures(self):
        """Verifie regulierement qu'aucun enregistrement en arriere-plan n'a echoue."""
        signaler_les_echecs(self.ecritures, self.chargeur, self.fenetre)
        self.surveillance = self.fenetre.after(300, self._surveiller_ecritures)

    # ------------------------------------------------------------------
    # Fermeture
    # ------------------------------------------------------------------

    def quitter(self):
        """Enregistre l'avancement et ferme la fenetre proprement."""
        self._annuler_attente()
        self.fenetre.after_cancel(self.surveillance)
        self.visionneuse.arreter()

        # Les derniers rognages doivent etre enregistres avant de fermer, et
        # avant de vider le dossier des sauvegardes.
        self.etiquette_avancement.config(text="Enregistrement des dernieres modifications...")
        self.fenetre.update_idletasks()
        self.ecritures.arreter()
        signaler_les_echecs(self.ecritures, self.chargeur, self.fenetre)
        self.chargeur.arreter()

        # Les copies de sauvegarde des rognages ne servent qu'a l'annulation en
        # cours de session (section 9.6) : elles sont effacees a la fermeture,
        # et les rognages quittent donc l'historique. Les deplacements, eux,
        # restent annulables a la session suivante.
        shutil.rmtree(self.suivi.chemin_dossier_temporaire(), ignore_errors=True)
        self.etat["historique"] = [action for action in self.etat["historique"]
                                   if action.get("action") != "rognage"]
        self.suivi.enregistrer()
        self.fenetre.destroy()
