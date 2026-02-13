import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Settings } from "lucide-react";

export function SettingsDialog() {
    const [open, setOpen] = useState(false);
    const [autonomyMode, setAutonomyMode] = useState("semi");

    const saveSettings = async () => {
        // TODO: Save to backend
        setOpen(false);
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors">
                    <Settings className="w-4 h-4" />
                    <span className="text-sm">Settings</span>
                </button>
            </DialogTrigger>
            <DialogContent className="bg-[#141414] border-white/10 text-white">
                <DialogHeader>
                    <DialogTitle>Aether Settings</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    <div className="flex flex-col gap-2">
                        <label className="text-sm font-medium">Autonomy Mode</label>
                        <select
                            value={autonomyMode}
                            onChange={(e) => setAutonomyMode(e.target.value)}
                            className="bg-white/5 border border-white/10 rounded px-3 py-2 text-sm"
                        >
                            <option value="semi">Semi-Autonomous (Ask for permission)</option>
                            <option value="auto">Fully Autonomous (Risky)</option>
                        </select>
                    </div>
                    {/* Add more settings here */}
                </div>
                <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                    <Button onClick={saveSettings}>Save</Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
