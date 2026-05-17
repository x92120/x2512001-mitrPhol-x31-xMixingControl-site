const messageStr = '{"Step_no":1,"Step_Timer":24,"Mixing_Tank_Volume":107.4,"Mixing_Tank_Temperature":61.04,"MixingTank_Agitator_Speed":1500,"HighShare_Speed":0,"watchdog":36,"PLC_State":1}';
const topic = '/MIX-02';
const topicUpper = topic.toUpperCase();

let payload;
if (messageStr.startsWith('{')) {
    try {
        payload = JSON.parse(messageStr);
    } catch (e) {
        payload = {};
    }
} else {
    payload = { raw: messageStr };
}

let plantId = '';
if (topicUpper.includes('MIX-1') || topicUpper.includes('MIX-01') || topic.includes('mixing/plant/1')) plantId = '1';
if (topicUpper.includes('MIX-2') || topicUpper.includes('MIX-02') || topic.includes('mixing/plant/2')) plantId = '2';
if (topicUpper.includes('MIX-3') || topicUpper.includes('MIX-03') || topic.includes('mixing/plant/3')) plantId = '3';

let actualPayload = payload;
if (payload['MIX-01']) { plantId = '1'; actualPayload = payload['MIX-01']; }
else if (payload['MIX-02']) { plantId = '2'; actualPayload = payload['MIX-02']; }
else if (payload['MIX-03']) { plantId = '3'; actualPayload = payload['MIX-03']; }

const prev = {}; // mock

console.log("plantId:", plantId);
console.log("watchdog:", actualPayload[`MIX0${plantId}.WATCHDOG`] ?? actualPayload[`MIX0${plantId}.Watch_Doc`] ?? actualPayload['Watch-Dog'] ?? actualPayload.Watch_Doc ?? actualPayload.watchdog ?? prev.watchdog);
