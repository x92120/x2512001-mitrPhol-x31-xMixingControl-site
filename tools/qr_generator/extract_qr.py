import sys
import fitz  # PyMuPDF
import cv2
import numpy as np

def extract_qr(pdf_path):
    print(f"Opening {pdf_path}...")
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Increase resolution for better QR detection
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        # Try cv2.QRCodeDetector
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)
        if data:
            print(f"Found QR code on page {page_num + 1}: {data}")
            return data

        # If not found, you can also check using QRCodeDetector with WechatQRCode (often more robust if available, but QRCodeDetector is standard)
        # Let's try PyZbar if installed, else fallback
        try:
            from pyzbar.pyzbar import decode
            decoded_objects = decode(img)
            for obj in decoded_objects:
                print(f"Found QR code (pyzbar) on page {page_num + 1}: {obj.data.decode('utf-8')}")
                return obj.data.decode('utf-8')
        except ImportError:
            pass
            
    print("No QR code found.")
    return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract_qr(sys.argv[1])
    else:
        print("Please provide a PDF path")
