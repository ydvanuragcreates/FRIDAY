"use client";

export default function Drawer({
  side,
  onClose,
  children,
}: {
  side: "left" | "right";
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-40">
      <button
        aria-label="Close panel"
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />
      <div
        className={`absolute top-0 h-full w-72 max-w-[85vw] border-border bg-panel shadow-xl ${
          side === "left" ? "left-0 border-r" : "right-0 border-l"
        }`}
      >
        {children}
      </div>
    </div>
  );
}
