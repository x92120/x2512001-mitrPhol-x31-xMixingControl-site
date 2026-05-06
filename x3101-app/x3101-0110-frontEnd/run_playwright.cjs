const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  const fileUrl = 'file://' + path.resolve('../../decode.html');
  await page.goto(fileUrl);
  
  // Wait for the output to change from "Decoding..."
  await page.waitForFunction(() => {
    const text = document.getElementById('output').innerText;
    return text !== 'Decoding...';
  }, { timeout: 10000 });
  
  const result = await page.$eval('#output', el => el.innerText);
  console.log(result);
  
  await browser.close();
})();
