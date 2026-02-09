import { toast } from "sonner";

interface ToastOptions {
  title?: string;
  description?: string;
  variant?: "default" | "destructive";
  duration?: number;
}

export function useToast() {
  const showToast = (options: ToastOptions) => {
    if (options.variant === "destructive") {
      toast.error(options.title, {
        description: options.description,
        duration: options.duration,
      });
    } else {
      toast.success(options.title, {
        description: options.description,
        duration: options.duration,
      });
    }
  };

  return {
    toast: showToast,
  };
}

export { toast };
