import fetch from 'node-fetch';
import * as cheerio from 'cheerio';

export default async function handler(req, res) {
  // CORS
  const allowOrigin = process.env.CORS_ORIGIN || '*'; // Ex.: 'https://el-teu-front.vercel.app'
  res.setHeader('Access-Control-Allow-Origin', allowOrigin);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();

  if (req.method !== 'POST') return res.status(405).send('Method not allowed');

  try {
    const { url } = req.body || {};
    if (!url || !/^https?:\/\/(www\.)?actawp\.natacio\.cat\/.+\/results/.test(url)) {
      return res.status(400).send('URL d’acta no vàlida');
    }
    // Mixed content: assegura't que enganxes https:// (no http://)
    // Scraping:
    const r = await fetch(url, { headers: { 'User-Agent': 'CNT-Stats/1.0 (+contacte@cnt.cat)' } });
    if (!r.ok) return res.status(r.status).send(`No s'ha pogut obrir l'acta (${r.status})`);
    const html = await r.text();

    const $ = cheerio.load(html);
    const blocs = [];
    $('table').each((_, tbl) => {
      const $tbl = $(tbl);
      const headers = $tbl.find('thead th').map((_, th) => $(th).text().trim().toLowerCase()).get();
      const iDorsal = headers.findIndex(h => h.includes('dorsal'));
      const iNom = headers.findIndex(h => h.startsWith('nom') || h.startsWith('name'));
      if (iDorsal < 0 || iNom < 0) return;
      const jugadors = $tbl.find('tbody tr').map((_, tr) => {
        const tds = $(tr).find('td');
        const dorsal = $(tds.get(iDorsal)).text().trim();
        const nom = $(tds.get(iNom)).text().trim();
        if (!nom) return null;
        return { dorsal, nom };
      }).get().filter(Boolean);
      if (!jugadors.length) return;
      let nomEquip =
        $tbl.prevAll('h3,h2,h4').first().text().trim() ||
        $tbl.closest('section,div').find('h3,h2,h4').first().text().trim();
      blocs.push({ nomEquip, jugadors });
    });

    if (!blocs.length) return res.status(422).send('No s’han trobat taules de jugadors a l’acta');

    const local = blocs[0] || { nomEquip: 'Local', jugadors: [] };
    const visitant = blocs[1] || { nomEquip: 'Visitant', jugadors: [] };
    res.json({ local, visitant });
  } catch (e) {
    console.error(e);
    res.status(500).send('Error processant l’acta');
  }
}
