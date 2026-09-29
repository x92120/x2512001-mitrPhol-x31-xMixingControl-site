# Barcode Scanning & Verification Workflow

This diagram illustrates the step-by-step logic the application follows when an operator scans a QR code using the handheld scanner. It highlights the error-handling logic for various scanning mistakes, including the Wrong Box handling.

```mermaid
flowchart TD
    A([Scanner reads QR Code]) --> B{Is a Batch already loaded?}
    B -- No --> C[Load the scanned Batch]
    B -- Yes --> D{Is scanned code a completely new Batch ID?}
    
    D -- Yes --> E[Switch and Load the new Batch]
    D -- No --> F[Verify as an Ingredient Bag]

    F --> G[Check local data for matching ingredient]
    G -- Match Found --> H([Mark Ingredient as ✅ Verified])
    G -- No Local Match --> I[Send scan to Backend API]

    I --> J{Backend Response}
    J -- Success --> K([Mark Ingredient as ✅ Verified])
    
    J -- Failure --> L{What did the operator actually scan?}
    
    L -- "The same Batch ID again" --> M([⚠️ Yellow Warning: <br>'You scanned the Batch Label!'])
    L -- "Unrecognized Bag for this Batch" --> N([❌ Red Toast Error: <br>'Ingredient not found'])
    L -- "Bag from a completely different box" --> O([🚨 Big Red Modal: <br>WRONG BOX!])
    
    O --> P{Operator Decision}
    P -- "I want to keep working on my current batch" --> Q([Close Modal & Continue])
    P -- "I want to scan a different batch instead" --> R([Start New Batch / Reset])
```
