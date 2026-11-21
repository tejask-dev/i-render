import assert from "node:assert/strict";
import { spokenCentimeters, spokenVibe } from "../frontend/dictation.js";

for (const [answer, cm] of [
  ["desktop, twenty centimeters", 20], ["thirty-five centimetres", 35],
  ["one hundred and fifty cm", 150], ["a hundred millimetres", 10],
  ["one thousand five hundred mm", 150], ["10 inches", 25],
  ["four and a half inches", 11], ["one point two five feet", 38],
  ["half a foot", 15], ["a foot", 30], ['3.5"', 9], ["3.5″", 9],
  ["10 in", 25], ["18cm", 18], ["I would like a 25 cm tall.", 25],
]) assert.equal(spokenCentimeters(answer), cm, answer);

for (const answer of [
  "desktop", "twenty", "some inches", "three meters", "minus ten cm", "−4 cm",
  "-10 inches", "one centimeter", "one hundred fifty-one cm", "2.9 centimeters",
  "between ten and twenty cm", "10–20 cm", "three inches by four inches",
  "2 feet and a half inch", "ten centimeters or a foot", "3,5 inches", "20 cm or inches",
  "minus about ten centimeters", "negative, twenty centimeters", "twenty in height",
  "less than 10 cm", "no more than one foot", "desktop, minus ten cm", "twenty zero cm",
]) assert.equal(spokenCentimeters(answer), null, answer);

assert.equal(spokenVibe("I want it playful and curious."), "playful, curious");
assert.equal(spokenVibe("I’d like my robot to feel gentle, scrappy and retro!"), "gentle, scrappy, retro");
assert.equal(spokenVibe("I want it playful, curious, retro, and chaotic."), "playful, curious, retro, chaotic");
assert.equal(spokenVibe("bold and soft-spoken"), "bold, soft-spoken");
console.log("PASS spoken units, number words, ambiguity, ranges and editable vibe phrasing");
