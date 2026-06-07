# Plan: Graceful degradation via webzoeken op de instellings-website

*Subproject: `validatie_samenwijzer` — "De digitale gids" / `digitale-gids.fly.dev`*
*Status: **Fase 1 geïmplementeerd + live op productie** (PR #164, 2026-06-07). Fase 2 & 3 open.*
*Datum: 2026-06-06 (plan), 2026-06-07 (Fase 1)*

> **Afwijkingen t.o.v. dit plan bij de Fase 1-implementatie:**
> - **Tool-versie `web_search_20250305`** i.p.v. `web_search_20260209` (dynamic filtering):
>   die laatste vereist de code-execution-tool, wat een tweede sandbox + de "verwart het
>   model"-valkuil introduceert. De basisversie ondersteunt `allowed_domains` + `max_uses`
>   volledig. Dynamic filtering is naar Fase 3 verschoven.
> - **`max_uses=3`** (niet `1`): documentatie-aanbeveling voor latency-gevoelige lookups;
>   bondig genoeg voor het 30s-streamcontract.
> - **Domeinmap geverifieerd** (uit OER-content + webcheck): `utrecht = mboutrecht.nl`
>   (MBO Utrecht, **niet** ROC MN/rocmn.nl) en `talland = talland.nl`.
> - Beide paden live geverifieerd op `digitale-gids.fly.dev` (Da Vinci, crebo 25882):
>   BSA-vraag → ⚠️-balk + `Bron:` met davinci.nl-URL's; kerntaken-vraag → normale
>   OER-citatie zonder balk (geen regressie/outage).

## 1. Probleemstelling & doel

De OER-chat beantwoordt vragen **uitsluitend** uit de geladen documenten (OER + KD + skills + instellingsbrede regelingen). Beide systeemtemplates sluiten af met *"Beantwoord uitsluitend op basis van deze bronnen — nooit vanuit eigen kennis. Als de informatie in geen van de bronnen staat, zeg dat dan expliciet."* Het gevolg: zodra een onderwerp niet in de docs staat (bv. inschrijfdeadlines, open dagen, contactgegevens, specifieke vakroosters), krijgt de gebruiker een doodlopend *"dit staat niet in de OER"* zonder verder hulp. **Doel:** graceful degradation — als de geladen bronnen tekortschieten, mag de assistent gericht op de **website van de betreffende instelling** zoeken via de server-side web search tool van Claude, en het webantwoord teruggeven met een **duidelijke markering** ("niet uit de OER — op internet gevonden") + bron-URL, zónder de juridische OER-citatieplicht te ondermijnen.

## 2. Trigger: hoe detecteren we "antwoord staat niet in de docs"?

| Optie | Werking | Voordeel | Nadeel |
|---|---|---|---|
| **A. Web search tool altijd beschikbaar; model beslist zelf** | `tools=[web_search]` staat in elke `genereer_antwoord`-call; het systeemprompt instrueert: zoek alléén als de bronnen tekortschieten | **Eén round-trip**; prompt-cache blijft intact (tool-blok is stabiele prefix vóór `system`); minste code | Model-discipline nodig; web search is met system-prompt aanwezig low-recall (zie §3) → expliciete "zoek-eerst"-instructie vereist |
| B. Sentinel-marker in antwoord + tweede call | Model schrijft bv. `[GEEN-BRON]`, app doet daarna een tweede call mét tool | Expliciete controle | **Twee round-trips** (latency ~verdubbeld, kan 30s-contract raken); tweede call heeft andere prefix → **volledige OER-context opnieuw betaald** |
| C. Tweede LLM-beoordeling (judge) | Aparte call beoordeelt of het OER-antwoord volstaat | Scheidbare logica | Idem B: extra latency + kosten; over-engineering |
| D. Tool conditioneel toevoegen op fallback | Tool alleen meesturen bij vermoeden tekortschieten | Tool niet altijd actief | Verandert de prefix per request → **breekt prompt-cache** op de dure OER-prefix |

**Aanbeveling: Optie A.** De doorslaggevende constraint is **prompt-caching**. De cache-volgorde is `tools` → `system` → `messages`; de app cachet de volledige OER-systeemprompt met 1h-TTL (dat is de dure prefix). Alleen bij een **altijd-aanwezig** tool-blok blijft die cache behouden én blijft het bij één round-trip binnen het 30s-contract. Opties B/C/D introduceren een tweede call of een wisselende prefix → OER-context per fallback opnieuw gebilld + dubbele latency. A wint dus op kosten én eenvoud.

## 3. Architectuurkeuze: Anthropic web search tool vs. eigen tool-use

**Aanbeveling: de server-side `web_search`-tool van Anthropic.**

- **Geciteerde bronnen gratis:** de server-side tool geeft bron-URL's als citaties terug, draait volledig op Anthropic-infra (Claude formuleert query, fetcht, verwerkt) — geen eigen sleutelbeheer, geen extra dependency.
- **Eigen tool-use met externe search-API (Tavily/SerpAPI/Brave) wordt afgewezen:** dat vereist een extra API-key + secret-management, een handmatige tool-loop in `chat.py` (de enige streaming-module), en levert geen ingebouwde citaties. Strijdig met "kleinste oplossing die het probleem afdekt".
- **Scoping tot de instelling-website:** via de tool-parameter `allowed_domains` (per instelling, bv. `["rocmn.nl"]` voor ROC Utrecht). Dit houdt de zoekresultaten op de officiële schoolsite en beperkt hallucinatie/verkeerde-site-risico.

> **Te verifiëren vóór implementatie** (niet uit geheugen invullen): de exacte tool-versie (`web_search_20250305` vs nieuwer), het schema — parameternaam/-plaatsing van `allowed_domains`, en of `max_uses` bestaat. Raadpleeg de claude-api skill / WebFetch de actuele web-search-tool-docs. Stel `max_uses` laag in (1–2) om de server-side sampling-loop (`stop_reason: pause_turn`) niet te raken. Eén scoped-domain-zoekopdracht haalt die limiet realistisch niet.

## 4. Hoe wordt het instelling-domein bepaald?

**Voorstel: een code-constante (mapping `naam` → domein), parallel aan `ingest._INSTELLINGEN`. Géén DB-kolom in Fase 1.** De `instellingen`-tabel heeft geen domein-veld; een kolom toevoegen is een migratie die we niet nodig hebben voor een handvol bekende instellingen.

```python
# chat.py (voorstel)
_INSTELLING_DOMEINEN: dict[str, str] = {
    "aeres": "aeres.nl",
    "curio": "curio.nl",
    "davinci": "davinci.nl",
    "deltion": "deltion.nl",
    "kwic": "kw1c.nl",
    "rijn_ijssel": "rijnijssel.nl",
    "talland": "talland.nl",        # te verifiëren
    "utrecht": "rocmn.nl",          # ROC Utrecht / ROC Midden Nederland — te verifiëren
}
```

> De exacte domeinen moeten **handmatig geverifieerd** worden (zie open vragen) — een verkeerd domein scoopt de zoekopdracht naar de verkeerde site. De map sluit aan op de bestaande "drie hardgecodeerde instelling-lijsten"-conventie.

**Wiring-gotcha (geverifieerd in de code):** de domeinmap sleutelt op de korte `naam`-key. Die is per pagina verschillend beschikbaar:

- **`0_oer_vraag.py`** (publiek): heeft `naam` — de kandidaat-rij komt uit `get_alle_oers_met_instelling` (selecteert `i.naam`). Bij multi-OER moet `allowed_domains` de **unie** van de domeinen van alle geladen instellingen worden.
- **`1_oer_assistent.py`** (student) en **`5_begeleidingssessie.py`** (mentor): **hebben alleen `instelling` = `display_naam` in session_state**, niet de korte `naam` (zie `main.py` regels 78/106; de OER-query selecteert wél `display_naam` maar niet `i.naam`). **Voorkeur: `i.naam` toevoegen aan de bestaande OER-query in `main.py` en als `instelling_naam` in session_state zetten** — minimaal en robuust.

## 5. Citatie & markering — bescherming van de juridische citatieplicht

De webzoek-fallback is een **andere, minder betrouwbare bron** en moet visueel én tekstueel scherp gescheiden blijven van de OER-citaties. De templates zijn het *load-bearing artefact*; de template-edit moet:

1. **De absolute slotregel vervangen** door een conditionele: bronnen blijven leidend en primair, maar als geen enkele geladen bron het onderwerp behandelt, mág de webzoek-tool gebruikt worden — uitsluitend op de meegegeven schoolwebsite.
2. **Een expliciete "zoek-eerst-bij-tekortschieten"-instructie** toevoegen (recall-herstel).
3. **Een eigen, aparte citatieformat voor webresultaten** voorschrijven, mét verplichte zichtbare disclaimer-inleider, vólledige bron-URL, en een **verbod** om webclaims te vermengen met OER-stijl sectie-/artikel-citaten of vindplaatsen te verzinnen.

**Concrete disclaimer-/citatie-tekst voor in de template:**

> Als het antwoord in géén van de bovenstaande bronnen (OER, instellingsbrede regelingen, kwalificatiedossier, skills) staat, mag je de webzoek-functie gebruiken — uitsluitend op de officiële website van de instelling. Begin een webantwoord ALTIJD met de waarschuwing:
> **"⚠️ Let op: dit staat niet in de officiële studiegids (OER). Onderstaande informatie komt van de website van de school en kan verouderd of minder bindend zijn — controleer het bij twijfel bij je opleiding."**
> Vermeld bij elke claim uit een webbron de volledige bron-URL. Geef webinformatie NOOIT de vorm van een OER-citaat (geen "Volgens de OER", geen sectie-, artikel- of paginanummer) — verzin nooit een vindplaats. De OER blijft de juridisch bindende bron; webinformatie is aanvullend en indicatief.

Zo blijft de bestaande blockquote-pull-quote-CSS gereserveerd voor de echte juridische citaten, en steekt het webantwoord er met de waarschuwingsbalk visueel boven uit.

## 6. Kosten- & latency-impact + effect op prompt-caching

- **Caching:** ongewijzigd zolang het tool-blok een stabiele prefix is en op elke call identiek meegestuurd wordt (zelfde JSON, zelfde volgorde, vóór `system`). **Let op:** `allowed_domains` verschilt per instelling → de prefix verschilt per instelling. Dat is geen probleem (de OER-cache is per sessie/instelling toch al uniek), maar bewaak dat de map **deterministisch gesorteerd** is en niet per request herordent (anders silent cache-miss). Verifieer met `usage.cache_read_input_tokens`.
- **Kosten:** geen extra prompt-tekens in het systeemblok (alleen de tool-definitie, ~enkele honderden tokens, éénmalig in de cache). Web search wordt **per zoekopdracht** gebilld + de opgehaalde paginatekst telt als extra input-tokens, alléén in beurten waarin daadwerkelijk gezocht wordt. Verreweg de meeste vragen worden uit de OER beantwoord → geen webkosten. Meet na implementatie met `scripts/meet_token_kosten.py`.
- **Latency:** een webzoek voegt server-side seconden toe (query + fetch + filtering) vóór de tekststroom begint. Binnen het 30s read-timeout-contract bij één scoped search realistisch; bewaak met `max_uses=1`.

## 7. Risico's & mitigaties

| Risico | Mitigatie |
|---|---|
| **Hallucinatie / verzonnen webfeiten** | `allowed_domains` scoopt naar de officiële site; template eist volledige bron-URL per claim; server-side citaties koppelen claims aan echte pagina's |
| **Verkeerde site** | Handmatig geverifieerde domeinmap; geen open zoeken (alleen `allowed_domains`) |
| **Vermenging met juridische OER-citatie** | Aparte citatieformat + verplichte waarschuwingsbalk + verbod op OER-stijl vindplaatsen bij web (zie §5) |
| **Verouderde info** | Disclaimer-balk waarschuwt expliciet "kan verouderd zijn — controleer bij je opleiding" |
| **AVG/privacy** | Web search stuurt de (geparafraseerde) vraag naar Anthropic's zoek-infra. Géén PII in de query borgen; **scope-vraag voor het team** of dit eerst alléén op de publieke (anonieme) pagina aan moet |
| **Cache-miss door wisselende tool-prefix** | Domeinmap deterministisch sorteren; `usage.cache_read_input_tokens` monitoren |
| **`pause_turn` breekt stream** | `max_uses=1` op de tool; resume-loop uitgesteld naar latere fase |

## 8. Gefaseerde implementatie

**Fase 1 — minimaal werkend op de publieke pagina (`0_oer_vraag.py`)** — ✅ GEDAAN (PR #164)
- Domeinmap-constante in `chat.py`; helper die uit geladen OER-items de unie van domeinen afleidt.
- `genereer_antwoord` (en `bouw_gecombineerd_systeem`/`bouw_systeem`-signatuur indien nodig) uitbreiden met de web search-tool + `allowed_domains` + `max_uses=1`.
- Beide templates aanpassen (slotregel + zoek-eerst-instructie + web-citatieformat per §5).
- *Succescriterium:* op `0_oer_vraag` een vraag stellen die aantoonbaar **niet** in de OER staat (bv. "wanneer is de eerstvolgende open dag?") → antwoord begint met de waarschuwingsbalk, bevat een bron-URL op het schooldomein, en een OER-vraag in dezelfde sessie geeft nog steeds een correct juridisch citaat (regressie-check). Geverifieerd via UI-smoke-test (chrome-devtools-mcp, publiek account).

**Fase 2 — student- & mentor-pagina's**
- `main.py`: `i.naam` toevoegen aan de OER-query en als `instelling_naam` in session_state zetten (student + mentor).
- `1_oer_assistent.py` en `5_begeleidingssessie.py` de domein-scoping laten meegeven.
- *Succescriterium:* ingelogde student (account uit seed) krijgt voor een niet-in-OER-vraag een gemarkeerd webantwoord op het juiste schooldomein; UI-smoke-test per rol.

**Fase 3 — verfijning (optioneel, uitgesteld)**
- Structurele citatieblokken uit de server-side response renderen (i.p.v. alleen URL-in-tekst).
- `pause_turn`-resume-loop indien fallbacks complexere zoekopdrachten blijken te vergen.
- Domeinen eventueel naar de DB als het aantal instellingen groeit.
- *Succescriterium:* citaties renderen als klikbare bronkaartjes; meting met `scripts/meet_token_kosten.py` bevestigt acceptabele meerkosten.

## 9. Open vragen voor gebruiker/team

1. **Scope publiek vs. login:** webfallback eerst alléén op de **publieke** pagina (anoniem, lager AVG-risico), of meteen ook achter login?
2. **Domeinverificatie:** kloppen de voorgestelde domeinen, en zijn subdomeinen nodig (bv. `mbo.…`, `student.…`)?
3. **Welke onderwerpen** zijn legitiem voor webfallback (open dagen, contact, inschrijven) en welke moeten bewust *geweigerd* blijven omdat ze juridisch bindend horen te zijn (examinering, BSA) en dus alleen uit de OER mogen komen?
4. **AVG/vraagtekst:** akkoord dat de (mogelijk geparafraseerde) studentvraag naar Anthropic's zoek-infra gaat? Filter/waarschuwing op PII in de vraag?
5. **Kosten-plafond:** acceptabele meerkosten per fallback-beurt, en moet web search achter een feature-flag (zoals `BEHEER_ENABLED`) staan voor gefaseerde uitrol?
