"""Olo's lines for the shared weekly goal and the level of the week (1.0.9), all four languages; merged into olo_lines.R.
Kinds: crowd_t1 / crowd_t2 / crowd_t3 (a tier the whole player base reached is waiting for the pilot), crowd_go (a goal
is running and the pilot has not added anything yet), wlevel_new ({lvl} is the level of the week, {pct} cleared it),
wlevel_clear (cleared it, the reward waits)."""
from olo_lines_places import L

C = {
    "crowd_t1": [
        [L("confetti", "İlk eşik geçildi! Hep birlikte. Ben de katkı yaptım. (Yaptım.)", "First mark reached! All together. I helped too. (I did.)",
           "Erste Marke geschafft! Alle zusammen. Ich hab auch geholfen. (Hab ich.)", "¡Primera marca! Todos juntos. Yo también ayudé. (Sí.)")],
        [L("clap", "%33! Yıldızlarınız işe yarıyor.", "33%! Your stars are working.",
           "33%! Eure Sterne wirken.", "¡33%! Vuestras estrellas funcionan.")],
    ],
    "crowd_t2": [
        [L("party", "%66! Ödül seni bekliyor, git al!", "66%! Your reward is waiting, go grab it!",
           "66%! Deine Belohnung wartet, hol sie dir!", "¡66%! Tu recompensa te espera, ¡cógela!")],
        [L("flex", "Herkes çalışıyor, ben de motive ediyorum.", "Everybody's working, I'm motivating.",
           "Alle arbeiten, ich motiviere.", "Todos trabajan, yo motivo.")],
    ],
    "crowd_t3": [
        [L("hooray", "HEDEF TAMAM! Hepiniz harikasınız!", "GOAL DONE! You're all amazing!",
           "ZIEL ERREICHT! Ihr seid alle großartig!", "¡META CUMPLIDA! ¡Sois increíbles!")],
        [L("party", "%100! Bugün pasta var. Sanal ama.", "100%! Cake today. A virtual one, though.",
           "100%! Heute gibt's Kuchen. Einen virtuellen.", "¡100%! Hoy hay tarta. Virtual, eso sí.")],
    ],
    "crowd_go": [
        [L("idea", "Ortak hedefte yıldız toplayalım! Herkes bir yıldız, hepimiz bir ödül.", "Let's collect stars for the team goal! One star each, a prize for all.",
           "Sammeln wir Sterne fürs Teamziel! Ein Stern pro Kopf, ein Preis für alle.", "¡Juntemos estrellas para la meta común! Una cada uno, premio para todos.")],
        [L("gamer", "Bu hafta hedef büyük. Parmaklar hazır mı?", "Big goal this week. Fingers ready?",
           "Großes Ziel diese Woche. Finger bereit?", "Gran meta esta semana. ¿Dedos listos?")],
    ],
    "wlevel_new": [
        [L("smug", "Haftanın bölümü {lvl}. Pilotların %{pct}'i geçti. Sen?", "Level of the week: {lvl}. {pct}% of pilots cleared it. You?",
           "Level der Woche: {lvl}. {pct}% der Piloten haben es geschafft. Du?", "Nivel de la semana: {lvl}. El {pct}% lo superó. ¿Y tú?")],
        [L("devil", "{lvl}. bölüm bu hafta sahnede. Zor mu zor.", "Level {lvl} is on stage this week. Hard as nails.",
           "Level {lvl} steht diese Woche im Rampenlicht. Knallhart.", "El nivel {lvl} es la estrella esta semana. Durísimo.")],
    ],
    "wlevel_clear": [
        [L("thumbs_up", "Haftanın bölümünü geçtin! Ödülünü almayı unutma.", "You cleared the level of the week! Don't forget your reward.",
           "Level der Woche geschafft! Vergiss deine Belohnung nicht.", "¡Superaste el nivel de la semana! No olvides tu recompensa.")],
    ],
}
