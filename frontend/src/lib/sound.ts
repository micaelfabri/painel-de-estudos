// Sons do cronômetro gerados no navegador (Web Audio): sem arquivo de áudio e sem nada externo.
// O navegador só libera áudio depois de um clique; por isso unlockAudio() roda no "Iniciar".

let ctx: AudioContext | null = null;

export function unlockAudio(): void {
  try {
    ctx ??= new AudioContext();
    if (ctx.state === "suspended") void ctx.resume();
  } catch {
    ctx = null; // sem áudio (navegador antigo ou bloqueado): o aviso visual continua
  }
}

function tone(freq: number, start: number, duration: number, volume: number): void {
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = freq;
  const t = ctx.currentTime + start;
  gain.gain.setValueAtTime(0.0001, t);
  gain.gain.exponentialRampToValueAtTime(volume, t + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + duration);
  osc.connect(gain).connect(ctx.destination);
  osc.start(t);
  osc.stop(t + duration + 0.05);
}

/** Meta atingida: dois toques suaves. */
export function playGoal(): void {
  tone(660, 0, 0.35, 0.25);
  tone(880, 0.4, 0.5, 0.25);
}

/** Alarme: três bipes mais fortes, repetidos duas vezes. */
export function playAlarm(): void {
  for (let r = 0; r < 2; r++) for (let i = 0; i < 3; i++) tone(988, r * 1.6 + i * 0.4, 0.25, 0.45);
}
