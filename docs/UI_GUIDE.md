# Aether UI - User Guide

**Version**: 1.0.0  
**Author**: Manus AI  
**Date**: February 1, 2026

## Overview

The Aether UI provides a modern, intuitive web interface for interacting with the Aether AI assistant agent. Inspired by Cursor's agent panel and Kilocode's interface, it features a sleek vertical panel design with real-time chat, file uploads, mode controls, context management, and integrated terminal access.

The interface maintains full compatibility with Aether's CLI capabilities while offering a visual, user-friendly experience for both technical and non-technical users.

## Design Philosophy

The Aether UI follows the **"Ethereal Tech"** design philosophy, combining deep space aesthetics with functional clarity. The interface features a dark theme with purple and cyan accents, glass-morphism effects, and smooth animations to create a premium AI assistant experience.

### Key Design Elements

The visual design emphasizes ambient depth through layered backgrounds with subtle gradients and glow effects. Functional clarity is maintained through a clear information hierarchy despite the dark theme. Fluid motion is achieved through smooth transitions and micro-interactions that enhance the user experience. Glass morphism creates frosted glass effects for panels and cards, adding depth and sophistication. Contextual awareness provides visual feedback for agent state and context usage, keeping users informed at all times.

## Interface Components

### Chat Interface

The chat interface serves as the primary interaction area where users communicate with Aether. Messages are displayed in a scrollable area with distinct visual styles for user and agent messages. User messages appear on the right side with a purple glow effect, while agent messages appear on the left with a cyan accent. Each message includes a timestamp for reference, and the interface supports streaming responses for real-time interaction.

The chat area automatically scrolls to show the latest messages, ensuring users always see the most recent conversation. Messages use glass-morphism effects with backdrop blur for a modern, polished appearance.

### Input Area

The input area at the bottom of the panel provides a text input field for composing messages to Aether. A paperclip button allows users to attach files and images for processing. A microphone button enables voice input through speech-to-text conversion. A speaker button toggles text-to-speech for agent responses. The send button, highlighted with a purple glow, submits messages to the agent. The input supports multi-line text entry and automatically expands as needed. Pressing Enter sends the message, while Shift+Enter creates a new line.

### Mode Selector

The mode selector allows users to toggle between two autonomy modes. **Semi-Autonomous mode** (indicated by a shield icon) requires human approval for risky actions such as sending emails, deleting files, or making external API calls. **Autonomous mode** (indicated by a lightning icon) allows the agent to execute tasks without requiring approval for most actions.

The current mode is clearly displayed with an icon and description. A toggle switch provides easy mode switching, and visual feedback confirms the active mode through color-coded indicators.

### Context Gauge

The context gauge displays the current memory usage as a percentage with a color-coded progress bar. Green indicates healthy usage (below 60%), yellow indicates moderate usage (60-80%), and red indicates high usage (above 80%). When context usage exceeds 80%, a **Compress Context** button appears, allowing users to migrate daily logs to long-term memory and free up space.

The gauge updates automatically every 5 seconds to reflect current memory status, helping users manage Aether's memory effectively.

### Quick Actions

Two quick action buttons provide access to additional features. The **Terminal** button opens a collapsible terminal output view showing command execution history and system status. The **Settings** button (placeholder for future implementation) will provide access to agent configuration options.

### Terminal Output

The terminal section displays command execution history and system output in a monospace font with syntax highlighting. Users can view recent commands, their output, and exit codes. The terminal supports auto-scrolling to show the latest output and includes a copy button for each command. The section is collapsible to save screen space when not needed.

### Status Indicator

A status badge in the header shows the agent's connection status. A pulsing green dot with "Online" indicates an active connection, while a red dot with "Offline" indicates disconnection. The badge updates in real-time based on WebSocket connection status.

## Features

### Real-Time Chat

The UI uses WebSocket connections for real-time bidirectional communication with the Aether backend. Messages are delivered instantly without page refreshes, and the interface supports streaming responses for long-running tasks. Automatic reconnection handles temporary network interruptions gracefully.

### File Upload

Users can attach files and images to messages using the paperclip button. Supported file types include documents, images, code files, and data files. Uploaded files are processed by Aether and can be referenced in subsequent messages. The interface shows upload progress and confirms successful uploads.

### Voice Input (Speech-to-Text)

The microphone button enables hands-free interaction with Aether through voice input. When clicked, the button changes to a checkmark and begins recording audio from the user's microphone. A pulsing visual indicator shows the current audio level, providing real-time feedback that the system is capturing speech. Users speak their message naturally, and when finished, click the checkmark button to stop recording. The recorded audio is sent to the configured ASR (Automatic Speech Recognition) service, which transcribes the speech to text. The transcribed text appears in the input field, where users can review and edit it before sending. This feature requires microphone permissions and works with any ASR service that accepts audio files and returns text transcriptions.

### Voice Output (Text-to-Speech)

The speaker button enables audio playback of agent responses through text-to-speech synthesis. When TTS is enabled (indicated by a cyan-highlighted speaker icon), all agent responses are automatically spoken aloud using the configured TTS service. The system queues responses and plays them in order, preventing overlapping audio. Users can toggle TTS on or off at any time by clicking the speaker button. When disabled, the button shows a muted speaker icon. This feature works with any TTS service that accepts text and returns audio data in common formats like MP3, WAV, or OGG.

### Context Management

The context gauge provides visibility into Aether's memory usage. Users can compress context manually when usage is high, and the system provides visual warnings when memory approaches capacity. Context statistics update automatically to reflect current usage.

### Mode Control

Users can switch between semi-autonomous and autonomous modes based on their trust level and task requirements. Mode changes take effect immediately and are confirmed with toast notifications. The current mode is always visible in the interface.

### Terminal Integration

The integrated terminal view shows command execution history and system status. Users can see commands executed by Aether, their output, and exit codes. The terminal supports syntax highlighting for improved readability.

## Usage Workflow

### Starting a Conversation

To begin interacting with Aether, ensure the status indicator shows "Online" in the header. Type your message in the input field at the bottom of the panel. Press Enter or click the send button to submit your message. Aether will process your request and respond in the chat area. You can continue the conversation by sending additional messages.

### Uploading Files

To upload a file for Aether to process, click the paperclip button next to the input field. Select the file you want to upload from your device. Wait for the upload to complete (indicated by a success message). Reference the uploaded file in your message to Aether. The agent will process the file and respond accordingly.

### Using Voice Input

To send a message using voice instead of typing, click the microphone button in the input area. The button will change to a checkmark and begin recording. Speak your message clearly into your microphone. Watch the pulsing indicator to confirm audio is being captured. Click the checkmark button when you finish speaking. Wait for the transcription to appear in the input field. Review and edit the transcribed text if needed. Press Enter or click Send to submit the message.

### Using Voice Output

To have agent responses spoken aloud, click the speaker button to enable TTS. The button will highlight in cyan when active. Send messages as normal and agent responses will be spoken automatically. Listen to the audio playback of each response. Click the speaker button again to disable TTS if desired. The system will stop speaking and return to text-only mode.

### Managing Context

To monitor and manage Aether's memory usage, check the context gauge regularly to see current usage. When usage exceeds 80%, the gauge turns red and a compress button appears. Click **Compress Context** to migrate daily logs to long-term memory. The gauge will update to show the new usage percentage after compression completes.

### Switching Modes

To change Aether's autonomy mode, locate the mode selector section below the input area. Toggle the switch to change between semi-autonomous and autonomous modes. A toast notification will confirm the mode change. The interface will update to show the new mode with the appropriate icon.

### Viewing Terminal Output

To see command execution history, click the **Terminal** button in the quick actions section. The terminal panel will expand to show recent commands and output. Scroll through the history to review past executions. Click the minimize button or the Terminal button again to collapse the panel.

## Technical Architecture

### Frontend Stack

The Aether UI is built with modern web technologies for performance and maintainability. React 19 provides the component framework with hooks for state management. TailwindCSS 4 handles styling with custom theme variables. Framer Motion adds smooth animations and transitions. shadcn/ui provides pre-built accessible components. Lucide React supplies icon assets. Wouter handles client-side routing.

### Backend Integration

The frontend communicates with the Aether backend through two channels. WebSocket connections at `ws://localhost:8000/ws/chat` provide real-time bidirectional messaging. REST API endpoints at `http://localhost:8000/api/*` handle status queries, mode changes, file uploads, and context management.

### State Management

The UI uses React hooks for local state management. The `useAetherWebSocket` custom hook manages WebSocket connections and message handling. The `aetherAPI` client library wraps REST API calls. React Context could be added for global state if needed in future versions.

### Data Flow

User interactions in the UI trigger actions that flow through the system. Chat messages are sent via WebSocket to the backend, processed by Aether core, and responses are streamed back to the UI. API calls for status, mode changes, and context management use REST endpoints with JSON payloads. File uploads use multipart form data sent to the upload endpoint.

## Configuration

### Environment Variables

The UI requires configuration through environment variables. `VITE_API_URL` specifies the backend API base URL (default: `http://localhost:8000`). `VITE_ASR_ENDPOINT` specifies the speech-to-text service endpoint (default: `http://localhost:8001/asr`). `VITE_TTS_ENDPOINT` specifies the text-to-speech service endpoint (default: `http://localhost:8002/tts`). These variables should be configured in the Manus project settings under Secrets.

For detailed voice service configuration, including API format requirements and compatible services, see the `VOICE_SETUP.md` guide included with the project.

### Backend Setup

Before using the UI, ensure the Aether backend is running. Start Redis Stack on port 6379. Configure the NVIDIA API key in the backend environment. Run the API server with `python aether/api_server.py`. Verify the server is running at `http://localhost:8000/health`.

## Troubleshooting

### Connection Issues

If the status indicator shows "Offline", check that the backend API server is running at the configured URL. Verify Redis Stack is running and accessible. Check browser console for WebSocket connection errors. Ensure no firewall is blocking WebSocket connections. Try refreshing the page to reconnect.

### Message Not Sending

If messages fail to send, confirm the WebSocket connection is active (status shows "Online"). Check that the input field is not empty. Verify the backend is processing messages (check backend logs). Look for error messages in browser console. Try reconnecting by refreshing the page.

### Context Gauge Not Updating

If the context gauge does not update, ensure the backend API is responding to `/api/context/stats` requests. Check browser network tab for failed API calls. Verify Redis is running and accessible to the backend. Try manually refreshing the page. Check backend logs for errors.

### File Upload Failing

If file uploads fail, verify the file size is within limits (check backend configuration). Ensure the file type is supported. Check network tab for upload errors. Verify the backend `/api/upload` endpoint is accessible. Check backend logs for processing errors.

## Future Enhancements

Several features are planned for future versions of the Aether UI. Settings panel implementation will provide access to agent configuration, API key management, and UI customization options. Voice input and output will enable natural voice interaction with Aether. Mobile responsive design will optimize the interface for tablet and smartphone screens. Keyboard shortcuts will provide power users with quick access to common actions. Theme customization will allow users to personalize colors and appearance. Multi-session support will enable managing multiple Aether instances simultaneously.

## Conclusion

The Aether UI provides a powerful, intuitive interface for interacting with the Aether AI assistant agent. By combining modern design principles with robust functionality, it makes AI assistance accessible to both technical and non-technical users while maintaining full compatibility with Aether's CLI capabilities.

For technical details on the backend API, see the main Aether documentation. For information on the agent's capabilities, refer to the Aether Architecture document.
