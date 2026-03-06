"use client";

import { Inter } from "next/font/google";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const navLinks = [
  { href: "/", label: "Home" },
  { href: "/submit", label: "Submit" },
  { href: "/jobs", label: "Jobs" },
];

function ApiKeyBanner() {
  const [hasKey, setHasKey] = useState(true);

  useEffect(() => {
    setHasKey(!!localStorage.getItem("rustdali_api_key"));
  }, []);

  if (hasKey) return null;

  return (
    <div className="bg-yellow-50 border-b border-yellow-200 px-6 py-2 text-sm text-yellow-800">
      No API key set.{" "}
      <Link href="/settings" className="underline font-medium">
        Configure your API key
      </Link>{" "}
      to use the service.
    </div>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <html lang="en">
      <body
        className={`${inter.variable} font-sans antialiased bg-gray-50 text-gray-900 min-h-screen flex flex-col`}
      >
        <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-14">
              <div className="flex items-center gap-6">
                <Link href="/" className="flex items-center">
                  <span className="text-xl font-bold text-blue-600">
                    RustDALI
                  </span>
                </Link>
                <nav className="flex space-x-1">
                  {navLinks.map((link) => (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        pathname === link.href
                          ? "bg-blue-100 text-blue-700"
                          : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                      }`}
                    >
                      {link.label}
                    </Link>
                  ))}
                </nav>
              </div>
              <Link
                href="/settings"
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Settings
              </Link>
            </div>
          </div>
        </header>
        <ApiKeyBanner />
        <main className="flex-grow max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
          {children}
        </main>
      </body>
    </html>
  );
}
