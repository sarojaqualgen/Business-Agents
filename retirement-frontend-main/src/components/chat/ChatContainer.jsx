import React from 'react';
import { ChatProvider } from '../../context/ChatContext.jsx';
import ChatWindow from './ChatWindow.jsx';

/**
 * Entry point mounted by the participant "Chat" route. Scopes ChatProvider
 * to this subtree only, so its localStorage-backed transcript hydrates
 * exactly when the chat page is visited and stays isolated from the rest
 * of the dashboard.
 */
export default function ChatContainer() {
  return (
    <ChatProvider>
      <ChatWindow />
    </ChatProvider>
  );
}
