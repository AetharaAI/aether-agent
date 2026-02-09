import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  FileText,
  Image as ImageIcon,
  Globe,
  Code,
  X,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  FileCode,
  Table,
  Eye
} from "lucide-react";

export interface Artifact {
  id: string;
  type: "file" | "image" | "web" | "code" | "data";
  title: string;
  content?: string;
  url?: string;
  mimeType?: string;
  size?: number;
  timestamp: string;
  metadata?: Record<string, any>;
}

interface ArtifactsPanelProps {
  artifacts: Artifact[];
  selectedArtifact?: Artifact | null;
  onSelectArtifact: (artifact: Artifact | null) => void;
  isOpen: boolean;
  onToggle: () => void;
}

export function ArtifactsPanel({
  artifacts,
  selectedArtifact,
  onSelectArtifact,
  isOpen,
  onToggle,
}: ArtifactsPanelProps) {
  const [activeTab, setActiveTab] = useState<string>("all");

  const getArtifactIcon = (type: Artifact["type"]) => {
    switch (type) {
      case "image":
        return <ImageIcon className="w-4 h-4" />;
      case "web":
        return <Globe className="w-4 h-4" />;
      case "code":
        return <Code className="w-4 h-4" />;
      case "data":
        return <Table className="w-4 h-4" />;
      default:
        return <FileText className="w-4 h-4" />;
    }
  };

  const filteredArtifacts = activeTab === "all" 
    ? artifacts 
    : artifacts.filter(a => a.type === activeTab);

  const artifactCounts = {
    all: artifacts.length,
    file: artifacts.filter(a => a.type === "file").length,
    image: artifacts.filter(a => a.type === "image").length,
    web: artifacts.filter(a => a.type === "web").length,
    code: artifacts.filter(a => a.type === "code").length,
    data: artifacts.filter(a => a.type === "data").length,
  };

  // Collapsed state - just show toggle button
  if (!isOpen) {
    return (
      <div className="flex-none w-12 border-l border-border/50 bg-card/30 backdrop-blur-xl flex flex-col items-center py-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          className="mb-4"
        >
          <ChevronLeft className="w-5 h-5" />
        </Button>
        {artifacts.length > 0 && (
          <div className="flex flex-col items-center gap-2">
            {artifacts.slice(0, 3).map((artifact) => (
              <button
                key={artifact.id}
                onClick={() => {
                  onToggle();
                  onSelectArtifact(artifact);
                }}
                className="p-2 rounded-lg hover:bg-accent/20 text-muted-foreground"
                title={artifact.title}
              >
                {getArtifactIcon(artifact.type)}
              </button>
            ))}
          </div>
        )}
        <div className="flex-1" />
      </div>
    );
  }

  // If an artifact is selected, show detail view
  if (selectedArtifact) {
    return (
      <div className="flex-none w-96 border-l border-border/50 bg-card/30 backdrop-blur-xl flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-border/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {getArtifactIcon(selectedArtifact.type)}
              <h3 className="font-semibold truncate max-w-[200px]">
                {selectedArtifact.title}
              </h3>
            </div>
            <div className="flex items-center gap-1">
              {selectedArtifact.url && (
                <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
                  <a href={selectedArtifact.url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => onSelectArtifact(null)}
              >
                <X className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={onToggle}
              >
                <ChevronRight className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>

        {/* Content */}
        <ScrollArea className="flex-1 p-4">
          {selectedArtifact.type === "image" && selectedArtifact.url && (
            <img
              src={selectedArtifact.url}
              alt={selectedArtifact.title}
              className="max-w-full rounded-lg"
            />
          )}
          
          {selectedArtifact.type === "code" && (
            <pre className="bg-muted/50 p-4 rounded-lg overflow-x-auto text-sm font-mono">
              <code>{selectedArtifact.content}</code>
            </pre>
          )}
          
          {selectedArtifact.type === "web" && (
            <div className="space-y-4">
              <a
                href={selectedArtifact.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-accent hover:underline"
              >
                <Globe className="w-4 h-4" />
                {selectedArtifact.url}
              </a>
              {selectedArtifact.content && (
                <div className="prose prose-sm prose-invert max-w-none">
                  {selectedArtifact.content}
                </div>
              )}
            </div>
          )}
          
          {(selectedArtifact.type === "file" || selectedArtifact.type === "data") && (
            <div className="space-y-4">
              {selectedArtifact.content && (
                <div className="prose prose-sm prose-invert max-w-none">
                  {selectedArtifact.content}
                </div>
              )}
              {selectedArtifact.url && (
                <Button asChild variant="outline" className="w-full">
                  <a href={selectedArtifact.url} download>
                    <Download className="w-4 h-4 mr-2" />
                    Download
                  </a>
                </Button>
              )}
            </div>
          )}

          {/* Metadata */}
          {selectedArtifact.metadata && (
            <div className="mt-6 pt-4 border-t border-border/30">
              <h4 className="text-sm font-medium mb-2">Metadata</h4>
              <dl className="space-y-1 text-sm">
                {Object.entries(selectedArtifact.metadata).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <dt className="text-muted-foreground">{key}:</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </ScrollArea>
      </div>
    );
  }

  // List view
  return (
    <div className="flex-none w-80 border-l border-border/50 bg-card/30 backdrop-blur-xl flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border/30">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Artifacts</h2>
          <Button variant="ghost" size="icon" onClick={onToggle}>
            <ChevronRight className="w-5 h-5" />
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <TabsList className="grid grid-cols-3 mx-4 mt-2">
          <TabsTrigger value="all" className="text-xs">
            All ({artifactCounts.all})
          </TabsTrigger>
          <TabsTrigger value="file" className="text-xs">
            Files ({artifactCounts.file})
          </TabsTrigger>
          <TabsTrigger value="web" className="text-xs">
            Web ({artifactCounts.web})
          </TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="flex-1 mt-0">
          <ScrollArea className="h-full">
            <div className="p-2 space-y-1">
              {filteredArtifacts.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <FileCode className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No artifacts yet</p>
                  <p className="text-xs">
                    Files, images, and web results will appear here
                  </p>
                </div>
              ) : (
                filteredArtifacts.map((artifact) => (
                  <button
                    key={artifact.id}
                    onClick={() => onSelectArtifact(artifact)}
                    className={cn(
                      "w-full flex items-center gap-3 p-3 rounded-lg text-left",
                      "hover:bg-accent/10 transition-colors"
                    )}
                  >
                    <div className="text-muted-foreground">
                      {getArtifactIcon(artifact.type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {artifact.title}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {artifact.type} • {new Date(artifact.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                    <Eye className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100" />
                  </button>
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default ArtifactsPanel;
