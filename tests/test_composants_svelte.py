"""Contrôle statique des composants Svelte.

## Pourquoi ce test existe

Un composant utilisé dans un template mais jamais importé compile sans que
rien ne proteste : `npm run build` passe, l'écran s'affiche, et le défaut
n'apparaît qu'au moment où la branche qui le contient est rendue. Pour
l'utilisateur, un bouton qui « ne fait rien ».

C'est arrivé sur `Modale` dans l'écran Sortants : la fenêtre de
confirmation de la vidange ne s'ouvrait jamais, et rien — ni le build, ni
les tests — ne le signalait. Ce contrôle rattrape la famille entière.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent / "src"

# `<svelte:head>`, `<svelte:window>`… ne sont pas des composants importables.
BALISES_SVELTE = re.compile(r"^svelte:")


def _fichiers_svelte() -> list[Path]:
    return sorted(RACINE.rglob("*.svelte"))


def _noms_disponibles(script: str, source: str) -> set[str]:
    """Tout ce qu'un template peut légitimement référencer."""
    noms: set[str] = set()

    # import X from "…"  /  import X, { a, b } from "…"
    noms |= set(re.findall(r"import\s+(\w+)", script))
    # import { a, b as c } from "…"
    for bloc in re.findall(r"import\s*\{([^}]*)\}", script):
        for morceau in bloc.split(","):
            noms.add(morceau.strip().split(" as ")[-1].strip())
    # let / const / function
    noms |= set(re.findall(r"(?:let|const|var|function)\s+(\w+)", script))
    # let { icon: Icon } = $props()  — le nom utile est après les deux-points
    for bloc in re.findall(r"(?:let|const)\s*\{([^}]*)\}\s*=", script):
        for morceau in bloc.split(","):
            if ":" in morceau:
                noms.add(morceau.split(":")[-1].split("=")[0].strip())
            else:
                noms.add(morceau.split("=")[0].strip())
    # {@const Ic = …} et {#snippet nom(…)}
    noms |= set(re.findall(r"\{@const\s+(\w+)\s*=", source))
    noms |= set(re.findall(r"\{#snippet\s+(\w+)", source))
    return {n for n in noms if n}


def _composants_utilises(source: str) -> set[str]:
    sans_script = re.sub(r"<script[^>]*>.*?</script>", "", source, flags=re.S)
    sans_style = re.sub(r"<style[^>]*>.*?</style>", "", sans_script, flags=re.S)
    utilises = set(re.findall(r"</?([A-Z][\w.]*)[\s/>]", sans_style))
    # `<Objet.Membre>` : seule la racine doit être déclarée.
    return {n.split(".")[0] for n in utilises if not BALISES_SVELTE.match(n)}


@pytest.mark.parametrize(
    "fichier", _fichiers_svelte(), ids=lambda p: p.relative_to(RACINE).as_posix()
)
def test_aucun_composant_utilise_sans_etre_declare(fichier: Path):
    """Un composant non déclaré ne fait pas échouer le build — seulement l'écran."""
    source = fichier.read_text(encoding="utf-8")
    script = "".join(re.findall(r"<script[^>]*>(.*?)</script>", source, re.S))

    manquants = sorted(_composants_utilises(source) - _noms_disponibles(script, source))

    assert not manquants, (
        f"{fichier.relative_to(RACINE).as_posix()} référence "
        f"{', '.join(manquants)} sans import ni déclaration — "
        "l'écran se compilera et le composant ne s'affichera jamais."
    )


def test_le_controle_detecte_bien_un_oubli(tmp_path: Path):
    """Le garde-fou doit échouer sur le cas qu'il prétend attraper."""
    source = """<script>
  let ouverte = $state(false);
</script>

{#if ouverte}
  <Modale titre="Confirmer ?" />
{/if}
"""
    script = "".join(re.findall(r"<script[^>]*>(.*?)</script>", source, re.S))
    manquants = _composants_utilises(source) - _noms_disponibles(script, source)
    assert manquants == {"Modale"}


def test_le_controle_ne_crie_pas_sur_les_formes_legitimes():
    """Icônes reçues en props, `{@const}`, snippets : rien de tout cela n'est un oubli."""
    source = """<script>
  import Loader from "@lucide/svelte/icons/loader-2";
  let { icon: Icon, children } = $props();
  function iconeType(t) { return Loader; }
</script>

{#snippet actions()}<Loader />{/snippet}
<Icon class="h-4 w-4" />
{@const Ic = iconeType("x")}
<Ic />
<svelte:window onkeydown={() => {}} />
"""
    script = "".join(re.findall(r"<script[^>]*>(.*?)</script>", source, re.S))
    assert not (_composants_utilises(source) - _noms_disponibles(script, source))
