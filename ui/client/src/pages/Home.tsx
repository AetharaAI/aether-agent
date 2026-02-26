import AetherPanelV2 from "@/components/AetherPanelV2";

interface HomeProps {
  sessionId?: string;
}

export default function Home({ sessionId }: HomeProps) {
  return (
    <div className="h-screen w-screen bg-transparent overflow-hidden">
      <AetherPanelV2 sessionId={sessionId} />
    </div>
  );
}
