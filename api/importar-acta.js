// api/importar-acta.js
// ✅ Sense node-fetch: usem fetch global de Node (Vercel Node 18+)
// ✅ Import dinàmic de cheerio per aïllar errors de paquets a runtime

export default async function handler(req, res) {
  // Si algun dia serveixes el front des d’un altre domini, activa CORS amb la variable:
  // Vercel → Project → Settings → Environment Variables → CORS_ORIGIN = https://EL-TEU-FRONT
  const ALLOW_ORIGIN = process.env.CORS_ORIGIN || null;
  if (ALLOW_ORIGIN) {
    res.setHeader('Access-Control-Allow-Origin', ALLOW_ORIGIN);
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    if (req.method === 'OPTIONS') return res.status(200).end();
  }

  // GET → 405 (per comprovar existència de la funció)
  if (req.method !== 'POST') {
    res.setHeader('Cache-Control', 'no-store');
    return res.status(405).send('Method not allowed');
  }

  try {
    // Validació bàsica
    const { url } = req.body || {};
    if (!url || !/^https?:\/\/(www\.)?actawp\.natacio\.cat\/.+\/results/.test(url)) {
      return res.status(400).send('URL d’acta no vàlida (ha d’acabar amb /results)');
    }

    // 1) Descarrega HTML (fetch global)
    const r = await fetch(url, { headers: { 'User-Agent': 'CNT-Stats/1.0 (+contacte@cnt.cat)' } });
    if (!r.ok) {
      return res.status(r.status).send(`No s'ha pogut obrir l'acta (${r.status})`);
    }
    const html = await r.text();

    // 2) Importa cheerio a runtime (evita crash d'import si no està instal·lat)
    const { load } = await import('cheerio');
    const $ = load(html);

    // 3) Extreu taules que tinguin capçaleres "Dorsal" i "Nom/Name"
    const blocs = [];
    $('table').each((_, tbl) => {
      const $tbl = $(tbl);
      const headers = $tbl.find('thead th')
        .map((_, th) => $(th).text().trim().toLowerCase())
        .get();

      if (!headers.length) return;

      const iDorsal = headers.findIndex(h => h.includes('dorsal'));
      const iNom    = headers.findIndex(h => h.startsWith('nom') || h.startsWith('name'));
      if (iDorsal < 0 || iNom < 0) return;

      const jugadors = $tbl.find('tbody tr').map((_, tr) => {
        const tds = $(tr).find('td');
        const dorsal = (tds.get(iDorsal) ? $(tds.get(iDorsal)).text().trim() : '') || '';
        const nom    = (tds.get(iNom)    ? $(tds.get(iNom)).text().trim()    : '') || '';
        if (!nom) return null;
        return { dorsal, nom };
      }).get().filter(Boolean);

      if (!jugadors.length) return;

      // Nom d’equip (heading proper)
      const nomEquip =
        $tbl.prevAll('h3,h2,h4').first().text().trim() ||
        $tbl.closest('section,div').find('h3,h2,h4').first().text().trim() ||
        '';

      blocs.push({ nomEquip, jugadors });
    });

    if (!blocs.length) {
      return res.status(422).send('No s’han trobat taules de jugadors a l’acta');
    }

    const local    = blocs[0] || { nomEquip: 'Local',    jugadors: [] };
    const visitant = blocs[1] || { nomEquip: 'Visitant', jugadors: [] };

    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).json({ local, visitant });

  } catch (err) {
    console.error('[importar-acta] ERROR:', err);
    // Envia missatge curt al client; el detall queda als logs
    return res.status(500).send('Error processant l’acta');
  }
}
