const small = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(" ");
const tens = "twenty thirty forty fifty sixty seventy eighty ninety".split(" ");
const numeric = /^(?:\d+(?:\.\d+)?|\.\d+)$/;
const numberWords = new Set([...small, ...tens, "hundred", "thousand", "point", "half", "quarter"]);

function cardinal(words) {
  if (words.length === 1 && numeric.test(words[0])) return Number(words[0]);
  let total = 0;
  for (const [place, factor] of [["thousand", 1000], ["hundred", 100]]) {
    const digit = small.indexOf(words[0]);
    if (words[1] === place && digit >= 1 && digit <= 9) {
      total += digit * factor;
      words = words.slice(2);
    }
  }
  if (!words.length) return total || null;
  if (total && words[0] === "and") words = words.slice(1);
  const single = small.indexOf(words[0]);
  if (words.length === 1 && single >= 0) return total + single;
  const ten = tens.indexOf(words[0]);
  if (ten < 0) return null;
  if (words.length === 1) return total + (ten + 2) * 10;
  const unit = small.indexOf(words[1]);
  return words.length === 2 && unit > 0 && unit <= 9 ? total + (ten + 2) * 10 + unit : null;
}

function amount(words) {
  const last = words.at(-1);
  if (last === "half" || last === "quarter") {
    const fraction = last === "half" ? 0.5 : 0.25;
    if (words.length === 1) return fraction;
    if (words.at(-3) !== "and" || words.at(-2) !== "a") return null;
    const whole = cardinal(words.slice(0, -3));
    return Number.isInteger(whole) ? whole + fraction : null;
  }
  const point = words.indexOf("point");
  if (point < 0) return cardinal(words);
  const whole = point ? cardinal(words.slice(0, point)) : 0;
  const digits = words.slice(point + 1).map(word => /^\d$/.test(word) ? Number(word) : small.indexOf(word));
  if (!Number.isInteger(whole) || !digits.length || digits.some(n => n < 0 || n > 9)) return null;
  return whole + Number("0." + digits.join(""));
}

const centimetersPerUnit = new Map([
  ["mm millimeter millimeters millimetre millimetres", 0.1],
  ["cm centimeter centimeters centimetre centimetres", 1],
  ['in inch inches " ″', 2.54],
  ["ft foot feet ' ′", 30.48],
].flatMap(([names, scale]) => names.split(" ").map(name => [name, scale])));

export function spokenCentimeters(phrase) {
  const text = phrase.toLowerCase().replace(/([a-z])[-‐‑](?=[a-z])/g, "$1 ");
  const tokens = text.match(/\d*\.\d+|\d+|[a-z]+|[^\s]/g) || [];
  const quantities = tokens.map((word, i) => {
    const article = word === "a" || word === "an";
    if (article && tokens[i - 1] !== "half" && tokens[i - 1] !== "quarter" &&
        (centimetersPerUnit.has(tokens[i + 1]) || ["hundred", "thousand"].includes(tokens[i + 1]))) return "one";
    return word;
  });
  const isNumber = word => numeric.test(word) || numberWords.has(word);
  const start = quantities.findIndex(isNumber), end = quantities.findLastIndex(isNumber);
  if (start < 0) return null;
  const prefix = tokens.slice(0, start).join(" ");
  if (/[−–-]|\b(?:minus|negative|not|under|over|between|than|at least|at most|up to)\b/.test(prefix)) return null;
  const words = quantities.slice(start, end + 1);
  const next = tokens[end + 1];
  const unitIndex = ["-", "a", "an"].includes(next) ? end + 2 : end + 1;
  const factor = centimetersPerUnit.get(tokens[unitIndex]);
  if (!factor) return null;
  if (tokens[unitIndex] === "in" && /^[a-z]/.test(tokens[unitIndex + 1] || "")) return null;
  if (["or", "and", "/", "to"].includes(tokens[unitIndex + 1]) && centimetersPerUnit.has(tokens[unitIndex + 2])) return null;
  const value = amount(words);
  if (value === null) return null;
  const cm = value * factor;
  return cm >= 3 && cm <= 150 ? Math.round(cm) : null;
}

export function spokenVibe(phrase) {
  return phrase.trim().replace(/^(?:i (?:want|would like)|i['’]d like)\s+(?:(?:it|(?:my|the) robot)(?: to (?:be|feel|seem))?\s+)?/i, "")
    .replace(/[.!?]+$/, "").replace(/,?\s+(?:and|or)\s+/gi, ", ");
}
