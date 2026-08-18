/** Serialize a chart's <svg> into a PNG and trigger a download. */
export function exportChartAsPng(container: HTMLElement | null, filename: string) {
  if (!container) return;
  const svg = container.querySelector("svg");
  if (!svg) return;

  const rect = svg.getBoundingClientRect();
  const scale = 2;
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(rect.width));
  clone.setAttribute("height", String(rect.height));

  // Inline computed strokes/fills so CSS variables survive serialization.
  const source = Array.from(svg.querySelectorAll("*"));
  Array.from(clone.querySelectorAll("*")).forEach((node, i) => {
    const original = source[i];
    if (!(original instanceof Element) || !(node instanceof SVGElement)) return;
    const cs = getComputedStyle(original);
    const stroke = cs.stroke;
    const fill = cs.fill;
    if (stroke && stroke !== "none") node.style.stroke = stroke;
    if (fill && fill !== "none") node.style.fill = fill;
    if (cs.fontSize) node.style.fontSize = cs.fontSize;
    if (cs.fontFamily) node.style.fontFamily = cs.fontFamily;
  });

  const bg = getComputedStyle(document.body).backgroundColor || "#ffffff";
  const data = new XMLSerializer().serializeToString(clone);
  const url = URL.createObjectURL(new Blob([data], { type: "image/svg+xml;charset=utf-8" }));

  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = rect.width * scale;
    canvas.height = rect.height * scale;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      ctx.drawImage(img, 0, 0);
      const a = document.createElement("a");
      a.href = canvas.toDataURL("image/png");
      a.download = `${filename}.png`;
      a.click();
    }
    URL.revokeObjectURL(url);
  };
  img.onerror = () => URL.revokeObjectURL(url);
  img.src = url;
}
