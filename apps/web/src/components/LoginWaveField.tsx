import { useEffect, useRef } from "react";
import type { ThemeMode } from "../theme";

type Palette = {
  bg: string;
  dot: string;
  glow: string;
  link: string;
};

const PALETTES: Record<ThemeMode, Palette> = {
  dark: {
    bg: "#070b12",
    dot: "rgba(96, 165, 250, 0.55)",
    glow: "rgba(59, 130, 246, 0.35)",
    link: "rgba(56, 189, 248, 0.08)",
  },
  light: {
    bg: "#eef3fa",
    dot: "rgba(37, 99, 235, 0.38)",
    glow: "rgba(37, 99, 235, 0.22)",
    link: "rgba(37, 99, 235, 0.06)",
  },
};

type LoginWaveFieldProps = {
  theme: ThemeMode;
};

export function LoginWaveField({ theme }: LoginWaveFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let dpr = 1;
    let raf = 0;
    let start = performance.now();

    type Dot = { x: number; y: number; phase: number; amp: number };
    let dots: Dot[] = [];

    function rebuild() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas!.width = Math.floor(width * dpr);
      canvas!.height = Math.floor(height * dpr);
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);

      const spacing = width < 640 ? 28 : 34;
      const next: Dot[] = [];
      for (let y = -spacing; y <= height + spacing; y += spacing) {
        for (let x = -spacing; x <= width + spacing; x += spacing) {
          next.push({
            x,
            y,
            phase: (x * 0.018 + y * 0.014) % (Math.PI * 2),
            amp: 10 + ((x * 13 + y * 7) % 9),
          });
        }
      }
      dots = next;
    }

    function draw(now: number) {
      const t = (now - start) / 1000;
      const p = PALETTES[theme];

      ctx!.fillStyle = p.bg;
      ctx!.fillRect(0, 0, width, height);

      // soft ambient wash
      const gx = width * (0.35 + 0.08 * Math.sin(t * 0.35));
      const gy = height * (0.4 + 0.1 * Math.cos(t * 0.28));
      const grad = ctx!.createRadialGradient(gx, gy, 40, gx, gy, Math.max(width, height) * 0.55);
      grad.addColorStop(0, p.glow);
      grad.addColorStop(1, "transparent");
      ctx!.fillStyle = grad;
      ctx!.fillRect(0, 0, width, height);

      const linkDist = width < 640 ? 52 : 64;

      // subtle links between nearby displaced dots
      ctx!.strokeStyle = p.link;
      ctx!.lineWidth = 1;
      for (let i = 0; i < dots.length; i += 3) {
        const a = dots[i];
        const ax =
          a.x +
          Math.sin(t * 0.7 + a.phase) * a.amp +
          Math.sin(t * 0.31 + a.y * 0.01) * 6;
        const ay =
          a.y +
          Math.cos(t * 0.55 + a.phase * 1.3) * a.amp * 0.7 +
          Math.sin(t * 0.42 + a.x * 0.008) * 8;
        for (let j = i + 1; j < Math.min(i + 8, dots.length); j++) {
          const b = dots[j];
          const bx =
            b.x +
            Math.sin(t * 0.7 + b.phase) * b.amp +
            Math.sin(t * 0.31 + b.y * 0.01) * 6;
          const by =
            b.y +
            Math.cos(t * 0.55 + b.phase * 1.3) * b.amp * 0.7 +
            Math.sin(t * 0.42 + b.x * 0.008) * 8;
          const dx = ax - bx;
          const dy = ay - by;
          const dist = Math.hypot(dx, dy);
          if (dist < linkDist) {
            ctx!.globalAlpha = (1 - dist / linkDist) * 0.9;
            ctx!.beginPath();
            ctx!.moveTo(ax, ay);
            ctx!.lineTo(bx, by);
            ctx!.stroke();
          }
        }
      }
      ctx!.globalAlpha = 1;

      for (const d of dots) {
        const waveX =
          Math.sin(t * 0.7 + d.phase) * d.amp + Math.sin(t * 0.31 + d.y * 0.01) * 6;
        const waveY =
          Math.cos(t * 0.55 + d.phase * 1.3) * d.amp * 0.7 +
          Math.sin(t * 0.42 + d.x * 0.008) * 8;
        const px = d.x + waveX;
        const py = d.y + waveY;
        const pulse = 0.55 + 0.45 * Math.sin(t * 1.1 + d.phase);
        const r = 1.1 + pulse * 1.4;

        ctx!.beginPath();
        ctx!.fillStyle = p.dot;
        ctx!.globalAlpha = 0.35 + pulse * 0.55;
        ctx!.arc(px, py, r, 0, Math.PI * 2);
        ctx!.fill();
      }
      ctx!.globalAlpha = 1;

      if (!reduced) raf = requestAnimationFrame(draw);
    }

    rebuild();
    if (reduced) {
      draw(performance.now());
    } else {
      raf = requestAnimationFrame(draw);
    }

    const onResize = () => {
      rebuild();
      if (reduced) draw(performance.now());
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
    };
  }, [theme]);

  return (
    <canvas
      ref={canvasRef}
      className="login-wave-field"
      aria-hidden="true"
    />
  );
}
