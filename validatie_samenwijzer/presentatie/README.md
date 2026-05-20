# Presentatie — Validatie Samenwijzer

Zelfstandige Slidev-presentatie (CEDA/Npuls-huisstijl) over de ontwikkeling van de Validatie
Samenwijzer: van klassieke RAG (vector store) naar full-document context.

Deze map is volledig zelfstandig — thema en assets zitten erin. Geen `clidev`-repo nodig.

## Draaien (vereist Node)

Alles in één commando (installeert indien nodig en start):

```bash
cd validatie_samenwijzer/presentatie
./start.sh                  # opent op http://localhost:3030
```

Of handmatig:

```bash
npm install                 # eenmalig per machine
npm run dev                 # opent op http://localhost:3030
```

- Presentatormodus (met speaker-notes): http://localhost:3030/presenter
- Navigeren: pijltjestoetsen / spatiebalk. `P` = presenter, `O` = overzicht, `F` = fullscreen.

## Exporteren (optioneel)

```bash
npm install -D playwright-chromium && npx playwright install chromium
npm run export              # PDF
npm run build              # statische site in dist/
```

Slidebestand: `260520_validatie_samenwijzer.md`.
