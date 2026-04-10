# EduPulse Huisstijl

Pas de volgende huisstijl toe op alle Streamlit-pagina's en -componenten die je schrijft of aanpast voor de EduPulse / CEDAssistentie app. Gebruik uitsluitend de kleuren, typografie, componenten en patronen die hieronder staan — voeg geen andere stijlen, kleuren of libraries toe.

---

## Kleurenpalet

| Naam              | Hex        | Gebruik                                              |
|-------------------|------------|------------------------------------------------------|
| Terracotta        | `#c8785a`  | Slider-accent, decoratieve accenten                  |
| Roze achtergrond  | `#f0d4d4`  | App-achtergrond startscherm, bottom bar startscherm  |
| Roze licht        | `#fae8e8`  | Header hoofdscherm, bottom bar hoofdscherm, hover    |
| Roze upload       | `#f2e4e4`  | Achtergrond file uploader                            |
| Zwart             | `#1a1a1a`  | Knoppen (primair), tekst, borders                    |
| Wit               | `#ffffff`  | Kaartachtergrond, actieve nav-pill                   |
| Grijs donker      | `#333`     | Body- en subtekst                                    |
| Grijs middel      | `#888`     | Terug-knop, secundaire tekst                         |
| Grijs licht       | `#999`     | "Niet beschikbaar"-tekst (cursief)                   |
| Rood risico       | `#c0392b`  | Risiconiveau HOOG, foutmeldingen                     |
| Oranje risico     | `#e67e22`  | Risiconiveau MATIG, datakwaliteitswaarschuwing       |
| Groen risico      | `#27ae60`  | Risiconiveau LAAG                                    |
| Badge groen bg    | `#e8f5e9`  | Achtergrond instellingsmodel-badge                   |
| Badge groen tekst | `#2e7d32`  | Tekst instellingsmodel-badge                         |

---

## Typografie

**Font**: General Sans via Fontshare. Altijd laden via:
```css
@import url('https://api.fontshare.com/v2/css?f[]=general-sans@400,500,600,700&display=swap');
font-family: 'General Sans', sans-serif;
```

| Element              | font-size  | font-weight | Overige                              |
|----------------------|------------|-------------|--------------------------------------|
| H1 (paginatitel)     | 3.2rem     | 600         | line-height: 1.15                    |
| H3 (kaartitel)       | standaard  | 500         | margin: 0, padding: 6px 0            |
| Body                 | 1rem       | 400         | color: #333, line-height: 1.6        |
| Subtekst / intro     | 1.3rem     | 500         | color: #333                          |
| Knoplabels / caps    | 13–17px    | 700         | letter-spacing: 0.05–0.07em          |
| Kleine labels        | 12–15px    | 500–600     |                                      |
| Niet-beschikbaar     | —          | normaal     | cursief, color: #999                 |

Alle knoppen en nav-labels zijn **volledig hoofdletters** (uppercase in de tekst, niet via CSS `text-transform`).

---

## Componenten

### Primaire knop (zwart pill)
```css
background-color: #1a1a1a;
color: white;
border-radius: 50px;
font-weight: 700;
letter-spacing: 0.07em;
border: none;
font-size: 13–17px;
```
Hover: `background-color: #333`. Disabled: `background-color: #aaa`.

### Secundaire knop / pill-knop
```css
background-color: white;
border-radius: 50px;
border: none;
box-shadow: 0 8px 24px rgba(0,0,0,0.20);
font-size: 15px;
```
Hover: `background-color: #e8c8c8`, `box-shadow: 0 10px 28px rgba(0,0,0,0.25)`.

### Navigatietabs (actief / inactief)
```css
/* Actief */
background: white;
border: 2px solid #1a1a1a;
color: #1a1a1a;
border-radius: 50px;
font-weight: 700;
font-size: 13px;
letter-spacing: 0.07em;

/* Inactief */
background: transparent;
border: none;
color: #1a1a1a;
border-radius: 50px;
font-size: 13px;
font-weight: 500;
letter-spacing: 0.05em;
```

### Terug-knop
```css
background: transparent;
border: none;
color: #888;
font-size: 13px;
```
Hover: `color: #1a1a1a`.

### Witte kaart (content-container)
```css
background: white;
border-radius: 20px;
border: none;
box-shadow: 0 4px 32px rgba(180,100,90,0.13);
padding: 4px 8px;
```

### Selectbox als pill
```css
border-radius: 50px;
border: 2px solid #1a1a1a;
font-size: 12–13px;
font-weight: 600;
letter-spacing: 0.03–0.05em;
background: white;
padding-left: 16px;
```
Student-selectbox: ook `text-transform: uppercase`.

### Zoek-input
```css
border: 2px solid #1a1a1a;
border-radius: 50px;
font-size: 15px;
height: 48px;
background: white;
```
Label verbergen: `label_visibility="collapsed"`.

### File uploader
```css
background: #f2e4e4;
border-radius: 12px;
padding: 4px 12px;
/* Dropzone: geen border, transparant */
/* Knop in dropzone: zelfde stijl als primaire knop */
```

### Slider
```css
/* Thumb en tick-accenten */
background-color: #c8785a;
border-color: #c8785a;
color: #c8785a; /* tick labels */
```

### Download-knop
Identiek aan primaire knop + `white-space: nowrap`, `width: 100%`.

### Instellingsmodel-badge (inline HTML)
```html
<span style='font-size:0.7rem; background:#e8f5e9; color:#2e7d32;
             border-radius:4px; padding:2px 6px; vertical-align:middle;
             font-weight:500;'>instellingsmodel</span>
```

### Risiconiveau-tekst (inline HTML)
```html
<span style='color:#c0392b; font-weight:700;'>HOOG</span>   <!-- > 65% -->
<span style='color:#e67e22; font-weight:700;'>MATIG</span>  <!-- 35–65% -->
<span style='color:#27ae60; font-weight:700;'>LAAG</span>   <!-- < 35% -->
```

### Niet-beschikbaar (inline HTML)
```html
<i style='color:#999;'>niet beschikbaar</i>
```

### Datakwaliteitswaarschuwing (inline HTML)
```html
<!-- Onvoldoende data (kritiek) -->
<span style='color:#c0392b;'>⚠️ <b>Datakwaliteit:</b> ... tekst ...</span>

<!-- Gedeeltelijk geïmputeerd (informatief) -->
<span style='color:#e67e22;'>ℹ️ ... tekst ...</span>
```

---

## Layout

- **Max-breedte**: 900px, gecentreerd (`max-width: 900px; margin: 0 auto`)
- **Padding**: `padding-top: 0 !important; padding-bottom: 2rem`
- **Kolom-verhouding centraal** (startscherm): `[1, 4, 1]`
- **Header** (hoofdscherm): sticky, `background-color: #fae8e8`, `z-index: 9999`
- **Bottom bar** (startscherm): `background-color: #f0d4d4`
- **Bottom bar** (hoofdscherm): `background-color: #fae8e8`
- **Sidebar**: altijd verborgen (`[data-testid="stSidebarCollapsedControl"] { display: none }`)
- **Toolbar en decoration**: verborgen op hoofdscherm

---

## App-achtergrond per scherm

| Scherm      | Kleur      |
|-------------|------------|
| Startscherm | `#f0d4d4`  |
| Hoofdscherm | `#f0d4d4`  |
| Header      | `#fae8e8`  |

---

## CSS-sjabloon (kopieer als startpunt)

```python
CSS = """
<style>
@import url('https://api.fontshare.com/v2/css?f[]=general-sans@400,500,600,700&display=swap');

[data-testid="stApp"]      { background-color: #f0d4d4; font-family: 'General Sans', sans-serif; font-weight: 500; }
[data-testid="stHeader"]   { background-color: #fae8e8 !important; }
[data-testid="stSidebarCollapsedControl"] { display: none; }
.block-container           { padding-top: 0 !important; max-width: 900px; margin: 0 auto; }

[data-testid="stBaseButton-primary"] {
    background-color: #1a1a1a !important;
    color: white !important;
    border-radius: 50px !important;
    font-weight: 700 !important;
    border: none !important;
    letter-spacing: 0.07em !important;
}
[data-testid="stBaseButton-primary"]:hover { background-color: #333 !important; }

[data-testid="stBaseButton-secondary"] {
    background-color: white !important;
    border-radius: 50px !important;
    border: none !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.20) !important;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    background: white !important;
    border-radius: 20px !important;
    border: none !important;
    box-shadow: 0 4px 32px rgba(180,100,90,0.13);
}

[data-testid="stBottom"]               { background-color: #fae8e8 !important; }
[data-testid="stBottomBlockContainer"] { background-color: #fae8e8 !important; }
</style>
"""
```

---

## Gebruik

- Importeer altijd de kleurconstanten uit `frontend/styles.py`:
  ```python
  from frontend.styles import TERRACOTTA, ROZE_BG, ROZE_LICHT, START_CSS, MAIN_CSS
  ```
- Schrijf alle gebruikersgerichte tekst in **het Nederlands**.
- Gebruik `st.markdown(..., unsafe_allow_html=True)` voor inline HTML-stijlen.
- Gebruik `st.container(border=True)` voor witte kaarten — de CSS past de stijl automatisch toe via `stVerticalBlockBorderWrapper`.
- Vermijd `st.sidebar` — de app heeft geen zijbalk.
