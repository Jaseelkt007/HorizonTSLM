import type { Metadata } from "next";
import "./globals.css";
import { StreamProvider } from "../context/StreamContext";

export const metadata: Metadata = {
  title: "Aeolus // Wind Farm Operational Status & TSLM Explainer",
  description:
    "Live wind farm fleet operational telemetry, OpenTSLM precomputed diagnostic inference, and early warning fault explainer.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#070a10] text-slate-100 min-h-screen antialiased">
        <StreamProvider>{children}</StreamProvider>
      </body>
    </html>
  );
}
