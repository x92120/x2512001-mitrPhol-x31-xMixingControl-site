const fs = require('fs');

const grouped = [
  { id: '1', is_recode: false, bags: [ { package_no: 1, total_packages: 1, net_volume: 0.5 } ] },
  { id: '2', is_recode: false, bags: [ { package_no: 1, total_packages: 1, net_volume: 0.5 } ] }
]

const HDR_H = 16, PKG_H = 12, START_Y = 80, MAX_Y = 200
let pages = []
let curY = START_Y
let currentRowsSvg = ''

const pushPageAndReset = () => {
    pages.push(currentRowsSvg)
    currentRowsSvg = ''
    curY = START_Y
}

for (const grp of grouped) {
    if (curY + HDR_H > MAX_Y) { pushPageAndReset() }
    const title = grp.is_recode ? grp.id : grp.id
    currentRowsSvg += `<rect x="10" y="${curY}" width="370" height="${HDR_H}" fill="#f0f0f0"/>\n<text x="14" y="${curY + 11}">${title}</text>\n`
    curY += HDR_H
    
    for (const bag of grp.bags) {
        if (curY + PKG_H > MAX_Y) {
            pushPageAndReset()
            currentRowsSvg += `<rect x="10" y="${curY}" width="370" height="${HDR_H}" fill="#f0f0f0"/>\n<text x="14" y="${curY + 11}">${title} (cont.)</text>\n`
            curY += HDR_H
        }
        currentRowsSvg += `<rect x="10" y="${curY}" width="370" height="${PKG_H}" fill="#ffffff"/>\n`
        curY += PKG_H
    }
}
if (currentRowsSvg !== '') { pages.push(currentRowsSvg) }

// Load svg
const templateSvg = fs.readFileSync("/Users/x92120/xGit/x2512001-mitrPhol/x01-frontEnd/x0101-xMixing/public/labels/packingbox-label_4x3.svg", "utf-8");
let finalHtmlContent = ''
for(let i = 0; i < pages.length; i++) {
    let pageSvg = templateSvg
        .replaceAll('{{Warehouse}}', 'FH')
        .replace('{{BoxId}}', `BOX-1-${i+1}`)
        .replace('{{PreBatchRows}}', pages[i])
        
    finalHtmlContent += pageSvg
}
console.log("totalPages: " + pages.length);
console.log("SVG Starts processing!");
console.log(finalHtmlContent.substring(0, 300));
