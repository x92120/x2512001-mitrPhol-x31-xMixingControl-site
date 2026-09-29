const mqtt = require('mqtt');
const client = mqtt.connect('ws://localhost:15675/ws', { username: 'xMixingNode-1', password: 'x123456' });
client.on('connect', () => { console.log('connected'); client.subscribe('/MIX-02'); });
client.on('message', (topic, msg) => { console.log(new Date().toISOString(), topic, JSON.parse(msg.toString())['MIX02.Watch_Doc']); });
setTimeout(() => process.exit(), 10000);
