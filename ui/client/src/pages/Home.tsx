import AetherPanel from "@/components/AetherPanel";

export default function Home() {
  return (
    <div className="h-screen w-screen overflow-hidden bg-background">
      {/* Background effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      </div>
      
      {/* Aether Panel - Full screen */}
      <AetherPanel />
    </div>
  );
}
