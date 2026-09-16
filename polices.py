"""
La police de caracteres des fenetres, choisie selon le systeme.

« Segoe UI » est la police de Windows : sous macOS et sous Linux elle n'existe
pas, et Tkinter la remplace alors par une police de secours souvent laide et
mal dimensionnee. Plutot que de nommer une police differente par systeme, on
demande a Tkinter celle qu'il emploie lui-meme pour ses propres boutons : c'est
toujours la police normale du systeme, donc la bonne, partout.

    from polices import police
    tk.Label(..., font=police(11, gras=True))

`police` ne peut etre appelee qu'une fois la fenetre principale creee, car
Tkinter ne connait ses polices qu'a partir de ce moment-la.
"""

import tkinter.font

# Retenue au premier appel : inutile d'interroger Tkinter a chaque etiquette.
_famille = None


def police(taille, gras=False):
    """Renvoie une police a donner a l'option `font` d'un widget Tkinter."""
    global _famille
    if _famille is None:
        try:
            _famille = tkinter.font.nametofont("TkDefaultFont").actual("family")
        except Exception:
            # Aucune fenetre ouverte, ou Tkinter incomplet : Helvetica existe
            # partout, c'est le nom de secours prevu par Tk lui-meme.
            _famille = "Helvetica"
    if gras:
        return (_famille, taille, "bold")
    return (_famille, taille)
