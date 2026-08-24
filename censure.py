"""
Etape 2 - La censure des yeux (section 9).

Les photos d'un seul dossier de tri sont passees en revue. Sur chacune, le
logiciel detecte les visages et la position des yeux ; l'utilisateur clique sur
une tete pour poser un bandeau noir, reclique pour le retirer. La touche Entree
incruste les bandeaux et reenregistre la photo par-dessus l'originale.

Point important : tant que la photo n'est pas validee, rien n'est ecrit sur le
disque (section 9.3). Les bandeaux ne sont que des dessins provisoires a l'ecran.
"""

import os
import shutil
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

import bandeaux as module_bandeaux
from bandeaux import Bandeau, poignee_sous_la_souris
from images import (ChargeurAnticipe, charger_image, enregistrer_au_format_origine,
                    est_une_image, format_origine)
from visages import DetecteurVisages, DetectionAnticipee, visage_le_plus_proche

COULEUR_FOND = "#1e1e1e"
COULEUR_TEXTE = "#f0f0f0"
COULEUR_SELECTION = "#00d0ff"

# Deplacement, en pixels ecran, en dessous duquel on considere que l'utilisateur
# a clique et non fait glisser. Sert a distinguer « retirer le bandeau » de
# « deplacer le bandeau » (section 9.4).
SEUIL_DE_GLISSEMENT = 4


def photos_du_dossier(chemin_dossier):
    """Liste les images d'un dossier de tri, ordonnees par leur numero."""
    if not os.path.isdir(chemin_dossier):
        return []
    noms = [nom for nom in os.listdir(chemin_dossier)
            if os.path.isfile(os.path.join(chemin_dossier, nom)) and est_une_image(nom)]

    def numero(nom):
        base = os.path.splitext(nom)[0]
        return (0, int(base)) if base.isdigit() else (1, 0)

    return sorted(noms, key=lambda nom: (numero(nom), nom))


class FenetreCensure:
    """Fenetre de l'etape de censure."""

    def __init__(self, racine, suivi, nom_dossier):
        self.suivi = suivi
        self.nom_dossier = nom_dossier
        self.dossier = suivi.chemin_dossier(nom_dossier)
        self.photos = suivi.censure["photos"]

        # Etat de la photo courante (jamais enregistre sur le disque).
        self.image = None
        self.visages = []
        self.bandeaux_visages = {}   # index du visage -> Bandeau
        self.bandeaux_manuels = []
        self.bandeau_selectionne = None
        self.photo_tk = None

        # Etat de la manipulation a la souris.
        self.action = None           # None, "poignee" ou "corps"
        self.poignee_active = None
        self.point_presse = None
        self.a_glisse = False

        chemins = [os.path.join(self.dossier, nom) for nom in self.photos]
        self.chargeur = ChargeurAnticipe(chemins)
        try:
            self.detecteur = DetecteurVisages()
            self.detection = DetectionAnticipee(self.detecteur, self.chargeur,
                                                len(self.photos))
        except Exception:
            # Le chargement anticipe est deja lance : si la detection echoue
            # (modele absent par exemple), il faut l'arreter avant de laisser
            # remonter l'erreur. Sans cela, un fil continuerait a lire des
            # photos alors que la fenetre ne s'ouvrira jamais, et le dossier
            # resterait « ouvert » pour Windows.
            self.chargeur.arreter()
            raise

        self.fenetre = tk.Toplevel(racine)
        self.fenetre.title("Censure - %s / %s" % (suivi.nom_evenement, nom_dossier))
        self.fenetre.geometry("1200x800")
        self.fenetre.configure(bg=COULEUR_FOND)
        self.fenetre.protocol("WM_DELETE_WINDOW", self.quitter)

        self._construire()
        self._brancher_commandes()
        self.fenetre.after(60, self.afficher_photo_courante)

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    def _construire(self):
        self.canvas = tk.Canvas(self.fenetre, bg=COULEUR_FOND, highlightthickness=0)
        self.canvas.pack(side="top", fill="both", expand=True)

        barre = tk.Frame(self.fenetre, bg="#2b2b2b")
        barre.pack(side="bottom", fill="x")

        self.etiquette_avancement = tk.Label(barre, text="", bg="#2b2b2b",
                                             fg=COULEUR_TEXTE,
                                             font=("Segoe UI", 11, "bold"),
                                             anchor="w", padx=10, pady=6)
        self.etiquette_avancement.pack(side="left")

        rappel = ("Clic = poser/retirer un bandeau  |  Entree = enregistrer  |  "
                  "Espace = passer  |  Retour arriere = annuler  |  Echap = quitter")
        tk.Label(barre, text=rappel, bg="#2b2b2b", fg="#b8b8b8",
                 font=("Segoe UI", 9), anchor="e", padx=10).pack(side="right")

    def _brancher_commandes(self):
        self.fenetre.bind("<Key>", self._touche)
        self.canvas.bind("<Button-1>", self._souris_pressee)
        self.canvas.bind("<B1-Motion>", self._souris_glissee)
        self.canvas.bind("<ButtonRelease-1>", self._souris_relachee)
        self.canvas.bind("<Configure>", lambda evenement: self._rendre())
        self.fenetre.focus_force()

    # ------------------------------------------------------------------
    # Correspondance entre coordonnees ecran et coordonnees photo
    # ------------------------------------------------------------------

    def _facteur(self):
        """Rapport entre un pixel de la photo et un pixel de l'ecran."""
        if self.image is None:
            return 1.0
        largeur = max(self.canvas.winfo_width(), 1)
        hauteur = max(self.canvas.winfo_height(), 1)
        return min(largeur / self.image.width, hauteur / self.image.height)

    def _decalage(self, facteur):
        """Position du coin haut-gauche de la photo dans le canvas (photo centree)."""
        largeur_affichee = self.image.width * facteur
        hauteur_affichee = self.image.height * facteur
        return ((self.canvas.winfo_width() - largeur_affichee) / 2,
                (self.canvas.winfo_height() - hauteur_affichee) / 2)

    def _vers_photo(self, x_ecran, y_ecran):
        """Convertit un point du canvas en coordonnees de la photo."""
        facteur = self._facteur()
        decalage_x, decalage_y = self._decalage(facteur)
        return ((x_ecran - decalage_x) / facteur, (y_ecran - decalage_y) / facteur)

    def _vers_ecran(self, x_photo, y_photo):
        facteur = self._facteur()
        decalage_x, decalage_y = self._decalage(facteur)
        return (x_photo * facteur + decalage_x, y_photo * facteur + decalage_y)

    # ------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------

    @property
    def position(self):
        return self.suivi.censure["position"]

    @position.setter
    def position(self, valeur):
        self.suivi.censure["position"] = valeur

    def afficher_photo_courante(self):
        if self.position >= len(self.photos):
            self._afficher_fin()
            return

        self.bandeaux_visages = {}
        self.bandeaux_manuels = []
        self.bandeau_selectionne = None

        self.chargeur.avancer(self.position)
        self.detection.avancer(self.position)
        self.image = self.chargeur.image(self.position)
        self.visages = self.detection.visages(self.position) if self.image else []

        self.etiquette_avancement.config(
            text="Photo %d sur %d   -   %s   -   %d visage(s) detecte(s)"
                 % (self.position + 1, len(self.photos),
                    self.photos[self.position], len(self.visages)))
        self._rendre()

    def _bandeaux_actifs(self):
        """Tous les bandeaux poses sur la photo, detectes et manuels confondus."""
        return list(self.bandeaux_visages.values()) + self.bandeaux_manuels

    def _rendre(self):
        self.canvas.delete("all")

        if self.image is None:
            self.canvas.create_text(
                self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2,
                text="Photo illisible", fill="#ff8080", font=("Segoe UI", 14))
            return

        largeur_canvas = self.canvas.winfo_width()
        hauteur_canvas = self.canvas.winfo_height()
        if largeur_canvas < 10 or hauteur_canvas < 10:
            return

        facteur = self._facteur()
        taille = (max(1, round(self.image.width * facteur)),
                  max(1, round(self.image.height * facteur)))
        self.photo_tk = ImageTk.PhotoImage(self.image.resize(taille, Image.LANCZOS))
        decalage_x, decalage_y = self._decalage(facteur)
        self.canvas.create_image(decalage_x, decalage_y, anchor="nw", image=self.photo_tk)

        # Les bandeaux sont dessines a l'ecran avec exactement la meme geometrie
        # que celle qui servira a les incruster dans le fichier : ce que
        # l'utilisateur voit est donc bien ce qui sera enregistre.
        for bandeau in self._bandeaux_actifs():
            points = [self._vers_ecran(x, y) for x, y in bandeau.coins()]
            self.canvas.create_polygon(points, fill="black", outline="")

        if self.bandeau_selectionne is not None:
            self._dessiner_poignees(self.bandeau_selectionne)

    def _dessiner_poignees(self, bandeau):
        """Entoure le bandeau manuel selectionne et montre ses poignees (section 9.4)."""
        points = [self._vers_ecran(x, y) for x, y in bandeau.coins()]
        self.canvas.create_polygon(points, fill="", outline=COULEUR_SELECTION, width=2)

        for nom, (x_photo, y_photo) in bandeau.poignees().items():
            x, y = self._vers_ecran(x_photo, y_photo)
            rayon = module_bandeaux.RAYON_POIGNEE
            if nom == "rotation":
                centre_x, centre_y = self._vers_ecran(bandeau.centre_x, bandeau.centre_y)
                self.canvas.create_line(centre_x, centre_y, x, y,
                                        fill=COULEUR_SELECTION, dash=(3, 3))
                self.canvas.create_oval(x - rayon, y - rayon, x + rayon, y + rayon,
                                        fill=COULEUR_SELECTION, outline="")
            else:
                self.canvas.create_rectangle(x - rayon, y - rayon, x + rayon, y + rayon,
                                             fill=COULEUR_SELECTION, outline="")

    def _afficher_fin(self):
        self.canvas.delete("all")
        self.etiquette_avancement.config(text="Censure terminee")
        self.canvas.create_text(
            self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2,
            text="Toutes les photos du dossier « %s » ont ete parcourues.\n"
                 "Appuyez sur Echap pour revenir au menu." % self.nom_dossier,
            fill=COULEUR_TEXTE, font=("Segoe UI", 16), justify="center")
        self.suivi.enregistrer()

    # ------------------------------------------------------------------
    # Souris
    # ------------------------------------------------------------------

    def _souris_pressee(self, evenement):
        if self.image is None:
            return
        self.point_presse = (evenement.x, evenement.y)
        self.a_glisse = False
        self.action = None
        self.poignee_active = None

        x, y = self._vers_photo(evenement.x, evenement.y)
        tolerance = module_bandeaux.RAYON_POIGNEE / max(self._facteur(), 0.0001)

        # Une poignee du bandeau selectionne a la priorite sur tout le reste.
        if self.bandeau_selectionne is not None:
            poignee = poignee_sous_la_souris(self.bandeau_selectionne, x, y, tolerance)
            if poignee:
                self.action = "poignee"
                self.poignee_active = poignee
                return

        # Sinon, on regarde si le clic tombe sur un bandeau manuel existant.
        for bandeau in reversed(self.bandeaux_manuels):
            if bandeau.contient(x, y):
                self.bandeau_selectionne = bandeau
                self.action = "corps"
                self._rendre()
                return

    def _souris_glissee(self, evenement):
        if self.action is None or self.point_presse is None:
            return

        depart_x, depart_y = self.point_presse
        if (abs(evenement.x - depart_x) > SEUIL_DE_GLISSEMENT
                or abs(evenement.y - depart_y) > SEUIL_DE_GLISSEMENT):
            self.a_glisse = True

        x, y = self._vers_photo(evenement.x, evenement.y)

        if self.action == "poignee":
            self.bandeau_selectionne.tirer_poignee(self.poignee_active, x, y)
        elif self.action == "corps":
            ancien_x, ancien_y = self._vers_photo(depart_x, depart_y)
            self.bandeau_selectionne.deplacer(x - ancien_x, y - ancien_y)
            self.point_presse = (evenement.x, evenement.y)

        self._rendre()

    def _souris_relachee(self, evenement):
        # Un glissement a deja produit son effet : il n'y a rien de plus a faire.
        if self.a_glisse:
            self.action = None
            self.point_presse = None
            return

        if self.image is not None:
            self._clic(*self._vers_photo(evenement.x, evenement.y))

        self.action = None
        self.point_presse = None

    def _clic(self, x, y):
        """Applique la bascule : poser ou retirer un bandeau (sections 9.3 et 9.4)."""
        # 1. Un clic sans deplacement sur un bandeau manuel le retire.
        for bandeau in reversed(self.bandeaux_manuels):
            if bandeau.contient(x, y):
                self.bandeaux_manuels.remove(bandeau)
                if self.bandeau_selectionne is bandeau:
                    self.bandeau_selectionne = None
                self._rendre()
                return

        # 2. Sinon, on rattache le clic au visage detecte correspondant.
        index_visage = visage_le_plus_proche(self.visages, x, y)
        if index_visage is not None:
            if index_visage in self.bandeaux_visages:
                del self.bandeaux_visages[index_visage]      # second clic : on retire
            else:
                visage = self.visages[index_visage]
                self.bandeaux_visages[index_visage] = Bandeau.depuis_yeux(
                    visage.oeil_droit, visage.oeil_gauche)
            self.bandeau_selectionne = None
            self._rendre()
            return

        # 3. Aucun visage a cet endroit : bandeau manuel de taille standard.
        nouveau = Bandeau.manuel_par_defaut(x, y, self.image.width)
        self.bandeaux_manuels.append(nouveau)
        self.bandeau_selectionne = nouveau
        self._rendre()

    # ------------------------------------------------------------------
    # Clavier
    # ------------------------------------------------------------------

    def _touche(self, evenement):
        touche = evenement.keysym
        if touche == "Escape":
            self.quitter()
        elif touche in ("Return", "KP_Enter"):
            self.valider()
        elif touche == "space":
            self.passer()
        elif touche == "BackSpace":
            self.annuler()

    # ------------------------------------------------------------------
    # Validation, passage, annulation
    # ------------------------------------------------------------------

    def valider(self):
        """Incruste les bandeaux, enregistre la photo sur place, puis passe a la suivante."""
        if self.position >= len(self.photos):
            return

        nom_fichier = self.photos[self.position]
        chemin = os.path.join(self.dossier, nom_fichier)
        liste_bandeaux = self._bandeaux_actifs()

        sauvegarde = None
        if liste_bandeaux and os.path.isfile(chemin):
            # Copie intacte AVANT toute modification, pour permettre l'annulation
            # (section 9.6). Aucune photo d'origine n'est perdue tant que la
            # session est en cours.
            dossier_temporaire = self.suivi.chemin_dossier_temporaire()
            os.makedirs(dossier_temporaire, exist_ok=True)
            sauvegarde = os.path.join(dossier_temporaire, nom_fichier)
            shutil.copy2(chemin, sauvegarde)

            # La photo est relue et remise dans le bon sens AVANT l'incrustation,
            # exactement comme elle etait affichee : les bandeaux se retrouvent
            # donc a l'emplacement ou l'utilisateur les a poses (section 9.5).
            format_image = format_origine(chemin)
            image = charger_image(chemin)
            dessin = ImageDraw.Draw(image)
            for bandeau in liste_bandeaux:
                bandeau.dessiner(dessin)
            enregistrer_au_format_origine(image, chemin, format_image)

            # La photo sur le disque a change : sa detection doit etre refaite si
            # l'on revient dessus.
            self.detection.oublier(self.position)

        # Sans aucun bandeau, le fichier n'est pas reecrit : cela eviterait une
        # recompression inutile, qui degraderait la photo sans rien y ajouter.
        self.suivi.censure["historique"].append({
            "fichier": nom_fichier,
            "sauvegarde": sauvegarde,
            "index": self.position,
        })
        self.position += 1
        self.suivi.enregistrer()
        self.afficher_photo_courante()

    def passer(self):
        """Passe a la photo suivante sans la modifier (section 9.5)."""
        if self.position < len(self.photos):
            self.position += 1
            self.suivi.enregistrer()
            self.afficher_photo_courante()

    def annuler(self):
        """Annule la derniere validation en restaurant la copie d'origine (section 9.6)."""
        historique = self.suivi.censure["historique"]
        if not historique:
            return

        derniere = historique.pop()
        sauvegarde = derniere.get("sauvegarde")
        if sauvegarde and os.path.isfile(sauvegarde):
            chemin = os.path.join(self.dossier, derniere["fichier"])
            shutil.move(sauvegarde, chemin)

        self.position = derniere["index"]
        # L'image restauree n'a plus de bandeaux : le cache doit etre vide pour
        # que ce soit bien l'original qui reapparaisse a l'ecran.
        self.chargeur.oublier(self.position)
        self.detection.oublier(self.position)
        self.suivi.enregistrer()
        self.afficher_photo_courante()

    # ------------------------------------------------------------------
    # Fermeture
    # ------------------------------------------------------------------

    def quitter(self):
        """Enregistre l'avancement, vide le dossier temporaire, ferme la fenetre."""
        # La detection se sert du chargeur : on l'arrete donc en premier, sans
        # quoi elle pourrait redemander une photo a un chargeur deja arrete.
        self.detection.arreter()
        self.chargeur.arreter()

        # Les copies de sauvegarde ne servent qu'a l'annulation en cours de
        # session (section 9.6) : elles sont effacees a la fermeture, et
        # l'historique correspondant devient donc inutilisable.
        shutil.rmtree(self.suivi.chemin_dossier_temporaire(), ignore_errors=True)
        self.suivi.censure["historique"] = []
        self.suivi.enregistrer()
        self.fenetre.destroy()


def lancer_censure(racine, suivi, nom_dossier):
    """Prepare le suivi puis ouvre l'etape de censure sur un dossier de tri."""
    chemin = suivi.chemin_dossier(nom_dossier)

    # On ne recalcule la liste des photos que lorsqu'on change de dossier :
    # reprendre le meme dossier doit retomber exactement sur la meme photo
    # qu'a la fermeture precedente (section 9.7).
    if (suivi.censure.get("dossier") != nom_dossier
            or not suivi.censure.get("photos")):
        suivi.censure["dossier"] = nom_dossier
        suivi.censure["photos"] = photos_du_dossier(chemin)
        suivi.censure["position"] = 0
        suivi.censure["historique"] = []
        suivi.enregistrer()
    elif suivi.censure["position"] >= len(suivi.censure["photos"]):
        # Le dossier avait deja ete parcouru en entier : le rouvrir signifie que
        # l'utilisateur veut le reprendre depuis le debut, et non retomber
        # aussitot sur l'ecran de fin.
        suivi.censure["photos"] = photos_du_dossier(chemin)
        suivi.censure["position"] = 0
        suivi.censure["historique"] = []
        suivi.enregistrer()

    if not suivi.censure["photos"]:
        return 0

    fenetre = FenetreCensure(racine, suivi, nom_dossier)
    racine.wait_window(fenetre.fenetre)
    return len(suivi.censure["photos"])
