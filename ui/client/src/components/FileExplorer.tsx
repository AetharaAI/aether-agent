"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import Editor from "@monaco-editor/react";
import {
  Folder,
  FileText,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  Save,
  X,
  FilePlus,
  FolderPlus,
  Trash2,
} from "lucide-react";

interface FileNode {
  name: string;
  type: "file" | "directory";
  path: string;
  size?: number;
  children?: FileNode[];
  isOpen?: boolean;
}

interface FileExplorerProps {
  className?: string;
}

export function FileExplorer({ className }: FileExplorerProps) {
  const [files, setFiles] = useState<FileNode[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const fetchFiles = useCallback(async (path: string = "/") => {
    try {
      const res = await fetch(`/api/files/list?path=${encodeURIComponent(path)}`);
      if (res.ok) {
        const data = await res.json();
        setFiles(data.files || []);
      }
    } catch (e) {
      console.error("Failed to fetch files:", e);
    }
  }, []);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const loadFile = async (path: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/files/read?path=${encodeURIComponent(path)}`);
      if (res.ok) {
        const data = await res.json();
        setFileContent(data.content || "");
        setSelectedFile(path);
      }
    } catch (e) {
      console.error("Failed to load file:", e);
    } finally {
      setIsLoading(false);
    }
  };

  const saveFile = async () => {
    if (!selectedFile) return;
    
    setIsSaving(true);
    try {
      const res = await fetch(`/api/files/write`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: selectedFile,
          content: fileContent,
        }),
      });
      
      if (res.ok) {
        // Show success indicator
      }
    } catch (e) {
      console.error("Failed to save file:", e);
    } finally {
      setIsSaving(false);
    }
  };

  const toggleFolder = (node: FileNode, nodes: FileNode[]): FileNode[] => {
    return nodes.map((n) => {
      if (n.path === node.path) {
        return { ...n, isOpen: !n.isOpen };
      }
      if (n.children) {
        return { ...n, children: toggleFolder(node, n.children) };
      }
      return n;
    });
  };

  const getLanguage = (filename: string): string => {
    const ext = filename.split(".").pop()?.toLowerCase();
    const map: Record<string, string> = {
      js: "javascript",
      ts: "typescript",
      jsx: "javascript",
      tsx: "typescript",
      py: "python",
      json: "json",
      md: "markdown",
      yaml: "yaml",
      yml: "yaml",
      html: "html",
      css: "css",
      sh: "shell",
      bash: "shell",
    };
    return map[ext || ""] || "plaintext";
  };

  const renderFileTree = (nodes: FileNode[], depth: number = 0) => {
    return nodes.map((node) => (
      <div key={node.path}>
        <button
          className={cn(
            "w-full flex items-center gap-1 px-2 py-1 text-sm hover:bg-muted/50 transition-colors",
            selectedFile === node.path && "bg-primary/10 text-primary"
          )}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          onClick={() => {
            if (node.type === "directory") {
              setFiles((prev) => toggleFolder(node, prev));
            } else {
              loadFile(node.path);
            }
          }}
        >
          {node.type === "directory" && (
            <span className="w-4 h-4 flex items-center justify-center">
              {node.isOpen ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
            </span>
          )}
          {node.type === "directory" ? (
            <Folder className="w-4 h-4 text-yellow-500" />
          ) : (
            <FileText className="w-4 h-4 text-blue-500" />
          )}
          <span className="truncate">{node.name}</span>
        </button>
        {node.type === "directory" &&
          node.isOpen &&
          node.children &&
          renderFileTree(node.children, depth + 1)}
      </div>
    ));
  };

  return (
    <div className={cn("flex h-[500px] border border-border rounded-lg overflow-hidden", className)}>
      {/* File Tree Sidebar */}
      <div className="w-48 flex flex-col border-r border-border bg-muted/20">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-2 py-1.5 border-b border-border">
          <span className="text-xs font-medium text-muted-foreground">Workspace</span>
          <div className="flex items-center gap-0.5">
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => fetchFiles()}>
              <RefreshCw className="w-3 h-3" />
            </Button>
            <Button variant="ghost" size="icon" className="h-6 w-6">
              <FilePlus className="w-3 h-3" />
            </Button>
            <Button variant="ghost" size="icon" className="h-6 w-6">
              <FolderPlus className="w-3 h-3" />
            </Button>
          </div>
        </div>

        {/* File Tree */}
        <div className="flex-1 overflow-auto py-1">
          {files.length > 0 ? (
            renderFileTree(files)
          ) : (
            <div className="text-center text-xs text-muted-foreground py-4">
              No files
            </div>
          )}
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 flex flex-col bg-background">
        {selectedFile ? (
          <>
            {/* Editor Header */}
            <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-muted/30">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-medium">{selectedFile.split("/").pop()}</span>
                <span className="text-xs text-muted-foreground">{selectedFile}</span>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1"
                  onClick={saveFile}
                  disabled={isSaving}
                >
                  {isSaving ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Save className="w-3.5 h-3.5" />
                  )}
                  Save
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => {
                    setSelectedFile(null);
                    setFileContent("");
                  }}
                >
                  <X className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>

            {/* Monaco Editor */}
            <div className="flex-1">
              <Editor
                height="100%"
                language={getLanguage(selectedFile)}
                value={fileContent}
                onChange={(value) => setFileContent(value || "")}
                theme="vs-dark"
                options={{
                  minimap: { enabled: false },
                  fontSize: 13,
                  lineNumbers: "on",
                  automaticLayout: true,
                  scrollBeyondLastLine: false,
                }}
                loading={
                  <div className="flex items-center justify-center h-full text-muted-foreground">
                    Loading editor...
                  </div>
                }
              />
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <FileText className="w-12 h-12 mb-4 opacity-50" />
            <p className="text-sm">Select a file to edit</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default FileExplorer;
