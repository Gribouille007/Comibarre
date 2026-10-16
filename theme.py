"""
Apparence commune a toutes les fenetres : les couleurs et les styles.

Jusqu'ici, la fenetre de tri etait sombre alors que l'ecran d'accueil, le menu
et la configuration gardaient le gris clair que Tkinter emploie par defaut : le
logiciel semblait fait de deux programmes differents. Tout passe desormais par
ce fichier, qui est le seul endroit ou une couleur est choisie.

Pourquoi un fond sombre, et pourquoi strictement neutre. Une photo se juge mal
sur un fond clair, qui la fait paraitre plus sombre qu'elle n'est, et mal sur un
fond teinte, qui deplace la perception de ses couleurs. Tous les gris de ce
fichier ont donc leurs trois composantes egales : ils ne portent aucune teinte.
Les seules couleurs du logiciel sont les trois accents, reserves aux
informations (mode actif, retouche en attente, erreur).

    import theme
    theme.appliquer(racine)              une fois, au demarrage
    theme.habiller(fenetre)              pour chaque Toplevel
"""

import tkinter as tk
from tkinter import ttk

from polices import police

# --- Les gris, du plus sombre au plus clair. Tous neutres. ----------------
NOIR_PHOTO = "#141414"        # derriere la photo, dans la visionneuse
FOND = "#1d1d1d"              # fond des fenetres
SURFACE = "#262626"           # barre du bas, panneaux
SURFACE_HAUTE = "#333333"     # boutons et champs de saisie
SURVOL = "#3f3f3f"            # le meme, souris dessus
BORDURE = "#454545"
SEPARATEUR = "#333333"

# --- Les textes ----------------------------------------------------------
TEXTE = "#f0f0f0"
TEXTE_DOUX = "#9a9a9a"        # explications, rappels de touches
TEXTE_FAIBLE = "#6f6f6f"      # elements inactifs

# --- Les trois accents ---------------------------------------------------
ACCENT = "#5a9ef8"            # information, element choisi
ATTENTION = "#ffc861"         # retouche pas encore enregistree
ALERTE = "#ff7a7a"            # erreur, mode actif qui modifie la photo

# Marge interieure commune aux fenetres de reglage : une seule valeur, pour
# que toutes les fenetres respirent de la meme facon.
MARGE = 22


def appliquer(racine):
    """Donne au logiciel son apparence. A appeler une fois, sur la fenetre racine.

    Les widgets ttk (boutons, champs, etiquettes des ecrans de reglage) ne se
    colorent pas un par un : ils suivent un « style ». Parmi les styles fournis
    avec Tkinter, seul « clam » accepte qu'on redefinisse ses couleurs ; les
    styles propres a Windows et a macOS sont dessines par le systeme et ignorent
    ce qu'on leur demande. On part donc de clam sur les trois systemes, ce qui a
    l'avantage de donner exactement le meme resultat partout.
    """
    racine.configure(bg=FOND)

    style = ttk.Style(racine)
    try:
        style.theme_use("clam")
    except tk.TclError:
        # Installation de Tk incomplete : on garde le style par defaut plutot
        # que d'empecher le logiciel de demarrer.
        return

    style.configure(".", background=FOND, foreground=TEXTE,
                    font=police(10), focuscolor=ACCENT)

    style.configure("TFrame", background=FOND)
    style.configure("Surface.TFrame", background=SURFACE)

    style.configure("TLabel", background=FOND, foreground=TEXTE)
    style.configure("Titre.TLabel", font=police(15, gras=True))
    style.configure("Doux.TLabel", foreground=TEXTE_DOUX)
    style.configure("Alerte.TLabel", foreground=ALERTE)

    # clam dessine un bouton en relief, avec un bord clair en haut et un bord
    # sombre en bas. Sur un fond sombre, ce bord clair ressort comme une
    # rayure : on donne donc aux quatre bords la couleur du bouton lui-meme, ce
    # qui le rend parfaitement plat.
    style.configure("TButton", background=SURFACE_HAUTE, foreground=TEXTE,
                    bordercolor=BORDURE, lightcolor=SURFACE_HAUTE,
                    darkcolor=SURFACE_HAUTE, relief="flat",
                    padding=(14, 9), anchor="center")
    style.map("TButton",
              background=[("disabled", SURFACE), ("pressed", SURFACE),
                          ("active", SURVOL)],
              lightcolor=[("pressed", SURFACE), ("active", SURVOL)],
              darkcolor=[("pressed", SURFACE), ("active", SURVOL)],
              foreground=[("disabled", TEXTE_FAIBLE)])

    # Le bouton de l'action principale : un simple lisere bleu suffit a le
    # designer, sans aplat de couleur qui attirerait l'oeil plus que la photo.
    style.configure("Accent.TButton", bordercolor=ACCENT, relief="solid",
                    borderwidth=1)
    style.map("Accent.TButton",
              bordercolor=[("active", ACCENT), ("pressed", ACCENT)])

    style.configure("TEntry", fieldbackground=SURFACE_HAUTE, foreground=TEXTE,
                    bordercolor=BORDURE, lightcolor=BORDURE,
                    darkcolor=BORDURE, insertcolor=TEXTE, padding=6)
    style.map("TEntry",
              fieldbackground=[("readonly", SURFACE), ("disabled", SURFACE)],
              foreground=[("readonly", TEXTE_DOUX), ("disabled", TEXTE_FAIBLE)],
              bordercolor=[("focus", ACCENT)],
              lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)])

    style.configure("TSeparator", background=SEPARATEUR)


def habiller(fenetre):
    """Donne le fond du theme a une fenetre. A appeler sur chaque Toplevel.

    Le fond d'une fenetre n'est pas un style ttk : il se regle fenetre par
    fenetre. Sans cet appel, une bande gris clair apparait autour du contenu.
    """
    fenetre.configure(bg=FOND)


def centrer(fenetre, parent):
    """Place une fenetre au milieu de celle qui l'a ouverte.

    Tkinter pose sinon les nouvelles fenetres au coin haut-gauche de l'ecran,
    loin du regard de l'utilisateur, qui regarde la fenetre courante.

    La fenetre racine du logiciel est masquee (voir main.py) : se centrer sur
    elle enverrait la fenetre dans le coin de l'ecran. On se rabat donc sur le
    milieu de l'ecran des que le parent n'est pas visible.
    """
    fenetre.update_idletasks()
    largeur = fenetre.winfo_width()
    hauteur = fenetre.winfo_height()

    if parent is not None and parent.winfo_viewable() and parent.winfo_width() > 1:
        x = parent.winfo_rootx() + (parent.winfo_width() - largeur) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - hauteur) // 3
    else:
        x = (fenetre.winfo_screenwidth() - largeur) // 2
        y = (fenetre.winfo_screenheight() - hauteur) // 3

    # Une fenetre ne doit jamais se retrouver a cheval sur le bord de l'ecran.
    x = max(0, min(x, fenetre.winfo_screenwidth() - largeur))
    y = max(0, min(y, fenetre.winfo_screenheight() - hauteur))
    fenetre.geometry("+%d+%d" % (x, y))


def demander_texte(parent, titre, question, valeur_initiale=""):
    """Demande une ligne de texte a l'utilisateur. Renvoie le texte, ou None.

    Remplace `tkinter.simpledialog.askstring`, qui fabrique son champ de saisie
    avec les widgets d'origine de Tkinter et reste donc gris clair quoi qu'on
    fasse : au milieu d'un logiciel sombre, la boite paraissait venir d'ailleurs.
    """
    boite = tk.Toplevel(parent)
    boite.title(titre)
    boite.resizable(False, False)
    boite.transient(parent)
    habiller(boite)

    saisie = tk.StringVar(value=valeur_initiale)
    reponse = {"texte": None}

    def valider():
        reponse["texte"] = saisie.get()
        boite.destroy()

    cadre = ttk.Frame(boite, padding=MARGE)
    cadre.grid(row=0, column=0)
    ttk.Label(cadre, text=question, wraplength=380,
              justify="left").grid(row=0, column=0, columnspan=2, sticky="w")

    champ = ttk.Entry(cadre, textvariable=saisie, width=44)
    champ.grid(row=1, column=0, columnspan=2, sticky="we", pady=(12, 0))
    champ.focus_set()
    champ.select_range(0, "end")

    boutons = ttk.Frame(cadre)
    boutons.grid(row=2, column=0, columnspan=2, sticky="e", pady=(MARGE, 0))
    ttk.Button(boutons, text="Annuler", width=14,
               command=boite.destroy).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(boutons, text="Valider", width=14, style="Accent.TButton",
               command=valider).grid(row=0, column=1)

    boite.bind("<Return>", lambda evenement: valider())
    boite.bind("<Escape>", lambda evenement: boite.destroy())

    # `grab_set` apres `centrer` : la fenetre doit etre placee avant de capter
    # le clavier, sinon on la voit sauter sous les yeux de l'utilisateur.
    centrer(boite, parent)
    boite.grab_set()
    parent.wait_window(boite)
    return reponse["texte"]
