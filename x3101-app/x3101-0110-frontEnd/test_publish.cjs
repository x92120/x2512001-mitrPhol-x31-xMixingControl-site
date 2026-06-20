const mqtt = require('mqtt');
const client = mqtt.connect('ws://localhost:15675/ws', { username: 'xMixingNode-1', password: 'x123456' });
client.on('connect', () => { 
    console.log('connected'); 
    client.publish('mixing/plant/2/cmd', JSON.stringify({command: 'START'}), (err) => {
        if(err) console.error('publish error', err);
        else console.log('published successfully');
    });
});
client.on('close', () => console.log('connection closed!'));
client.on('error', (err) => console.log('error', err));
setTimeout(() => process.exit(), 3000);
