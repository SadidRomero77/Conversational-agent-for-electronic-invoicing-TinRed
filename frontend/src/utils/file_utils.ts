/**
 * Funciones auxiliares para trabajar con archivos temporales.
 */
import fs from "fs";

export function fileToBase64(path: string): string {
  const buffer = fs.readFileSync(path);
  return buffer.toString("base64");
}

export function deleteIfExists(path: string) {
  if (fs.existsSync(path)) fs.unlinkSync(path);
}
