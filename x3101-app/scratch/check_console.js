const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  page.on('console', msg => console.log(`[BROWSER ${msg.type().toUpperCase()}] ${msg.text()}`));
  page.on('pageerror', exception => console.log(`[BROWSER EXCEPTION] ${exception}`));
  
  console.log("Navigating to http://localhost:3031/x100-PlantMonitor ...");
  try {
    await page.goto('http://localhost:3031/x100-PlantMonitor', { waitUntil: 'networkidle' });
  } catch (e) {
    console.log("Goto error:", e);
  }
  
  console.log("Waiting 10 seconds for MQTT messages...");
  await page.waitForTimeout(10000);
  
  await browser.close();
})();
