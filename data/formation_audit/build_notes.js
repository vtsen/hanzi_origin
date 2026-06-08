// Build formation_notes.json from batch files + manual enhancements
// Run: node data/formation_audit/build_notes.js
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname);

// Merge all batch files
let raw = {};
for (let i = 1; i <= 10; i++) {
  const f = path.join(dir, `days1to5_batch${i}.json`);
  Object.assign(raw, JSON.parse(fs.readFileSync(f, 'utf8')));
}

// Manual enhancements: wiktionary_url (use trad form where appropriate),
// concise learner-facing note, and multi_simplified flag where a simplified
// char covers multiple unrelated traditional chars.
const enhancements = {
  // --- SIGNIF ---
  '甲': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E7%94%B2',
    note: 'Wiktionary reads 甲 as a carapace or suit of armor (Proto-Sino-Tibetan *krap "shell/shield"), not a sprouting seed shell as stated in our data.',
  },
  '虫': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E8%9F%B2', // 蟲
    note: 'The simplified 虫 is itself a pictograph (snake), but its traditional form 蟲 is an ideogrammic compound (3×虫). Our formation describes the component 虫, not the traditional character 蟲.',
    multi_simplified: false, // same concept, just simplified vs traditional
  },
  '广': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E5%BB%A3', // 廣
    note: 'Wiktionary classifies 廣 as a phono-semantic compound: 广 (cliff/shelter, semantic) + 黃 (phonetic). Our data treats it as a simple pictograph of a mountain-side shelter.',
  },
  '食': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E9%A3%9F',
    note: 'Wiktionary classifies 食 as an ideogrammic compound: 亼 (mouth) + 皀 (food in a vessel). Our data incorrectly assigns 皂 as a phonetic component, making it phono-semantic.',
  },
  '足': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E8%B6%B3',
    note: 'Wiktionary reads 足 as a unified pictograph of a leg and foot, not a compound of separate semantic components (止 + knee).',
  },
  '干': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E5%B9%B9', // 幹
    note: 'Simplified 干 merges three traditional chars: 幹 (trunk/manage, phono-semantic: 倝+木), 乾 (dry, phono-semantic), and 干 (shield/offend, pictograph). Our formation describes the 干 (shield) sense only.',
    multi_simplified: true,
  },
  '甘': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E7%94%98',
    note: 'Wiktionary classifies 甘 as a simple indicative (指事): the stroke inside 口 is an abstract position marker for "something sweet in the mouth," not a second semantic component making it a compound ideograph.',
  },
  '十': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E5%8D%81',
    note: 'Formation origin uncertain. Wiktionary does not confirm the indicative reading; theories include a borrowed pictogram of a needle or a knotted cord used for counting.',
  },
  '皮': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E7%9A%AE',
    note: 'Wiktionary classifies 皮 as a pictograph: a unified depiction of a hand stripping an animal pelt, not an ideogrammic compound of independent semantic parts.',
  },
  '亡': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E4%BA%A1',
    note: 'Wiktionary classifies 亡 as a simple indicative: a mark on a knife blade indicating the hidden/absent edge — original form of 芒. Our data\'s compound ideograph analysis (入+乚 = person hiding) is a later folk reading.',
  },
  '旦': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E6%97%A6',
    note: 'Wiktionary classifies 旦 as a phono-semantic compound: 日 (semantic) + 丁 (phonetic). The popular "sun above the horizon" indicative reading is considered folk etymology.',
  },
  '示': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E7%A4%BA',
    note: 'Wiktionary classifies 示 as a pictograph: a direct depiction of a ritual altar or spirit tablet, not an ideogrammic compound of separate semantic parts.',
  },
  '古': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E5%8F%A4',
    note: 'Wiktionary classifies 古 as a simple indicative, with the top element reading as a contracted shield (not 十), meaning "firm/strong" — original form of 固. The "ten mouths = ancient" folk reading in our data is not etymologically supported.',
  },
  '申': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E7%94%B3',
    note: 'Wiktionary classifies 申 as a pictograph of a lightning bolt, not an indicative of an upright bound body. The lightning interpretation aligns with its original meaning "9th earthly branch" and related character 電.',
  },
  '舌': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E8%88%8C',
    note: 'Wiktionary reads 舌 as a pictograph of a snake\'s forked tongue above a mouth — a unified image, not an ideogrammic compound of 口 + 干.',
  },
  '之': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E4%B9%8B',
    note: 'Wiktionary identifies the components as 止 (foot) + 一 (ground), meaning "to go/proceed." Our data\'s sprouting-plant description misidentifies the character; that imagery belongs to 生 or 屮.',
  },
  '黑': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E9%BB%91',
    note: 'Wiktionary classifies 黑 as a pictograph of a face or head covered in soot/markings. Our chimney+fire compound reading is not supported by glyph analysis.',
  },
  '夕': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E5%A4%95',
    note: 'Wiktionary classifies 夕 as a pictograph of a crescent moon — same imagery as our note, but formation type is pictograph not simple indicative.',
  },
  '韦': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E9%9F%8B', // 韋
    note: 'Wiktionary classifies 韋 as an ideogrammic compound: 舛 (contrary footsteps) + 囗 (enclosure) = feet going opposite ways around a wall. Our data treats 囗 as a phonetic, making it phono-semantic — incorrect.',
  },
  '谷': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E7%A9%80', // 穀
    note: 'Simplified 谷 covers two unrelated traditional characters: 谷 (valley, ideogrammic compound) and 穀 (grain, phono-semantic: 禾+𣪊). These were merged in simplification; our formation addresses only the valley sense.',
    multi_simplified: true,
  },
  '向': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E5%90%91', // 向 itself; 嚮 is a derived form
    note: 'Wiktionary classifies 向 as an ideogrammic compound: 宀 (dwelling) + 口 (opening/window) = a north-facing window. Our data calls it a pictograph.',
  },
  '垂': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E5%9E%82',
    note: 'Wiktionary classifies 垂 as a pictograph of hanging flowers drooping toward the ground — a unified image. Our data incorrectly assigns a phono-semantic structure (土 semantic + 垂 phonetic, which is circular).',
  },
  '青': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E9%9D%92',
    note: 'Wiktionary (citing Zhang 2022) classifies 青 as a phono-semantic compound: 生 (semantic, growth/plant) + 井 (phonetic). The Shuowen compound ideograph reading (生+丹) is an older analysis.',
  },
  '走': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E8%B5%B0',
    note: 'Wiktionary classifies 走 as a pictograph of a running person — a unified pictorial image, not an ideogrammic compound of person + foot parts.',
  },
  '士': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E5%A3%AB',
    note: 'Wiktionary classifies 士 as a pictograph of a war axe. The "一+十 = a man of virtue" compound reading in our data is a folk etymology not supported by glyph analysis.',
  },
  '旨': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E6%97%A8',
    note: 'Wiktionary\'s primary classification is ideogrammic compound: 匕 (spoon) + 甘 (sweet) = something delicious eaten with a spoon. The phono-semantic reading (匕 phonetic) is Shuowen\'s secondary account.',
  },
  '合': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E9%96%A4', // 閤
    note: '閤 is a derived character (門+合, phono-semantic) distinct from 合 itself. 合 (ideogrammic compound: 亼+口 = lid closing over mouth) is correct; but the traditional form listed in our data (閤) is a separate word meaning "side door."',
    multi_simplified: true,
  },
  '束': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E6%9D%9F',
    note: 'Wiktionary classifies 束 as a simple indicative: a depiction of a bag tied at both ends, with the binding marks as position indicators — not an ideogrammic compound of 囗 (rope) + 木 (wood).',
  },
  '五': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E4%BA%94',
    note: 'Wiktionary\'s leading theory classifies 五 as a pictograph (palm lines or a knotted cord representing the number 5), not a simple indicative. Origin uncertain.',
  },
  '莫': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E8%8E%AB',
    note: 'Wiktionary classifies 莫 as a pictograph: sun sinking into vegetation = dusk, a unified visual image. Our data classifies it as an ideogrammic compound of 日 + 茻 — same imagery but different classification.',
  },
  '千': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E5%8D%83',
    note: 'Wiktionary classifies 千 as a phono-semantic compound: 一 (semantic) + 人 (phonetic). Our simple indicative reading is not supported. Note: the traditional form 韆 listed in our data means "swing" (千秋), not the numeral — an incorrect trad mapping.',
    multi_simplified: true,
  },
  '斗': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E9%AC%A5', // 鬥
    note: 'Simplified 斗 merges two unrelated traditional characters: 斗 (ladle/measure, pictograph of a handled vessel) and 鬥 (fight, pictograph of two people wrestling). These are completely different characters with different etymologies.',
    multi_simplified: true,
  },

  // --- MINOR (only those with a meaningful alternative to show) ---
  '言': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E8%A8%80',
    note: 'Both classify as simple indicative. Wiktionary describes the marker as a tongue-position indicator above 口 (mouth), slightly different from our "tongue speaking" reading.',
  },
  '又': {
    wiktionary_url: 'https://en.wiktionary.org/wiki/%E5%8F%88',
    note: 'Both classify as pictograph. Wiktionary clarifies the depicted object is a right hand (original form of 右), not "repetition" as our note implies.',
  },
  '旦': { // already in SIGNIF above
  },
};

// Build the output — only SIGNIF and meaningful MINOR entries
const out = {};
for (const [ch, data] of Object.entries(raw)) {
  if (data.verdict === 'MATCH') continue;
  const enh = enhancements[ch] || {};
  if (!enh.wiktionary_url && data.verdict === 'MINOR') continue; // skip minor without enhancement

  out[ch] = {
    verdict: data.verdict,
    our_type: data.our_type,
    wiki_type: data.wiki_type,
    wiki_summary: data.wiki_summary,
    wiktionary_url: enh.wiktionary_url || `https://en.wiktionary.org/wiki/${encodeURIComponent(ch)}`,
    note: enh.note || data.difference,
    ...(enh.multi_simplified ? { multi_simplified: true } : {}),
  };
}

const outPath = path.join(__dirname, 'formation_notes.json');
fs.writeFileSync(outPath, JSON.stringify(out, null, 2), 'utf8');
console.log(`Written ${Object.keys(out).length} entries to formation_notes.json`);
Object.entries(out).forEach(([ch, v]) => console.log(`  ${ch} [${v.verdict}]${v.multi_simplified ? ' MULTI' : ''}`));
