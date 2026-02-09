import { useState, useRef, useCallback, KeyboardEvent, ChangeEvent } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Attachment } from "@/hooks/useAgentRuntime";
import { 
  Send, 
  Paperclip, 
  X, 
  FileText, 
  Image as ImageIcon,
  Loader2,
  Mic
} from "lucide-react";

interface AetherInputProps {
  onSend: (text: string, attachments?: Attachment[]) => void;
  isLoading?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export function AetherInput({ 
  onSend, 
  isLoading, 
  disabled,
  placeholder = "Type a message..."
}: AetherInputProps) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, []);

  const handleTextChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    adjustHeight();
  };

  const handleSend = () => {
    if ((!text.trim() && attachments.length === 0) || isLoading || disabled) return;
    
    onSend(text.trim(), attachments.length > 0 ? attachments : undefined);
    setText("");
    setAttachments([]);
    
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const newAttachments: Attachment[] = [];

    for (const file of Array.from(files)) {
      // Read file as base64
      const reader = new FileReader();
      const base64Promise = new Promise<string>((resolve) => {
        reader.onloadend = () => {
          const base64 = reader.result?.toString().split(",")[1] || "";
          resolve(base64);
        };
      });
      
      reader.readAsDataURL(file);
      const base64 = await base64Promise;

      newAttachments.push({
        type: "file",
        filename: file.name,
        mime_type: file.type,
        content: base64,
      });
    }

    setAttachments((prev) => [...prev, ...newAttachments]);
    
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (!files.length) return;

    const newAttachments: Attachment[] = [];

    for (const file of Array.from(files)) {
      const reader = new FileReader();
      const base64Promise = new Promise<string>((resolve) => {
        reader.onloadend = () => {
          const base64 = reader.result?.toString().split(",")[1] || "";
          resolve(base64);
        };
      });
      
      reader.readAsDataURL(file);
      const base64 = await base64Promise;

      newAttachments.push({
        type: "file",
        filename: file.name,
        mime_type: file.type,
        content: base64,
      });
    }

    setAttachments((prev) => [...prev, ...newAttachments]);
  };

  const hasContent = text.trim().length > 0 || attachments.length > 0;

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        "relative rounded-xl border bg-background transition-colors",
        isDragging && "border-primary bg-primary/5",
        disabled && "opacity-50"
      )}
    >
      {/* Attachment preview */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 p-2 border-b border-border/50">
          {attachments.map((att, i) => (
            <AttachmentPreview 
              key={i} 
              attachment={att} 
              onRemove={() => removeAttachment(i)} 
            />
          ))}
        </div>
      )}

      {/* Text input */}
      <div className="flex items-end gap-2 p-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="flex-1 bg-transparent border-0 resize-none py-2 px-1 focus:outline-none focus:ring-0 min-h-10 max-h-50"
        />

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0 pb-1">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            accept="image/*,.txt,.md,.json,.csv,.pdf"
          />

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            type="button"
          >
            <Paperclip className="w-4 h-4" />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            disabled={disabled}
            type="button"
          >
            <Mic className="w-4 h-4" />
          </Button>

          <Button
            onClick={handleSend}
            disabled={!hasContent || isLoading || disabled}
            size="icon"
            className={cn(
              "h-8 w-8 transition-all",
              hasContent && "bg-primary text-primary-foreground"
            )}
            type="button"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Drag overlay */}
      {isDragging && (
        <div className="absolute inset-0 bg-primary/5 border-2 border-dashed border-primary rounded-xl flex items-center justify-center">
          <p className="text-sm text-primary font-medium">Drop files here</p>
        </div>
      )}
    </div>
  );
}

function AttachmentPreview({ 
  attachment, 
  onRemove 
}: { 
  attachment: Attachment; 
  onRemove: () => void;
}) {
  const isImage = attachment.mime_type?.startsWith("image/");

  return (
    <div className="flex items-center gap-2 px-2 py-1.5 bg-muted rounded-lg text-sm group">
      {isImage ? (
        <ImageIcon className="w-4 h-4 text-muted-foreground" />
      ) : (
        <FileText className="w-4 h-4 text-muted-foreground" />
      )}
      <span className="max-w-30 truncate text-xs">
        {attachment.filename}
      </span>
      <button
        onClick={onRemove}
        className="opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <X className="w-3 h-3 text-muted-foreground hover:text-foreground" />
      </button>
    </div>
  );
}

export default AetherInput;
