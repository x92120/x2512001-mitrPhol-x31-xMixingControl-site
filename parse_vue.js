const fs = require('fs');
const compiler = require('vue/compiler-sfc');
const content = fs.readFileSync('x3101-app/x3101-0110-frontEnd/app/pages/x60-CheckForProduction.vue', 'utf8');

try {
  const result = compiler.parse(content);
  if (result.errors.length) {
    console.error(result.errors);
  } else {
    console.log("Parsed OK!");
  }
} catch (e) {
  console.error(e);
}
