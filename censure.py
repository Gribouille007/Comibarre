"""
La censure des yeux : poser et retoucher des bandeaux sur la photo affichee
(section 9).

Il n'y a plus de fenetre de censure a part : la censure est un mode de la
fenetre de rangement (rangement.py), que l'on active ou desactive avec la
touche Tab. Ce module fournit l'outil que la fenetre confie alors a la
visionneuse : celle-ci lui transmet les clics, en coordonnees de la photo
d'origine (non pivotee), et lui laisse peindre les bandeaux a l'ecran.

Point important : rien n'est ecrit sur le disque ici (section 9.3). Les
bandeaux ne sont que des dessins provisoires ; c'est la fenetre qui les fait
incruster dans le fichier quand l'utilisateur valide (voir retouches.py).
"""

import selection
from bandeaux import Bandeau, poignee_sous_la_souris, remplir_polygone_lisse
from visages import Visage, visage_le_plus_proche

# Distances en pixels ecran, independantes du zoom.
TOLERANCE_POIGNEE = 11      # rayon de la zone sensible autour d'une poignee
MARGE_PRISE = 3             # debord accepte autour d'un bandeau, pour le saisir
MARGE_ROTATION = 30         # distance entre le bord du bandeau et sa poignee de rotation

# Forme du pointeur selon ce qui se trouve dessous. Tk traduit ces noms sur
# chaque systeme ; si l'un d'eux manque, on retombe sur la fleche ordinaire.
POINTEURS = {
    None: "",
    "corps": "fleur",
    "longueur_droite": "sb_h_double_arrow",
    "longueur_gauche": "sb_h_double_arrow",
    "epaisseur_haut": "sb_v_double_arrow",
    "epaisseur_bas": "sb_v_double_arrow",
    "rotation": "exchange",
}


class OutilBandeaux:
    """Bandeaux provisoires de la photo affichee, et leur manipulation a la souris.

    Toutes les coordonnees sont exprimees en pixels de la photo d'origine,
    remise dans le bon sens (EXIF) mais pas pivotee par la touche R : ce sont
    exactement celles qui servent a incruster les bandeaux dans le fichier.
    """

    def __init__(self, visionneuse, au_changement):
        """`au_changement` est appele chaque fois qu'un bandeau est pose ou retire."""
        self.visionneuse = visionneuse
        self.au_changement = au_changement

        self.visages = []
        self.bandeaux_visages = {}   # index du visage -> Bandeau
        self.bandeaux_manuels = []
        self.bandeau_selectionne = None
        # Les visages arrivent de la detection en arriere-plan, parfois une
        # fraction de seconde apres la photo : voir recevoir_visages.
        self.visages_connus = False
        self.bandeaux_en_attente = []   # (x, y, bandeau manuel) poses d'ici la

        # Etat de la manipulation a la souris.
        self.action = None           # None, "poignee" ou "corps"
        self.poignee_active = None
        self.dernier_point = None    # point de la photo sous la souris au dernier mouvement
        self.survol = None           # nom de poignee, "corps", ou None

    # ------------------------------------------------------------------
    # Ce que la fenetre demande a l'outil
    # ------------------------------------------------------------------

    def vider(self):
        """Retire tous les bandeaux et oublie les visages (nouvelle photo)."""
        self.visages = []
        self.visages_connus = False
        self.bandeaux_en_attente = []
        self.bandeaux_visages = {}
        self.bandeaux_manuels = []
        self.bandeau_selectionne = None
        self.action = None
        self.poignee_active = None
        self.dernier_point = None
        self.survoler(None)
        self.au_changement()

    def bandeaux(self):
        """Tous les bandeaux poses sur la photo, detectes et manuels confondus."""
        return list(self.bandeaux_visages.values()) + self.bandeaux_manuels

    def recevoir_visages(self, visages):
        """Les visages de la photo sont connus : reprend les clics faits en les attendant.

        La detection se fait en arriere-plan, et peut arriver une fraction de
        seconde apres la photo (juste apres Tab ou une annulation). Un clic
        fait entre-temps pose aussitot un bandeau manuel : la photo n'est
        jamais sans bandeau, meme validee dans la foulee. Mais ce bandeau
        restait horizontal, sans suivre la tete. Maintenant que les visages
        sont la, il est remplace par celui du visage vise, s'il y en a un.
        """
        self.visages = visages
        self.visages_connus = True
        en_attente = self.bandeaux_en_attente
        self.bandeaux_en_attente = []
        for x, y, manuel in en_attente:
            if not any(manuel is bandeau for bandeau in self.bandeaux_manuels):
                continue        # retire entre-temps par un double-clic
            index_visage = visage_le_plus_proche(self.visages, x, y)
            if index_visage is None or index_visage in self.bandeaux_visages:
                continue
            visage = self.visages[index_visage]
            nouveau = Bandeau.depuis_yeux(visage.oeil_droit, visage.oeil_gauche)
            self.bandeaux_manuels = [bandeau for bandeau in self.bandeaux_manuels
                                     if bandeau is not manuel]
            self.bandeaux_visages[index_visage] = nouveau
            if self.bandeau_selectionne is manuel:
                self.bandeau_selectionne = nouveau
        self.au_changement()
        self._redessiner()

    def decaler(self, gauche, haut, largeur, hauteur):
        """Suit un rognage : la photo commence desormais au point (gauche, haut).

        Les bandeaux et les visages sont decales d'autant, pour rester sur les
        memes yeux. Un bandeau dont le centre tombe hors de la photo rognee est
        retire : il ne masquerait plus rien.

        Un visage dont les yeux sont sortis du cadre a disparu de la photo :
        il est oublie. Sans cela, il attirait encore les clics, et un clic pres
        du nouveau bord posait son bandeau hors de la photo. Les visages
        gardes changeant de numero, les bandeaux qui leur sont rattaches sont
        renumerotes ; celui d'un visage disparu, s'il est reste dans le cadre,
        devient un bandeau manuel.
        """
        for bandeau in self.bandeaux():
            bandeau.deplacer(-gauche, -haut)

        visages_gardes = []
        nouveau_numero = {}          # ancien numero du visage -> nouveau
        for index, visage in enumerate(self.visages):
            decale = Visage(visage.x - gauche, visage.y - haut,
                            visage.largeur, visage.hauteur,
                            (visage.oeil_droit[0] - gauche, visage.oeil_droit[1] - haut),
                            (visage.oeil_gauche[0] - gauche, visage.oeil_gauche[1] - haut),
                            visage.score)
            milieu_x = (decale.oeil_droit[0] + decale.oeil_gauche[0]) / 2
            milieu_y = (decale.oeil_droit[1] + decale.oeil_gauche[1]) / 2
            if 0 <= milieu_x <= largeur and 0 <= milieu_y <= hauteur:
                nouveau_numero[index] = len(visages_gardes)
                visages_gardes.append(decale)
        self.visages = visages_gardes

        manuels = [bandeau for bandeau in self.bandeaux_manuels
                   if _dans_le_cadre(bandeau, largeur, hauteur)]
        bandeaux_visages = {}
        for index, bandeau in self.bandeaux_visages.items():
            if not _dans_le_cadre(bandeau, largeur, hauteur):
                continue
            if index in nouveau_numero:
                bandeaux_visages[nouveau_numero[index]] = bandeau
            else:
                manuels.append(bandeau)
        self.bandeaux_manuels = manuels
        self.bandeaux_visages = bandeaux_visages
        self.bandeaux_en_attente = [(x - gauche, y - haut, bandeau)
                                    for x, y, bandeau in self.bandeaux_en_attente]
        if self.bandeau_selectionne not in self.bandeaux():
            self.bandeau_selectionne = None
        self.au_changement()

    # ------------------------------------------------------------------
    # Dessin
    # ------------------------------------------------------------------

    def peindre(self, image, vers_ecran):
        """Peint les bandeaux, et l'habillage du bandeau choisi, dans l'image affichee.

        `vers_ecran` convertit un point de la photo d'origine en pixel de
        `image` : il tient compte du zoom, du cadrage et de la rotation
        d'examen. Les bandeaux sont peints avec la meme geometrie et le meme
        lissage des bords que ceux qui serviront a les incruster dans le
        fichier : ce que l'utilisateur voit est donc bien ce qui sera
        enregistre.
        """
        for bandeau in self.bandeaux():
            remplir_polygone_lisse(image, [vers_ecran(x, y) for x, y in bandeau.coins()])

        # L'habillage du bandeau choisi (contour et poignees) est peint dans
        # cette meme image, et non trace sur le canvas : Tkinter ne sait pas
        # lisser ses traits, alors que Pillow le fait (voir selection.py).
        if self.bandeau_selectionne is not None:
            bandeau = self.bandeau_selectionne
            selection.dessiner_habillage(
                image,
                [vers_ecran(x, y) for x, y in bandeau.coins()],
                {nom: vers_ecran(x, y)
                 for nom, (x, y) in bandeau.poignees(self._marge_rotation()).items()},
                self.survol if self.survol != "corps" else None)

    def _redessiner(self):
        self.visionneuse.demander_dessin()

    # ------------------------------------------------------------------
    # Ce qui se trouve sous la souris
    # ------------------------------------------------------------------

    def _en_pixels_photo(self, distance_ecran):
        """Convertit une distance a l'ecran en pixels de la photo, zoom compris."""
        return distance_ecran / max(self.visionneuse.facteur_affichage(), 0.0001)

    def _marge_rotation(self):
        """Distance bord-poignee de rotation, convertie en pixels de la photo."""
        return self._en_pixels_photo(MARGE_ROTATION)

    def _bandeau_sous_le_point(self, x, y):
        """Le bandeau situe sous un point de la photo, ou None.

        Les bandeaux manuels sont examines en premier, et les plus recents
        avant les plus anciens : ce sont ceux qui apparaissent au-dessus des
        autres a l'ecran, et c'est donc celui-la que l'utilisateur vise quand
        deux bandeaux se superposent.
        """
        marge = self._en_pixels_photo(MARGE_PRISE)
        for bandeau in reversed(self.bandeaux_manuels):
            if bandeau.contient(x, y, marge):
                return bandeau
        for bandeau in reversed(list(self.bandeaux_visages.values())):
            if bandeau.contient(x, y, marge):
                return bandeau
        return None

    def _bandeau_du_visage_vise(self, x, y):
        """Le bandeau deja pose sur le visage que designe ce point, ou None.

        Sert quand le clic tombe a cote du bandeau mais bien sur la tete :
        c'est ce bandeau-la que l'utilisateur veut atteindre.
        """
        index_visage = visage_le_plus_proche(self.visages, x, y)
        if index_visage is None:
            return None
        return self.bandeaux_visages.get(index_visage)

    def _ce_qui_est_sous_le_point(self, x, y):
        """Ce que designe un point de la photo : nom de poignee, "corps", ou None."""
        bandeau = self.bandeau_selectionne
        if bandeau is not None:
            tolerance = self._en_pixels_photo(TOLERANCE_POIGNEE)
            poignee = poignee_sous_la_souris(bandeau, x, y, tolerance,
                                             self._marge_rotation())
            # Bandeau fin a l'ecran (moins de deux fois la tolerance) : les
            # zones de ses deux poignees d'epaisseur le recouvrent alors en
            # entier. Le prendre par son milieu pour le deplacer tirait une
            # poignee : l'epaisseur tombait presque a zero et les yeux se
            # decouvraient. La moitie centrale d'un bandeau fin sert donc a le
            # deplacer ; le quart pres de chaque bord, ou la pastille de la
            # poignee est dessinee, et ce qui depasse, tirent l'epaisseur.
            if (poignee and poignee.startswith("epaisseur")
                    and bandeau.epaisseur < 2 * tolerance
                    and bandeau.contient(x, y, -bandeau.epaisseur / 4)):
                poignee = None
            if poignee:
                return poignee
        if self._bandeau_sous_le_point(x, y) is not None:
            return "corps"
        return None

    # ------------------------------------------------------------------
    # Souris (appelees par la visionneuse)
    # ------------------------------------------------------------------

    def pressee(self, x, y):
        """Bouton enfonce. Renvoie True si l'appui concerne un bandeau.

        Sinon, la visionneuse s'en sert pour deplacer la vue, et l'outil ne
        reagira qu'au relachement, si la souris n'a pas glisse entre-temps.
        """
        self.action = None
        self.poignee_active = None
        self.dernier_point = (x, y)

        # Une poignee du bandeau choisi a la priorite sur tout le reste.
        vise = self._ce_qui_est_sous_le_point(x, y)
        if vise is not None and vise != "corps":
            self.action = "poignee"
            self.poignee_active = vise
            return True

        # Sinon, un clic sur un bandeau existant, detecte ou manuel, le choisit
        # et permet de le deplacer. Il n'est jamais retire ici : c'est le
        # double-clic qui retire (voir double_clic).
        bandeau = self._bandeau_sous_le_point(x, y)
        if bandeau is not None:
            self.bandeau_selectionne = bandeau
            self.action = "corps"
            self._redessiner()
            return True
        return False

    def glissee(self, x, y):
        """Souris deplacee bouton enfonce, sur un bandeau ou une poignee."""
        # La photo peut avoir change depuis l'appui : rien n'empeche d'appuyer
        # sur une touche de tri en maintenant le bouton enfonce, et le passage a
        # la photo suivante vide alors les bandeaux. Sans cette garde, on
        # tirerait la poignee d'un bandeau qui n'existe plus, et le logiciel
        # s'arretait.
        if self.bandeau_selectionne is None or self.dernier_point is None:
            return

        if self.action == "poignee":
            self.bandeau_selectionne.tirer_poignee(self.poignee_active, x, y)
        elif self.action == "corps":
            ancien_x, ancien_y = self.dernier_point
            self.bandeau_selectionne.deplacer(x - ancien_x, y - ancien_y)
            # Un glissement trop vif ne doit pas emporter le bandeau hors de la
            # photo, ou il ne serait plus visible nulle part.
            image = self.visionneuse.image
            self.bandeau_selectionne.limiter_au_cadre(image.width, image.height)
        # Un bandeau retouche a la main reste tel quel : l'arrivee des visages
        # ne doit plus le remplacer (voir recevoir_visages). Il revenait sinon
        # sur la personne d'abord visee, et l'autre restait decouverte.
        self.bandeaux_en_attente = [attente for attente in self.bandeaux_en_attente
                                    if attente[2] is not self.bandeau_selectionne]
        self.dernier_point = (x, y)
        self._redessiner()

    def relachee(self, x, y, a_glisse):
        """Termine la manipulation en cours, ou pose un bandeau la ou l'on a clique.

        Un simple clic sur un bandeau ou sur une de ses poignees ne fait rien de
        plus ici : le bandeau a deja ete choisi a l'enfoncement du bouton. C'est
        important, car les poignees « longueur » et « epaisseur » sont posees
        sur le bord meme du bandeau : les traiter comme un clic sur le bandeau
        ferait disparaitre celui-ci des qu'on effleure une poignee.

        Un glissement dans le vide a deplace la vue : il ne pose rien.
        """
        if self.action is None and not a_glisse:
            self._clic_dans_le_vide(x, y)
        self.action = None
        self.poignee_active = None
        self.dernier_point = None

    def _clic_dans_le_vide(self, x, y):
        """Pose un bandeau la ou l'utilisateur a clique (sections 9.3 et 9.4)."""
        # 0. Un clic dans la bande sombre qui entoure la photo ne vise
        #    personne. Il posait un bandeau hors de la photo : invisible, mais
        #    compte, et la photo etait reenregistree pour rien a la validation.
        image = self.visionneuse.image
        if not (0 <= x <= image.width and 0 <= y <= image.height):
            return

        # 1. Le clic tombe sur une tete detectee, mais a cote du bandeau deja
        #    pose dessus : on choisit ce bandeau plutot que d'en creer un autre.
        deja_pose = self._bandeau_du_visage_vise(x, y)
        if deja_pose is not None:
            self.bandeau_selectionne = deja_pose
            self._redessiner()
            return

        # 2. Le clic est rattache au visage detecte correspondant : le bandeau
        #    epouse alors l'inclinaison de la tete (section 9.3).
        index_visage = visage_le_plus_proche(self.visages, x, y)
        if index_visage is not None:
            visage = self.visages[index_visage]
            nouveau = Bandeau.depuis_yeux(visage.oeil_droit, visage.oeil_gauche)
            self.bandeaux_visages[index_visage] = nouveau
        else:
            # 3. Aucun visage a cet endroit : bandeau manuel de taille standard,
            #    horizontal A L'ECRAN. Les bandeaux sont memorises dans le
            #    repere de la photo non pivotee : si l'utilisateur l'a tournee
            #    d'un quart de tour avec R, un bandeau d'angle 0 y serait
            #    vertical a l'ecran. Tourner la photo de `rotation` degres
            #    dans le sens des aiguilles d'une montre fait tourner ses
            #    traits d'autant ; un bandeau incline de -rotation dans la
            #    photo revient donc a l'horizontale une fois la photo tournee.
            largeur_affichee, _ = self.visionneuse.dimensions_affichees()
            nouveau = Bandeau.manuel_par_defaut(x, y, largeur_affichee,
                                                angle=-self.visionneuse.rotation)
            self.bandeaux_manuels.append(nouveau)
            if not self.visages_connus:
                # Pas « aucun visage ici », mais « visages pas encore
                # connus » : voir recevoir_visages.
                self.bandeaux_en_attente.append((x, y, nouveau))

        self.bandeau_selectionne = nouveau
        self.au_changement()
        self._redessiner()

    def double_clic(self, x, y):
        """Retire le bandeau double-clique, qu'il ait ete pose a la main ou non.

        Le premier des deux clics a pu poser ou choisir un bandeau : le
        double-clic retire celui qui se trouve sous le pointeur, quel qu'il
        soit. Double-cliquer dans le vide revient donc a poser un bandeau puis
        a le retirer aussitot, c'est-a-dire a ne rien faire.

        Sur une poignee, en revanche, rien n'est retire : deux saisies rapides
        d'une poignee forment un double-clic pour Tk, alors que l'utilisateur
        retouchait simplement le bandeau en deux temps. Il disparaissait.

        Renvoie True si un bandeau a ete retire.
        """
        vise = self._ce_qui_est_sous_le_point(x, y)
        if vise is not None and vise != "corps":
            return False
        bandeau = self._bandeau_sous_le_point(x, y)
        if bandeau is None:
            bandeau = self._bandeau_du_visage_vise(x, y)
        if bandeau is None:
            return False
        self._retirer(bandeau)
        return True

    def _retirer(self, bandeau):
        """Retire un bandeau de la photo courante (rien n'est ecrit sur le disque)."""
        if bandeau in self.bandeaux_manuels:
            self.bandeaux_manuels.remove(bandeau)
        else:
            for index, pose in list(self.bandeaux_visages.items()):
                if pose is bandeau:
                    del self.bandeaux_visages[index]
                    break

        if self.bandeau_selectionne is bandeau:
            self.bandeau_selectionne = None
        self.action = None
        self.poignee_active = None
        self.survoler(None)
        self.au_changement()
        self._redessiner()

    # ------------------------------------------------------------------
    # Survol : ce que la souris designe, sans avoir encore clique
    # ------------------------------------------------------------------

    def survoler(self, point):
        """Met en avant la poignee ou le bandeau que la souris survole.

        L'utilisateur voit ainsi ce qu'il va saisir avant d'appuyer, et la
        forme du pointeur lui dit ce qui va se passer. `point` vaut None quand
        la souris quitte la photo.
        """
        nouveau = None if point is None else self._ce_qui_est_sous_le_point(*point)
        if nouveau == self.survol:
            return
        self.survol = nouveau
        # C'est la visionneuse qui regle le pointeur, et elle seule : sinon le
        # mode barrer et le rognage se le disputaient, et entrer en rognage
        # effacait aussitot le pointeur annoncant le bord a tirer.
        self.visionneuse.definir_curseur(POINTEURS.get(nouveau, ""))
        self._redessiner()


def _dans_le_cadre(bandeau, largeur, hauteur):
    return 0 <= bandeau.centre_x <= largeur and 0 <= bandeau.centre_y <= hauteur
