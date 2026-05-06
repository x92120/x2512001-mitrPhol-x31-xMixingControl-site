const fs = require('fs');
const content = fs.readFileSync('x3101-app/x3101-0110-frontEnd/app/pages/x60-CheckForProduction.vue', 'utf8');
const script = content.substring(content.indexOf('<script'), content.indexOf('</script>'));

let parens = 0;
const lines = script.split('\n');

for (let i = 0; i < lines.length; i++) {
  let line = lines[i];
  for (let j = 0; j < line.length; j++) {
    if (line[j] === '(') parens++;
    if (line[j] === ')') parens--;
  }
  if (parens < 0) {
     console.log('Parens went negative at line:', i + 1);
     console.log(line);
     break;
  }
}
