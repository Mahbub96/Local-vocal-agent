import { motion } from "framer-motion";

export type VoiceOrbProps = {
  /** Pulse ambient ring + orb when assistant is active. */
  active?: boolean;
};

/** Center gradient orb with orbital rings (voice / assistant visual). */
export function VoiceOrb({ active = false }: VoiceOrbProps) {
  return (
    <div className="relative flex size-26 items-center justify-center sm:size-30 md:size-32">
      <motion.div
        className="absolute inset-[-20%] rounded-full bg-linear-to-br from-[#00d2ff]/25 via-[#6366f1]/15 to-[#9d50bb]/28 blur-3xl"
        animate={{ opacity: active ? [0.45, 0.88, 0.45] : 0.35, scale: active ? [0.96, 1.04, 0.96] : 1 }}
        transition={{ duration: 3.2, repeat: active ? Infinity : 0, ease: "easeInOut" }}
        aria-hidden
      />
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center" aria-hidden>
        <div className="absolute aspect-square w-[118%] rounded-full border border-dashed border-white/18" />
        <div className="absolute aspect-square w-[138%] rounded-full border border-dashed border-white/10" />
        <div className="absolute aspect-square w-[158%] rounded-full border border-dotted border-white/[0.07]" />
      </div>
      <motion.div
        className="relative z-10 rounded-full bg-linear-to-b from-[#9d50bb] via-indigo-600 to-[#00d2ff] p-px shadow-[0_0_40px_rgba(157,80,187,0.45),0_0_32px_rgba(0,210,255,0.28)]"
        animate={active ? { scale: [1, 1.03, 1] } : { scale: 1 }}
        transition={{ duration: 2.4, repeat: active ? Infinity : 0, ease: "easeInOut" }}
      >
        <div
          className="relative grid size-20 place-items-center overflow-hidden rounded-full sm:size-24 md:size-26"
          style={{
            background:
              "radial-gradient(ellipse 80% 70% at 40% 35%, rgba(255,255,255,0.12), transparent 55%), #060a10",
            boxShadow: "inset 0 0 40px rgba(59,130,246,0.12)",
          }}
        >
          <div
            className="pointer-events-none absolute inset-[18%] rounded-full opacity-40"
            style={{
              background:
                "radial-gradient(ellipse at 30% 20%, rgba(34,211,238,0.35), transparent 55%), radial-gradient(ellipse at 70% 80%, rgba(168,85,247,0.25), transparent 50%)",
            }}
            aria-hidden
          />
        </div>
      </motion.div>
    </div>
  );
}
