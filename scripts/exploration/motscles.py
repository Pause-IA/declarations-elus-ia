"""Mots-clés partagés par les scripts d'exploration.

Chaque mot-clé a un mode de recherche :
- "partout"     : texte en minuscules et sans accents ;
- "casse"       : texte brut, majuscules exactes (sigles, noms propres ambigus) ;
- "si_ia"       : comme "partout", mais seulement si l'IA est citée à proximité ;
- "casse_si_ia" : comme "casse", mais seulement si l'IA est citée à proximité.
"""
import re
import unicodedata

# The passage talks about AI. « ai » is left out on purpose: in French it is
# the verb (« j'ai »), and the few English speeches say "artificial intelligence".
IA = r"intelligences? artificielles?|\bia\b|artificial intelligence"

# « Near » = within this many characters on either side, about two sentences:
# a Sénat intervention can run for pages, so « in the same intervention »
# would tie public finances on page one to AI on page three.
FENETRE = 300

FAMILLES = {
    "Risques extrêmes": {
        "superintelligence": (r"super[- ]?intelligen", "partout"),
        "IA générale": (r"intelligences? artificielles? generales?|\bia generale"
                        r"|artificial general intelligence", "partout"),
        # « agi » is a French past participle; « AGI-SON » an association.
        "AGI / IAG": (r"(?<![\w-])(AGI|IAG)(?![\w-])", "casse"),
        "extinction": (r"extinction de l.(humanite|espece humaine)|human extinction",
                       "partout"),
        "singularité": (r"singularite technologique|technological singularity",
                        "partout"),
        "auto-amélioration": (r"auto[- ]?amelioration|self[- ]improv", "si_ia"),
        # Common in politics on their own (Ukraine, steel, public finances).
        "risque existentiel": (r"risques? existentiels?|existential risks?", "si_ia"),
        "perte de contrôle": (r"perte de (la )?(controle|maitrise)|loss of control",
                              "si_ia"),
        "AI 2027": (r"\bai ?2027\b|\bia ?2027\b", "partout"),
    },
    "Sécurité et gouvernance de l'IA": {
        "sécurité / sûreté de l'IA": (r"(securite|surete) (de l.|des )(ia\b|intelligences?"
                                      r" artificielles?)|ai safety", "partout"),
        # « Alignement avec les priorités de l'État » is not AI alignment:
        # only the phrasings that name what is being aligned.
        "alignement": (r"alignement (des |de l.)(ia\b|intelligences? artificielles?"
                       r"|modeles?|systemes? d.ia)|probleme d.alignement|\balignment\b",
                       "partout"),
        # « Des moratoires ont dû être imposés » on data centres is not a call to
        # pause AI: a moratorium ON something, or a call FOR one.
        "moratoire / pause": (r"moratoires? (sur|de|du|des) (l.|les )?(ia\b|intelligence"
                              r"|developpement|recherche|modeles?)"
                              r"|appel\w* (meme )?a (un|une) (moratoire|pause)"
                              r"|\bpause (dans|du|sur) (le |la |l.)?(developpement|ia\b"
                              r"|intelligence|recherche)", "si_ia"),
        "modèles de frontière": (r"(modeles?|ia) de frontiere|frontier (models?|ai)",
                                 "partout"),
        "risque systémique": (r"risques? systemiques?|systemic risks?", "si_ia"),
        "instituts de sécurité": (r"\binesia\b|ai safety institute|bletchley", "partout"),
        "armes autonomes": (r"armes? (letales? )?autonomes?|robots? tueurs?"
                            r"|killer robots?|autonomous weapons?", "partout"),
        # French typography writes pronounceable acronyms like words (« Otan »),
        # so the record says « Sala »; also a surname, hence the AI-nearby rule.
        "SALA": (r"(?<![\w-])(SALA|Sala)(?![\w-])", "casse_si_ia"),
    },
    "Entreprises et produits": {
        "OpenAI / ChatGPT": (r"\bopen ?(ai|ia)\b|chat ?gpt|\bgpt-?[345]", "partout"),
        "Anthropic": (r"\banthropic\b", "partout"),
        # A first name in Parliament (Claude Malhuret, Jean-Claude…): kept only
        # when no surname follows and AI is mentioned nearby.
        "Claude": (r"(?<!-)\bClaude\b(?!\s+[A-ZÉÈÀ][\w'-])", "casse_si_ia"),
        "Mistral AI": (r"\bmistral (ai|ia)\b", "partout"),
        # Bare « Mistral » only, so a « Mistral AI » passage is not counted
        # twice; also a wind and a warship, hence the AI-nearby rule.
        "Mistral": (r"\bmistral\b(?! (ai|ia)\b)", "si_ia"),
        "DeepMind / Gemini": (r"\bdeepmind\b|\bgemini\b", "si_ia"),
        "xAI / Grok": (r"\bgrok\b|\bxai\b", "si_ia"),
        "Llama": (r"\bllama\b", "si_ia"),
        "DeepSeek": (r"\bdeepseek\b", "partout"),
    },
    "Personnalités": {
        "Maxime Fournes": (r"maxime fournes", "partout"),   # Fournes is also a town
        "Yoshua Bengio": (r"\bbengio\b", "partout"),
        "Geoffrey Hinton": (r"\bhinton\b", "partout"),
        "Stuart Russell": (r"stuart russell", "partout"),
        "Sam Altman": (r"\baltman\b", "partout"),
        "Dario Amodei": (r"\bamodei\b", "partout"),
        "Demis Hassabis": (r"\bhassabis\b", "partout"),
        "Yann LeCun": (r"\ble ?cun\b", "partout"),
        "Arthur Mensch": (r"arthur mensch", "partout"),
        # Researchers who left frontier labs warning about the risks.
        "Jacob Coxon": (r"\bcoxon\b", "partout"),
        "Daniel Kokotajlo": (r"\bkokotajlo\b", "partout"),
        "Jan Leike": (r"\bleike\b", "partout"),
        "Leopold Aschenbrenner": (r"\baschenbrenner\b", "partout"),
        "Steven Adler": (r"steven adler", "partout"),   # Adler alone is too common
    },
    "Organisations de la sécurité de l'IA": {
        "Pause IA / PauseAI": (r"\bpause ?(ia|ai)\b", "partout"),
        "CeSIA": (r"\bcesia\b|centre pour la securite de l.(ia\b|intelligence artificielle)",
                  "partout"),
        "Future of Life Institute": (r"future of life", "partout"),
        "Center for AI Safety": (r"center for ai safety", "partout"),
    },
}


def norm(s):
    """Lowercase, accents stripped: « Contrôle » and « controle » match alike."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower()


def ia_proche(texte, debut, fin):
    zone = texte[max(0, debut - FENETRE):fin + FENETRE]
    return re.search(IA, norm(zone)) is not None


def analyser(brut):
    """(parle_ia, {famille: [mots-clés trouvés]}) pour un passage."""
    n = norm(brut)
    familles = {}
    for famille, mots in FAMILLES.items():
        for mot, (rx, mode) in mots.items():
            texte = brut if mode.startswith("casse") else n
            for m in re.finditer(rx, texte):
                if mode.endswith("si_ia") and not ia_proche(texte, m.start(), m.end()):
                    continue
                familles.setdefault(famille, []).append(mot)
                break   # one hit is enough for this keyword
    return bool(re.search(IA, n)), familles


def decrire(familles):
    """« Famille : mot, mot ; Famille : mot » pour le CSV."""
    return " ; ".join(f"{f} : {', '.join(m)}" for f, m in familles.items())
