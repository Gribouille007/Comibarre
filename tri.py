"""
Etape 1 - Le tri (section 8).

Les photos du dossier source defilent une par une en grand. Une touche du
clavier range la photo affichee dans l'un des quatre dossiers de tri, et la
photo suivante apparait aussitot.

Le zoom et la rotation ne servent qu'a mieux examiner la photo : ils ne
modifient jamais le fichier, qui est deplace tel quel (section 8.1).
"""

import os
import shutil
import tkinter as tk

from PIL import Image, ImageTk

from images import ChargeurAnticipe

# Bornes du zoom. 1.0 correspond a la photo entiere ajustee a la fenetre.
ZOOM_MINIMUM = 1.0
ZOOM_MAXIMUM = 8.0
PAS_DE_ZOOM = 1.15

COULEUR_FOND = "#1e1e1e"
COULEUR_TEXTE = "#f0f0f0"


class FenetreTri:
    """Fenetre de l'etape de tri."""

    def __init__(self, racine, suivi):
        self.suivi = suivi
        self.photos = suivi.tri["photos"]

        # Etat de l'affichage (jamais enregistre : purement visuel).
        self.rotation_affichage = 0
        self.zoom = 1.0
        self.vue_x = 0.0
        self.vue_y = 0.0
        self.image_pivotee = None
        self.photo_tk = None
        self.glissement = None

        chemins = [os.path.join(suivi.dossier_source, nom) for nom in self.photos]
        self.chargeur = ChargeurAnticipe(chemins)

        self.fenetre = tk.Toplevel(racine)
        self.fenetre.title("Tri - %s" % suivi.nom_evenement)
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
                                             fg=COULEUR_TEXTE, font=("Segoe UI", 11, "bold"),
                                             anchor="w", padx=10, pady=6)
        self.etiquette_avancement.pack(side="left")

        rappel = "  |  ".join(
            "%s = %s" % (dossier["touche"], dossier["nom"])
            for dossier in self.suivi.dossiers_tri)
        rappel += "  |  Espace = passer  |  Retour arriere = annuler  |  R = pivoter  |  Echap = quitter"
        tk.Label(barre, text=rappel, bg="#2b2b2b", fg="#b8b8b8",
                 font=("Segoe UI", 9), anchor="e", padx=10).pack(side="right")

    def _brancher_commandes(self):
        self.fenetre.bind("<Key>", self._touche)
        self.canvas.bind("<MouseWheel>", self._molette)
        self.canvas.bind("<Button-1>", self._debut_glissement)
        self.canvas.bind("<B1-Motion>", self._glisser)
        self.canvas.bind("<ButtonRelease-1>", self._fin_glissement)
        self.canvas.bind("<Configure>", lambda evenement: self._rendre())
        self.fenetre.focus_force()

    # ------------------------------------------------------------------
    # Affichage de la photo
    # ------------------------------------------------------------------

    @property
    def position(self):
        return self.suivi.tri["position"]

    @position.setter
    def position(self, valeur):
        self.suivi.tri["position"] = valeur

    def afficher_photo_courante(self):
        """Charge et affiche la photo a la position courante."""
        if self.position >= len(self.photos):
            self._afficher_fin()
            return

        # Remise a zero de l'affichage : chaque photo se presente ajustee et
        # dans son sens d'origine.
        self.rotation_affichage = 0
        self.zoom = 1.0
        self.vue_x = 0.0
        self.vue_y = 0.0

        self.chargeur.avancer(self.position)
        image = self.chargeur.image(self.position)
        self.image_pivotee = image

        self.etiquette_avancement.config(
            text="Photo %d sur %d   -   %s"
                 % (self.position + 1, len(self.photos), self.photos[self.position]))
        self._rendre()

    def _appliquer_rotation(self):
        """Recalcule l'image pivotee, seulement quand la rotation change."""
        image = self.chargeur.image(self.position)
        if image is None:
            self.image_pivotee = None
            return
        if self.rotation_affichage:
            # expand=True agrandit le cadre pour que la photo pivotee tienne
            # entierement dedans, au lieu d'etre coupee.
            image = image.rotate(-self.rotation_affichage, expand=True)
        self.image_pivotee = image

    def _facteur_ajustement(self):
        """Facteur qui fait tenir la photo entiere dans la fenetre."""
        image = self.image_pivotee
        largeur = max(self.canvas.winfo_width(), 1)
        hauteur = max(self.canvas.winfo_height(), 1)
        return min(largeur / image.width, hauteur / image.height)

    def _zone_visible(self, facteur):
        """Taille, en pixels de la photo, de la portion montree a l'ecran."""
        image = self.image_pivotee
        largeur = min(image.width, self.canvas.winfo_width() / facteur)
        hauteur = min(image.height, self.canvas.winfo_height() / facteur)
        return largeur, hauteur

    def _rendre(self):
        """Dessine la photo dans le canvas, en tenant compte du zoom et du cadrage.

        Seule la portion visible de la photo est redimensionnee, et non la photo
        entiere. Sans cette precaution, zoomer x4 sur une photo de 24 millions de
        pixels obligerait a fabriquer une image de 400 millions de pixels en
        memoire ; ici, le travail reste proportionnel a la taille de la fenetre.
        """
        self.canvas.delete("all")

        if self.image_pivotee is None:
            self.canvas.create_text(
                self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2,
                text="Photo illisible : %s" % self.photos[self.position],
                fill="#ff8080", font=("Segoe UI", 14))
            return

        largeur_canvas = self.canvas.winfo_width()
        hauteur_canvas = self.canvas.winfo_height()
        if largeur_canvas < 10 or hauteur_canvas < 10:
            return

        facteur = self._facteur_ajustement() * self.zoom
        largeur_visible, hauteur_visible = self._zone_visible(facteur)

        # Le cadrage ne doit jamais sortir de la photo.
        image = self.image_pivotee
        self.vue_x = max(0.0, min(self.vue_x, image.width - largeur_visible))
        self.vue_y = max(0.0, min(self.vue_y, image.height - hauteur_visible))

        zone = image.crop((round(self.vue_x), round(self.vue_y),
                           round(self.vue_x + largeur_visible),
                           round(self.vue_y + hauteur_visible)))
        cible = (max(1, round(largeur_visible * facteur)),
                 max(1, round(hauteur_visible * facteur)))
        # Reduction : LANCZOS donne un rendu net. Agrandissement : BILINEAR
        # suffit et reste instantane.
        filtre = Image.LANCZOS if facteur <= 1 else Image.BILINEAR
        self.photo_tk = ImageTk.PhotoImage(zone.resize(cible, filtre))

        self.canvas.create_image((largeur_canvas - cible[0]) // 2,
                                 (hauteur_canvas - cible[1]) // 2,
                                 anchor="nw", image=self.photo_tk)

    def _afficher_fin(self):
        self.canvas.delete("all")
        self.etiquette_avancement.config(text="Tri termine")
        self.canvas.create_text(
            self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2,
            text="Toutes les photos ont ete parcourues.\n"
                 "Appuyez sur Echap pour revenir au menu.",
            fill=COULEUR_TEXTE, font=("Segoe UI", 16), justify="center")
        self.suivi.tri["terminee"] = True
        self.suivi.enregistrer()

    # ------------------------------------------------------------------
    # Actions de l'utilisateur
    # ------------------------------------------------------------------

    def _touche(self, evenement):
        touche = evenement.keysym

        if touche == "Escape":
            self.quitter()
        elif touche == "space":
            self.passer()
        elif touche == "BackSpace":
            self.annuler()
        elif touche.lower() == "r":
            self.pivoter()
        elif evenement.char:
            nom_dossier = self.suivi.dossier_tri_pour_touche(evenement.char)
            if nom_dossier:
                self.ranger(nom_dossier)

    def ranger(self, nom_dossier):
        """Deplace la photo affichee vers un dossier de tri, puis passe a la suivante."""
        if self.position >= len(self.photos):
            return

        nom_fichier = self.photos[self.position]
        source = os.path.join(self.suivi.dossier_source, nom_fichier)
        if not os.path.isfile(source):
            # La photo a disparu entre-temps : on avance sans rien casser.
            self.position += 1
            self.suivi.enregistrer()
            self.afficher_photo_courante()
            return

        destination_dossier = self.suivi.chemin_dossier(nom_dossier)
        os.makedirs(destination_dossier, exist_ok=True)
        shutil.move(source, os.path.join(destination_dossier, nom_fichier))

        # L'historique permet d'annuler plusieurs rangements de suite.
        self.suivi.tri["historique"].append({
            "fichier": nom_fichier,
            "dossier": nom_dossier,
            "index": self.position,
        })
        self.position += 1
        self.suivi.enregistrer()
        self.afficher_photo_courante()

    def passer(self):
        """Passe a la photo suivante sans rien deplacer (section 8.2)."""
        if self.position < len(self.photos):
            self.position += 1
            self.suivi.enregistrer()
            self.afficher_photo_courante()

    def annuler(self):
        """Ramene la derniere photo rangee a sa place et la reaffiche."""
        historique = self.suivi.tri["historique"]
        if not historique:
            return

        derniere = historique.pop()
        origine = os.path.join(self.suivi.chemin_dossier(derniere["dossier"]),
                               derniere["fichier"])
        destination = os.path.join(self.suivi.dossier_source, derniere["fichier"])
        if os.path.isfile(origine):
            shutil.move(origine, destination)

        self.position = derniere["index"]
        self.suivi.tri["terminee"] = False
        self.suivi.enregistrer()
        self.afficher_photo_courante()

    def pivoter(self):
        """Fait pivoter l'affichage d'un quart de tour (le fichier n'est pas modifie)."""
        self.rotation_affichage = (self.rotation_affichage + 90) % 360
        self.zoom = 1.0
        self.vue_x = 0.0
        self.vue_y = 0.0
        self._appliquer_rotation()
        self._rendre()

    # ------------------------------------------------------------------
    # Zoom et deplacement de la vue
    # ------------------------------------------------------------------

    def _molette(self, evenement):
        if self.image_pivotee is None:
            return
        self._zoomer(PAS_DE_ZOOM if evenement.delta > 0 else 1 / PAS_DE_ZOOM)

    def _zoomer(self, multiplicateur):
        """Change le zoom en gardant au centre le meme point de la photo."""
        facteur_avant = self._facteur_ajustement() * self.zoom
        largeur_avant, hauteur_avant = self._zone_visible(facteur_avant)
        centre_x = self.vue_x + largeur_avant / 2
        centre_y = self.vue_y + hauteur_avant / 2

        self.zoom = max(ZOOM_MINIMUM, min(ZOOM_MAXIMUM, self.zoom * multiplicateur))

        facteur_apres = self._facteur_ajustement() * self.zoom
        largeur_apres, hauteur_apres = self._zone_visible(facteur_apres)
        self.vue_x = centre_x - largeur_apres / 2
        self.vue_y = centre_y - hauteur_apres / 2
        self._rendre()

    def _debut_glissement(self, evenement):
        self.glissement = (evenement.x, evenement.y)

    def _glisser(self, evenement):
        if self.glissement is None or self.image_pivotee is None:
            return
        ancien_x, ancien_y = self.glissement
        facteur = self._facteur_ajustement() * self.zoom
        # Un deplacement de la souris vers la droite fait glisser la vue vers
        # la gauche dans la photo, d'ou le signe negatif.
        self.vue_x -= (evenement.x - ancien_x) / facteur
        self.vue_y -= (evenement.y - ancien_y) / facteur
        self.glissement = (evenement.x, evenement.y)
        self._rendre()

    def _fin_glissement(self, evenement):
        self.glissement = None

    # ------------------------------------------------------------------
    # Fermeture
    # ------------------------------------------------------------------

    def quitter(self):
        """Enregistre l'avancement et ferme la fenetre proprement."""
        self.suivi.enregistrer()
        self.chargeur.arreter()
        self.fenetre.destroy()


def lancer_tri(racine, suivi):
    """Ouvre l'etape de tri et attend sa fermeture."""
    if not suivi.tri["photos"]:
        return
    fenetre = FenetreTri(racine, suivi)
    racine.wait_window(fenetre.fenetre)
