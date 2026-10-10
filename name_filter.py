"""Pilot names on the shared rankings: players may call themselves anything (the server only limits letters and
length), but every viewer gets a filter for offensive names (on by default, switchable on the ranking) and can hide a
player or report a name - the user-generated-content safeguards the App Store and Google Play ask for."""
import config

# word roots, matched after normalising (upper case, Turkish letters folded, digits/symbols read as letters, spacing
# and punctuation removed); kept short and stem-like so suffixed forms are caught too
_ROOTS = (
    # Turkish
    "AMK", "AMQ", "AMINA", "AMCIK", "AMCK", "SIK", "SIKIM", "SIKER", "SIKTIR", "YARAK", "YARRAK", "YARRA", "OROSPU",
    "ORSPU", "PICI", "PIC", "GOT", "GOTVER", "GAVAT", "KAHPE", "IBNE", "PUSTU", "PUST", "SERFIL", "YAVSAK", "KALTAK",
    "SIKEY", "SIKIS", "SIKIK", "MK", "AQ",
    # English
    "FUCK", "FUK", "FCK", "SHIT", "BITCH", "CUNT", "DICK", "COCK", "PUSSY", "ASSHOLE", "BASTARD", "WHORE", "SLUT",
    "NIGG", "NIGA", "FAG", "RETARD", "PENIS", "VAGINA", "PORN", "SEX", "RAPE", "NAZI", "HITLER",
    # German / Spanish
    "SCHEISS", "FICK", "HURE", "FOTZE", "PUTA", "PUTO", "MIERDA", "COÑO", "CONO", "JODER", "CABRON", "PENDEJ", "VERGA",
)
# short roots that are only offensive as a whole word (else "MAL" would hit "NORMAL", "MK" every name with M+K ...)
_WHOLE_ONLY = {"MK", "AQ", "PIC", "GOT", "SIK", "SEX", "FUK", "CONO", "PUST"}
_FOLD = str.maketrans({"İ": "I", "I": "I", "Ş": "S", "Ğ": "G", "Ü": "U", "Ö": "O", "Ç": "C", "0": "O", "1": "I",
                       "3": "E", "4": "A", "5": "S", "7": "T", "8": "B", "@": "A", "$": "S", "!": "I"})


def _norm(text):
    return "".join(ch for ch in str(text).upper().translate(_FOLD) if ch.isalpha())


def _words(text):
    out, cur = [], ""
    for ch in str(text).upper().translate(_FOLD):
        if ch.isalpha():
            cur += ch
        elif cur:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def is_offensive(name):
    n = _norm(name)
    if not n:
        return False
    words = set(_words(name))
    for root in _ROOTS:
        r = _norm(root)
        if root in _WHOLE_ONLY:
            if r in words or n == r:
                return True
        elif r in n:
            return True
    return False


def masked(name):
    """First letter, then stars: S****."""
    s = str(name)
    return (s[:1] + "*" * max(3, len(s) - 1)) if s else s


def shown_name(save_mgr, player_id, name):
    """What this viewer sees for another player's name on a ranking / ghost label."""
    if player_id and player_id in hidden_players(save_mgr):
        return None                                   # the row shows the "hidden pilot" label
    if filter_on(save_mgr) and is_offensive(name):
        return masked(name)
    return name


def filter_on(save_mgr):
    return bool(save_mgr.settings.get("hide_bad_names", True)) and not config.get("names_unfiltered", False)


def hidden_players(save_mgr):
    h = save_mgr.data.get("hidden_players")
    return h if isinstance(h, list) else []


def set_hidden(save_mgr, player_id, hidden):
    h = [x for x in hidden_players(save_mgr) if x != player_id]
    if hidden:
        h.append(player_id)
    save_mgr.data["hidden_players"] = h[-200:]
    save_mgr.save()
