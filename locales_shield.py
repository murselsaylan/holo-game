"""Shield button of the failure screen, the HUD's free tag and the toast (1.0.9), merged into locales.STRINGS."""

SHIELD = {
    "tr": {"shield_retry_stock": "KALKANLA DENE  (elinde {n})", "shield_retry_free": "KALKANLA DENE: BEDAVA",
           "shield_retry_buy": "KALKAN AL + DENE: {cost}", "shield_retry_need": "KALKAN: {cost} ELMAS GEREK",
           "shield_free_tag": "BEDAVA", "shield_short_toast": "Kalkan için elmas yetmiyor, aşağıdan elmas al"},
    "en": {"shield_retry_stock": "RETRY WITH SHIELD  (you have {n})", "shield_retry_free": "RETRY WITH SHIELD: FREE",
           "shield_retry_buy": "BUY SHIELD + RETRY: {cost}", "shield_retry_need": "SHIELD NEEDS {cost} GEMS",
           "shield_free_tag": "FREE", "shield_short_toast": "Not enough diamonds for a shield, get some below"},
    "de": {"shield_retry_stock": "MIT SCHILD NOCHMAL  (du hast {n})", "shield_retry_free": "MIT SCHILD NOCHMAL: GRATIS",
           "shield_retry_buy": "SCHILD KAUFEN + NOCHMAL: {cost}", "shield_retry_need": "SCHILD: {cost} DIAMANTEN NÖTIG",
           "shield_free_tag": "GRATIS", "shield_short_toast": "Zu wenig Diamanten für ein Schild, unten kaufen"},
    "es": {"shield_retry_stock": "REINTENTAR CON ESCUDO  (tienes {n})", "shield_retry_free": "REINTENTAR CON ESCUDO: GRATIS",
           "shield_retry_buy": "COMPRAR ESCUDO + REINTENTAR: {cost}", "shield_retry_need": "ESCUDO: FALTAN {cost} DIAMANTES",
           "shield_free_tag": "GRATIS", "shield_short_toast": "Diamantes insuficientes para un escudo, compra abajo"},
}

ENDLESS = {"tr": "Kalkanlı tırmanış için elmas yetmiyor", "en": "Not enough diamonds for a shielded climb", "de": "Zu wenig Diamanten für einen Aufstieg mit Schild", "es": "Diamantes insuficientes para una subida con escudo"}
for _l, _t in ENDLESS.items():
    SHIELD[_l]["shield_short_toast_endless"] = _t
