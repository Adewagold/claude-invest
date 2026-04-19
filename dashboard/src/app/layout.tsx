import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Claude Invest",
  description: "AI-powered trading dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-zinc-950 text-zinc-100`}>
        <div className="flex">
          <Nav />
          <main className="flex-1 p-6 overflow-auto min-h-screen">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
