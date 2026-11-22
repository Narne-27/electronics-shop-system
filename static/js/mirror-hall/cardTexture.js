/**
 * Electrodesk - Mirror Hall 3D Section Carousel
 * Procedural Liquid Marble / Ink Card Texture Generator
 */

import * as THREE from 'three';
import { CONFIG } from './config.js';

// Vector helper for noise blending
function hexToRgb(hex) {
  const c = parseInt(hex.replace('#', ''), 16);
  return [(c >> 16) & 255, (c >> 8) & 255, c & 255];
}

/**
 * Procedural domain-warping ink marble generator
 */
function renderMarbleBackdrop(ctx, width, height, primaryColor, accentColor, seed) {
  const imgData = ctx.createImageData(width, height);
  const data = imgData.data;

  const rgbBase1 = hexToRgb('#060212'); // Deep void
  const rgbBase2 = hexToRgb('#12062d'); // Rich indigo
  const rgbPrimary = hexToRgb(primaryColor || '#2bf0ff');
  const rgbAccent = hexToRgb(accentColor || '#7a3cff');

  const s = seed * 13.37;
  const invW = 1.0 / width;
  const invH = 1.0 / height;

  for (let y = 0; y < height; y++) {
    const ny = y * invH * 3.2;
    for (let x = 0; x < width; x++) {
      const nx = x * invW * 2.4;

      // Layer 1 warp
      const qx = Math.sin(nx * 2.0 + s) * 0.8 + Math.cos(ny * 1.5 + s * 0.7);
      const qy = Math.cos(ny * 2.2 + s * 1.1) * 0.8 + Math.sin(nx * 1.3 - s);

      // Layer 2 domain-warped perturbation
      const rx = Math.sin((nx + qx) * 3.5 + s * 0.5);
      const ry = Math.cos((ny + qy) * 3.2 - s * 0.4);

      // Ribbon field
      const v = Math.sin((nx + rx * 0.6) * 4.0 + (ny + ry * 0.6) * 3.0);
      const t = Math.max(0, Math.min(1, 0.5 + 0.5 * v));

      // Fine silk vein
      const vein = Math.pow(Math.max(0, 1.0 - Math.abs(v)), 5.5);

      // Color composition
      const r = Math.min(255, rgbBase1[0] * (1 - t) + rgbBase2[0] * t + rgbPrimary[0] * vein * 0.75 + rgbAccent[0] * t * 0.25);
      const g = Math.min(255, rgbBase1[1] * (1 - t) + rgbBase2[1] * t + rgbPrimary[1] * vein * 0.75 + rgbAccent[1] * t * 0.25);
      const b = Math.min(255, rgbBase1[2] * (1 - t) + rgbBase2[2] * t + rgbPrimary[2] * vein * 0.75 + rgbAccent[2] * t * 0.25);

      const idx = (y * width + x) * 4;
      data[idx] = r;
      data[idx + 1] = g;
      data[idx + 2] = b;
      data[idx + 3] = 255;
    }
  }

  ctx.putImageData(imgData, 0, 0);

  // Overlay subtle vignette & glass reflection sheen
  const sheen = ctx.createLinearGradient(0, 0, width, height * 0.8);
  sheen.addColorStop(0, 'rgba(255, 255, 255, 0.16)');
  sheen.addColorStop(0.35, 'rgba(255, 255, 255, 0.04)');
  sheen.addColorStop(0.65, 'transparent');
  sheen.addColorStop(1, 'rgba(0, 0, 0, 0.45)');
  ctx.fillStyle = sheen;
  ctx.fillRect(0, 0, width, height);
}

/**
 * Generates the full canvas texture with live metrics and branding
 */
export function createCardTexture(section, index) {
  const w = CONFIG.textureWidth;
  const h = CONFIG.textureHeight;

  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });

  const primaryColor = section.accent || '#2bf0ff';
  const warmColor = section.warm_accent || '#7a3cff';

  // 1. Procedural liquid marble background
  renderMarbleBackdrop(ctx, w, h, primaryColor, warmColor, (index + 1) * 3.7);

  // 2. Card Border Frame & Inset Glow
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.18)';
  ctx.lineWidth = 4;
  ctx.strokeRect(16, 16, w - 32, h - 32);

  // Accent Edge Line at top
  const topAccent = ctx.createLinearGradient(16, 16, w - 16, 16);
  topAccent.addColorStop(0, 'transparent');
  topAccent.addColorStop(0.5, primaryColor);
  topAccent.addColorStop(1, 'transparent');
  ctx.strokeStyle = topAccent;
  ctx.lineWidth = 6;
  ctx.beginPath();
  ctx.moveTo(32, 16);
  ctx.lineTo(w - 32, 16);
  ctx.stroke();

  // 3. Header: Eyebrow + Section Code
  ctx.font = '600 18px "Inter", -apple-system, sans-serif';
  ctx.fillStyle = 'rgba(232, 246, 255, 0.75)';
  ctx.letterSpacing = '3px';
  ctx.fillText(section.eyebrow || 'MODULE', 38, 56);

  ctx.font = '700 16px "Inter", monospace';
  ctx.fillStyle = primaryColor;
  ctx.letterSpacing = '1px';
  ctx.textAlign = 'right';
  ctx.fillText(section.code || `0${index + 1}`, w - 38, 56);
  ctx.textAlign = 'left';

  // 4. Notification Badge Pill (e.g. "5 Low", "6 Soon")
  if (section.badge) {
    const badgeText = section.badge;
    ctx.font = '700 15px "Inter", sans-serif';
    const bWidth = ctx.measureText(badgeText).width + 26;
    const bHeight = 28;
    const bx = w - 38 - bWidth;
    const by = 80;

    // Glowing Pill Background - High contrast vivid red
    ctx.fillStyle = '#dc2626';
    ctx.beginPath();
    ctx.roundRect(bx, by, bWidth, bHeight, 14);
    ctx.fill();

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.8;
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.fillText(badgeText, bx + bWidth / 2, by + 19);
    ctx.textAlign = 'left';
  }

  // 5. Stylized Central Motif Tile
  const cx = w / 2;
  const cy = h * 0.42;
  const tileRadius = 68;

  // Outer ambient glow circle
  const glowGrad = ctx.createRadialGradient(cx, cy, 10, cx, cy, tileRadius + 45);
  glowGrad.addColorStop(0, primaryColor + '40');
  glowGrad.addColorStop(0.5, warmColor + '20');
  glowGrad.addColorStop(1, 'transparent');
  ctx.fillStyle = glowGrad;
  ctx.beginPath();
  ctx.arc(cx, cy, tileRadius + 45, 0, Math.PI * 2);
  ctx.fill();

  // Glass Tile Base
  ctx.fillStyle = 'rgba(10, 5, 36, 0.75)';
  ctx.beginPath();
  ctx.roundRect(cx - tileRadius, cy - tileRadius, tileRadius * 2, tileRadius * 2, 28);
  ctx.fill();
  ctx.strokeStyle = primaryColor + 'aa';
  ctx.lineWidth = 3;
  ctx.stroke();

  // Central Icon Letter/Symbol
  ctx.font = '800 52px "Inter", sans-serif';
  ctx.fillStyle = '#ffffff';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const symbol = (section.name || 'E')[0].toUpperCase();
  ctx.fillText(symbol, cx, cy - 2);

  // 6. Section Name (Prominent Centered Heading)
  ctx.textBaseline = 'alphabetic';
  ctx.font = '700 36px "Inter", sans-serif';
  ctx.fillStyle = '#ffffff';
  ctx.letterSpacing = '-0.5px';
  ctx.shadowColor = 'rgba(0,0,0,0.8)';
  ctx.shadowBlur = 16;
  ctx.fillText(section.name, cx, h * 0.64);
  ctx.shadowBlur = 0;

  // 7. Live Metric Glass Container
  const panelW = w - 76;
  const panelH = 74;
  const panelX = 38;
  const panelY = h * 0.72;

  ctx.fillStyle = 'rgba(10, 5, 36, 0.65)';
  ctx.beginPath();
  ctx.roundRect(panelX, panelY, panelW, panelH, 18);
  ctx.fill();

  ctx.strokeStyle = 'rgba(143, 230, 255, 0.25)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Metric Value Text
  ctx.font = '700 22px "Inter", sans-serif';
  ctx.fillStyle = '#8fe6ff';
  ctx.fillText(section.metric || 'Realtime Active', panelX + 22, panelY + 36);

  ctx.font = '500 14px "Inter", sans-serif';
  ctx.fillStyle = 'rgba(232, 246, 255, 0.65)';
  ctx.fillText('LIVE STATUS', panelX + 22, panelY + 58);

  // Status indicator dot (cyan pulse)
  ctx.fillStyle = '#2bf0ff';
  ctx.beginPath();
  ctx.arc(panelX + panelW - 30, panelY + panelH / 2, 6, 0, Math.PI * 2);
  ctx.fill();

  // 8. Footer prompt: "Enter Section ↵"
  ctx.font = '600 16px "Inter", sans-serif';
  ctx.fillStyle = 'rgba(232, 246, 255, 0.85)';
  ctx.textAlign = 'center';
  ctx.letterSpacing = '1px';
  const actionText = section.locked ? 'LOCKED (RESTRICTED ROLE)' : 'ENTER SECTION  ↵';
  ctx.fillText(actionText, cx, h - 42);

  // Create Three.js Texture
  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  return texture;
}
