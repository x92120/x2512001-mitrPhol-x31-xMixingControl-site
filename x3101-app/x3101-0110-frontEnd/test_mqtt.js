const mqtt = require('mqtt');

function testConnection(username, password) {
    const client = mqtt.connect('ws://192.168.21.198:15675/ws', {
        clientId: 'test-' + Math.random().toString(16).slice(2,8),
        username: username,
        password: password,
        connectTimeout: 5000
    });

    client.on('connect', () => {
        console.log(`[${username}] CONNECTED! Testing publish...`);
        client.publish('MIX-01-PUT', '{"test": 1}', (err) => {
            if (err) console.log(`[${username}] Publish failed:`, err.message);
            else console.log(`[${username}] Publish SUCCESS!`);
            client.end();
        });
    });

    client.on('error', (err) => {
        console.log(`[${username}] ERROR:`, err.message);
    });

    client.on('close', () => {
        console.log(`[${username}] Connection closed.`);
    });
}

testConnection('xMixingNode-1', 'x123456');
setTimeout(() => testConnection('admin', 'admin'), 2000);
setTimeout(() => testConnection('admin', 'x123456'), 4000);
