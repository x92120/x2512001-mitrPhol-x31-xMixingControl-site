/**
 * useQrCode — offline-safe QR code generator composable
 * Uses the locally-installed 'qrcode' npm package (no CDN required)
 */
import QRCode from 'qrcode'

/**
 * Generates a QR code as a base64 PNG data URL.
 * @param text  The text/URL to encode
 * @param size  Pixel size (width = height). Default 150.
 * @returns     A data:image/png;base64,... string suitable for <img src="">
 */
export async function generateQrDataUrl(text: string, size = 150): Promise<string> {
    try {
        return await QRCode.toDataURL(text, {
            width: size,
            margin: 1,
            errorCorrectionLevel: 'M',
            color: {
                dark: '#000000',
                light: '#ffffff'
            }
        })
    } catch (err) {
        console.error('[useQrCode] Failed to generate QR:', err)
        return ''
    }
}

/**
 * Generates a QR code as an inline SVG string.
 * Useful when embedding directly into SVG labels.
 */
export async function generateQrSvg(text: string, size = 150): Promise<string> {
    try {
        return await QRCode.toString(text, {
            type: 'svg',
            width: size,
            margin: 1,
            errorCorrectionLevel: 'M'
        })
    } catch (err) {
        console.error('[useQrCode] Failed to generate QR SVG:', err)
        return ''
    }
}

export function useQrCode() {
    return { generateQrDataUrl, generateQrSvg }
}
