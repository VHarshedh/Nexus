import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/lib/auth-context';
import { QueryProvider } from '@/lib/query-provider';
import { Toaster } from 'react-hot-toast';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'NEXUS — Autonomous Career Intelligence',
  description: 'AI-powered career matching, analysis, and briefings',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans`}>
        <QueryProvider>
          <AuthProvider>
            {children}
            <Toaster
              position="bottom-right"
              toastOptions={{
                style: {
                  background: '#1a1a26',
                  color: '#e2e8f0',
                  border: '1px solid #2a2a3a',
                },
                error: {
                  iconTheme: { primary: '#ef4444', secondary: '#1a1a26' },
                },
                success: {
                  iconTheme: { primary: '#22c55e', secondary: '#1a1a26' },
                },
              }}
            />
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
