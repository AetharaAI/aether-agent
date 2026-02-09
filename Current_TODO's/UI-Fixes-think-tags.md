
## **PROMPT FOR YOUR INTERNAL AGENT (copy/paste)**

> **Goal:** Fix response formatting, make “thinking” collapsible, and ensure correct auto-scroll behavior in the Aether Agent UI — without changing the model’s reasoning behavior.
>
> ### 1) Canonical response format (server-side contract)
>
> Enforce this structure in every streamed response:
>
> ```
> <think>
> ...raw chain-of-thought...
> </think>
>
> <answer>
> ...final response in clean markdown...
> </answer>
> ```
>
> If the model does not already emit these tags, wrap them at the API gateway layer before streaming to the client.
>
> ---
>
> ### 2) Client-side rendering rules (React)
>
> **Parsing rule**
>
> * Split incoming message on `<think>` and `</think>`.
> * Everything inside becomes a **collapsible block**.
> * Everything inside `<answer>` renders as normal markdown.
>
> **Render the thinking block like this:**
>
> ```tsx
> function ThinkingBlock({ content }: { content: string }) {
>   return (
>     <details className="thinking">
>       <summary>🧠 Model reasoning (click to expand)</summary>
>       <pre>{content}</pre>
>     </details>
>   );
> }
> ```
>
> **Render the answer normally:**
>
> ```tsx
> <MarkdownRenderer content={answerText} />
> ```
>
> CSS (minimal)
>
> ```css
> .thinking {
>   opacity: 0.85;
>   font-size: 0.9rem;
>   margin: 8px 0;
> }
> .thinking summary {
>   cursor: pointer;
>   font-weight: 600;
> }
> ```
>
> ---
>
> ### 3) Streaming behavior
>
> * Stream **answer first** for UI responsiveness.
> * Buffer `<think>` in memory and render it **after** the answer arrives (still collapsible).
>
> ---
>
> ### 4) Auto-scroll (critical fix)
>
> Create a bottom sentinel and scroll to it **on two events only**:
>
> 1. When the user hits Send
> 2. When a new chunk arrives from the WebSocket
>
> ```tsx
> const bottomRef = useRef<HTMLDivElement>(null);
>
> function scrollToBottom() {
>   bottomRef.current?.scrollIntoView({ behavior: "smooth" });
> }
>
> useEffect(() => {
>   scrollToBottom();        // on every new message chunk
> }, [messages]);
> ```
>
> In your layout:
>
> ```tsx
> <div className="chat-scroll-area">
>   {messages.map(renderMessage)}
>   <div ref={bottomRef} />   // sentinel
> </div>
> ```
>
> ---
>
> ### 5) Sticky input bar (do NOT break this)
>
> Keep the input pinned. Only `.chat-scroll-area` should scroll.
>
> ---
>
> ### 6) Acceptance tests (must pass)
>
> * Sending a message auto-scrolls to bottom **before** the reply.
> * As the reply streams, the viewport stays locked to the newest text.
> * Thinking is visible **only when expanded**; collapsed state shows a single line.
> * Copy/paste of a full message preserves clean markdown.
> * No regressions to WebSocket streaming speed or formatting.
>
> If any test fails, fix it before shipping.

---

