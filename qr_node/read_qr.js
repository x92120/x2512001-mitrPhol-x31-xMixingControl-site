const fs = require('fs');
const PNG = require('pngjs').PNG;
const jsQR = require('jsqr');

function readQR(imagePath) {
    fs.createReadStream(imagePath)
    .pipe(new PNG({ filterType: 4 }))
    .on('parsed', function() {
        const qrCode = jsQR(new Uint8ClampedArray(this.data), this.width, this.height, {
            inversionAttempts: "dontInvert",
        });
        if (qrCode) {
            console.log(qrCode.data);
        } else {
            // try again
            const qrCode2 = jsQR(new Uint8ClampedArray(this.data), this.width, this.height, {
                inversionAttempts: "attemptBoth",
            });
            if (qrCode2) {
                console.log(qrCode2.data);
            } else {
                console.log("NO_QR");
            }
        }
    })
    .on('error', function(err) {
        console.error("Error:", err);
    });
}

readQR(process.argv[2]);
