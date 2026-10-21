"""Olo points at the shield button on the failure screen (from the 3rd death), all four languages here.

Same shape as olo_lines.R; the pool is "shield_tip" (olo.Olo.react)."""
from olo_lines_places import L

S = {
    "shield_tip": [
        [L("smug", "{n}. deneme. Kalkan diye bir şey duydun mu?", "Try {n}. Ever heard of a shield?",
           "Versuch {n}. Schon mal von einem Schild gehört?", "Intento {n}. ¿Has oído hablar de los escudos?"),
         L("thumbs_up", "Aşağıdaki mavi düğme. Basması bedava (bazen).", "The blue button below. Free to press (sometimes).",
           "Der blaue Knopf unten. Gratis (manchmal).", "El botón azul de abajo. Gratis (a veces).")],
        [L("think", "Aynı yerde ölüyorsun. Bir kalkan bu sefer seni kurtarır.", "Same spot every time. A shield saves you once.",
           "Immer dieselbe Stelle. Ein Schild rettet dich einmal.", "Siempre el mismo sitio. Un escudo te salva una vez.")],
        [L("idea", "Fikir: Kalkanla dene. Ben denedim, çalışıyor.", "Idea: retry with a shield. I tried it, it works.",
           "Idee: Versuch's mit Schild. Ich hab's getestet, es klappt.", "Idea: prueba con escudo. Yo lo probé y funciona.")],
        [L("flex", "Kalkan takınca bile havalı görünürsün.", "You look cooler with a shield on.",
           "Mit Schild siehst du sogar cooler aus.", "Con escudo hasta te ves más guay.")],
        [L("coffee", "Zor yerde bir kalkan, bir kahve gibi: iyi gelir.", "A shield at a hard spot is like coffee: it helps.",
           "Ein Schild an einer schweren Stelle ist wie Kaffee: hilft.", "Un escudo en un punto difícil es como un café: ayuda.")],
        [L("shrug", "Kalkan kullanmayan çok. Hepsi benim gibi kaybediyor.", "Most people never use shields. They lose like me.",
           "Die meisten nutzen nie Schilde. Sie verlieren wie ich.", "Casi nadie usa escudos. Pierden como yo.")],
    ],
}
