import * as QRCodeModule from 'qrcode'
const QRCode = (QRCodeModule as any).default || QRCodeModule

export const useLabelPrinter = () => {

  /**
   * Processes an SVG template by replacing placeholders with actual data
   * @param templateName Name of the svg file in /public/labels (e.g. 'ingredient-label')
   * @param data Object containing keys to replace {{KEY}} in the SVG
   */
  const generateLabelSvg = async (templateName: string, data: Record<string, string | number>) => {
    try {
      const response = await fetch(`/labels/${templateName}.svg`);
      if (!response.ok) throw new Error(`Template ${templateName} not found`);
      let svgContent = await response.text();

      // Process QR Codes if present in data
      const dataToInject = { ...data };

      for (const [key, value] of Object.entries(data)) {
        if (key.toLowerCase().includes('qrcode') && value) {
          try {
            // Generate QR as DataURL (PNG) for maximum compatibility in SVG <image> tag
            const qrDataUrl = await QRCode.toDataURL(String(value), {
              margin: 0,
              errorCorrectionLevel: 'M',
              width: 300 // High enough resolution for clear printing
            });

            // Using an <image> tag is more robust for SVG rendering than injecting paths
            dataToInject[key] = `<image x="0" y="0" width="100" height="100" href="${qrDataUrl}" />`;
          } catch (qrErr) {
            console.error('QR Generation Error:', qrErr);
            dataToInject[key] = '';
          }
        }
      }

      // Replace placeholders {{KEY}} with dataToInject[KEY]
      // Using split/join to avoid regex replacement issues with large strings
      Object.entries(dataToInject).forEach(([key, value]) => {
        const placeholder = `{{${key}}}`;
        svgContent = svgContent.split(placeholder).join(String(value));
      });

      return svgContent;
    } catch (error) {
      console.error('Label Generation Error:', error);
      return null;
    }
  };

  /**
   * Triggers the browser print dialog for one or multiple SVG labels
   * @param svgInput Single SVG string or an array of SVG strings
   */
  const printLabel = (svgInput: string | string[] | null) => {
    if (!svgInput) return;

    const svgs = Array.isArray(svgInput) ? svgInput : [svgInput];
    if (svgs.length === 0) return;

    const printWindow = window.open('', '_blank');
    if (!printWindow) return;

    const svgHtml = svgs.map((svg, idx) => `
      <div class="label-container" style="${idx < svgs.length - 1 ? 'page-break-after: always;' : ''}">
        ${svg}
      </div>
    `).join('');

    printWindow.document.write(`
      <html>
        <head>
          <title>Print Label</title>
          <style>
            @page { size: auto; margin: 0 !important; }
            body { margin: 0; padding: 0; background: white; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            .label-container { 
              width: 4in; 
              height: 3in; 
              display: block; 
              overflow: hidden;
              position: relative;
              padding-left: 2.5mm; /* Physical Left Offset */
              padding-top: 1.5mm;  /* Physical Top Offset */
              box-sizing: border-box;
            }
            svg { width: 100%; height: 100%; display: block; }
          </style>
        </head>
        <body>
          ${svgHtml}
          <script>
            window.onload = () => {
              window.print();
              setTimeout(() => window.close(), 500);
            };
          </script>
        </body>
      </html>
    `);
    printWindow.document.close();
  };

  return {
    generateLabelSvg,
    printLabel
  };
};
