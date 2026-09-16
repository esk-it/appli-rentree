"""Tests de la conversion HTML → PDF.

Le rendu lui-même est celui d'Edge ou de Chrome : rien à tester d'un
moteur qu'on n'écrit pas. Ce qui se teste ici est ce qui nous appartient —
le choix du navigateur, le refus propre quand il n'y en a pas, le fait
qu'un échec n'emporte pas le lot, et les noms de fichiers.
"""
from __future__ import annotations

import pytest


def test_nom_de_fichier_accepte_les_codes_classe():
    from backend.services.impression_pdf import nom_de_fichier

    assert nom_de_fichier("Etiquettes_2_BPGATL") == "Etiquettes_2_BPGATL"
    assert nom_de_fichier("T_G4B") == "T_G4B"


def test_nom_de_fichier_remplace_ce_que_windows_refuse():
    from backend.services.impression_pdf import nom_de_fichier

    assert nom_de_fichier("3e/4e") == "3e-4e"
    assert nom_de_fichier('a:b*c?') == "a-b-c-"
    # Un point ou un espace final rend le fichier inatteignable sous Windows.
    assert nom_de_fichier("classe. ") == "classe"


def test_nom_de_fichier_ne_rend_jamais_vide():
    """Un nom vide ferait un fichier sans nom, que le système refuse."""
    from backend.services.impression_pdf import nom_de_fichier

    assert nom_de_fichier("") == "document"
    assert nom_de_fichier("   ") == "document"
    assert nom_de_fichier("...") == "document"
    # Un nom qui ne contient que des caractères remplacés reste un nom :
    # il est laid mais utilisable, et le masquer cacherait la donnée fausse.
    assert nom_de_fichier("///") == "---"


def test_sans_navigateur_le_refus_est_explicite(monkeypatch):
    """Le HTML reste produit : le message doit le dire, pas s'excuser."""
    from backend.services import impression_pdf

    monkeypatch.setattr(impression_pdf, "trouver_navigateur", lambda: None)
    with pytest.raises(impression_pdf.ImpressionImpossible, match="Edge ou Chrome"):
        impression_pdf.rendre([impression_pdf.Planche(nom="x", html="<p>x</p>")])


def test_un_echec_nemporte_pas_le_lot(monkeypatch, tmp_path):
    """Chaque planche part chez un professeur différent.

    Perdre les douze parce que la troisième a mal rendu serait
    disproportionné : on rend ce qui a abouti et on nomme le reste.
    """
    from backend.services import impression_pdf

    faux = tmp_path / "navigateur.exe"
    faux.write_text("")

    def imprimer(moteur, source, cible, profil):
        if "casse" in source.read_text(encoding="utf-8"):
            raise impression_pdf.ImpressionImpossible("rendu refusé")
        cible.write_bytes(b"%PDF-1.4 faux")

    monkeypatch.setattr(impression_pdf, "_imprimer", imprimer)
    r = impression_pdf.rendre(
        [
            impression_pdf.Planche(nom="2_1", html="<p>ok</p>"),
            impression_pdf.Planche(nom="2_2", html="<p>casse</p>"),
            impression_pdf.Planche(nom="2_3", html="<p>ok</p>"),
        ],
        navigateur=str(faux),
    )

    assert sorted(r.pdfs) == ["2_1", "2_3"]
    assert [nom for nom, _ in r.echecs] == ["2_2"]
    assert r.nb_rendus == 2


def test_le_navigateur_du_path_passe_avant_les_chemins_connus(monkeypatch):
    from backend.services import impression_pdf

    monkeypatch.setattr(
        impression_pdf.shutil, "which", lambda n: r"C:\ailleurs\msedge.exe" if n == "msedge" else None
    )
    assert impression_pdf.trouver_navigateur() == r"C:\ailleurs\msedge.exe"


def test_chrome_prend_le_relais_si_edge_manque(monkeypatch):
    from backend.services import impression_pdf

    monkeypatch.setattr(
        impression_pdf.shutil, "which", lambda n: "/usr/bin/chrome" if n == "chrome" else None
    )
    assert impression_pdf.trouver_navigateur() == "/usr/bin/chrome"


def test_html_en_pdf_remonte_lechec_au_lieu_de_rendre_du_vide(monkeypatch, tmp_path):
    from backend.services import impression_pdf

    faux = tmp_path / "navigateur.exe"
    faux.write_text("")

    def imprimer(*_a, **_k):
        raise impression_pdf.ImpressionImpossible("le navigateur n'a rien écrit")

    monkeypatch.setattr(impression_pdf, "_imprimer", imprimer)
    with pytest.raises(impression_pdf.ImpressionImpossible, match="rien écrit"):
        impression_pdf.html_en_pdf("<p>x</p>", navigateur=str(faux))
