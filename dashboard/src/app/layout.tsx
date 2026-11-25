import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BlastGate — Autonomous Recovery. Provable Boundaries.",
  description:
    "An agentic operations system that detects, diagnoses and safely recovers unhealthy ECS workers under independent authorization (R1–R8).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0B0F14] text-[#F5F4F1] antialiased font-sans selection:bg-[#D8A955]/20 selection:text-[#D8A955]">
        {children}
      </body>
    </html>
  );
}
