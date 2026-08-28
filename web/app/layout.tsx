import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "fenrir",
  description: "Multi-agent, human-in-the-loop bug bounty assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
