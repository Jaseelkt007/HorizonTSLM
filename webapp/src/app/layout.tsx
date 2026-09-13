import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import Sidebar from "@/components/Sidebar";
import { loadDemo } from "@/lib/data";

import "./globals.css";

const ui = Inter({ subsets: ["latin"], variable: "--font-ui", display: "swap" });
const mono = JetBrains_Mono({ weight: ["400", "500"], subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Turbine Alarm Explainer", template: "%s · Turbine Alarm Explainer" },
  description: "Early warning for wind-turbine fault stops from 24 h of SCADA, with evidence an engineer can check.",
};

// Applies a saved theme before first paint so the page never flashes the other theme.
const themeScript = `(function(){try{var t=localStorage.getItem("tae-theme");if(t==="dark"||t==="light")document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const { meta, windows } = loadDemo();
  return (
    <html lang="en" suppressHydrationWarning className={`${ui.variable} ${mono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <div className="shell">
          <Sidebar model={meta.model} nWindows={windows.length} />
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
