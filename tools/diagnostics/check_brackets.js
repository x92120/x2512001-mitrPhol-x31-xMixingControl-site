const fs = require('fs');
const content = fs.readFileSync('x3101-app/x3101-0110-frontEnd/app/pages/x60-CheckForProduction.vue', 'utf8');
const script = content.substring(content.indexOf('<script'), content.indexOf('</script>'));

let braces = 0;
let parens = 0;
let brackets = 0;

for (let i = 0; i < script.length; i++) {
  if (script[i] === '{') braces++;
  if (script[i] === '}') braces--;
  if (script[i] === '(') parens++;
  if (script[i] === ')') parens--;
  if (script[i] === '[') brackets++;
  if (script[i] === ']') brackets--;
}
console.log('Braces:', braces, 'Parens:', parens, 'Brackets:', brackets);
