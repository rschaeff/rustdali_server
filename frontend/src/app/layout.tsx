import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RustDALI",
  description: "Protein structural search service",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 min-h-screen">
        <nav className="bg-white border-b border-gray-200 px-6 py-3">
          <div className="max-w-7xl mx-auto flex items-center gap-6">
            <a href="/" className="text-lg font-bold">
              RustDALI
            </a>
            <a href="/submit" className="text-sm hover:underline">
              Submit
            </a>
            <a href="/jobs" className="text-sm hover:underline">
              Jobs
            </a>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
