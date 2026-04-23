type WaveformIconProps = { className?: string };

/** Decorative top-bar waveform between title parts */
export function WaveformIcon({ className }: WaveformIconProps) {
  const bars = [2, 6, 3, 8, 2, 7, 3, 5, 1, 6, 2, 5];
  return (
    <svg
      className={className}
      viewBox="0 0 48 12"
      width={48}
      height={12}
      aria-hidden
    >
      {bars.map((h, i) => {
        const x = 2 + i * 3.5;
        const y = 10 - h;
        return <rect className="waveform-icon__bar" key={i} x={x} y={y} width="2" height={h} rx="0.5" fill="currentColor" />;
      })}
    </svg>
  );
}
