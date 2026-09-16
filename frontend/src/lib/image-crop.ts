export interface NormalizedCrop {
  x: number;
  y: number;
  width: number;
  height: number;
}

const clamp = (value: number) => Math.min(1, Math.max(0, value));

export function cropFromPoints(
  start: { x: number; y: number },
  end: { x: number; y: number },
): NormalizedCrop {
  const startX = clamp(start.x);
  const startY = clamp(start.y);
  const endX = clamp(end.x);
  const endY = clamp(end.y);
  return {
    x: Math.min(startX, endX),
    y: Math.min(startY, endY),
    width: Math.abs(endX - startX),
    height: Math.abs(endY - startY),
  };
}

export function isUsableCrop(crop: NormalizedCrop | null): crop is NormalizedCrop {
  return Boolean(crop && crop.width >= 0.02 && crop.height >= 0.02);
}

export async function cropImageFile(
  file: File,
  crop: NormalizedCrop,
  image: HTMLImageElement,
): Promise<File> {
  if (!image.naturalWidth || !image.naturalHeight) {
    throw new Error("图片尚未加载完成，请稍后重试");
  }

  const sourceX = Math.round(crop.x * image.naturalWidth);
  const sourceY = Math.round(crop.y * image.naturalHeight);
  const sourceWidth = Math.max(1, Math.round(crop.width * image.naturalWidth));
  const sourceHeight = Math.max(1, Math.round(crop.height * image.naturalHeight));
  const canvas = document.createElement("canvas");
  canvas.width = sourceWidth;
  canvas.height = sourceHeight;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("当前浏览器无法创建裁剪画布");
  context.drawImage(
    image,
    sourceX,
    sourceY,
    sourceWidth,
    sourceHeight,
    0,
    0,
    sourceWidth,
    sourceHeight,
  );

  const outputType = file.type === "image/png" ? "image/png" : "image/jpeg";
  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob(resolve, outputType, 0.94);
  });
  if (!blob) throw new Error("图片裁剪失败，请使用整张图片重试");
  const stem = file.name.replace(/\.[^.]+$/, "") || "table";
  return new File([blob], `${stem}-cropped.${outputType === "image/png" ? "png" : "jpg"}`, {
    type: outputType,
    lastModified: Date.now(),
  });
}
