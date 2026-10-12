// Descarga el iCal de Airbnb y escribe casa-pena/reservas.json con solo las fechas
// de entrada y salida, sumando las reservas de casa-pena/reservas-manuales.json.
// Uso: AIRBNB_ICAL=<url> node .github/scripts/sync-airbnb.mjs
import { readFile, writeFile } from 'node:fs/promises';

const ICAL_URL = process.env.AIRBNB_ICAL;
const OUT = 'casa-pena/reservas.json';
const MANUAL = 'casa-pena/reservas-manuales.json';

if (!ICAL_URL) throw new Error('Falta la variable AIRBNB_ICAL.');

const res = await fetch(ICAL_URL, { headers: { 'User-Agent': 'casa-pena-sync' } });
if (!res.ok) throw new Error(`Airbnb respondió ${res.status}.`);
const ics = await res.text();
// Si Airbnb devuelve otra cosa (error, página de login), no tocamos el calendario.
if (!ics.includes('BEGIN:VCALENDAR')) throw new Error('La respuesta no es un calendario iCal.');

// Las líneas largas del iCal se parten en varias que empiezan con espacio: se vuelven a unir.
const lines = ics.replace(/\r?\n[ \t]/g, '').split(/\r?\n/);
const toISO = v => `${v.slice(0, 4)}-${v.slice(4, 6)}-${v.slice(6, 8)}`;

const airbnb = [];
let ev = null;
for (const line of lines) {
  if (line === 'BEGIN:VEVENT') ev = {};
  else if (line === 'END:VEVENT') {
    if (ev.entrada && ev.salida) airbnb.push(ev);
    ev = null;
  } else if (ev) {
    const m = line.match(/^(DTSTART|DTEND)[^:]*:(\d{8})/);
    if (m) ev[m[1] === 'DTSTART' ? 'entrada' : 'salida'] = toISO(m[2]);
  }
}

let manuales = [];
try {
  manuales = JSON.parse(await readFile(MANUAL, 'utf8')).reservas || [];
} catch (e) {
  if (e.code !== 'ENOENT') throw e;
}

const hoy = new Date().toISOString().slice(0, 10);
const vistos = new Set();
const reservas = [...airbnb, ...manuales]
  .map(({ entrada, salida }) => ({ entrada, salida }))
  .filter(r => /^\d{4}-\d{2}-\d{2}$/.test(r.entrada) && /^\d{4}-\d{2}-\d{2}$/.test(r.salida))
  .filter(r => r.salida > r.entrada && r.salida > hoy)
  .sort((a, b) => a.entrada.localeCompare(b.entrada) || a.salida.localeCompare(b.salida))
  .filter(r => {
    const k = `${r.entrada}/${r.salida}`;
    return !vistos.has(k) && vistos.add(k);
  });

const data = {
  _instrucciones: 'Archivo generado automáticamente cada hora desde el calendario de Airbnb. No lo edites a mano: agrega las reservas que no vienen de Airbnb en reservas-manuales.json.',
  reservas,
};
const json = `{\n  "_instrucciones": ${JSON.stringify(data._instrucciones)},\n  "reservas": [\n${reservas
  .map(r => `    ${JSON.stringify(r).replace(/,/g, ', ').replace(/:/g, ': ')}`)
  .join(',\n')}\n  ]\n}\n`;

await writeFile(OUT, json);
console.log(`${airbnb.length} eventos de Airbnb, ${manuales.length} manuales → ${reservas.length} reservas vigentes.`);
