const mqtt = require('mqtt');
const client = mqtt.connect('mqtt://localhost:1883', {
    username: 'xMixingNode-1',
    password: 'x123456'
});
client.on('connect', () => {
    console.log('Connected');
    client.subscribe('#');
    setTimeout(() => {
        client.end();
        process.exit(0);
    }, 5000); // Listen for 5 seconds
});
client.on('message', (topic, message) => {
    console.log('Topic:', topic);
    console.log('Message:', message.toString());
});
