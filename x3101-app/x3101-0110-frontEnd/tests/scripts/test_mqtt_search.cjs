const mqtt = require('mqtt');
const client = mqtt.connect('mqtt://localhost:1883', {
    username: 'xMixingNode-1',
    password: 'x123456'
});

console.log('Connecting to MQTT...');

client.on('connect', () => {
    console.log('Connected! Listening for messages containing "plan" or "batch"...');
    client.subscribe('#');
    setTimeout(() => {
        console.log('Finished listening.');
        client.end();
        process.exit(0);
    }, 10000); // Listen for 10 seconds
});

client.on('message', (topic, message) => {
    const msgStr = message.toString().toLowerCase();
    if (msgStr.includes('plan') || msgStr.includes('batch')) {
        console.log('-----------------------------------');
        console.log('Topic:', topic);
        console.log('Message:', message.toString());
    }
});
