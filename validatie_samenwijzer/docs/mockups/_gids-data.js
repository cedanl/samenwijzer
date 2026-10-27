/* Gedeelde voorbeelddata + keuzelogica voor de mockups (geen echte data).
   Volgorde van de keuze: instelling → opleiding → leerweg → cohort.
   Eén mogelijkheid = automatisch gekozen (zoals de echte kiezer het cohort overslaat). */
window.GIDS = (() => {
  const SCHOLEN = ["Da Vinci College", "Rijn IJssel", "Deltion College", "ROC Nijmegen",
    "Graafschap College", "Talland", "KW1C", "Curio"];
  const OPLS = [
    {n: "Verzorgende IG",          lw: {BOL: [2023, 2024, 2025], BBL: [2024, 2025]}},
    {n: "Kok",                     lw: {BOL: [2024, 2025]}},
    {n: "Software developer",      lw: {BOL: [2023, 2024, 2025], BBL: [2025]}},
    {n: "Tandartsassistent",       lw: {BOL: [2025]}},
    {n: "Assistent horeca",        lw: {BOL: [2024, 2025], BBL: [2025]}},
    {n: "Mediavormgever",          lw: {BOL: [2023, 2025]}},
    {n: "Helpende Zorg & Welzijn", lw: {BOL: [2024, 2025], BBL: [2024]}},
    {n: "Bouwkunde",               lw: {BOL: [2023, 2024]}},
    {n: "Elektrotechniek",         lw: {BOL: [2025], BBL: [2025]}}
  ];
  const vind = n => OPLS.find(o => o.n === n);
  const opleidingen = s => OPLS.filter((_, i) => (i + SCHOLEN.indexOf(s)) % 3 !== 0).map(o => o.n);
  const leerwegen = o => Object.keys(vind(o).lw);
  const cohorten = (o, l) => vind(o).lw[l];

  const nieuw = () => ({school: null, opl: null, lw: null, coh: null, auto: {}});
  const autoCoh = sel => {
    if (!sel.lw) return;
    const c = cohorten(sel.opl, sel.lw);
    if (c.length === 1) { sel.coh = c[0]; sel.auto.coh = true; }
  };
  const zetSchool = (sel, v) => Object.assign(sel, {school: v, opl: null, lw: null, coh: null, auto: {}});
  const zetOpl = (sel, v) => {
    Object.assign(sel, {opl: v, lw: null, coh: null, auto: {}});
    const l = leerwegen(v);
    if (l.length === 1) { sel.lw = l[0]; sel.auto.lw = true; autoCoh(sel); }
  };
  const zetLw = (sel, v) => { Object.assign(sel, {lw: v, coh: null}); delete sel.auto.coh; autoCoh(sel); };
  const zetCoh = (sel, v) => { sel.coh = v; };
  const stappen = sel => [sel.school, sel.opl, sel.lw, sel.coh].filter(x => x !== null).length;
  const compleet = sel => stappen(sel) === 4;
  const label = sel => `${sel.school} · ${sel.opl} · ${sel.lw} ${sel.coh}`;
  const initialen = n => (n.includes(" ") ? n.split(" ").map(w => w[0]).join("") : n.slice(0, 2)).slice(0, 2).toUpperCase();

  const ANTWOORD = {
    tekst: "Ja. Aan het einde van je eerste studiejaar geeft je opleiding een bindend studieadvies. Dat advies is negatief als je onder de norm van 40 studiepunten blijft.",
    vindplaats: "Onderwijs- en examenregeling — artikel 4.3",
    citaat: "De student ontvangt aan het einde van het eerste jaar een <mark>bindend studieadvies</mark> indien minder dan 40 studiepunten zijn behaald.",
    vraag: "Krijg ik een bindend studieadvies als ik mijn punten niet haal?",
    vervolg: ["En als ik een vak mag herkansen?", "Wat zijn mijn opties bij een negatief advies?"]
  };
  const SUGGESTIES = ["Wanneer krijg ik een bindend studieadvies?", "Hoe vaak mag ik herkansen?", "Telt mijn stage mee?"];

  return {SCHOLEN, opleidingen, leerwegen, cohorten, nieuw, zetSchool, zetOpl, zetLw, zetCoh,
          stappen, compleet, label, initialen, ANTWOORD, SUGGESTIES};
})();
