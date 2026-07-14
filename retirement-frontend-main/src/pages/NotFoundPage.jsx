import React from 'react';
import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg text-text px-6">
      <div className="text-center">
        <p className="font-mono text-text-faint text-sm mb-2">404</p>
        <h1 className="text-xl font-semibold mb-4">Page not found</h1>
        <Link to="/" className="text-accent hover:text-accent-dark text-sm">
          Return home
        </Link>
      </div>
    </div>
  );
}
