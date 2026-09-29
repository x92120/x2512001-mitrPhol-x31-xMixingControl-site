const mqtt = require('mqtt');
const client = mqtt.connect('mqtt://localhost:1883', {
    username: 'xMixingNode-1',
    password: 'x123456'
});

client.on('connect', () => {
    console.log('Connected! Listening to all topics...');
    client.subscribe('#');
    setTimeout(() => {
        client.end();
        process.exit(0);
    }, 5000);
});

const seenTopics = new Set();

client.on('message', (topic, message) => {
    if (seenTopics.has(topic)) return;
    seenTopics.add(topic);
    
    console.log('\n--- Topic:', topic);
    const msgStr = message.toString();
    try {
        const parsed = JSON.parse(msgStr);
        console.log('Keys:', Object.keys(parsed).join(', '));
        console.log('Payload snippet:', msgStr.substring(0, 200));
    } catch (e) {
        console.log('Non-JSON payload:', msgStr.substring(0, 100));
    }
});
