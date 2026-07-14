import React, { useState } from 'react';
import Sidebar from './Sidebar.jsx';
import Header from './Header.jsx';

/**
 * Shared enterprise shell: fixed sidebar + scrollable content column with a
 * sticky header. `variant` selects the sidebar's role-scoped navigation.
 * Below the `lg` breakpoint the sidebar becomes a slide-in drawer, toggled
 * from the hamburger button in the header, so the console stays usable on
 * tablet and mobile widths.
 */
export default function AppLayout({ variant, title, subtitle, children }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-bg text-text">
      <Sidebar variant={variant} isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      <div className="flex-1 min-w-0 flex flex-col">
        <Header title={title} subtitle={subtitle} onMenuClick={() => setIsSidebarOpen(true)} />
        <main className="flex-1 px-4 py-5 sm:px-6 sm:py-6 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
