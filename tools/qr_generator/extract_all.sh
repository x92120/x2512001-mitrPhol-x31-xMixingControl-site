#!/bin/bash

cd /home/x-root/Desktop

for pdf in *.pdf; do
    echo "Processing $pdf..."
    # Convert first page to PNG
    pdftoppm -png -r 300 -f 1 -l 1 "$pdf" "/tmp/qr_temp"
    
    # Send to API
    result=$(curl -s -F "file=@/tmp/qr_temp-1.png" https://api.qrserver.com/v1/read-qr-code/)
    
    # Print result
    echo "Result for $pdf:"
    echo "$result" | jq -r '.[0].symbol[0].data'
    echo "-----------------------------------"
    
    # Cleanup
    rm /tmp/qr_temp-1.png
done
