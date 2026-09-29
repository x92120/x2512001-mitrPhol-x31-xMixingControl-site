const fs = require('fs');
let code = fs.readFileSync('/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0110-frontEnd/app/composables/useMQTT.ts', 'utf8');

// The bug in useMQTT.ts is that watchdog reconnects but doesn't re-bind events
